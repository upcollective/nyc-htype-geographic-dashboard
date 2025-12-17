"""
Data loading and processing utilities for the geographic dashboard.
Handles Google Sheets API, coordinate parsing, and data cleaning.

Data Source: Google Sheets API (live data from "HTYPE PowerBI Export")

Available Sheets/Tabs:
- School Training Status: Main school data with training status
- Participant Detail: Individual participant records
- Geographic Reference: District and superintendent mappings
- PPR_Participating_Schools: PPR reporting data
- Date Dimension: Date reference table
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import logging

from .color_schemes import normalize_training_status, get_color_for_status
from .vulnerability_loader import load_vulnerability_data, merge_vulnerability_with_training

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
    'date_dimension': 'Date Dimension',
}


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


def get_credentials_path() -> Optional[Path]:
    """Get the path to the service account credentials file."""
    # Check multiple possible locations
    possible_paths = [
        Path(__file__).parent.parent / '.credentials' / 'service-account.json',
        Path.home() / '.config' / 'htype-dashboard' / 'service-account.json',
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def load_from_google_sheets(
    sheet_id: str = GOOGLE_SHEET_ID,
    sheet_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Load data from Google Sheets using service account credentials.

    Supports both:
    - Streamlit Cloud: credentials from st.secrets["gcp_service_account"]
    - Local development: credentials from .credentials/service-account.json

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
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Google Sheets dependencies not installed. "
            "Run: pip install gspread google-auth"
        )

    # Define required scopes
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly'
    ]

    # Get credentials - Streamlit Cloud uses secrets, local uses file
    import streamlit as st

    # Check if running on Streamlit Cloud with secrets configured
    # Note: len(st.secrets) throws an exception if no secrets exist, so we use try/except
    use_secrets = False
    try:
        if "gcp_service_account" in st.secrets:
            use_secrets = True
    except Exception:
        # No secrets configured - will use file credentials
        pass

    if use_secrets:
        # Running on Streamlit Cloud with secrets configured
        credentials = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=scopes
        )
        logger.info("Using Streamlit Cloud secrets for authentication")
    else:
        # Local development - use file credentials
        credentials_path = get_credentials_path()
        if not credentials_path:
            raise FileNotFoundError(
                "Service account credentials not found. "
                "Expected at: .credentials/service-account.json"
            )
        credentials = Credentials.from_service_account_file(
            str(credentials_path),
            scopes=scopes
        )
        logger.info("Using local file credentials for authentication")

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


def load_school_data() -> pd.DataFrame:
    """
    Load and process school training status data from Google Sheets.

    Returns a DataFrame with:
    - Parsed coordinates (latitude, longitude)
    - Normalized training status
    - Color assignments for visualization

    Raises:
        RuntimeError: If Google Sheets connection fails
    """
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

    # Add color column for visualization
    df['color'] = df['training_status'].apply(get_color_for_status)

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

    # Normalize superintendent names (convert "Last, First" to "First Last", normalize case)
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
            # Remove middle initials for consistency (e.g., "Rafael T. Alvarez" -> "Rafael Alvarez")
            # Only remove single-letter middle parts followed by period (case insensitive after title())
            import re
            name = re.sub(r'\s+[A-Za-z]\.\s+', ' ', name)  # "Rafael T. Alvarez" -> "Rafael Alvarez"
            name = re.sub(r'\s+', ' ', name)  # Clean up any double spaces
            return name.strip()
        df['superintendent_name'] = df['superintendent_name'].apply(normalize_name)

    # Filter to valid coordinates only for mapping
    df['has_coordinates'] = df['latitude'].notna() & df['longitude'].notna()

    # Load and merge vulnerability data from Google Sheets
    # NO FALLBACK - fail loudly if Vulnerability_Indicators tab doesn't work
    vuln_df = load_vulnerability_data()
    logger.info(f"Loaded vulnerability data: {len(vuln_df)} rows")

    if len(vuln_df) > 0:
        df = merge_vulnerability_with_training(df, vuln_df)
        logger.info(f"Merged vulnerability data for {len(df)} schools")
    else:
        logger.warning("Vulnerability data is empty!")

    return df


def load_geographic_reference() -> pd.DataFrame:
    """Load geographic reference data (districts, superintendents) from Google Sheets."""
    return load_from_google_sheets(
        sheet_id=GOOGLE_SHEET_ID,
        sheet_name=SHEET_TABS['geographic_reference']
    )


def load_participant_detail() -> pd.DataFrame:
    """Load participant detail data from Google Sheets."""
    return load_from_google_sheets(
        sheet_id=GOOGLE_SHEET_ID,
        sheet_name=SHEET_TABS['participant_detail']
    )


def load_ppr_participating_schools() -> pd.DataFrame:
    """Load PPR participating schools data from Google Sheets."""
    return load_from_google_sheets(
        sheet_id=GOOGLE_SHEET_ID,
        sheet_name=SHEET_TABS['ppr_participating_schools']
    )


def get_filter_options(df: pd.DataFrame) -> dict:
    """Extract unique values for filter dropdowns."""
    options = {
        'boroughs': sorted(df['borough'].dropna().unique().tolist()),
        'districts': sorted(df['district'].dropna().unique().tolist()),
        'training_statuses': ['All', 'Complete', 'Fundamentals Only', 'LIGHTS Only', 'No Training'],
        'superintendents': sorted(df['superintendent_name'].dropna().unique().tolist()) if 'superintendent_name' in df.columns else [],
        'school_types': sorted(df['school_type'].dropna().unique().tolist()) if 'school_type' in df.columns else [],
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
    Filter schools by training status (global filter - task-oriented).

    This is a user-friendly filter that affects ALL views
    (Map, Statistics, Indicators, Data Table).

    Args:
        df: School DataFrame
        status: One of:
            - 'Training Coverage' - Schools with ANY training (default)
            - 'Outreach Targets' - Schools with NO training
            - 'Fundamentals Only' - Has Fundamentals training
            - 'LIGHTS Only' - Has LIGHTS ToT training
            - 'Complete Training' - Has BOTH Fundamentals AND LIGHTS
            - 'All Schools (Reference)' - No filtering (full universe)

    Returns:
        Filtered DataFrame
    """
    if status == 'All Schools (Reference)' or not status:
        return df

    filtered = df.copy()

    if status == 'Training Coverage':
        # Schools with ANY training (Fundamentals OR LIGHTS)
        mask = (filtered['has_fundamentals'] == 'Yes') | (filtered['has_lights'] == 'Yes')
        return filtered[mask]
    elif status == 'Outreach Targets':
        # Schools with NO training - uniform gray dots
        mask = (filtered['has_fundamentals'] == 'No') & (filtered['has_lights'] == 'No')
        return filtered[mask]
    elif status == 'Fundamentals Only':
        return filtered[filtered['has_fundamentals'] == 'Yes']
    elif status == 'LIGHTS Only':
        return filtered[filtered['has_lights'] == 'Yes']
    elif status == 'Complete Training':
        mask = (filtered['has_fundamentals'] == 'Yes') & (filtered['has_lights'] == 'Yes')
        return filtered[mask]

    return df


def apply_layer_filter(
    df: pd.DataFrame,
    layer_type: str,
    layer_config: dict
) -> pd.DataFrame:
    """
    Apply a single layer's filter configuration to the DataFrame.

    Args:
        df: School DataFrame
        layer_type: 'fundamentals', 'lights', or 'student_sessions'
        layer_config: Dict with 'enabled', 'filter', 'min_depth' keys

    Returns:
        Filtered DataFrame for this layer
    """
    if not layer_config.get('enabled', False):
        return pd.DataFrame()  # Empty if layer not enabled

    filtered = df.copy()

    # Map layer type to column names
    column_map = {
        'fundamentals': ('has_fundamentals', 'fundamentals_participants'),
        'lights': ('has_lights', 'lights_participants'),
        'student_sessions': ('has_student_sessions', 'student_sessions_count'),  # Future
    }

    has_col, count_col = column_map.get(layer_type, column_map['fundamentals'])

    # Apply filter type
    filter_type = layer_config.get('filter', 'All Schools')

    if filter_type == 'Has Training':
        if has_col in filtered.columns:
            filtered = filtered[filtered[has_col] == 'Yes']
        else:
            # If column doesn't exist, assume no training data
            return pd.DataFrame()

    elif filter_type == 'Missing Training':
        if has_col in filtered.columns:
            filtered = filtered[filtered[has_col] == 'No']
        else:
            # If column doesn't exist, all schools are "missing" this training
            pass

    # Apply depth filter
    min_depth = layer_config.get('min_depth', 0)
    if min_depth > 0 and count_col in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered[count_col], errors='coerce').fillna(0) >= min_depth
        ]

    return filtered


def filter_schools_by_layers(
    df: pd.DataFrame,
    layer_config: dict,
    intersection: bool = False
) -> pd.DataFrame:
    """
    Filter schools based on multi-layer training configuration.

    By default, returns UNION of all enabled layers (school appears if it matches
    ANY enabled layer). Set intersection=True to require ALL enabled layers.

    Args:
        df: School DataFrame
        layer_config: Dict with keys 'fundamentals', 'lights', 'student_sessions'
        intersection: If True, require schools to match ALL enabled layers

    Returns:
        Filtered DataFrame
    """
    if not layer_config:
        return df

    layer_results = []

    for layer_type in ['fundamentals', 'lights', 'student_sessions']:
        config = layer_config.get(layer_type, {})
        if config.get('enabled', False) and not config.get('placeholder', False):
            layer_df = apply_layer_filter(df, layer_type, config)
            if len(layer_df) > 0:
                layer_results.append(set(layer_df['school_dbn'].tolist()))

    if not layer_results:
        # No layers enabled - return all schools
        return df

    if intersection:
        # Schools must match ALL enabled layers
        matching_dbns = layer_results[0]
        for result_set in layer_results[1:]:
            matching_dbns = matching_dbns & result_set
    else:
        # Schools must match ANY enabled layer (union)
        matching_dbns = set()
        for result_set in layer_results:
            matching_dbns = matching_dbns | result_set

    return df[df['school_dbn'].isin(matching_dbns)]


def calculate_summary_stats(df: pd.DataFrame, full_df: Optional[pd.DataFrame] = None) -> dict:
    """
    Calculate summary statistics for the filtered data.

    Args:
        df: Filtered DataFrame (respects all filters including training status)
        full_df: Optional full DataFrame (geographic filters only, no training status filter).
                 Used for "universe" reference metrics like priority_schools and no_training
                 that should always show the big picture for strategic awareness.
    """
    total = len(df)
    mappable = df['has_coordinates'].sum() if 'has_coordinates' in df.columns else total

    # Use full_df for universe metrics if provided, otherwise fall back to df
    universe_df = full_df if full_df is not None else df
    universe_total = len(universe_df)

    stats = {
        'total_schools': total,
        'mappable_schools': mappable,
        'complete': len(df[df['training_status'] == 'Complete']),
        'partial': len(df[df['training_status'].isin(['Fundamentals Only', 'LIGHTS Only'])]),
        # no_training uses universe_df so it always shows schools needing outreach
        'no_training': len(universe_df[universe_df['training_status'] == 'No Training']),
        'total_participants': df['total_participants'].sum() if 'total_participants' in df.columns else 0,
    }

    # Calculate percentages (based on filtered view)
    if total > 0:
        stats['complete_pct'] = round(stats['complete'] / total * 100, 1)
        stats['partial_pct'] = round(stats['partial'] / total * 100, 1)
    else:
        stats['complete_pct'] = stats['partial_pct'] = 0

    # no_training percentage uses universe total for proper context
    if universe_total > 0:
        stats['no_training_pct'] = round(stats['no_training'] / universe_total * 100, 1)
    else:
        stats['no_training_pct'] = 0

    # STH statistics (separate indicator) - from filtered view
    if 'sth_percent' in df.columns:
        sth_data = df['sth_percent'].dropna()
        stats['schools_with_sth'] = len(sth_data)
        stats['avg_sth_percent'] = sth_data.mean() if len(sth_data) > 0 else None
        stats['max_sth_percent'] = sth_data.max() if len(sth_data) > 0 else None
        if 'high_sth' in df.columns:
            stats['high_sth_count'] = df['high_sth'].sum()

    # ENI statistics (separate indicator) - from filtered view
    if 'economic_need_index' in df.columns:
        eni_data = df['economic_need_index'].dropna()
        stats['schools_with_eni'] = len(eni_data)
        stats['avg_eni'] = eni_data.mean() if len(eni_data) > 0 else None
        stats['max_eni'] = eni_data.max() if len(eni_data) > 0 else None
        if 'high_eni' in df.columns:
            stats['high_eni_count'] = df['high_eni'].sum()

    # Priority schools: high STH + no training - uses universe_df for strategic awareness
    # (always shows actionable outreach targets regardless of training status filter)
    if 'high_sth' in universe_df.columns and 'training_status' in universe_df.columns:
        priority_mask = (universe_df['high_sth'] == True) & (universe_df['training_status'] == 'No Training')
        stats['priority_schools'] = priority_mask.sum()

    return stats
