import pandas as pd
import numpy as np
import scipy.interpolate

class SimpleAcceptReject() :

    def __init__(self,
                 targetDistData,
                 sampleDistData,
                 numBins,
                 targetColumnName,
                 sampleColumnName,
                 rejectionEfficiency=10) :

        self.distData = {'target' : targetDistData if isinstance(targetDistData, pd.DataFrame) else None,
                         'sample' : sampleDistData if isinstance(sampleDistData, pd.DataFrame) else None }

        self.columnName = {'target' : targetColumnName if isinstance(targetColumnName, str) else None,
                           'sample' : sampleColumnName if isinstance(sampleColumnName, str) else targetColumnName }

        self.distHisto = {'target' : None, 'sample' : None}
        self.distHistoBins = {'target' : None, 'sample' : numBins if isinstance(numBins, int) else None }

        self.distFrame = {'target' : None, 'sample' : None}
        self.distSpline = {'target' : None, 'sample' : None}

        self.pdfFrameColNames = ['density', 'bin_low_edge', 'bin_high_edge', 'bin_centre']

        self.resampledDistFrame = None

        self.rejectionEfficiency = rejectionEfficiency

    def genProbDist(self, key) :
        print ('Generating probability disribution for {}...'.format(key))
        self.distHisto[key] = np.histogram(self.distData[key][self.columnName[key]].values,
                                           bins=self.distHistoBins[key],
                                           density = True)
        self.distFrame[key] = pd.DataFrame([(*zipped, 0.5*(zipped[1]+zipped[2])) for zipped in zip(self.distHisto[key][0], self.distHisto[key][1][0:-1], self.distHisto[key][1][1:])],
                                            columns=self.pdfFrameColNames)
        self.distSpline[key] = scipy.interpolate.UnivariateSpline(self.distFrame[key]['bin_centre'].values, self.distFrame[key]['density'].values, s=0)
        if key == 'sample' :
            self.distHistoBins['target'] = self.distHisto[key][1]

    def genResampledDistribution(self) :
        print ('Generating resampled distribution...')
        while len(self.resampledDistFrame.index) < len(self.distData['target'].index) :
            # select a random sample of rows from the illustris dataset (select more than we need)
            fullSample = self.distData['sample'].sample(1000)
            # generate the same number of random uniform variates
            uniformVariates = np.random.uniform(size=1000)
            # generate pdf values for the stellar masses corresponding to each of the samples
            targetPdfVals = self.distSpline['target'](fullSample[self.columnName['sample']])
            samplePdfVals = self.distSpline['sample'](fullSample[self.columnName['sample']])
            pdfRatioVals = targetPdfVals/(self.rejectionEfficiency*samplePdfVals)
            # select only those rows of the sample that fulfil the acceptance criterion
            filteredSample = fullSample[uniformVariates <= pdfRatioVals]
            self.resampledDistFrame = pd.concat([self.resampledDistFrame,filteredSample], ignore_index=True)
        print ('Done.')

    def getResampledDataset(self) :
        # initialization of probability distributions
        for key in ['sample', 'target'] :
            if self.distData[key] is not None and self.columnName[key] is not None and self.distHistoBins[key] is not None :
                self.genProbDist(key)
        # initialization of output resampled distribution
        self.resampledDistFrame = pd.DataFrame(columns=self.distData['target'].columns)
        self.genResampledDistribution()
        return self.resampledDistFrame
