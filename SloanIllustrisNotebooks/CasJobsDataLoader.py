import SciServer.LoginPortal
import pickle

class CasJobsDataLoader() :

    def __init__(self,
                 casJobsAuthToken,
                 outputBaseDir = '') :

        self.casJobsAuthToken = casJobsAuthToken
        SciServer.LoginPortal.setKeystoneToken(self.casJobsAuthToken)
        self.casJobsUserManager = SciServer.LoginPortal.getKeystoneUserWithToken(self.casJobsAuthToken)

        self.sdssFilters = ['u', 'g', 'r', 'i', 'z']
        self.galaxyViewAlias = 'galView'
        self.casJobsMyDBTableName = 'sdssDataForZooniverse'

        self.outputBaseDir = outputBaseDir
        # Append trailing slash if required
        if self.outputBaseDir and self.outputBaseDir[-1] != '/' :
            self.outputBaseDir += '/'

        self.galaxyZoo2TableColumns = None
        self.galaxyViewColumns = None
        self.sdssDataQuery = None

        self.sdssDataFrame = None

        self.sdssDataFileName = 'casJobs_sdssGalaxyZooData.pkl'

    def printUserManagerUserName(self) :
        print(self.casJobsUserManager.userName)

    def __retrieveGalaxyZoo2TableColumns(self) :
        # retrieve the names of all columns except "specobjid"
        query = """SELECT name FROM DBColumns WHERE tablename='zoo2MainSpecz' AND name <> 'specobjid'"""
        self.galaxyZoo2TableColumns = CasJobs.executeQuery(query, "dr10", token=self.casJobsAuthToken)

    def __generateFilterSpecificColumnNames(self) :
        self.galaxyViewColumns = [ self.galaxyViewAlias + '.expAB_' + filterName for filterName in self.sdssFilters ]
        self.galaxyViewColumns.extend([ self.galaxyViewAlias + '.deVAB_' + filterName for filterName in self.sdssFilters ])
        self.galaxyViewColumns.extend([ self.galaxyViewAlias + '.fracDeV_' + filterName for filterName in self.sdssFilters ])
        self.galaxyViewColumns.extend([ self.galaxyViewAlias + '.petror90_' + filterName for filterName in self.sdssFilters ])

    def __dropCasJobsMyDBTable(self) :
        casJobsResult = CasJobs.executeQuery("DROP TABLE " + self.casJobsMyDBTableName,
                                             token = self.casJobsAuthToken,
                                             context='MyDB')
        return isinstance(sdssResult, pd.DataFrame)

    def __checkCasJobsMyDBTableExists(self) :
        casJobsResult = CasJobs.executeQuery("SELECT TOP 1 * FROM mydb." + self.casJobsMyDBTableName,
                                             token = self.casJobsAuthToken)
        return isinstance(casJobsResult, pd.DataFrame)

    def __generateSDSSDataQuery(self) :
        if self.galaxyViewColumns is None :
            self.__generateFilterSpecificColumnNames()

        if self.galaxyZoo2TableColumns is None:
            self.__retrieveGalaxyZoo2TableColumns()

        self.sdssDataQuery = """SELECT spec.z, spec.zErr, spec.zWarning,
        spec.petroMag_u, spec.petroMag_g, spec.petroMag_r, spec.petroMag_i, spec.petroMag_z,
        dbo.fCosmoAbsMag(spec.petroMag_u,spec.z,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT) as absPetroMag_u,
        dbo.fCosmoAbsMag(spec.petroMag_g,spec.z,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT) as absPetroMag_g,
        dbo.fCosmoAbsMag(spec.petroMag_r,spec.z,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT) as absPetroMag_r,
        dbo.fCosmoAbsMag(spec.petroMag_i,spec.z,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT) as absPetroMag_i,
        dbo.fCosmoAbsMag(spec.petroMag_z,spec.z,DEFAULT,DEFAULT,DEFAULT,DEFAULT,DEFAULT) as absPetroMag_z,
        """ + ','.join(self.galaxyViewColumns) + """
        , zooSpecExtra.* FROM
        (
        SELECT
        """ + ','.join(['zoo.' + colName for colName in self.galaxyZoo2TableColumns['name']]) + """, specExtra.*
        FROM zoo2MainSpecz AS zoo
        LEFT JOIN
        galSpecExtra AS specExtra
        ON (specExtra.specObjID = zoo.specobjid)
        )
        AS zooSpecExtra
        LEFT JOIN
        SpecPhoto AS spec
        ON
        (spec.specObjID = zooSpecExtra.specobjid)
        LEFT JOIN
        Galaxy AS """ + self.galaxyViewAlias + """
        ON
        (galView.specObjID = zooSpecExtra.specobjid)
        WHERE
        (spec.z > 0.04 AND spec.z < 0.06)
        INTO mydb.""" + self.casJobsMyDBTableName

    def __retrieveSDSSData(self, dropExistingQueryResults = False) :
        haveExistingQueryResults = self.__checkCasJobsMyDBTableExists()
        if dropExistingQueryResults and haveExistingQueryResults :
            self.__dropCasJobsMyDBTable()
            haveExistingQueryResults = False

        if self.sdssDataQuery is None :
            self.__generateSDSSDataQuery()

        if not haveExistingQueryResults :
            casJobsJobId = CasJobs.submitJob(self.sdssDataQuery, context="dr10", token=self.casJobsAuthToken)
            casJobsJobResponse = CasJobs.waitForJob(casJobsJobId)

        if haveExistingQueryResults or casJobsJobResponse['Status'] == 5 :
            casJobsResult = CasJobs.executeQuery("SELECT * FROM mydb." + self.casJobsMyDBTableName,
                                                 token=self.casJobsAuthToken)
            if(not isinstance(casJobsResult, pd.DataFrame)) :
                raise RuntimeError('CasJobs interface did not return the expected DataFrame. Instead, it returned: {}'.format(casJobsResult))
            else :
                self.sdssDataFrame = casJobsResult

    def getSDSSData(self, reload = False, dropExistingQueryResults = False) :
        if reload or self.sdssDataFrame is None :
            self.__retrieveSDSSData(dropExistingQueryResults)
        return self.sdssDataFrame

    def saveSDSSData(self) :
        self.userData.to_pickle(self.outputBaseDir + self.sdssDataFileName)

    def loadSDSSData(self) :
        file = open(self.outputBaseDir + self.sdssDataFileName, 'rb')
        self.sdssDataFrame = pickle.load(file)
        file.close()
        return self.sdssDataFrame

    def setOutputBaseDir(self, outputBaseDir) :
        self.outputBaseDir = outputBaseDir
