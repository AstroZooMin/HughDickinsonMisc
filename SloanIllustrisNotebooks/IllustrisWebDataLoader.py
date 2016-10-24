# Module to issue http requests to the Illustris web service
import requests
import pprint
import pickle

import pandas as pd

class IllustrisWebDataLoader():

    def __init__(self,
                 illustrisAPIKey,
                 illustrisSimulationName = 'Illustris-1',
                 illustrisSimulationSnapshotIndex = -1,
                 illustrisAPIUrl = 'http://www.illustris-project.org/api/',
                 outputBaseDir = '',) :

        self.illustrisAPIKey = illustrisAPIKey
        self.illustrisAPIUrl = illustrisAPIUrl

        self.illustrisSimulationName = illustrisSimulationName
        self.illustrisSimulationSnapshotIndex = illustrisSimulationSnapshotIndex

        self.webServiceSchemaData = None
        self.availableSimulationData = None
        self.simulationMetaData = {}
        self.simulationSnapshotMetaData = {}

        # Only maintain detailed halo information for one run/snapshot combination
        self.simulationHaloMetaData = None
        self.simulationHaloMetaDataFrame = None
        self.simulationHaloMetaDataIsValid = False

        self.simulationHaloData = None
        self.simulationHaloDataFrame = None
        self.simulationHaloDataIsValid = False

        # Data serialization and deserialization
        self.outputBaseDir = outputBaseDir
        # Append trailing slash if required
        if self.outputBaseDir and self.outputBaseDir[-1] != '/' :
            self.outputBaseDir += '/'

        self.simulationHaloMetaDataFileName = 'illustrisWebService_haloMetaData.pkl'
        self.simulationHaloDataFileName = 'illustrisWebService_haloData.pkl'

        self.prettyPrinter = pprint.PrettyPrinter(indent=4)

    def __getAPIHeaders(self) :
        return {"api-key" : self.illustrisAPIKey}

    def __requestSimulationSnapshotMetaData(self) :
        availableSnapshotData = self.requestData(self.getSimulationMetaData()['snapshots'])
        return self.requestData(availableSnapshotData[self.illustrisSimulationSnapshotIndex]['url'])

    def __invalidateHaloData(self, setToNone = False) :
        pass

    def __validateHaloData(self) :
        # Can't actually verify validity but should at least check that objects exist
        if self.simulationHaloData is not None :
            self.simulationHaloDataIsValid = True

    def __invalidateHaloMetaData(self, setToNone = False) :
        self.simulationHaloDataIsValid = False
        if setToNone :
            self.simulationHaloMetaData = None
            self.simulationHaloMetaDataFrame = None

    def __validateHaloMetaData(self) :
        # Can't actually verify validity but should at least check that object exists
        if self.simulationHaloMetaData is not None :
            self.simulationHaloDataIsValid = True

    def __retrieveHaloMetaData(self, limit, reload=False, batchsize=1e3, verbose = True) :
        if reload or (not self.simulationHaloMetaDataIsValid) or self.simulationHaloMetaData is None :
            if verbose :
                print ('Retrieving {} halos in batches of at most {}...'.format(limit, batchsize))
            # retrieve and store the first batch of halo data - this will include a URL to retrieve the next batch
            simulationHaloMetaDataResponse = self.requestData(self.getSimulationSnapshotMetaData(reload)['subhalos'],
                                                          requestParameters = {'limit' : batchsize})
            self.simulationHaloMetaData = simulationHaloMetaDataResponse['results']
            while len(self.simulationHaloMetaData) < limit and simulationHaloMetaDataResponse['next'] is not None :
                simulationHaloMetaDataResponse = self.requestData(simulationHaloMetaDataResponse['next'])
                self.simulationHaloMetaData.extend(simulationHaloMetaDataResponse['results'])
                if verbose and (len(self.simulationHaloMetaData) % 5000 == 0) :
                    # How many halos have data been downloaded for?
                    print('Retrieved data for {} halos...'.format(len(self.simulationHaloMetaData)))
                    # The URL that should be queried to retrieve the next block of data
                    print('Now querying {}...'.format(simulationHaloMetaDataResponse['next']))
            if verbose :
                print ('Finished.')
            self.__validateHaloMetaData()
        elif verbose :
            print ('Preexisting halo metadata is available and remains valid. New data will not be downloaded.')

    def __tabulateHaloMetaData(self) :
        if (not self.simulationHaloMetaDataIsValid) or self.simulationHaloMetaData is None :
            raise RuntimeError('No halo metadata is available to tabulate: simulationHaloMetaDataIsValid => {}, simulationHaloMetaData => {}.'.format(self.simulationHaloMetaDataIsValid, self.simulationHaloMetaData))
        self.simulationHaloMetaDataFrame = pd.DataFrame(self.simulationHaloMetaData)
        self.simulationHaloMetaDataFrame.set_index("id", inplace=True)

    def __retrieveHaloData(self, requiredHaloMetaData, reload = False, batchsize=100, verbose = True) :
        if reload or (not self.simulationHaloDataIsValid) or self.simulationHaloData is None :
            if verbose :
                print ('Retrieving {} halos in batches of at most {}...'.format(len(requiredHaloMetaData.index), batchsize))
            self.simulationHaloData = []
            while len(self.simulationHaloData) < len(requiredHaloMetaData.index) :
                numToRetrieve = min(len(requiredHaloMetaData.index) - len(self.simulationHaloData), batchsize)
                self.simulationHaloData.extend([self.requestData(haloUrl) for haloUrl in requiredHaloMetaData.iloc[len(self.simulationHaloData):len(self.simulationHaloData) + numToRetrieve]['url']])
                if verbose :
                    print ('Retrieved {0} subHalo datasets...'.format(len(self.simulationHaloData)))
            self.__validateHaloData()
        elif verbose :
            print ('Preexisting halo data is available and remains valid. New data will not be downloaded.')

    def __tabulateHaloData(self) :
        if (not self.simulationHaloDataIsValid) or self.simulationHaloData is None :
            raise RuntimeError('No detailed halo data is available to tabulate: simulationHaloMetaDataIsValid => {}, simulationHaloMetaData => {}.'.format(self.simulationHaloMetaDataIsValid, self.simulationHaloMetaData))
        self.simulationHaloDataFrame = pd.DataFrame(self.simulationHaloData)
        self.simulationHaloDataFrame.set_index('id', inplace=True)

    def requestData(self, path, requestParameters = None) :
        # make HTTP GET request to path
        response = requests.get(path, params=requestParameters, headers=self.__getAPIHeaders())
        # raise exception if response code is not HTTP SUCCESS (200)
        response.raise_for_status()

        # parse json responses automatically
        if response.headers['content-type'] == 'application/json':
            return response.json()

        return response

    def getWebServiceSchema(self, reload = False) :
        if reload or self.webServiceSchemaData is None :
            self.webServiceSchemaData = self.requestData(self.illustrisAPIUrl)
        return self.webServiceSchemaData

    def getAvailableSimulationData(self, reload = False) :
        if reload or self.availableSimulationData is None :
            self.availableSimulationData = self.getWebServiceSchema(reload)['simulations']
        return self.availableSimulationData

    def getSimulationMetaData(self, reload = False) :
        illustrisSimulationInfo = next(
            (simDatum for simDatum in self.getAvailableSimulationData(reload) if simDatum['name'] == self.illustrisSimulationName),
            None # default if not found
        )
        if illustrisSimulationInfo is not None :
            if illustrisSimulationInfo['name'] in self.simulationMetaData :
                if reload :
                    self.simulationMetaData[illustrisSimulationInfo['name']] = self.requestData(illustrisSimulationInfo['url'])
            else :
                self.simulationMetaData.update({illustrisSimulationInfo['name'] : self.requestData(illustrisSimulationInfo['url'])})
        return self.simulationMetaData[illustrisSimulationInfo['name']]

    def getSimulationSnapshotMetaData(self, reload = False) :
        if self.illustrisSimulationName in self.simulationSnapshotMetaData :
            if self.illustrisSimulationSnapshotIndex in self.simulationSnapshotMetaData[self.illustrisSimulationName] :
                if reload :
                    self.simulationSnapshotMetaData[self.illustrisSimulationName][self.illustrisSimulationSnapshotIndex] = self.__requestSimulationSnapshotMetaData()
            else :
                self.simulationSnapshotMetaData[self.illustrisSimulationName].update({self.illustrisSimulationSnapshotIndex : self.__requestSimulationSnapshotMetaData()})
        else :
            self.simulationSnapshotMetaData.update({self.illustrisSimulationName : {self.illustrisSimulationSnapshotIndex : self.__requestSimulationSnapshotMetaData()}})
        return self.simulationSnapshotMetaData[self.illustrisSimulationName][self.illustrisSimulationSnapshotIndex]

    def getSimulationHaloMetaData(self, limit, reload=False, batchsize=1e3, verbose=True) :
        self.__retrieveHaloMetaData(limit=limit, reload=reload, batchsize=batchsize, verbose=verbose)
        self.__tabulateHaloMetaData()
        return self.simulationHaloMetaDataFrame

    def getSimulationHaloData(self, requiredHaloMetaData, reload=False, batchsize=100, verbose=True) :
        self.__retrieveHaloData(requiredHaloMetaData=requiredHaloMetaData, reload=reload, batchsize=batchsize, verbose=verbose)
        self.__tabulateHaloData()
        return self.simulationHaloDataFrame

    def printWebServiceSchema(self, reload = False) :
        print('Web Service Schema:')
        self.prettyPrinter.pprint(self.getWebServiceSchema(reload))

    def printAvailableSimulationData(self, reload = False) :
        print('Available Simulations:')
        self.prettyPrinter.pprint(self.getAvailableSimulationData(reload))

    def printSimulationMetaData(self, reload = False) :
        print('Simulation Metadata for {}:'.format(self.illustrisSimulationName))
        self.prettyPrinter.pprint(self.getSimulationMetaData(reload))

    def printSimulationSnapshotMetaData(self, reload = False) :
        print('Simulation Snapshot Metadata for {}, snapshot {}:'.format(self.illustrisSimulationName, self.illustrisSimulationSnapshotIndex))
        self.prettyPrinter.pprint(self.getSimulationSnapshotMetaData(reload))

    def setIllustrisSimulationName(self, illustrisSimulationName) :
        self.illustrisSimulationName = illustrisSimulationName
        self.__invalidateHaloMetaData(setToNone = False)

    def setIllustrisSimulationSnapshotIndex(self, illustrisSimulationSnapshotIndex) :
        self.illustrisSimulationSnapshotIndex = illustrisSimulationSnapshotIndex
        self.__invalidateHaloMetaData(setToNone = False)

    def saveHaloMetaData(self) :
        self.simulationHaloMetaDataFrame.to_pickle(self.outputBaseDir + self.simulationHaloMetaDataFileName)

    def saveHaloData(self) :
        self.simulationHaloDataFrame.to_pickle(self.outputBaseDir + self.simulationHaloDataFileName)

    def loadHaloMetaData(self) :
        file = open(self.outputBaseDir + self.simulationHaloMetaDataFileName, 'rb')
        self.simulationHaloMetaDataFrame = pickle.load(file)
        file.close()
        self.__validateHaloMetaData()
        return self.simulationHaloMetaDataFrame

    def loadHaloData(self) :
        file = open(self.outputBaseDir + self.simulationHaloDataFileName, 'rb')
        self.simulationHaloDataFrame = pickle.load(file)
        file.close()
        self.__validateHaloData()
        return self.simulationHaloDataFrame
