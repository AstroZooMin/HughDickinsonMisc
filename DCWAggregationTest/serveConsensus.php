<?php

class SubjectSelector {

  public $dbConnection = null;

  function __construct($dbConnection){
    $this->dbConnection = $dbConnection;
  }

  function generateQuery($minReliability, $maxReliability, $numSamples){
    $query = 'SELECT id, huntingtonId, subjectReliability, url FROM Subjects WHERE subjectReliability > '.$minReliability.' AND subjectReliability < '.$maxReliability.' ORDER BY RAND() LIMIT 0, '.$numSamples;
    return $query;
  }

  function executeQuery($minReliability, $maxReliability, $numSamples){
    if(!$subjectResult = $this->dbConnection->query($this->generateQuery($minReliability, $maxReliability, $numSamples))){
      die('There was an error running the subject query [' . $this->dbConnection->error . ']');
    }
    return $subjectResult;
  }

  function getSubjectData($minReliability, $maxReliability, $numSamples, $numSteps){
    for($iStep = 0; $iStep < $numSteps; ++$iStep){
      $stepSize = 1.0/$numSteps;
      $subjectResult = $this->executeQuery($stepSize*$iStep, $stepSize*($iStep + 1), $numSamples);
      $resultsArray = array();
      while($row = $subjectResult->fetch_assoc()){
        $resultsArray[] = $row;
      }
      $allResultsArray[] =  array('minReliability' => $stepSize*$iStep, 'maxReliability' => $stepSize*($iStep+1), 'exampleData' => $resultsArray);
    }
    return $allResultsArray;
  }

  function getSubjectJSON($minReliability, $maxReliability, $numSamples, $numSteps){
    return json_encode($this->getSubjectData($minReliability, $maxReliability, $numSamples, $numSteps));
  }

  function processGetRequest(){
    $minReliability = $_GET['minReliability'];
    $maxReliability = $_GET['maxReliability'];
    $numSamples = $_GET['numSamples'];
    $numSteps = $_GET['numSteps'];

    echo $this->getSubjectJSON($minReliability, $maxReliability, $numSamples, $numSteps);
  }

}

class LineBoxMatcher{
  public $lines = null;
  public $boxes = null;
  public $subject = 0;

  function __construct($subject, $lines, $boxes){
    $this->lines = $lines;
    $this->boxes = $boxes;
    $this->subject = $subject;
  }

  function getLinesForBox($box){
    $minY = $box['meanY'];
    $maxY = $box['meanY'] + $box['meanHeight'];
    $minX = $box['meanX'];
    $maxX = $box['meanX'] + $box['meanWidth'];
    foreach ($this->lines as $line) {
      $meanLineY = 0.5*($line['meanY1'] + $line['meanY2']);

      $xOverlap = min($maxX, $line['meanX2']) - max($minX, $line['meanX1']);
      $xOverlapFraction = $xOverlap > 0 ? ($line['meanX2'] - $line['meanX1']) / $xOverlap : 0;

      $lineIsInBox = $meanLineY > $minY && $meanLineY < $maxY;
      $lineIsInBox &= $xOverlapFraction > 0.95;//$line['meanX1'] > $minX && $line['meanX2'] < $maxX;

      if($lineIsInBox){
        $boxLines[] = $line;
      }
    }
    return $boxLines;
  }

  function computeBoxStats($boxLines){
    $boxStats['reliability'] = 0.0;
    foreach ($boxLines as $lineData) {
      $boxStats['reliability'] += $lineData['lineReliability'];
    }
    $boxStats['numLines'] = count($boxLines);
    $boxStats['reliability'] /= $boxStats['numLines'];
    return $boxStats;
  }

  public function getLinesForBoxes(){
    if (is_array($this->boxes)){
      foreach ($this->boxes as $box) {
        $boxLines[$box['bestBoxIndex']] = $this->getLinesForBox($box);
      }
    }
    else{
      $boxLines = array();
    }

    foreach ($boxLines as $index => $ignoreMe) {
      $boxStats[$index] = $this->computeBoxStats($boxLines);
    }

    return array('boxLines' => $boxLines, 'boxStats' => $boxStats);
  }
}

class ConsensusProcessor{

  private $subject = null;
  private $dbConnection = null;

  private $subjectResult = null;
  private $subjectBoxResult = null;
  private $subjectTelegramResult = null;

  private $subjectSummary = null;
  private $boxLineData = null;

  private $lineResults = null;
  private $boxResults = null;
  private $telegramResults = null;
  private $allResults = null;

  function __construct($dbConnection, $subject){
    $this->subject = $subject;
    $this->dbConnection = $dbConnection;

    $this->lineResults = array();
    $this->boxResults = array();
    $this->telegramResults = array();
  }

  function updateResults(&$lineResults, $lastRow, $lineWords){
    $lineResults[] = array(
      'id' => $lastRow['id'],
      'subjectId' => $lastRow['subjectId'],
      'bestLineIndex' => $lastRow['bestLineIndex'],
      'url' => $lastRow['url'],
      'meanX1'  => $lastRow['meanX1'],
      'meanX2' => $lastRow['meanX2'],
      'meanY1' => $lastRow['meanY1'],
      'meanY2' => $lastRow['meanY2'],
      'words' => $lineWords,
      'lineReliability' => $lastRow['lineReliability']
    );
  }

  function retrieveSubjectData(){

    $subjectQuery = "SELECT Subjects.url, Subjects.subjectReliability, Subjects.huntingtonId, SubjectLines.*, LineWords.* FROM Subjects LEFT JOIN (SubjectLines RIGHT JOIN LineWords ON LineWords.lineId = SubjectLines.id) ON (Subjects.id = SubjectLines.subjectId) WHERE Subjects.id = ".$this->subject." ORDER BY lineId, position, rank";

    if(!$this->subjectResult = $this->dbConnection->query($subjectQuery)){
      die('There was an error running the subject query [' . $this->dbConnection->error . ']');
    }

  }

  function retrieveBoxData(){
    $subjectBoxQuery = "SELECT SubjectBoxes.* FROM SubjectBoxes WHERE SubjectBoxes.subjectId =".$this->subject;

    if(!$this->subjectBoxResult = $this->dbConnection->query($subjectBoxQuery)){
      die('There was an error running the subject box query [' . $this->dbConnection->error . ']');
    }

  }

  function retrieveTelegramData(){
    $subjectTelegramQuery = "SELECT SubjectTelegrams.* FROM SubjectTelegrams WHERE SubjectTelegrams.subjectId =".$this->subject." ORDER BY SubjectTelegrams.telegramId";

    if(!$this->subjectTelegramResult = $this->dbConnection->query($subjectTelegramQuery)){
      die('There was an error running the subject telegram query [' . $this->dbConnection->error . ']');
    }

  }

  function processSubjectLines(){
    // process textual transcription data
    $lineWords = array();
    $lineIndex = 0;
    $lastRow = null;

    while($row = $this->subjectResult->fetch_assoc()){
      // if a new line (following the first) has started
      if($row['bestLineIndex'] != $lineIndex){
        /* initialize and populate a new element in the results structure
        * to represent the line.
        */
        $this->updateResults($this->lineResults, $lastRow, $lineWords);

        $lineIndex = $row['bestLineIndex'];
        $lineWords = array();

      }
      $lastRow = $row;
      $lineWords[$row['position']][$row['rank']] = $row['wordText'];

    }
    // append the data for the final line to the results set
    $this->updateResults($this->lineResults, $lastRow, $lineWords);
    // update the subject summary description using data from the final row
    $this->subjectSummary = array('url' => $lastRow['url'], 'huntingtonId' => $lastRow['huntingtonId'], 'subjectReliability' => $lastRow['subjectReliability']);
  }

  function processSubjectBoxes(){
    // process telegram boxing data
    while($row = $this->subjectBoxResult->fetch_assoc()){
      $this->boxResults[] = $row;
    }
  }

  function processSubjectTelegrams(){
    // process telegram number data
    while($row = $this->subjectTelegramResult->fetch_assoc()){
      $this->telegramResults[] = $row;
    }
  }

  function processBoxTelegramsAndLines(){
    $lineBoxMatcher = new LineBoxMatcher($this->subject, $this->lineResults, $this->boxResults);
    $this->boxLineData = $lineBoxMatcher->getLinesForBoxes();

    $telegramIndex=0;
    foreach ($this->boxResults as &$boxResult) {
      if($boxResult['numBoxesMarked'] > 1){
        $boxResult['telegramData'] = $this->telegramResults[$telegramIndex++];
      }
      else{
        $boxResult['telegramData'] = null;
      }
    }
  }

  function combineData(){
    $this->allResults = array('subjectData' => array('url' => $this->subjectSummary['url'], 'huntingtonId' => $this->subjectSummary['huntingtonId'], 'reliability' => $this->subjectSummary['subjectReliability']), 'telegramData' => $this->telegramResults, 'boxData' => $this->boxResults,'lineData' => $this->lineResults, 'boxLineData' => $this->boxLineData);
  }

  function freeMysqlResults(){
    $this->subjectResult->free();
    $this->subjectBoxResult->free();
    $this->subjectTelegramResult->free();
  }

  function processSubjectData(){

    $this->retrieveSubjectData();
    $this->processSubjectLines();

    $this->retrieveBoxData();
    $this->processSubjectBoxes();

    $this->retrieveTelegramData();
    $this->processSubjectTelegrams();

    $this->processBoxTelegramsAndLines();

    $this->combineData();

    $this->freeMysqlResults();

  }

  function getAllResults(){
    if(!$this->allResults){
      $this->processSubjectData();
    }
    return $this->allResults;
  }

  function getSubjectJSON(){
    echo json_encode($this->getAllResults());
  }

}

class ConsensusTextGenerator{

  private $subject = null;
  private $subjectData = null;

  function __construct($dbConnection, $subject){
    $this->subject = $subject;
    $this->dbConnection = $dbConnection;
  }

  function getConsensusText(){
    if (!$this->subjectData){
      $consensusProcessor = new ConsensusProcessor($this->dbConnection, $this->subject);
      $this->subjectData = $consensusProcessor->getAllResults();
    }
    $lineData = $this->subjectData['lineData'];
    $bestLineArray = array();
    foreach ($lineData as $lineDatum) {
      $bestWordArray = array();
      foreach ($lineDatum['words'] as $wordOptions) {
        $bestWordArray[] = $wordOptions[0];
      }
      $bestLineArray[] = join(' ', $bestWordArray);
    }
    $consensusText = join('<br/>', $bestLineArray);
    return $consensusText;
  }

  function printConsensusText(){
    $consensusText = $this->getConsensusText();
    echo 'ID: '.$this->subjectData['subjectData']['huntingtonId'].
    ' (Reliability : '.$this->subjectData['subjectData']['reliability'].')<br/><br/>'.
    $consensusText.
    '<hr/>';
  }
}

class ReliabilitySamplePrinter{

  private $subjectData = null;
  private $dbConnection = null;
  private $minReliability = 0.0;
  private $maxReliability = 1.0;
  private $numSamples = 2;
  private $numSteps = 10;


  function __construct($dbConnection, $minReliability, $maxReliability, $numSamples, $numSteps){
    $this->dbConnection = $dbConnection;
    $this->minReliability = $minReliability;
    $this->maxReliability = $maxReliability;
    $this->numSamples = $numSamples;
    $this->numSteps = $numSteps;
  }

  function printConsensusTexts(){
    $subjectSelector = new SubjectSelector($this->dbConnection);
    $this->subjectData = $subjectSelector->getSubjectData($this->minReliability, $this->maxReliability, $this->numSamples, $this->numSteps);
    foreach ($this->subjectData as $subjectDatum) {
      foreach ($subjectDatum['exampleData'] as $exampleDatum){
        $consensusTextGenerator = new ConsensusTextGenerator($this->dbConnection, $exampleDatum['id']);
        $consensusTextGenerator->printConsensusText();
      }
    }
  }
}

// INITIAL DATABASE CONNECTION
$database = new mysqli('localhost', 'REDACTED', 'REDACTED', 'dcwConsensus');

if($database->connect_errno > 0){
  die('Unable to connect to database [' . $database->connect_error . ']');
}

if ($_GET['task'] == 'getSubjectData'){

  $subject = $_GET['id'];

  $consensusProcessor = new ConsensusProcessor($database, $subject);
  $consensusProcessor->getSubjectJSON();
}
else if ($_GET['task'] == 'getSampleForReliability'){
  $subjectSelector = new SubjectSelector($database);
  $subjectSelector->processGetRequest();
}
else if  ($_GET['task'] == 'printReliabilitySample'){
  $reliabilitySamplePrinter = new ReliabilitySamplePrinter($database, 0.0, 1.0, 2, 10);
  $reliabilitySamplePrinter->printConsensusTexts();
}

?>
