from pymongo import MongoClient
from bson.son import SON
import pandas as pd
import numpy as np
import pickle

class MongoDataHandler():

    def __init__(self,
                 dbName = 'test',
                 collectionNames = {'classifications' : 'galaxy_zoo_classifications',
                                    'subjects' : 'galaxy_zoo_subjects',
                                    'groups' : 'galaxy_zoo_groups'},
                 outputBaseDir = ''
                ):

        self.dbName = dbName
        self.collectionNames = collectionNames
        self.outputBaseDir = outputBaseDir
        # Append trailing slash if required
        if self.outputBaseDir and self.outputBaseDir[-1] != '/' :
            self.outputBaseDir += '/'

        self.surveyNames = None

        self.rawUserData = None
        self.userData = None
        self.userFilter = None

        self.rawIllustrisData = None

        self.illustrisMetaData = None
        self.illustrisClassificationData = None
        self.illustrisCombinedData = None

        self.userDataFileName = 'galaxyZoo_userData.pkl'
        self.illustrisClassificationDataFileName = 'galaxyZoo_illustrisClassificationData.pkl'
        self.illustrisMetaDataFileName = 'galaxyZoo_illustrisMetaData.pkl'
        self.illustrisCombinedDataFileName = 'galaxyZoo_illustrisCombinedData.pkl'

        self.clientInstance = self.database = self.collections = None
        self.__initDatabase()

    def __initDatabase(self) :
        # Rely on exceptions raised by API to indicate connection failures!
        self.clientInstance = MongoClient()
        self.database = self.clientInstance[self.dbName]
        self.collections = {'classifications' : self.database[self.collectionNames['classifications']],
                            'subjects' : self.database[self.collectionNames['subjects']],
                            'groups' : self.database[self.collectionNames['groups']]}

    def __retrieveUserData(self, reload = False) :
        if reload == True or self.rawUserData is None :
            print ('Retrieving user data...')
            self.rawUserData = list(self.collections['classifications'].aggregate([ {"$sort" : {"user_name" : 1} }, {"$group": { "_id" : "$user_name", "count" : {"$sum" : 1 } } }]))
            print ('Done.')

    def __tabulateUserData(self, reload = False) :
        if reload or self.userData is None :
            # The following is a no-op if self.rawUserData is not None and reload is False
            self.__retrieveUserData(reload)
            print ('Tabulating user data...')
            self.userData = pd.DataFrame.from_dict({'user_name' : [userData['_id'] for userData in self.rawUserData], 'classification_count' : [userData['count'] for userData in self.rawUserData]})
            self.userData = self.userData.set_index("user_name")
            print('Done.')

    def __collateIllustrisClassificationData(self) :
        allSubjectAnswers = {}
        for found in self.rawIllustrisData :
            subjectAnswers = {}
            for annotations in found['classifications'] :
                # Optional filtering based on user history
                if(self.userFilter is not None and ('user_name' not in annotations or not userFilter(annotations['user_name'], self.userData))) :
                    continue
                for answer in annotations['annotations'] :
                    questionKey = str(list(answer)[0])
                    answerKey = str(answer[questionKey])
                    if 'illustris' not in questionKey :
                        continue
                    if questionKey in subjectAnswers :
                        if answerKey in subjectAnswers[questionKey] :
                            subjectAnswers[questionKey][answerKey] += 1
                        else :
                            subjectAnswers[questionKey].update({answerKey : 1})
                    else :
                        subjectAnswers.update({questionKey : {answerKey : 1}})
            allSubjectAnswers.update({found["metadata"]["subhalo_id"]: subjectAnswers})

        return allSubjectAnswers

    def __appendComputedIllustrisColumns(self) :
        if self.illustrisClassificationData is None :
            # This will call __appendComputedIllustrisColumns again once the requisite frame is built
            self.__tabulateIllustrisClassificationData()
        else :
            # add computed vote fraction values
            self.illustrisClassificationData['p_smooth'] = self.illustrisClassificationData['num_smooth']/(self.illustrisClassificationData['num_smooth'] + self.illustrisClassificationData['num_features'])
            self.illustrisClassificationData['p_features'] = self.illustrisClassificationData['num_features']/(self.illustrisClassificationData['num_smooth'] + self.illustrisClassificationData['num_features'])
            # Add computed columns for "edge on" versus "not edge on"
            pFeaturesThreshold = 0.6
            self.illustrisClassificationData['is_edge_on'] = np.logical_and(self.illustrisClassificationData['num_edgeon'] >= self.illustrisClassificationData['num_faceon'], self.illustrisClassificationData['num_edgeon'] !=0)
            self.illustrisClassificationData['is_features_and_edge_on'] = np.logical_and(self.illustrisClassificationData['is_edge_on'], self.illustrisClassificationData['p_features'] > pFeaturesThreshold)

    def __tabulateIllustrisClassificationData(self, reload = False) :
        if reload or self.illustrisClassificationData is None :
            # The following is a no-op if self.rawIllustrisData is not None and reload is False
            self.__retrieveIllustrisData(reload)
            print ('Tabulating Illustris classification data...')
            self.illustrisClassificationData = pd.DataFrame([(key,
                                                         value['illustris-0']['a-0'] if 'a-0' in value['illustris-0'] else 0,
                                                         value['illustris-0']['a-1'] if 'a-1' in value['illustris-0'] else 0,
                                                         value['illustris-0']['a-2'] if 'a-2' in value['illustris-0'] else 0,
                                                         value['illustris-1']['a-0'] if ('illustris-1' in value and 'a-0' in value['illustris-1']) else 0,
                                                         value['illustris-1']['a-1'] if ('illustris-1' in value and 'a-1' in value['illustris-1']) else 0
                                                        )
                                                        for key, value in self.__collateIllustrisClassificationData().items()],
                                                       columns=['subhalo_id', 'num_smooth', 'num_features', 'num_artifact', 'num_edgeon', 'num_faceon'])
            self.illustrisClassificationData = self.illustrisClassificationData.set_index('subhalo_id')
            self.illustrisClassificationData = self.illustrisClassificationData.sort_index()
            self.__appendComputedIllustrisColumns()
            print('Done.')

    def __tabulateIllustrisMetaData(self, reload = False) :
        if reload or self.illustrisMetaData is None :
            # The following is a no-op if self.rawIllustrisClassificationData is not None and reload is False
            self.__retrieveIllustrisData(reload)
            print ('Tabulating Illustris metadata...')
            self.illustrisMetaData = pd.DataFrame([ (
                        found["metadata"]["subhalo_id"],
                        found["metadata"]["priority"],
                        found["metadata"]["mass_log_msun"],
                        np.log10(found["metadata"]["radius_half"]),
                        np.log10(found["metadata"]["sfr"]) if found["metadata"]["sfr"] != 0 else 0.0,
                        float(found["metadata"]["mag"]["absmag_r"]),
                        float(found["metadata"]["mag"]["absmag_b"]),
                        float(found["metadata"]["mag"]["absmag_g"]),
                        float(found["metadata"]["mag"]["absmag_i"]),
                        float(found["metadata"]["mag"]["absmag_k"]),
                        float(found["metadata"]["mag"]["absmag_u"]),
                        float(found["metadata"]["mag"]["absmag_v"]),
                        float(found["metadata"]["mag"]["absmag_z"])
                    ) for found in self.rawIllustrisData],
                                                  columns=["subhalo_id",
                                                           "priority",
                                                           "mass_log_msun",
                                                           "log_radius_half",
                                                           "log_sfr",
                                                           "absmag_r",
                                                           "absmag_b",
                                                           "absmag_g",
                                                           "absmag_i",
                                                           "absmag_k",
                                                           "absmag_u",
                                                           "absmag_v",
                                                           "absmag_z"]
                                                 )
            # index the metadata according to halo id
            self.illustrisMetaData = self.illustrisMetaData.set_index("subhalo_id")
            print ('Done.')

    def __retrieveIllustrisData(self, reload=False) :
        # check whether the data have already been loaded - the query is reasonably time consuming
        if reload or self.rawIllustrisData is None :
            print ('Retrieving Illustris data...')
            self.illustrisClassificationData = None
            # Assemble query/aggregation pipleine
            galaxyPropertiesIllustrisPipeline = [{"$match" :
                                              {"$and" : [ {"metadata.survey" : "illustris"},
                                                         {"state" : "complete"}
                                                        ] }
                                             },
                                             {"$lookup" : {"from" : "galaxy_zoo_classifications",
                                                           "localField" : "_id",
                                                           "foreignField" : "subject_ids",
                                                           "as": "classifications" }
                                             },
                                             {"$project" : {"classifications.annotations": 1,
                                                            "zooniverse_id" : 1,
                                                            "classification_count" : 1,
                                                            "metadata" : 1,
                                                            "classifications.user_name" : 1 }
                                                          }
                                            ]
            # Execute the query and store the result immediately
            self.rawIllustrisData = list(self.collections['subjects'].aggregate(galaxyPropertiesIllustrisPipeline, allowDiskUse=True, batchSize=1000))
            print('Done.')

    def __addFirstFixedMass(self) :
        if self.illustrisCombinedData is not None :
            fixedMassSubset = self.illustrisCombinedData[self.illustrisCombinedData['priority'] == 'fixed_mass'].drop_duplicates()
            fixedMassSubset.replace(to_replace='fixed_mass', value='first_fixed_mass', inplace=True)
            self.illustrisCombinedData = pd.concat([self.illustrisCombinedData, fixedMassSubset])

    def getUserData(self, reload = False) :
        self.__tabulateUserData(reload)

        return self.userData

    def getSurveyNames(self) :
        if self.surveyNames is None :
            self.surveyNames = pd.DataFrame([found for found in self.collections['groups'].find({},{"name": 1, "_id": 0})])

        return self.surveyNames

    def getIllustrisClassificationData(self, reload = False) :
        self.__tabulateIllustrisClassificationData(reload)

        return self.illustrisClassificationData

    def getIllustrisMetaData(self, reload=False) :
        self.__tabulateIllustrisMetaData(reload)

        return self.illustrisMetaData

    def getIllustrisCombinedData(self, reload = False) :
        if reload or self.illustrisCombinedData is None :
            metaData = self.getIllustrisMetaData(reload)
            classificationData = self.getIllustrisClassificationData(reload)
            self.illustrisCombinedData = metaData.merge(classificationData, left_index=True, right_index=True, how='left')
            self.__addFirstFixedMass()
        return self.illustrisCombinedData

    def setUserFilter(self, userFilter) :
        if hasattr(userFilter, "__call__") :
            self.userFilter = userFilter
        else :
            print ('Warning! Supplied filter cannot be called. User filter will not be applied.')

    def saveIllustrisMetaData(self) :
        self.illustrisMetaData.to_pickle(self.outputBaseDir + self.illustrisMetaDataFileName)

    def loadIllustrisMetaData(self) :
        file = open(self.outputBaseDir + self.illustrisMetaDataFileName, 'rb')
        self.illustrisMetaData = pickle.load(file)
        file.close()
        return self.illustrisMetaData

    def saveIllustrisClassificationData(self) :
        self.illustrisClassificationData.to_pickle(self.outputBaseDir + self.illustrisClassificationDataFileName)

    def loadIllustrisClassificationData(self) :
        file = open(self.outputBaseDir + self.illustrisClassificationDataFileName, 'rb')
        self.illustrisClassificationData = pickle.load(file)
        file.close()
        return self.illustrisClassificationData

    def saveIllustrisCombinedData(self) :
        self.illustrisCombinedData.to_pickle(self.outputBaseDir + self.illustrisCombinedDataFileName)

    def loadIllustrisCombinedData(self) :
        file = open(self.outputBaseDir + self.illustrisCombinedDataFileName, 'rb')
        self.illustrisCombinedData = pickle.load(file)
        file.close()
        return self.illustrisCombinedData

    def saveUserData(self) :
        self.userData.to_pickle(self.outputBaseDir + self.userDataFileName)

    def loadUserData(self) :
        file = open(self.outputBaseDir + self.userDataFileName, 'rb')
        self.userData = pickle.load(file)
        file.close()
        return self.userData

    def setUserDataFileName(self, userDataFileName) :
        self.userDataFileName = userDataFileName

    def setIllustrisMetaDataFileName(self, illustrisMetaDataFileName) :
        self.illustrisMetaDataFileName = illustrisMetaDataFileName

    def setIllustrisClassificationDataFileName(self, illustrisClassificationDataFileName) :
        self.illustrisClassificationDataFileName = illustrisClassificationDataFileName

    def setIllustrisCombinedDataFileName(self, illustrisCombinedDataFileName) :
        self.illustrisCombinedDataFileName = illustrisCombinedDataFileName

    def setOutputBaseDir(self, outputBaseDir) :
        self.outputBaseDir = outputBaseDir
