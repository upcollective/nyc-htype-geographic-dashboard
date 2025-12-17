#!/usr/bin/env python3
"""
Setup script for NYC Schools Reference Data Google Sheet.

Run this AFTER you've:
1. Created a new Google Sheet named "NYC Schools Reference Data"
2. Shared it with: htype-dashboard-reader@work-projects-mcp.iam.gserviceaccount.com
3. Copied the Sheet ID from the URL

Usage:
    python setup_reference_sheet.py <SHEET_ID>

Example:
    python setup_reference_sheet.py 1ABC123def456...
"""

import sys
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
import pandas as pd
from datetime import datetime

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nERROR: Please provide the Google Sheet ID as an argument.")
        print("\nTo get the Sheet ID:")
        print("1. Open your Google Sheet")
        print("2. Look at the URL: https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit")
        print("3. Copy the SHEET_ID_HERE part")
        sys.exit(1)

    sheet_id = sys.argv[1]

    # Setup paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    cred_path = project_dir / '.credentials' / 'service-account.json'
    vuln_dir = project_dir / 'data' / 'vulnerability'

    if not cred_path.exists():
        print(f"ERROR: Credentials not found at {cred_path}")
        sys.exit(1)

    # Connect to Google Sheets
    print("Connecting to Google Sheets...")
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    credentials = Credentials.from_service_account_file(str(cred_path), scopes=scopes)
    client = gspread.authorize(credentials)

    try:
        spreadsheet = client.open_by_key(sheet_id)
        print(f"✓ Connected to: {spreadsheet.title}")
    except gspread.exceptions.SpreadsheetNotFound:
        print("ERROR: Sheet not found. Make sure you've shared it with:")
        print("  htype-dashboard-reader@work-projects-mcp.iam.gserviceaccount.com")
        sys.exit(1)

    # Setup worksheets
    print("\nSetting up worksheets...")

    # Get or create ENI sheet
    try:
        eni_sheet = spreadsheet.worksheet('ENI_by_School')
        print("  ✓ Found ENI_by_School")
    except gspread.exceptions.WorksheetNotFound:
        try:
            sheet1 = spreadsheet.sheet1
            sheet1.update_title('ENI_by_School')
            eni_sheet = sheet1
            print("  ✓ Renamed Sheet1 to ENI_by_School")
        except:
            eni_sheet = spreadsheet.add_worksheet('ENI_by_School', rows=2000, cols=10)
            print("  ✓ Created ENI_by_School")

    # Get or create STH sheet
    try:
        sth_sheet = spreadsheet.worksheet('STH_by_School')
        print("  ✓ Found STH_by_School")
    except gspread.exceptions.WorksheetNotFound:
        sth_sheet = spreadsheet.add_worksheet('STH_by_School', rows=2000, cols=10)
        print("  ✓ Created STH_by_School")

    # Get or create Metadata sheet
    try:
        meta_sheet = spreadsheet.worksheet('_Metadata')
        print("  ✓ Found _Metadata")
    except gspread.exceptions.WorksheetNotFound:
        meta_sheet = spreadsheet.add_worksheet('_Metadata', rows=20, cols=5)
        print("  ✓ Created _Metadata")

    # Upload ENI data
    print("\nUploading data...")
    eni_path = vuln_dir / 'eni_by_school.csv'
    if eni_path.exists():
        eni_df = pd.read_csv(eni_path)
        eni_data = [eni_df.columns.tolist()] + eni_df.fillna('').values.tolist()
        eni_sheet.clear()
        eni_sheet.update('A1', eni_data)
        print(f"  ✓ Uploaded {len(eni_df)} ENI records")
    else:
        print(f"  ⚠ ENI file not found: {eni_path}")

    # Upload STH data
    sth_path = vuln_dir / 'sth_by_school.csv'
    if sth_path.exists():
        sth_df = pd.read_csv(sth_path)
        sth_data = [sth_df.columns.tolist()] + sth_df.fillna('').values.tolist()
        sth_sheet.clear()
        sth_sheet.update('A1', sth_data)
        print(f"  ✓ Uploaded {len(sth_df)} STH records")
    else:
        print(f"  ⚠ STH file not found: {sth_path}")

    # Update metadata
    metadata = [
        ['Field', 'Value'],
        ['Last Updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Data Source', 'NYC Open Data'],
        ['ENI Records', str(len(eni_df)) if eni_path.exists() else 'N/A'],
        ['STH Records', str(len(sth_df)) if sth_path.exists() else 'N/A'],
        ['Update Method', 'Apps Script or manual'],
        ['Sheet ID', sheet_id],
    ]
    meta_sheet.clear()
    meta_sheet.update('A1', metadata)
    print("  ✓ Updated metadata")

    print(f"\n{'='*50}")
    print("✅ SUCCESS! Reference data sheet is ready.")
    print(f"{'='*50}")
    print(f"\nSheet URL: {spreadsheet.url}")
    print(f"Sheet ID:  {sheet_id}")
    print("\nNext steps:")
    print("1. Open the sheet and add the Apps Script (see apps_script_refresh.js)")
    print("2. Update data_loader.py with the new sheet ID")


if __name__ == '__main__':
    main()
