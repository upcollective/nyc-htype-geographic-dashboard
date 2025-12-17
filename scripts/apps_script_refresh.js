/**
 * NYC Schools Reference Data - Auto-Refresh Script
 *
 * This Apps Script pulls fresh data from NYC Open Data APIs
 * and updates the Google Sheet.
 *
 * SETUP:
 * 1. Open your "NYC Schools Reference Data" Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Delete the default code and paste this entire file
 * 4. Save (Ctrl+S or Cmd+S)
 * 5. Run > Run function > onOpen (to add the menu)
 * 6. Authorize the script when prompted
 *
 * USAGE:
 * - Use the "Reference Data" menu that appears in the sheet
 * - Or set up a time-based trigger for automatic monthly updates
 */

// NYC Open Data API endpoints
// Updated December 2025 with current dataset IDs
const DATA_SOURCES = {
  // Economic Need Index - 2017-18 to 2021-22 Demographic Snapshot
  // https://data.cityofnewyork.us/Education/2017-18-2021-22-Demographic-Snapshot/c7ru-d68s
  ENI: {
    name: 'Economic Need Index',
    endpoint: 'https://data.cityofnewyork.us/resource/c7ru-d68s.json',
    sheet: 'ENI_by_School',
    // Get most recent year (2021-22) data
    query: '$select=dbn,school_name,total_enrollment,economic_need_index&$where=year=%272021-22%27&$limit=3000',
    columns: ['school_dbn', 'school_name', 'enrollment', 'economic_need_index'],
    transform: function(row) {
      return [
        row.dbn || '',
        row.school_name || '',
        parseInt(row.total_enrollment) || 0,
        parseFloat(row.economic_need_index) || 0
      ];
    }
  },

  // Students in Temporary Housing - 2021
  // https://data.cityofnewyork.us/Education/2021-Students-In-Temporary-Housing/3wtp-43m9
  // Columns: dbn, school_name, total_students, students_in_temporary_housing,
  //          students_in_temporary_housing_1 (percent), students_residing_in_shelter, etc.
  STH: {
    name: 'Students in Temporary Housing',
    endpoint: 'https://data.cityofnewyork.us/resource/3wtp-43m9.json',
    sheet: 'STH_by_School',
    query: '$select=dbn,students_in_temporary_housing,students_in_temporary_housing_1&$limit=3000',
    columns: ['school_dbn', 'sth_count', 'sth_percent'],
    transform: function(row) {
      return [
        row.dbn || '',
        parseInt(row.students_in_temporary_housing) || 0,
        parseFloat(row.students_in_temporary_housing_1) || 0
      ];
    }
  }
};


/**
 * Add custom menu when spreadsheet opens
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('Reference Data')
    .addItem('Refresh All Data', 'refreshAllData')
    .addSeparator()
    .addItem('Refresh ENI Only', 'refreshENI')
    .addItem('Refresh STH Only', 'refreshSTH')
    .addSeparator()
    .addItem('View Last Update', 'showLastUpdate')
    .addItem('Setup Monthly Trigger', 'setupMonthlyTrigger')
    .addToUi();
}


/**
 * Refresh all data sources
 */
function refreshAllData() {
  const ui = SpreadsheetApp.getUi();

  ui.alert('Refreshing Data', 'This may take a minute...', ui.ButtonSet.OK);

  try {
    refreshENI();
    refreshSTH();
    updateMetadata();

    ui.alert('Success', 'All data has been refreshed!', ui.ButtonSet.OK);
  } catch (error) {
    ui.alert('Error', 'Failed to refresh data: ' + error.message, ui.ButtonSet.OK);
    Logger.log('Error refreshing data: ' + error);
  }
}


/**
 * Refresh ENI data from NYC Open Data
 */
function refreshENI() {
  const source = DATA_SOURCES.ENI;
  refreshDataSource(source);
}


/**
 * Refresh STH data from NYC Open Data
 */
function refreshSTH() {
  const source = DATA_SOURCES.STH;
  refreshDataSource(source);
}


/**
 * Generic function to refresh a data source
 */
function refreshDataSource(source) {
  Logger.log('Refreshing: ' + source.name);

  // Fetch data from API
  const url = source.endpoint + '?' + source.query;
  const response = UrlFetchApp.fetch(url);
  const data = JSON.parse(response.getContentText());

  if (!data || data.length === 0) {
    throw new Error('No data returned from ' + source.name);
  }

  Logger.log('Fetched ' + data.length + ' records');

  // Transform data
  const rows = data.map(source.transform);

  // Get or create sheet
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(source.sheet);

  if (!sheet) {
    sheet = ss.insertSheet(source.sheet);
  }

  // Clear and write data
  sheet.clear();

  // Write headers
  sheet.getRange(1, 1, 1, source.columns.length).setValues([source.columns]);
  sheet.getRange(1, 1, 1, source.columns.length).setFontWeight('bold');

  // Write data
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, source.columns.length).setValues(rows);
  }

  Logger.log('Updated ' + source.sheet + ' with ' + rows.length + ' records');
}


/**
 * Update metadata sheet with refresh timestamp
 */
function updateMetadata() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('_Metadata');

  if (!sheet) {
    sheet = ss.insertSheet('_Metadata');
  }

  // Get record counts
  const eniSheet = ss.getSheetByName('ENI_by_School');
  const sthSheet = ss.getSheetByName('STH_by_School');

  const eniCount = eniSheet ? Math.max(0, eniSheet.getLastRow() - 1) : 0;
  const sthCount = sthSheet ? Math.max(0, sthSheet.getLastRow() - 1) : 0;

  const metadata = [
    ['Field', 'Value'],
    ['Last Updated', new Date().toISOString()],
    ['Data Source', 'NYC Open Data API'],
    ['ENI Records', eniCount],
    ['STH Records', sthCount],
    ['Update Method', 'Apps Script'],
    ['ENI API', DATA_SOURCES.ENI.endpoint],
    ['STH API', DATA_SOURCES.STH.endpoint]
  ];

  sheet.clear();
  sheet.getRange(1, 1, metadata.length, 2).setValues(metadata);
  sheet.getRange(1, 1, 1, 2).setFontWeight('bold');
}


/**
 * Show when data was last updated
 */
function showLastUpdate() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('_Metadata');

  if (!sheet) {
    SpreadsheetApp.getUi().alert('No metadata found. Please refresh data first.');
    return;
  }

  const data = sheet.getDataRange().getValues();
  let lastUpdate = 'Unknown';

  for (const row of data) {
    if (row[0] === 'Last Updated') {
      lastUpdate = row[1];
      break;
    }
  }

  SpreadsheetApp.getUi().alert('Last Update', 'Data was last refreshed: ' + lastUpdate, SpreadsheetApp.getUi().ButtonSet.OK);
}


/**
 * Setup a monthly trigger to auto-refresh data
 */
function setupMonthlyTrigger() {
  // Delete existing triggers for this function
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'refreshAllData') {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  // Create new monthly trigger (runs on the 1st of each month at 3 AM)
  ScriptApp.newTrigger('refreshAllData')
    .timeBased()
    .onMonthDay(1)
    .atHour(3)
    .create();

  SpreadsheetApp.getUi().alert(
    'Trigger Created',
    'Data will automatically refresh on the 1st of each month at 3 AM.\n\n' +
    'You can manage triggers in Extensions > Apps Script > Triggers.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}
