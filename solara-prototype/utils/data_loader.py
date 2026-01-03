"""
Data loading and processing utilities for the Solara geographic dashboard.
Handles Google Sheets API, coordinate parsing, and data cleaning.

Data Source: Google Sheets API (live data from "HTYPE PowerBI Export")

Credential sources (in priority order):
1. Environment variable: GOOGLE_CREDENTIALS_JSON (JSON string)
2. Environment variable: GOOGLE_APPLICATION_CREDENTIALS (file path)
3. Local file: .credentials/service-account.json

Available Sheets/Tabs:
- School Training Status: Main school data with training status
- Participant Detail: Individual participant records
- Geographic Reference: District and superintendent mappings
- Vulnerability_Indicators: STH/ENI consolidated data
"""
import os
import json
import re
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import logging

from .color_schemes import normalize_training_status, get_color_for_status

# Configure logging
logger = logging.getLogger(__name__)

# Google Sheets configuration
GOOGLE_SHEET_ID = "18ktDu4Itz8zZXQqrDCdHFMFYkBYz4uFmHw12kQAygww"

# Tab names within the workbook
SHEET_TABS = {
    'school_training_status': 'School Training Status',
    'participant_detail': 'Participant Detail',
    'geographic_reference': 'Geographic Reference',
    'ppr_participating_schools': 'PPR_Participating_Schools',
    'vulnerability_indicators': 'Vulnerability_Indicators',
    'date_dimension': 'Date Dimension',
    # Risk indicator dimension tables (geographic aggregates)
    'crime_by_precinct': 'Crime_By_Precinct',
    'shelter_by_cd': 'Shelter_By_CD',
}


def classify_entity_type(dbn: str) -> str:
    """
    Classify DBN as school or district office based on NYC DOE patterns.

    District Superintendent Office pattern: DD[B]8DD
    - e.g., 01M801 = District 01 Manhattan office
    - e.g., 12X812 = District 12 Bronx office
    - e.g., 28Q828 = District 28 Queens office

    All 32 community school districts (01-32) have one superintendent office each.

    Returns:
        'district_office' for superintendent offices
        'school' for regular schools (default)
    """
    if pd.isna(dbn) or not dbn:
        return 'school'

    dbn = str(dbn).strip().upper()

    if len(dbn) != 6:
        return 'school'

    district = dbn[:2]
    school_num = dbn[3:6]

    # District Superintendent Office pattern: DD[B]8DD
    # e.g., 01M801 = district 01, school_num 801 (8 + "01")
    if district.isdigit():
        d_int = int(district)
        if 1 <= d_int <= 32:
            expected_suffix = f"8{district}"
            if school_num == expected_suffix:
                return 'district_office'

    return 'school'


def parse_coordinates(coord_str: str) -> Tuple[Optional[float], Optional[float]]:
    """Parse 'lat,lng' string into separate float values."""
    if pd.isna(coord_str) or not coord_str:
        return None, None

    try:
        parts = str(coord_str).split(',')
        if len(parts) == 2:
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            # Validate NYC bounds (rough)
            if 40.4 <= lat <= 41.0 and -74.3 <= lng <= -73.6:
                return lat, lng
    except (ValueError, AttributeError):
        pass

    return None, None


def process_coordinates(df: pd.DataFrame, coord_column: str = 'geo_coordinates') -> pd.DataFrame:
    """Add latitude and longitude columns from geo_coordinates."""
    coords = df[coord_column].apply(parse_coordinates)
    df['latitude'] = coords.apply(lambda x: x[0])
    df['longitude'] = coords.apply(lambda x: x[1])
    return df


def get_credentials():
    """
    Get Google service account credentials from environment or file.

    Priority:
    1. GOOGLE_CREDENTIALS_JSON env var (JSON string - for cloud deployment)
    2. GOOGLE_APPLICATION_CREDENTIALS env var (file path)
    3. Local .credentials/service-account.json file

    Returns:
        google.oauth2.service_account.Credentials object

    Raises:
        ImportError: If google-auth is not installed
        FileNotFoundError: If no credentials found
    """
    try:
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Google Sheets dependencies not installed. "
            "Run: pip install gspread google-auth"
        )

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly'
    ]

    # Option 1: JSON string in environment variable (for cloud deployment)
    json_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if json_creds:
        try:
            creds_dict = json.loads(json_creds)
            logger.info("Using credentials from GOOGLE_CREDENTIALS_JSON env var")
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse GOOGLE_CREDENTIALS_JSON: {e}")

    # Option 2: File path in environment variable
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path and Path(creds_path).exists():
        logger.info(f"Using credentials from GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
        return Credentials.from_service_account_file(creds_path, scopes=scopes)

    # Option 3: Local .credentials directory
    possible_paths = [
        Path(__file__).parent.parent / '.credentials' / 'service-account.json',
        Path(__file__).parent.parent.parent / '.credentials' / 'service-account.json',
        Path.home() / '.config' / 'htype-dashboard' / 'service-account.json',
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"Using credentials from local file: {path}")
            return Credentials.from_service_account_file(str(path), scopes=scopes)

    raise FileNotFoundError(
        "Google service account credentials not found. Options:\n"
        "1. Set GOOGLE_CREDENTIALS_JSON env var with JSON credentials string\n"
        "2. Set GOOGLE_APPLICATION_CREDENTIALS env var with path to credentials file\n"
        "3. Place credentials at .credentials/service-account.json"
    )


def load_from_google_sheets(
    sheet_id: str = GOOGLE_SHEET_ID,
    sheet_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Load data from Google Sheets using service account credentials.

    Args:
        sheet_id: The Google Sheet document ID
        sheet_name: Optional specific sheet/tab name to load (default: first sheet)

    Returns:
        DataFrame with the sheet data

    Raises:
        ImportError: If gspread or google-auth is not installed
        FileNotFoundError: If credentials file is not found
        PermissionError: If sheet is not shared with service account
        RuntimeError: If Google Sheets API fails
    """
    try:
        import gspread
    except ImportError:
        raise ImportError(
            "Google Sheets dependencies not installed. "
            "Run: pip install gspread google-auth"
        )

    credentials = get_credentials()

    try:
        # Connect to Google Sheets
        client = gspread.authorize(credentials)

        # Open the spreadsheet
        spreadsheet = client.open_by_key(sheet_id)

        # Get the specific sheet or first sheet
        if sheet_name:
            worksheet = spreadsheet.worksheet(sheet_name)
        else:
            worksheet = spreadsheet.sheet1

        # Get all data as a DataFrame
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        logger.info(f"Loaded {len(df)} rows from '{sheet_name or 'Sheet1'}' via Google Sheets API")
        return df

    except gspread.exceptions.SpreadsheetNotFound:
        raise PermissionError(
            f"Google Sheet not accessible. "
            f"Ensure it's shared with the service account email in credentials."
        )
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Worksheet '{sheet_name}' not found in spreadsheet.")
    except gspread.exceptions.APIError as e:
        raise RuntimeError(f"Google Sheets API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load from Google Sheets: {e}")


def load_school_data(use_cache: bool = True) -> pd.DataFrame:
    """
    Load and process school training status data from Google Sheets.

    Returns a DataFrame with:
    - Parsed coordinates (latitude, longitude)
    - Normalized training status
    - Color assignments for visualization
    - Merged vulnerability data (STH, ENI)

    Args:
        use_cache: If True, uses cached data when available (not yet implemented)

    Raises:
        RuntimeError: If Google Sheets connection fails
    """
    from .vulnerability_loader import load_vulnerability_data, merge_vulnerability_with_training

    # Load from Google Sheets
    df = load_from_google_sheets(
        sheet_id=GOOGLE_SHEET_ID,
        sheet_name=SHEET_TABS['school_training_status']
    )

    logger.info(f"Loaded {len(df)} schools from Google Sheets (live data)")

    # Parse coordinates
    if 'geo_coordinates' in df.columns:
        df = process_coordinates(df)

    # Normalize training status
    if 'training_completion_status' in df.columns:
        df['training_status'] = df['training_completion_status'].apply(normalize_training_status)
    else:
        df['training_status'] = 'Unknown'

    # Add color column for visualization (hex for ipyleaflet)
    from .color_schemes import get_hex_for_status
    df['color'] = df['training_status'].apply(get_hex_for_status)

    # Clean up borough names (normalize variations)
    if 'borough' in df.columns:
        df['borough'] = df['borough'].str.upper().str.strip()
        # Fix common abbreviations/typos
        borough_mapping = {
            'BROOKLN': 'BROOKLYN',
            'STATEN IS': 'STATEN ISLAND',
            'SI': 'STATEN ISLAND',
            'BX': 'BRONX',
            'BK': 'BROOKLYN',
            'MN': 'MANHATTAN',
            'QN': 'QUEENS',
        }
        df['borough'] = df['borough'].replace(borough_mapping)

    # Clean district (ensure integer)
    if 'district' in df.columns:
        df['district'] = pd.to_numeric(df['district'], errors='coerce').fillna(0).astype(int)

    # Normalize superintendent names
    if 'superintendent_name' in df.columns:
        def normalize_name(name):
            if pd.isna(name) or not name:
                return name
            name = str(name).strip()
            # If name contains comma, assume "Last, First" format
            if ',' in name:
                parts = name.split(',', 1)
                if len(parts) == 2:
                    last_name = parts[0].strip()
                    first_name = parts[1].strip()
                    name = f"{first_name} {last_name}"
            # Normalize case to Title Case
            name = name.title()
            # Remove middle initials for consistency
            name = re.sub(r'\s+[A-Za-z]\.\s+', ' ', name)
            name = re.sub(r'\s+', ' ', name)
            return name.strip()
        df['superintendent_name'] = df['superintendent_name'].apply(normalize_name)

    # Filter to valid coordinates only for mapping
    df['has_coordinates'] = df['latitude'].notna() & df['longitude'].notna()

    # Classify entity type (school vs district office)
    if 'school_dbn' in df.columns:
        df['entity_type'] = df['school_dbn'].apply(classify_entity_type)
        df['is_school'] = df['entity_type'] == 'school'
        df['is_office'] = df['entity_type'] == 'district_office'
        office_count = df['is_office'].sum()
        school_count = df['is_school'].sum()
        logger.info(f"Entity classification: {school_count} schools, {office_count} district offices")

    # Load and merge vulnerability data
    try:
        vuln_df = load_vulnerability_data()
        logger.info(f"Loaded vulnerability data: {len(vuln_df)} rows")

        if len(vuln_df) > 0:
            df = merge_vulnerability_with_training(df, vuln_df)
            logger.info(f"Merged vulnerability data for {len(df)} schools")
        else:
            logger.warning("Vulnerability data is empty!")
            # Add placeholder columns
            df['sth_percent'] = None
            df['economic_need_index'] = None
            df['high_sth'] = False
            df['high_eni'] = False
    except Exception as e:
        logger.warning(f"Failed to load vulnerability data: {e}")
        df['sth_percent'] = None
        df['economic_need_index'] = None
        df['high_sth'] = False
        df['high_eni'] = False

    # Load and merge crime data (joins via police_precinct from Vulnerability_Indicators)
    try:
        from .vulnerability_loader import (
            load_crime_by_precinct,
            load_shelter_by_cd,
            merge_crime_data_with_schools,
            merge_shelter_data_with_schools,
            get_crime_tier,
            get_shelter_tier
        )

        crime_df = load_crime_by_precinct()
        if len(crime_df) > 0 and 'police_precinct' in df.columns:
            df = merge_crime_data_with_schools(df, crime_df)
            # Add crime tier for visualization
            if 'htype_relevant_count' in df.columns:
                df['crime_tier'] = df['htype_relevant_count'].apply(get_crime_tier)
            logger.info(f"Added crime data to {len(df)} schools")
        else:
            logger.info("Skipping crime merge - no data or missing police_precinct column")
    except Exception as e:
        logger.warning(f"Failed to load crime data: {e}")

    # Load and merge shelter data (joins via community_district from Vulnerability_Indicators)
    try:
        shelter_df = load_shelter_by_cd()
        if len(shelter_df) > 0 and 'community_district' in df.columns:
            df = merge_shelter_data_with_schools(df, shelter_df)
            # Add shelter tier for visualization
            if 'shelter_individuals' in df.columns:
                df['shelter_tier'] = df['shelter_individuals'].apply(get_shelter_tier)
            logger.info(f"Added shelter data to {len(df)} schools")
        else:
            logger.info("Skipping shelter merge - no data or missing community_district column")
    except Exception as e:
        logger.warning(f"Failed to load shelter data: {e}")

    return df


def get_filter_options(
    df: pd.DataFrame,
    selected_boroughs: Optional[list] = None,
    selected_districts: Optional[list] = None
) -> dict:
    """
    Extract unique values for filter dropdowns with cascading support.

    When boroughs are selected, districts/superintendents/school_types
    are filtered to only show options relevant to those boroughs.
    """
    # Boroughs - always show all (top level)
    all_boroughs = sorted(df['borough'].dropna().unique().tolist())

    # Start with full dataframe for cascading
    cascade_df = df.copy()

    # If boroughs selected, filter for downstream options
    if selected_boroughs and len(selected_boroughs) > 0:
        cascade_df = cascade_df[cascade_df['borough'].isin(selected_boroughs)]

    # If districts also selected, filter further for superintendent/school_type
    district_cascade_df = cascade_df.copy()
    if selected_districts and len(selected_districts) > 0:
        district_cascade_df = district_cascade_df[district_cascade_df['district'].isin(selected_districts)]

    options = {
        'boroughs': all_boroughs,
        'districts': sorted(cascade_df['district'].dropna().unique().tolist()),
        'training_statuses': ['All', 'Complete', 'Fundamentals Only', 'LIGHTS Only', 'No Training'],
        'superintendents': sorted(district_cascade_df['superintendent_name'].dropna().unique().tolist()) if 'superintendent_name' in district_cascade_df.columns else [],
        'school_types': sorted(district_cascade_df['school_type'].dropna().unique().tolist()) if 'school_type' in district_cascade_df.columns else [],
    }
    return options


def filter_schools(
    df: pd.DataFrame,
    boroughs: Optional[list] = None,
    districts: Optional[list] = None,
    training_status: Optional[str] = None,
    superintendent: Optional[str] = None,
    school_type: Optional[str] = None,
    search_query: Optional[str] = None,
    has_fundamentals: Optional[bool] = None,
    has_lights: Optional[bool] = None,
    high_sth_only: bool = False,
    high_eni_only: bool = False,
    min_sth: Optional[float] = None,
    min_eni: Optional[float] = None,
) -> pd.DataFrame:
    """Apply filters to school DataFrame."""
    filtered = df.copy()

    if boroughs and len(boroughs) > 0:
        filtered = filtered[filtered['borough'].isin(boroughs)]

    if districts and len(districts) > 0:
        filtered = filtered[filtered['district'].isin(districts)]

    if training_status and training_status != 'All':
        filtered = filtered[filtered['training_status'] == training_status]

    if superintendent:
        filtered = filtered[filtered['superintendent_name'] == superintendent]

    if school_type and school_type != 'All':
        filtered = filtered[filtered['school_type'] == school_type]

    if search_query:
        query_lower = search_query.lower()
        filtered = filtered[
            filtered['school_name'].str.lower().str.contains(query_lower, na=False) |
            filtered['school_dbn'].str.lower().str.contains(query_lower, na=False)
        ]

    if has_fundamentals is not None:
        fund_val = 'Yes' if has_fundamentals else 'No'
        filtered = filtered[filtered['has_fundamentals'] == fund_val]

    if has_lights is not None:
        lights_val = 'Yes' if has_lights else 'No'
        filtered = filtered[filtered['has_lights'] == lights_val]

    # STH filters
    if high_sth_only and 'high_sth' in filtered.columns:
        filtered = filtered[filtered['high_sth'] == True]

    if min_sth is not None and 'sth_percent' in filtered.columns:
        filtered = filtered[filtered['sth_percent'] >= min_sth]

    # ENI filters
    if high_eni_only and 'high_eni' in filtered.columns:
        filtered = filtered[filtered['high_eni'] == True]

    if min_eni is not None and 'economic_need_index' in filtered.columns:
        filtered = filtered[filtered['economic_need_index'] >= min_eni]

    return filtered


def filter_by_training_status(df: pd.DataFrame, status: str) -> pd.DataFrame:
    """
    Filter schools by training status mode (global filter - task-oriented).

    Each mode provides a tailored stats panel for that workflow:
    - Overview: Full picture - all schools with training breakdown
    - Trained: Progress view - schools with any training
    - Untrained: Outreach targets - schools with no training
    - Need LIGHTS: Next step ready - have Fundamentals, need LIGHTS

    Args:
        df: School DataFrame
        status: One of the mode names

    Returns:
        Filtered DataFrame
    """
    if status == 'Overview' or not status:
        return df

    filtered = df.copy()

    if status == 'Trained':
        # Schools with ANY training (Fundamentals OR LIGHTS)
        mask = (filtered['has_fundamentals'] == 'Yes') | (filtered['has_lights'] == 'Yes')
        return filtered[mask]
    elif status == 'Untrained':
        # Schools with NO training at all - outreach targets
        mask = (filtered['has_fundamentals'] == 'No') & (filtered['has_lights'] == 'No')
        return filtered[mask]
    elif status == 'Need LIGHTS':
        # Schools with Fundamentals but NO LIGHTS - ready for next step
        mask = (filtered['has_fundamentals'] == 'Yes') & (filtered['has_lights'] == 'No')
        return filtered[mask]

    return df


def calculate_summary_stats(
    df: pd.DataFrame,
    full_df: Optional[pd.DataFrame] = None,
    mode: str = 'Overview'
) -> dict:
    """
    Calculate summary statistics for the filtered data.

    Args:
        df: Filtered DataFrame
        full_df: Optional full DataFrame for universe metrics
        mode: Current view mode

    Returns:
        Dictionary of statistics
    """
    total = len(df)
    mappable = df['has_coordinates'].sum() if 'has_coordinates' in df.columns else total

    universe_df = full_df if full_df is not None else df
    universe_total = len(universe_df)

    # Training status counts
    lights_trained = len(df[df['training_status'] == 'Complete'])
    fundamentals_only_count = len(df[df.get('has_fundamentals', pd.Series()) == 'Yes']) - lights_trained if 'has_fundamentals' in df.columns else 0
    not_started = len(df[df['training_status'] == 'No Training'])

    stats = {
        'total': total,
        'mappable': mappable,
        'complete': lights_trained,
        'fundamentals': max(0, fundamentals_only_count),
        'no_training': not_started,
    }

    # Calculate percentages
    if total > 0:
        stats['complete_pct'] = round(lights_trained / total * 100, 1)
        stats['fundamentals_pct'] = round(max(0, fundamentals_only_count) / total * 100, 1)
        stats['no_training_pct'] = round(not_started / total * 100, 1)
    else:
        stats['complete_pct'] = stats['fundamentals_pct'] = stats['no_training_pct'] = 0

    # Priority schools: high ENI + no training
    if 'high_eni' in df.columns and 'training_status' in df.columns:
        priority_mask = (df['high_eni'] == True) & (df['training_status'] == 'No Training')
        stats['priority'] = priority_mask.sum()
    else:
        stats['priority'] = 0

    # High ENI count
    if 'high_eni' in df.columns:
        stats['high_eni'] = (df['high_eni'] == True).sum()
    else:
        stats['high_eni'] = 0

    # High STH count
    if 'high_sth' in df.columns:
        stats['high_sth'] = (df['high_sth'] == True).sum()
    else:
        stats['high_sth'] = 0

    # Average indicators
    if 'sth_percent' in df.columns:
        sth_data = df['sth_percent'].dropna()
        stats['avg_sth'] = round(sth_data.mean() * 100, 1) if len(sth_data) > 0 else 0
    else:
        stats['avg_sth'] = 0

    if 'economic_need_index' in df.columns:
        eni_data = df['economic_need_index'].dropna()
        stats['avg_eni'] = round(eni_data.mean() * 100, 1) if len(eni_data) > 0 else 0
    else:
        stats['avg_eni'] = 0

    # Crime indicator statistics
    if 'htype_relevant_count' in df.columns:
        crime_data = df['htype_relevant_count'].dropna()
        stats['schools_with_crime_data'] = len(crime_data)
        stats['total_htype_offenses'] = int(crime_data.sum()) if len(crime_data) > 0 else 0
        stats['avg_htype_offenses'] = round(crime_data.mean(), 1) if len(crime_data) > 0 else 0
        stats['high_crime_schools'] = (df['crime_tier'] == 'High (200+)').sum() if 'crime_tier' in df.columns else 0
    else:
        stats['schools_with_crime_data'] = 0
        stats['total_htype_offenses'] = 0
        stats['avg_htype_offenses'] = 0
        stats['high_crime_schools'] = 0

    # Shelter indicator statistics
    if 'shelter_individuals' in df.columns:
        shelter_data = df['shelter_individuals'].dropna()
        stats['schools_with_shelter_data'] = len(shelter_data)
        stats['avg_shelter_individuals'] = round(shelter_data.mean(), 0) if len(shelter_data) > 0 else 0
        stats['high_shelter_schools'] = (df['shelter_tier'] == 'High (1500+)').sum() if 'shelter_tier' in df.columns else 0
    else:
        stats['schools_with_shelter_data'] = 0
        stats['avg_shelter_individuals'] = 0
        stats['high_shelter_schools'] = 0

    return stats


# ============================================================================
# PARTICIPANT DETAIL DATA
# ============================================================================

def load_participant_data() -> pd.DataFrame:
    """
    Load participant detail data from Google Sheets.

    Returns DataFrame with:
    - first_name, last_name, role_standardized
    - school_dbn, training_type, training_date
    - Priority role flag for SAPIS/Social Worker/SSM

    The Participant Detail tab contains one row per participant per training type.
    """
    df = load_from_google_sheets(
        sheet_id=GOOGLE_SHEET_ID,
        sheet_name=SHEET_TABS['participant_detail']
    )

    logger.info(f"Loaded {len(df)} participant records from Participant Detail")

    # Standardize roles - look for SAPIS and other priority roles
    def standardize_role_display(role):
        if pd.isna(role) or not role:
            return 'Unknown'
        role_str = str(role).strip()
        role_lower = role_str.lower()

        # Check for SAPIS (School-Age Parent Infant Specialist or similar)
        if 'sapis' in role_lower:
            return 'SAPIS'

        # Keep other standardized roles as-is (they come pre-standardized)
        return role_str

    if 'role_standardized' in df.columns:
        df['role_display'] = df['role_standardized'].apply(standardize_role_display)
    elif 'role_category' in df.columns:
        df['role_display'] = df['role_category'].apply(standardize_role_display)
    else:
        df['role_display'] = 'Unknown'

    # Flag priority roles for sorting
    priority_roles = ['SAPIS', 'Social Worker', 'Student Service Manager', 'School Counselor']
    df['is_priority_role'] = df['role_display'].isin(priority_roles)

    # Parse training_date if it exists
    if 'training_date' in df.columns:
        df['training_date'] = pd.to_datetime(df['training_date'], errors='coerce')

    # Ensure school_dbn is uppercase for joining
    if 'school_dbn' in df.columns:
        df['school_dbn'] = df['school_dbn'].str.upper().str.strip()

    return df
