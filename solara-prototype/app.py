"""
HTYPE Geographic Dashboard - Solara Prototype v5
=================================================

Production-ready version with live Google Sheets integration.
Custom layout using solara.Column/Row for precise control.

Layout:
- White toolbar at top (56px) with filters
- Left info panel (360px) with mode tabs, stats, collapsibles
- Map fills remaining space

Data source: Google Sheets (HTYPE PowerBI Export) with fallback to mock CSV.

Run with: solara run app.py --port 8504
"""

import solara
import pandas as pd
import json
import logging
import io
import base64
from datetime import datetime
from pathlib import Path
from ipyleaflet import Map, CircleMarker, GeoJSON, Choropleth, basemaps, WidgetControl, ZoomControl
from branca.colormap import linear
from ipywidgets import Layout, HTML as HTMLWidget, ToggleButtons, VBox, Checkbox
import reacton.ipyvuetify as rv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Startup diagnostic
logger.info("=" * 50)
logger.info("HTYPE Geographic Dashboard starting up...")
logger.info(f"Python executing from: {__file__}")
import os
logger.info(f"GOOGLE_CREDENTIALS_JSON set: {'Yes' if os.environ.get('GOOGLE_CREDENTIALS_JSON') else 'No'}")
logger.info(f"DASHBOARD_PASSWORD set: {'Yes' if os.environ.get('DASHBOARD_PASSWORD') else 'No (public access)'}")
logger.info("=" * 50)

# ============================================================================
# AUTHENTICATION
# ============================================================================
# Password is stored in environment variable DASHBOARD_PASSWORD
# If not set, dashboard is publicly accessible (for development)
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', '')

# Try to import utils for live data (may fail if dependencies not installed)
try:
    from utils import (
        load_school_data as load_live_data,
        load_participant_data as load_participant_data_live,
        calculate_summary_stats,
        TRAINING_COLORS_HEX,
        get_hex_for_status,
        # Multi-layer color utilities
        TRAINING_LAYER_COLORS,
        DEPTH_THRESHOLDS,
        calculate_dot_radius,
        get_layer_color_hex,
        HIGH_STH_THRESHOLD,
        HIGH_ENI_THRESHOLD,
    )
    LIVE_DATA_AVAILABLE = True
    logger.info("Utils module loaded - live data available")
except ImportError as e:
    LIVE_DATA_AVAILABLE = False
    logger.warning(f"Utils module not available: {e}. Using mock data only.")
    # Fallback constants (must match vulnerability_loader.py values)
    HIGH_STH_THRESHOLD = 0.15  # 15% STH threshold
    HIGH_ENI_THRESHOLD = 0.74  # 74% ENI threshold

# ============================================================================
# CSS VARIABLES (matching mockup)
# ============================================================================
COLORS = {
    'complete': '#6B9080',      # Sage green
    'fundamentals': '#D4A574',  # Warm tan
    'no_training': '#B87D7D',   # Dusty rose
    'sth': '#ff6464',           # Bright coral
    'eni': '#00dcdc',           # Bright cyan
    'bg_page': '#f0f2f6',
    'bg_panel': '#ffffff',
    'border': '#e5e7eb',
    'text_primary': '#262730',
    'text_secondary': '#6b7280',
    'text_muted': '#9ca3af',
}

# ============================================================================
# DATA LOADING
# ============================================================================

# Cache for loaded data (avoid repeated API calls)
_cached_data = None
_data_source = None

def load_school_data() -> pd.DataFrame:
    """
    Load school data from Google Sheets (live) with fallback to mock CSV.

    Returns DataFrame with standardized columns:
    - school_dbn, school_name, borough, district
    - latitude, longitude
    - training_status, color
    - sth_pct (%), eni_score (0-1)
    - superintendent (name)
    """
    global _cached_data, _data_source

    # Return cached data if available
    if _cached_data is not None:
        return _cached_data.copy()

    # Try live data first
    if LIVE_DATA_AVAILABLE:
        try:
            logger.info("Attempting to load live data from Google Sheets...")
            df = load_live_data()
            logger.info(f"Loaded {len(df)} schools from Google Sheets (live data)")

            # Normalize column names to match what the app expects
            df = normalize_live_data_columns(df)

            _cached_data = df
            _data_source = "live"
            return df.copy()

        except Exception as e:
            logger.warning(f"Failed to load live data: {e}. Falling back to mock data.")

    # Fallback to mock CSV
    logger.info("Loading mock data from CSV...")
    data_path = Path(__file__).parent / "data" / "mock_schools.csv"

    if not data_path.exists():
        # Create minimal fallback data so the app can at least load
        logger.error(f"Mock data file not found: {data_path}")
        logger.error("Creating minimal fallback data - dashboard will have limited functionality")
        df = pd.DataFrame({
            'school_dbn': ['00X000'],
            'school_name': ['Data Loading Error - Check Credentials'],
            'borough': ['UNKNOWN'],
            'district': [0],
            'latitude': [40.7128],
            'longitude': [-74.0060],
            'training_status': ['No Training'],
            'color': ['#B87D7D'],
            'eni_score': [0],
            'sth_pct': [0],
            'superintendent': ['Check GOOGLE_CREDENTIALS_JSON env var'],
        })
        _cached_data = df
        _data_source = "error"
        return df.copy()

    df = pd.read_csv(data_path)

    # Add any missing columns expected by the app
    if 'superintendent' not in df.columns and 'superintendent_name' in df.columns:
        df['superintendent'] = df['superintendent_name']

    _cached_data = df
    _data_source = "mock"
    logger.info(f"Loaded {len(df)} schools from mock CSV")
    return df.copy()


def normalize_live_data_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names from live data to match mock data structure.

    Live data uses:          Mock data uses:
    - superintendent_name    -> superintendent
    - sth_percent (0-1)      -> sth_pct (0-100 scale)
    - economic_need_index    -> eni_score
    - high_sth               -> (computed)
    - high_eni               -> (computed)
    """
    # Rename columns
    column_mapping = {
        'superintendent_name': 'superintendent',
        'economic_need_index': 'eni_score',
    }
    df = df.rename(columns=column_mapping)

    # Convert sth_percent from 0-1 to 0-100 scale (matching mock data)
    if 'sth_percent' in df.columns:
        df['sth_pct'] = df['sth_percent'] * 100  # Convert 0.15 -> 15.0

    # Ensure eni_score is in 0-1 range (live data should already be)
    if 'eni_score' in df.columns:
        if df['eni_score'].max() > 1:
            df['eni_score'] = df['eni_score'] / 100

    return df


def get_data_source() -> str:
    """Return the current data source ('live' or 'mock')."""
    return _data_source or "unknown"


def refresh_data():
    """Force refresh of cached data."""
    global _cached_data, _data_source, _cached_participant_data
    _cached_data = None
    _data_source = None
    _cached_participant_data = None


# Cache for participant data
_cached_participant_data = None


def load_participant_data() -> pd.DataFrame:
    """
    Load participant detail data from Google Sheets.

    Returns DataFrame with:
    - first_name, last_name, role_display
    - school_dbn, training_type, training_date
    - is_priority_role flag for sorting

    Returns empty DataFrame if participant data is not available.
    """
    global _cached_participant_data

    # Return cached data if available
    if _cached_participant_data is not None:
        return _cached_participant_data.copy()

    # Try to load live data
    if LIVE_DATA_AVAILABLE:
        try:
            df = load_participant_data_live()
            logger.info(f"Loaded {len(df)} participant records")
            _cached_participant_data = df
            return df.copy()
        except Exception as e:
            logger.warning(f"Failed to load participant data: {e}")
            # Return empty DataFrame with expected columns
            _cached_participant_data = pd.DataFrame(columns=[
                'first_name', 'last_name', 'role_display', 'is_priority_role',
                'school_dbn', 'training_type', 'training_date'
            ])
            return _cached_participant_data.copy()

    # No live data available - return empty DataFrame
    _cached_participant_data = pd.DataFrame(columns=[
        'first_name', 'last_name', 'role_display', 'is_priority_role',
        'school_dbn', 'training_type', 'training_date'
    ])
    return _cached_participant_data.copy()


def get_stats(df: pd.DataFrame) -> dict:
    """Calculate summary statistics from school data.

    Includes both legacy status counts (for backward compatibility) and
    layer-specific counts for the new three-layer model.
    """
    total = len(df)

    # Entity type counts (schools vs offices)
    if 'is_school' in df.columns:
        school_count = int(df['is_school'].sum())
        office_count = int(df['is_office'].sum()) if 'is_office' in df.columns else 0
    else:
        school_count = total
        office_count = 0

    # Legacy status counts (still used in some places)
    complete = len(df[df['training_status'] == 'Complete'])
    fundamentals = len(df[df['training_status'] == 'Fundamentals Only'])
    no_training = len(df[df['training_status'] == 'No Training'])

    # NEW: Layer-specific counts (for three-layer model)
    has_fund_count = len(df[df.get('has_fundamentals', pd.Series(['No'] * total)) == 'Yes']) if 'has_fundamentals' in df.columns else 0
    has_lights_count = len(df[df.get('has_lights', pd.Series(['No'] * total)) == 'Yes']) if 'has_lights' in df.columns else 0
    has_students_count = 0  # Placeholder - student sessions not yet tracked

    # Trained count: schools with ANY training (Fundamentals OR LIGHTS)
    # Note: These overlap, so we use OR logic to avoid double-counting
    has_any_training = pd.Series([False] * len(df), index=df.index)
    if 'has_fundamentals' in df.columns:
        has_any_training |= (df['has_fundamentals'] == 'Yes')
    if 'has_lights' in df.columns:
        has_any_training |= (df['has_lights'] == 'Yes')
    trained_count = int(has_any_training.sum())

    # Training gap metrics for comprehensive overview
    # Schools that need LIGHTS: have Fundamentals but NOT LIGHTS
    need_lights_count = 0
    if 'has_fundamentals' in df.columns and 'has_lights' in df.columns:
        need_lights_mask = (df['has_fundamentals'] == 'Yes') & (df['has_lights'] != 'Yes')
        need_lights_count = int(need_lights_mask.sum())

    # Schools with LIGHTS awaiting student sessions (all LIGHTS schools until tracking implemented)
    # This shows schools with LIGHTS trainers who could be delivering sessions
    awaiting_sessions_count = has_lights_count  # Currently all LIGHTS schools

    # New metrics using ENI/STH columns
    # STH ≥15% puts school in top ~30% for housing instability
    # ENI ≥74% is DOE's own "skewed toward lower incomes" cutoff
    high_eni_threshold = 0.74  # ENI ≥ 74%
    high_sth_threshold = 15.0  # STH ≥ 15%

    # Count schools with high ENI
    high_eni = len(df[df['eni_score'] >= high_eni_threshold]) if 'eni_score' in df.columns else 0

    # Count schools with high STH
    high_sth = len(df[df['sth_pct'] >= high_sth_threshold]) if 'sth_pct' in df.columns else 0

    # High-need unique count (schools with high ENI OR high STH, no double-counting)
    high_need_mask = pd.Series([False] * len(df), index=df.index)
    if 'eni_score' in df.columns:
        high_need_mask |= (df['eni_score'] >= high_eni_threshold)
    if 'sth_pct' in df.columns:
        high_need_mask |= (df['sth_pct'] >= high_sth_threshold)
    high_need_unique = int(high_need_mask.sum())

    # Priority schools: no training AND high need (ENI or STH)
    priority = len(df[high_need_mask & (df['training_status'] == 'No Training')])

    # Average ENI and STH across filtered schools
    avg_eni = round(df['eni_score'].mean() * 100, 1) if 'eni_score' in df.columns and total > 0 else 0
    avg_sth = round(df['sth_pct'].mean(), 1) if 'sth_pct' in df.columns and total > 0 else 0

    return {
        'total': total,
        # Entity type counts
        'school_count': school_count,
        'office_count': office_count,
        # Legacy status counts (backward compatibility)
        'complete': complete,
        'fundamentals': fundamentals,
        'no_training': no_training,
        'complete_pct': round(complete / total * 100, 1) if total > 0 else 0,
        'fund_pct': round(fundamentals / total * 100, 1) if total > 0 else 0,
        'none_pct': round(no_training / total * 100, 1) if total > 0 else 0,
        # NEW: Layer-specific coverage counts (three-layer model)
        'has_fund_count': has_fund_count,
        'has_lights_count': has_lights_count,
        'has_students_count': has_students_count,
        'has_fund_pct': round(has_fund_count / total * 100, 1) if total > 0 else 0,
        'has_lights_pct': round(has_lights_count / total * 100, 1) if total > 0 else 0,
        'has_students_pct': round(has_students_count / total * 100, 1) if total > 0 else 0,
        # Aggregate trained count (schools with ANY training)
        'trained_count': trained_count,
        'trained_pct': round(trained_count / total * 100, 1) if total > 0 else 0,
        # Training gap metrics (for comprehensive overview)
        'need_lights_count': need_lights_count,  # Have Fundamentals but not LIGHTS
        'awaiting_sessions_count': awaiting_sessions_count,  # Have LIGHTS, awaiting student sessions
        # Vulnerability metrics
        'priority': priority,
        'high_eni': high_eni,
        'high_sth': high_sth,
        'high_need_unique': high_need_unique,  # Schools with high ENI OR high STH (no double-count)
        'avg_eni': avg_eni,
        'avg_sth': avg_sth,
    }


# ============================================================================
# MULTI-LAYER MARKER PROPERTIES
# ============================================================================

def compute_marker_properties(
    row: pd.Series,
    fundamentals_enabled: bool,
    lights_enabled: bool,
    sth_highlight: bool,
    eni_highlight: bool,
    show_gaps: bool = False,
) -> dict:
    """
    Compute marker visual properties based on layer toggles, highlight state, and gaps mode.

    Priority: LIGHTS (purple) > Fundamentals (blue)
    When highlights are active, they override the base layer colors.

    GAPS MODE (show_gaps=True):
    - Schools WITH training: solid dots but faded (50% opacity)
    - Schools WITHOUT training: hollow circles (stroke only), larger radius, same color family

    Returns:
        dict with: fill_color, border_color, radius, fill_opacity, visible
    """
    # Get training info from row
    has_fund = row.get('has_fundamentals', 'No') == 'Yes'
    has_lights = row.get('has_lights', 'No') == 'Yes'
    fund_count = pd.to_numeric(row.get('fundamentals_participants', 0), errors='coerce') or 0
    lights_count = pd.to_numeric(row.get('lights_participants', 0), errors='coerce') or 0

    # ==========================================================================
    # TRAINING HIERARCHY ANOMALY DETECTION
    # ==========================================================================
    # Training should follow: Fundamentals → LIGHTS → Student Sessions
    # Flag schools with training "out of order" as anomalies
    is_anomaly = False
    if has_lights and not has_fund:
        # Has LIGHTS but no Fundamentals - this shouldn't happen
        is_anomaly = True

    # Define layer colors
    layer_colors = {
        'fundamentals': '#4183C4',  # Blue
        'lights': '#9C66B2',        # Purple
        'anomaly': '#E67E22',       # Orange/Amber for warnings
    }

    # Determine if school matches any enabled layer (has training for that layer)
    matches_enabled_layer = False
    layer_type = None
    participant_count = 0

    # Priority: LIGHTS > Fundamentals (for schools that have both)
    if lights_enabled and has_lights:
        matches_enabled_layer = True
        layer_type = 'lights'
        participant_count = lights_count
    elif fundamentals_enabled and has_fund:
        matches_enabled_layer = True
        layer_type = 'fundamentals'
        participant_count = fund_count

    # ==========================================================================
    # GAPS MODE: Determine what gaps to show
    # ==========================================================================
    # When both layers enabled, show PARTIAL gaps (missing ANY layer, not just ALL)
    is_gap = False
    gap_layer_type = None

    if show_gaps:
        both_layers_enabled = fundamentals_enabled and lights_enabled

        if both_layers_enabled:
            # PARTIAL GAPS: Show gaps for EACH missing layer
            # Priority: Show Fundamentals gap first (it's the prerequisite)
            if not has_fund:
                is_gap = True
                gap_layer_type = 'fundamentals'  # Blue = needs Fundamentals
            elif not has_lights:
                is_gap = True
                gap_layer_type = 'lights'  # Purple = needs LIGHTS
        else:
            # Single layer: show gap if missing that specific layer
            if fundamentals_enabled and not has_fund:
                is_gap = True
                gap_layer_type = 'fundamentals'
            elif lights_enabled and not has_lights:
                is_gap = True
                gap_layer_type = 'lights'

    # ==========================================================================
    # RENDER: Anomaly (has LIGHTS but no Fund) - always show with warning
    # ==========================================================================
    if is_anomaly and fundamentals_enabled:
        # Show as orange/amber warning - this school needs Fundamentals follow-up
        return {
            'fill_color': layer_colors['anomaly'],
            'border_color': '#C0392B',    # Darker orange-red border
            'radius': 7,
            'fill_opacity': 0.7,
            'weight': 2,
            'visible': True,
        }

    # ==========================================================================
    # RENDER: Gaps as hollow circles
    # ==========================================================================
    if show_gaps and is_gap:
        gap_color = layer_colors.get(gap_layer_type, '#4183C4')
        return {
            'fill_color': 'transparent',
            'border_color': gap_color,
            'radius': 8,
            'fill_opacity': 0,
            'weight': 3,  # Slightly thicker for better visibility
            'visible': True,
        }

    # ==========================================================================
    # School has training (or gaps mode is off)
    # ==========================================================================
    if not matches_enabled_layer:
        # No layers enabled or school doesn't match any enabled layer
        return {
            'fill_color': '#cccccc',
            'border_color': '#999999',
            'radius': 4,
            'fill_opacity': 0.1,
            'visible': fundamentals_enabled or lights_enabled,
        }

    # Calculate base color and radius from layer type and participant count
    if LIVE_DATA_AVAILABLE:
        base_color = get_layer_color_hex(layer_type, int(participant_count))
        base_radius = calculate_dot_radius(int(participant_count))
    else:
        base_color = layer_colors.get(layer_type, '#4183C4')
        base_radius = 6

    # Check if highlights are active
    highlight_active = sth_highlight or eni_highlight

    # ==========================================================================
    # GAPS MODE: Make trained schools very subtle so gaps pop out
    # ==========================================================================
    if show_gaps and not highlight_active:
        # Trained schools become subtle gray "ghosts"
        return {
            'fill_color': '#b0b0b0',
            'border_color': '#b0b0b0',
            'radius': max(4, base_radius - 1),
            'fill_opacity': 0.15,        # Even more faded (15%)
            'weight': 0,
            'visible': True,
        }

    if not highlight_active:
        # Normal mode (no highlights, no gaps) - use layer colors at full opacity
        return {
            'fill_color': base_color,
            'border_color': base_color,
            'radius': base_radius,
            'fill_opacity': 0.8,
            'visible': True,
        }

    # ==========================================================================
    # HIGHLIGHT MODE: STH/ENI takes precedence
    # ==========================================================================
    sth_val = row.get('sth_pct', 0) or 0
    eni_val = row.get('eni_score', 0) or 0

    # Convert sth_pct from 0-100 to 0-1 scale if needed
    if sth_val > 1:
        sth_val = sth_val / 100

    matches_sth = sth_highlight and sth_val >= HIGH_STH_THRESHOLD
    matches_eni = eni_highlight and eni_val >= HIGH_ENI_THRESHOLD
    matches_highlight = matches_sth or matches_eni

    if matches_highlight:
        # School matches highlight criteria - bright coral or cyan fill
        if matches_sth:
            highlight_color = '#ff6464'  # Coral for STH
            border_color = '#ff4444'
        else:
            highlight_color = '#00dcdc'  # Cyan for ENI
            border_color = '#00b8b8'

        return {
            'fill_color': highlight_color,
            'border_color': border_color,
            'radius': int(base_radius * 1.5),  # Enlarge highlighted schools
            'fill_opacity': 0.9,
            'visible': True,
        }
    else:
        # School doesn't match highlight - strong fade
        return {
            'fill_color': '#cccccc',
            'border_color': '#999999',
            'radius': int(base_radius * 0.6),  # Shrink non-matching
            'fill_opacity': 0.15,
            'visible': True,
        }


# ============================================================================
# FLOATING LAYER CONTROL WIDGET
# ============================================================================

def create_layer_control_widget(
    fundamentals_enabled: bool,
    lights_enabled: bool,
    sth_highlight: bool,
    eni_highlight: bool,
    on_fund_change: callable,
    on_lights_change: callable,
    on_sth_change: callable,
    on_eni_change: callable,
):
    """
    Create the floating layer control panel for the map.

    Contains checkboxes for:
    - Training layers (Fundamentals, LIGHTS)
    - Indicator highlights (STH, ENI)
    """
    # Header
    header = HTMLWidget(value='''
        <div style="font-size: 11px; font-weight: 600; color: #6b7280;
                    padding: 6px 10px 4px 10px; border-bottom: 1px solid #e5e7eb;
                    background: #f9fafb; border-radius: 8px 8px 0 0;">
            Layers
        </div>
    ''')

    # Training layer checkboxes
    fund_checkbox = Checkbox(
        value=fundamentals_enabled,
        description='🔵 Fundamentals',
        indent=False,
        layout=Layout(width='auto', margin='2px 8px'),
    )
    fund_checkbox.observe(lambda change: on_fund_change(change['new']), names='value')

    lights_checkbox = Checkbox(
        value=lights_enabled,
        description='🟣 LIGHTS',
        indent=False,
        layout=Layout(width='auto', margin='2px 8px'),
    )
    lights_checkbox.observe(lambda change: on_lights_change(change['new']), names='value')

    # Divider
    divider = HTMLWidget(value='''
        <div style="height: 1px; background: #e5e7eb; margin: 4px 8px;"></div>
    ''')

    # Highlight label
    highlight_label = HTMLWidget(value='''
        <div style="font-size: 10px; font-weight: 500; color: #9ca3af;
                    padding: 2px 10px; text-transform: uppercase; letter-spacing: 0.5px;">
            Highlights
        </div>
    ''')

    # Indicator highlight checkboxes
    sth_checkbox = Checkbox(
        value=sth_highlight,
        description='🔴 STH ≥15%',
        indent=False,
        layout=Layout(width='auto', margin='2px 8px'),
    )
    sth_checkbox.observe(lambda change: on_sth_change(change['new']), names='value')

    eni_checkbox = Checkbox(
        value=eni_highlight,
        description='🔵 ENI ≥74%',
        indent=False,
        layout=Layout(width='auto', margin='2px 8px'),
    )
    eni_checkbox.observe(lambda change: on_eni_change(change['new']), names='value')

    # Container with styling
    container = VBox(
        [header, fund_checkbox, lights_checkbox, divider, highlight_label, sth_checkbox, eni_checkbox],
        layout=Layout(
            width='145px',
            border='1px solid #e5e7eb',
            border_radius='8px',
            background_color='white',
            overflow='hidden',
        )
    )

    return container


# ============================================================================
# DISTRICT CHOROPLETH FUNCTIONS
# ============================================================================

def load_district_geojson() -> dict:
    """Load NYC School Districts GeoJSON boundaries."""
    geo_path = Path(__file__).parent / 'data' / 'geo' / 'nyc_school_districts.geojson'
    if not geo_path.exists():
        return None
    with open(geo_path, 'r') as f:
        return json.load(f)


def aggregate_by_district(df: pd.DataFrame, training_type: str = 'any') -> pd.DataFrame:
    """
    Aggregate school training data by district for choropleth visualization.

    Args:
        df: DataFrame with school data including has_fundamentals, has_lights columns
        training_type: One of 'any', 'fundamentals', 'lights'
            - 'any': Schools with either training type (default behavior)
            - 'fundamentals': Only schools with Fundamentals training
            - 'lights': Only schools with LIGHTS training

    Returns:
        DataFrame with district-level statistics including coverage_pct
    """
    if 'district' not in df.columns or len(df) == 0:
        return pd.DataFrame()

    # Ensure required columns exist with defaults
    df_copy = df.copy()
    if 'has_fundamentals' not in df_copy.columns:
        df_copy['has_fundamentals'] = 'No'
    if 'has_lights' not in df_copy.columns:
        df_copy['has_lights'] = 'No'

    # Group by district to get total schools per district
    district_stats = df_copy.groupby('district').agg(
        total_schools=('school_dbn', 'count'),
    ).reset_index()

    # Calculate training-specific counts per district
    if training_type == 'fundamentals':
        trained_counts = df_copy[df_copy['has_fundamentals'] == 'Yes'].groupby('district').size()
    elif training_type == 'lights':
        trained_counts = df_copy[df_copy['has_lights'] == 'Yes'].groupby('district').size()
    else:  # 'any' - original behavior (schools with ANY training)
        trained_counts = df_copy[
            (df_copy['has_fundamentals'] == 'Yes') | (df_copy['has_lights'] == 'Yes')
        ].groupby('district').size()

    # Merge trained counts back to district stats
    district_stats['schools_with_training'] = district_stats['district'].map(trained_counts).fillna(0).astype(int)

    # Calculate coverage percentage
    district_stats['coverage_pct'] = (
        district_stats['schools_with_training'] / district_stats['total_schools'] * 100
    ).round(1)

    return district_stats


def get_choropleth_color(coverage_pct: float) -> str:
    """
    Get hex color for choropleth based on coverage percentage.

    Uses a blue gradient from light (low coverage) to dark (high coverage).
    Returns CSS-compatible hex color string.
    """
    if coverage_pct < 20:
        return '#DCE6F0'  # Very light blue
    elif coverage_pct < 40:
        return '#93BAE1'  # Light blue
    elif coverage_pct < 60:
        return '#4183C4'  # Medium blue
    elif coverage_pct < 80:
        return '#2D64A0'  # Dark blue
    else:
        return '#1F5284'  # Very dark blue


def prepare_choropleth_geojson(df: pd.DataFrame, geojson: dict) -> dict:
    """
    Prepare GeoJSON with embedded district statistics for choropleth rendering.

    Merges school aggregation data into GeoJSON properties for each district.
    """
    if geojson is None:
        return None

    # Aggregate school data by district
    district_stats = aggregate_by_district(df)

    # Create lookup dict (district number -> stats)
    stats_lookup = {}
    for _, row in district_stats.iterrows():
        stats_lookup[int(row['district'])] = {
            'total_schools': int(row['total_schools']),
            'schools_with_training': int(row['schools_with_training']),
            'coverage_pct': float(row['coverage_pct']),
            'complete': int(row['complete']),
            'no_training': int(row['no_training']),
        }

    # Enhance GeoJSON features with stats
    enhanced_features = []
    for feature in geojson['features']:
        # Get district number from properties
        district_num = feature['properties'].get('SchoolDist')
        if district_num is not None:
            try:
                district_num = int(district_num)
            except (ValueError, TypeError):
                district_num = None

        # Get stats for this district (default to zeros if not in data)
        stats = stats_lookup.get(district_num, {
            'total_schools': 0,
            'schools_with_training': 0,
            'coverage_pct': 0,
            'complete': 0,
            'no_training': 0,
        })

        # Calculate fill color based on coverage
        fill_color = get_choropleth_color(stats['coverage_pct'])

        # Create enhanced feature with stats in properties
        enhanced_feature = {
            'type': 'Feature',
            'geometry': feature['geometry'],
            'properties': {
                **feature['properties'],
                'district': district_num,
                **stats,
                'fill_color': fill_color,
            }
        }
        enhanced_features.append(enhanced_feature)

    return {
        'type': 'FeatureCollection',
        'features': enhanced_features
    }


# ============================================================================
# GLOBAL STYLES
# ============================================================================

GLOBAL_CSS = """
<style>
    /* ===== MOBILE-FIRST BASE STYLES ===== */
    html, body {
        margin: 0;
        padding: 0;
        height: 100%;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .solara-content {
        padding: 0 !important;
    }
    .v-application--wrap {
        min-height: 100vh !important;
        /* Modern viewport units for mobile Safari address bar */
        min-height: 100dvh !important;
    }

    /* ===== MAIN APP CONTAINER - MOBILE FIX ===== */
    /* Ensure the main Column container respects flexbox */
    .v-application .container {
        max-width: 100% !important;
        padding: 0 !important;
    }

    /* Target Solara's main content Column */
    .solara-content > div > div {
        display: flex !important;
        flex-direction: column !important;
    }

    /* Mobile: Ensure proper stacking context */
    @media (max-width: 768px) {
        /* Main app container height fix for mobile */
        .v-application--wrap {
            height: 100vh !important;
            height: 100dvh !important;  /* Dynamic viewport height */
            min-height: -webkit-fill-available !important;  /* iOS Safari fallback */
        }

        html {
            height: -webkit-fill-available;
        }
    }
    /* Override Vuetify defaults */
    .v-btn {
        text-transform: none !important;
        letter-spacing: normal !important;
    }
    /* CRITICAL: Fix dropdown z-index - must be above map */
    .v-menu__content {
        z-index: 9999 !important;
    }
    .v-overlay {
        z-index: 9998 !important;
    }

    /* ===== TOOLBAR CONTAINER - CRITICAL FOR MOBILE ===== */
    /* Prevent toolbar from collapsing in flex container */
    .toolbar-filters {
        flex-shrink: 0 !important;
        flex-grow: 0 !important;
        min-height: 52px !important;
        background: #ffffff !important;
        position: relative !important;
        z-index: 100 !important;  /* Above normal content, below overlays */
    }

    /* ===== TOOLBAR ROW LAYOUT ===== */
    /* Override Solara's default Row gap within toolbar */
    .toolbar-filters > .solara-row,
    .toolbar-filters .solara-row {
        gap: 6px !important;
    }
    /* Ensure all children are vertically centered */
    .toolbar-filters .solara-row > * {
        display: flex !important;
        align-items: center !important;
    }

    /* ===== TOOLBAR DROPDOWN STYLING ===== */
    /* Container - remove all margins */
    .toolbar-filters .v-input {
        margin: 0 !important;
        padding: 0 !important;
        max-height: 32px !important;
        flex-shrink: 0 !important;
    }
    /* Inner control wrapper */
    .toolbar-filters .v-input__control {
        min-height: 30px !important;
        max-height: 30px !important;
    }
    /* The actual input slot (visual box) */
    .toolbar-filters .v-input__slot {
        min-height: 30px !important;
        max-height: 30px !important;
        height: 30px !important;
        background: #f8f9fa !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 6px !important;
        padding: 0 4px 0 10px !important;
        margin: 0 !important;
        box-shadow: none !important;
    }
    .toolbar-filters .v-input__slot:hover {
        background: #f0f2f6 !important;
        border-color: #d1d5db !important;
    }
    /* Selected text styling - ensure it fits in box */
    .toolbar-filters .v-select__selection {
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #374151 !important;
        line-height: 28px !important;
        max-width: calc(100% - 24px) !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }
    /* Fix Vuetify select selections container */
    .toolbar-filters .v-select__selections {
        flex-wrap: nowrap !important;
        overflow: hidden !important;
        padding: 0 !important;
        line-height: 28px !important;
    }
    /* Hide the details/messages section */
    .toolbar-filters .v-text-field__details {
        display: none !important;
    }
    /* Dropdown arrow positioning */
    .toolbar-filters .v-input__append-inner {
        margin: 0 !important;
        padding: 0 2px !important;
        align-self: center !important;
    }
    .toolbar-filters .v-input__icon {
        min-width: 18px !important;
        width: 18px !important;
        height: 28px !important;
    }
    .toolbar-filters .v-input__icon .v-icon {
        font-size: 16px !important;
        color: #9ca3af !important;
    }

    /* ===== TOOLBAR BUTTON STYLING ===== */
    .toolbar-filters .v-btn {
        height: 30px !important;
        min-height: 30px !important;
        max-height: 30px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        vertical-align: middle !important;
        flex-shrink: 0 !important;
        box-shadow: none !important;
    }
    .toolbar-filters .v-btn:hover {
        opacity: 0.9 !important;
    }

    /* ===== SIDEBAR MODE SELECTOR (Sprint 6) ===== */
    /* Make the View Mode dropdown more compact */
    .mode-selector-container .v-input {
        margin: 0 !important;
        padding: 0 !important;
    }
    .mode-selector-container .v-input__control {
        min-height: 36px !important;
        max-height: 36px !important;
    }
    .mode-selector-container .v-input__slot {
        min-height: 34px !important;
        max-height: 34px !important;
        padding: 0 10px !important;
        background: white !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 6px !important;
        box-shadow: none !important;
    }
    .mode-selector-container .v-select__selection {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #374151 !important;
    }
    .mode-selector-container .v-text-field__details {
        display: none !important;
    }

    /* ===== SEARCH INPUT IN TOOLBAR ===== */
    .toolbar-filters .solara-input-text .v-input__slot {
        min-height: 28px !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    .toolbar-filters .solara-input-text .v-text-field__details {
        display: none !important;
    }
    .toolbar-filters .solara-input-text input {
        font-size: 13px !important;
        padding: 4px 0 !important;
    }

    /* ===== RESPONSIVE BREAKPOINTS ===== */
    /*
     * CRITICAL: Solara/Vuetify inject their own flex styles.
     * We use ultra-high specificity selectors to override them.
     * Pattern: html body .v-application [class]
     */

    /* ===== DESKTOP (>1200px) - Explicit media query ===== */
    @media (min-width: 1201px) {
        /* Toolbar row: horizontal layout - HIGH SPECIFICITY */
        html body .v-application .toolbar-row,
        html body .v-application .toolbar-row.row,
        html body .v-application .toolbar-row.v-col,
        html body .v-application div.toolbar-row {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 8px !important;
        }

        /* Desktop: Indicators section visible */
        html body .v-application .toolbar-indicators-section,
        .toolbar-indicators-section {
            display: flex !important;
        }

        /* Desktop: Hide overflow-only items */
        html body .v-application .overflow-show-at-1100,
        html body .v-application .overflow-show-at-900,
        html body .v-application .overflow-show-at-600,
        html body .v-application .overflow-show-supt,
        html body .v-application .overflow-mobile-only,
        .overflow-show-at-1100,
        .overflow-show-at-900,
        .overflow-show-at-600,
        .overflow-show-supt,
        .overflow-mobile-only {
            display: none !important;
        }

        /* Desktop: overflow menu hidden */
        html body .v-application .overflow-menu-container,
        .overflow-menu-container {
            display: none !important;
        }

        /* Desktop: sidebar toggle (hamburger) hidden */
        html body .v-application .sidebar-toggle-btn,
        .sidebar-toggle-btn {
            display: none !important;
        }

        /* Desktop: header spacer hidden (not needed when in row mode) */
        html body .v-application .header-spacer,
        .header-spacer {
            display: none !important;
        }

        /* Desktop: Show all toolbar sections inline */
        html body .v-application .toolbar-header-section,
        html body .v-application .toolbar-filters-section,
        html body .v-application .toolbar-toggles-section {
            display: flex !important;
            flex-direction: row !important;
            flex-shrink: 0 !important;
        }

        /* Desktop: desktop-only elements visible */
        html body .v-application .desktop-only,
        .desktop-only {
            display: inline-flex !important;
        }
    }

    /* ===== TABLET/MOBILE (≤1200px) ===== */
    @media (max-width: 1200px) {
        /* Show overflow menu - HIGH SPECIFICITY */
        html body .v-application .overflow-menu-container,
        .overflow-menu-container {
            display: flex !important;
            z-index: 10000 !important;
            position: relative !important;
        }

        /* Show hamburger for sidebar toggle */
        html body .v-application .sidebar-toggle-btn,
        .sidebar-toggle-btn {
            display: inline-flex !important;
        }

        /* Show header spacer - pushes overflow to right */
        html body .v-application .header-spacer,
        .header-spacer {
            display: block !important;
            flex: 1 1 auto !important;
        }

        /* Hide desktop-only indicators - HIGH SPECIFICITY */
        html body .v-application .toolbar-indicators-section,
        .toolbar-indicators-section {
            display: none !important;
        }
        html body .v-application .desktop-only,
        .desktop-only {
            display: none !important;
        }

        /* Show items in overflow menu */
        html body .v-application .overflow-show-at-1100,
        html body .v-application .overflow-mobile-only,
        .overflow-show-at-1100,
        .overflow-mobile-only {
            display: block !important;
        }

        /* Toolbar: switch to column (stacked) layout - HIGH SPECIFICITY */
        html body .v-application .toolbar-row,
        html body .v-application .toolbar-row.row,
        html body .v-application .toolbar-row.v-col,
        html body .v-application div.toolbar-row {
            display: flex !important;
            flex-direction: column !important;
            height: auto !important;
            min-height: auto !important;
            padding: 8px 12px !important;
            gap: 8px !important;
            z-index: 1100 !important;
            position: relative !important;
        }

        /* Header section: row layout (hamburger + search + title + overflow) */
        html body .v-application .toolbar-header-section,
        .toolbar-header-section {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 8px !important;
            width: 100% !important;
        }

        /* Filter dropdowns: full width, stretch evenly */
        html body .v-application .toolbar-filters-section,
        .toolbar-filters-section {
            width: 100% !important;
            display: flex !important;
            flex-direction: row !important;
            gap: 8px !important;
        }
        .toolbar-filters-section .v-input,
        .toolbar-filters-section .solara-select,
        .toolbar-filters-section > div {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            max-width: none !important;
        }

        /* Toggle buttons: full width, evenly distributed */
        html body .v-application .toolbar-toggles-section,
        .toolbar-toggles-section {
            width: 100% !important;
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 6px !important;
        }
        .toolbar-toggles-section .v-btn,
        .toolbar-toggles-section > div {
            flex: 1 1 0 !important;
            min-width: 0 !important;
        }

        /* Hide desktop-only spacers and dividers */
        html body .v-application .toolbar-spacer,
        html body .v-application .toolbar-divider-desktop,
        .toolbar-spacer,
        .toolbar-divider-desktop {
            display: none !important;
        }

        /* Overflow dropdown z-index */
        .overflow-dropdown {
            z-index: 10001 !important;
        }
    }

    /* ----- NARROW TABLET (1000px): Superintendent dropdown stays visible ----- */
    /* Removed: supt-dropdown hiding - user wants it visible at all breakpoints */

    /* ----- SIDEBAR WIDTH ----- */
    /* Full sidebar on wide screens */
    .info-panel-container {
        width: 360px;
        min-width: 360px;
        max-width: 360px;
        transition: width 0.2s ease, min-width 0.2s ease, max-width 0.2s ease, margin-left 0.2s ease;
    }

    /* Narrower sidebar on medium screens */
    @media (max-width: 1100px) {
        .info-panel-container {
            width: 300px;
            min-width: 300px;
            max-width: 300px;
        }
    }

    /* Even narrower */
    @media (max-width: 950px) {
        .info-panel-container {
            width: 280px;
            min-width: 280px;
            max-width: 280px;
        }
    }

    /* ----- MOBILE (768px): Sidebar overlays map ----- */
    @media (max-width: 768px) {
        /* Main container: fixed to viewport */
        .main-app-container {
            height: 100vh !important;
            height: 100dvh !important;
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
        }

        /* Toolbar: takes natural height */
        .toolbar-filters {
            flex-shrink: 0 !important;
            flex-grow: 0 !important;
            z-index: 1100 !important;
            background: #ffffff !important;
        }

        /* Content row: fills remaining space */
        .content-row {
            flex: 1 !important;
            min-height: 0 !important;
            overflow: hidden !important;
        }

        /* Sidebar: overlays on mobile */
        .info-panel-container {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            z-index: 1200 !important;
            height: 100% !important;
            width: 320px !important;
            min-width: 320px !important;
            max-width: 320px !important;
            box-shadow: 4px 0 12px rgba(0,0,0,0.15) !important;
            flex-shrink: 0 !important;
        }

        .info-panel-container.sidebar-closed {
            transform: translateX(-100%) !important;
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            overflow: hidden !important;
            box-shadow: none !important;
        }

        /* Ensure toolbar items can shrink but fill available space */
        .toolbar-filters .v-input {
            flex-shrink: 1 !important;
            flex-grow: 1 !important;
            min-width: 0 !important;
        }

        /* Hide legend on mobile - takes too much screen space */
        .leaflet-top.leaflet-right {
            display: none !important;
        }

        /* Ensure overflow menu is always visible on mobile - HIGH SPECIFICITY */
        html body .v-application .overflow-menu-container,
        .overflow-menu-container {
            display: flex !important;
        }

        /* Ensure indicators section stays hidden at mobile */
        html body .v-application .toolbar-indicators-section,
        .toolbar-indicators-section {
            display: none !important;
        }

        /* AGGRESSIVE viewport lock - prevent ALL scrolling on mobile */
        html, body {
            overflow: hidden !important;
            position: fixed !important;
            width: 100% !important;
            height: 100% !important;
            top: 0 !important;
            left: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* Lock Vuetify/Solara containers too */
        .v-application,
        .v-application--wrap,
        .solara-container,
        #app {
            overflow: hidden !important;
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            max-height: 100vh !important;
            max-height: 100dvh !important;
        }

        /* Main app container - absolutely fixed */
        .main-app-container {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            width: 100% !important;
            height: 100vh !important;
            height: 100dvh !important;
            overflow: hidden !important;
        }

        /* Prevent any element from triggering scroll-into-view */
        * {
            scroll-margin: 0 !important;
            scroll-padding: 0 !important;
        }

        /* CRITICAL: Allow scrolling INSIDE sidebar content area */
        .sidebar-scrollable {
            overflow-y: auto !important;
            overflow-x: hidden !important;
            -webkit-overflow-scrolling: touch !important;
            overscroll-behavior: contain !important;
            touch-action: pan-y !important;
        }

        /* Also ensure info-panel can contain scrollable content */
        .info-panel-container {
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
        }
    }

    /* Phone: Bottom sheet pattern for sidebar */
    @media (max-width: 600px) {
        /* REMOVED: Grid layout for toolbar-toggles-section was collapsing filters to left */
        /* JavaScript now handles all toolbar responsive layout */

        /* Override sidebar to be bottom sheet */
        .info-panel-container {
            /* Position at bottom instead of left */
            top: auto !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            /* Full width, taller height (70% of screen) to account for browser chrome */
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            /* Use dvh (dynamic viewport height) for browsers that support it, fallback to vh */
            height: 70vh !important;
            height: 70dvh !important;  /* Overrides previous line in supporting browsers */
            /* Visual styling */
            border-radius: 16px 16px 0 0 !important;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.15) !important;
            /* Slide up/down instead of left/right */
            transform: translateY(0) !important;
            transition: transform 0.3s ease, opacity 0.3s ease !important;
            /* CRITICAL: Allow touch events to reach scrollable children */
            touch-action: auto !important;
            pointer-events: auto !important;
        }

        .info-panel-container.sidebar-closed {
            transform: translateY(100%) !important;
            /* Reset width overrides from tablet breakpoint */
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            height: 70vh !important;
            height: 70dvh !important;
        }

        /* Bottom sheet drag handle - Solara Button styled as handle bar */
        .bottom-sheet-handle {
            display: flex !important;
            justify-content: center;
            align-items: center;
            min-height: 28px !important;
            height: 28px !important;
            width: 100% !important;
            background: transparent !important;
            box-shadow: none !important;
            border: none !important;
            flex-shrink: 0;
            position: relative;
        }

        /* Override Vuetify button ripple and focus styles */
        .bottom-sheet-handle.v-btn::before,
        .bottom-sheet-handle .v-btn__overlay {
            display: none !important;
        }

        /* Visual pill indicator using ::after */
        .bottom-sheet-handle::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 40px;
            height: 4px;
            background: #9ca3af;
            border-radius: 2px;
        }

        /* Hover feedback */
        .bottom-sheet-handle:hover::after {
            background: #6b7280;
        }

        .bottom-sheet-handle:active::after {
            background: #4b5563;
        }

        /* CRITICAL: Phone-specific scrollable content within bottom sheet */
        .sidebar-scrollable {
            flex: 1 1 0 !important;
            min-height: 0 !important;
            /* Explicit max-height: bottom sheet (70vh) minus handle (28px) minus mode selector (~80px) minus stats (~60px) */
            max-height: calc(70vh - 170px) !important;
            max-height: calc(70dvh - 170px) !important;  /* Dynamic viewport fallback */
            height: auto !important;
            overflow-y: scroll !important;  /* 'scroll' forces scrollbar, more reliable than 'auto' on iOS */
            overflow-x: hidden !important;
            -webkit-overflow-scrolling: touch !important;
            overscroll-behavior-y: contain !important;
            touch-action: pan-y !important;
            /* Ensure this element receives touch events */
            pointer-events: auto !important;
        }

        /* Ensure content inside scrollable area doesn't block touch */
        .sidebar-scrollable > * {
            pointer-events: auto !important;
        }

        /* CRITICAL: School detail sidebar - make ENTIRE content scrollable on mobile */
        .school-sidebar-container {
            height: 100% !important;  /* Fill parent (70vh bottom sheet) instead of 100vh */
            max-height: calc(70vh - 28px) !important;  /* Bottom sheet minus drag handle */
            max-height: calc(70dvh - 28px) !important;  /* Dynamic viewport fallback */
            overflow-y: scroll !important;  /* Make the whole thing scrollable */
            overflow-x: hidden !important;
            -webkit-overflow-scrolling: touch !important;
            overscroll-behavior-y: contain !important;
            touch-action: pan-y !important;
            display: block !important;  /* Change from flex to block for natural flow */
        }

        /* First child (header with back button) - sticky at top */
        .school-sidebar-container > div:first-child {
            position: sticky !important;
            top: 0 !important;
            z-index: 10 !important;
            background: white !important;
        }

        /* Tab content area - no longer needs its own scroll, parent scrolls */
        .school-sidebar-tab-content {
            overflow: visible !important;  /* Let parent handle scroll */
            min-height: auto !important;
            flex: none !important;
        }

        /* ===== COMPACT HEADER FOR MOBILE ===== */
        /* Reduce padding in header section */
        .school-sidebar-container > div:first-child {
            padding: 8px 12px !important;  /* Reduced from 12px 16px */
            gap: 4px !important;
        }

        /* Smaller back button */
        .school-sidebar-container > div:first-child > button {
            font-size: 11px !important;
            padding: 2px 6px !important;
            margin-bottom: 4px !important;
        }

        /* Compact school name */
        .school-sidebar-container h2 {
            font-size: 13px !important;  /* Reduced from 15px */
            margin: 0 0 2px 0 !important;
        }

        /* Compact DBN and reduce spacing */
        .school-sidebar-container > div:first-child p {
            font-size: 10px !important;
            margin: 0 0 4px 0 !important;  /* Reduced from 8px */
        }

        /* Compact training status badge */
        .school-sidebar-container > div:first-child > div:last-child {
            padding: 3px 8px !important;
            font-size: 10px !important;
        }

        /* Compact Training Depth section */
        .school-sidebar-container > div:nth-child(2) {
            padding: 8px 12px !important;  /* Reduced from 12px 16px */
            gap: 6px !important;
        }

        /* Compact tab buttons */
        .school-sidebar-container > div:nth-child(3) button {
            padding: 8px 10px !important;  /* Reduced from 10px 14px */
            font-size: 11px !important;
        }

        /* Compact tab content padding */
        .school-sidebar-tab-content {
            padding: 12px !important;  /* Reduced from 16px */
        }
    }

    /* Hide drag handle on tablet/desktop where sidebar is on the side */
    @media (min-width: 601px) {
        .bottom-sheet-handle {
            display: none !important;
        }
    }

    /* ----- OVERFLOW DROPDOWN STYLING ----- */
    .overflow-dropdown .v-input {
        margin: 0 !important;
    }
    .overflow-dropdown .v-input__control {
        min-height: 32px !important;
    }
    .overflow-dropdown .v-input__slot {
        min-height: 30px !important;
        padding: 0 8px !important;
    }

    /* ----- SIDEBAR SCROLLING FIX ----- */
    /* Force proper flex column layout for sidebar panel */
    .info-panel-container {
        display: flex !important;
        flex-direction: column !important;
        overflow: hidden !important;
    }

    /* Scrollable content area within sidebar */
    .sidebar-scrollable {
        flex: 1 1 0 !important;
        min-height: 0 !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }

    /* ===== SCHOOL ROW HOVER STATES ===== */
    /* Target Vuetify buttons in the school list */
    .school-row-button {
        transition: background-color 0.15s ease, box-shadow 0.15s ease !important;
    }
    .school-row-button:hover {
        background-color: #EBF5FF !important;  /* Light blue tint on hover */
        box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.2) !important;
    }
    /* Priority rows (with colored backgrounds) need different hover */
    .school-row-button.priority-critical:hover {
        background-color: #FEE2E2 !important;  /* Deeper red tint */
    }
    .school-row-button.priority-missing:hover {
        background-color: #FEF3C7 !important;  /* Deeper yellow tint */
    }
    .school-row-button.priority-highneed:hover {
        background-color: #FFEDD5 !important;  /* Deeper orange tint */
    }
</style>

<script>
// =====================================================================
// SCROLL PREVENTION FOR MOBILE
// Only reset page scroll after MAP interactions - NOT on sidebar changes
// This allows sidebar content to scroll normally
// =====================================================================
(function() {
    function isPhoneWidth() {
        return window.innerWidth <= 600;
    }

    function resetPageScroll() {
        // Only reset page-level scroll, NOT sidebar scroll
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;

        // Reset app containers but NOT .sidebar-scrollable
        var containers = document.querySelectorAll(
            '.v-application, .v-application--wrap, .solara-container, ' +
            '.main-app-container, #app'
        );
        containers.forEach(function(c) {
            // Skip if this is the sidebar scrollable area
            if (c && !c.classList.contains('sidebar-scrollable')) {
                c.scrollTop = 0;
                c.scrollLeft = 0;
            }
        });
    }

    // === BURST MODE: Run reset rapidly for N frames ===
    function burstReset(durationMs) {
        var endTime = Date.now() + durationMs;
        function frame() {
            resetPageScroll();
            if (Date.now() < endTime) {
                requestAnimationFrame(frame);
            }
        }
        requestAnimationFrame(frame);
    }

    // === Watch for MAP interactions only ===
    function startMapObserver() {
        var mapContainer = document.querySelector('.leaflet-container');
        if (!mapContainer) {
            setTimeout(startMapObserver, 500);
            return;
        }

        // After any touch/click on map, burst reset for 500ms
        mapContainer.addEventListener('touchend', function() {
            if (!isPhoneWidth()) return;
            burstReset(500);
        }, { passive: true });

        mapContainer.addEventListener('click', function() {
            if (!isPhoneWidth()) return;
            burstReset(500);
        }, { passive: true });
    }

    // === Window scroll listener - only catch unwanted page scrolls ===
    window.addEventListener('scroll', function() {
        if (!isPhoneWidth()) return;
        // Only reset if it's actual page scroll (window.scrollY > 0)
        if (window.scrollY > 0 || document.documentElement.scrollTop > 0) {
            resetPageScroll();
        }
    }, { passive: true });

    // Start map observer when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            startMapObserver();
        });
    } else {
        startMapObserver();
    }
})();

// =====================================================================
// RESPONSIVE TOOLBAR LAYOUT
// Overrides Solara's inline flex-direction based on viewport width
// =====================================================================
(function() {
    console.log('[TOOLBAR] Responsive toolbar script loaded');
    var DESKTOP_BREAKPOINT = 1200;

    function applyToolbarLayout() {
        var isDesktop = window.innerWidth > DESKTOP_BREAKPOINT;
        console.log('[TOOLBAR] applyToolbarLayout called, isDesktop=' + isDesktop + ', width=' + window.innerWidth);

        // Main toolbar container
        var toolbarRow = document.querySelector('.toolbar-row');
        console.log('[TOOLBAR] toolbarRow found:', toolbarRow ? 'YES' : 'NO');
        if (toolbarRow) {
            if (isDesktop) {
                // Desktop: horizontal row layout
                toolbarRow.style.flexDirection = 'row';
                toolbarRow.style.flexWrap = 'nowrap';
                toolbarRow.style.alignItems = 'center';
                toolbarRow.style.gap = '8px';
                toolbarRow.style.padding = '0 16px';
                toolbarRow.style.justifyContent = 'flex-start';
            } else {
                // Mobile/Tablet: vertical column layout
                toolbarRow.style.flexDirection = 'column';
                toolbarRow.style.flexWrap = 'nowrap';
                toolbarRow.style.alignItems = 'stretch';
                toolbarRow.style.gap = '8px';
                toolbarRow.style.padding = '8px 12px';
                toolbarRow.style.justifyContent = 'flex-start';
            }
        }

        // Header section - always visible, row layout
        var headerSection = document.querySelector('.toolbar-header-section');
        if (headerSection) {
            headerSection.style.display = 'flex';
            headerSection.style.flexDirection = 'row';
            headerSection.style.alignItems = 'center';
            headerSection.style.flexShrink = '0';
            if (isDesktop) {
                headerSection.style.width = 'auto';
            } else {
                headerSection.style.width = '100%';
            }
        }

        // Hamburger menu (sidebar toggle) - only at mobile
        var hamburger = document.querySelector('.sidebar-toggle-btn');
        if (hamburger) {
            hamburger.style.display = isDesktop ? 'none' : 'inline-flex';
        }

        // Overflow menu container - only at mobile
        var overflowMenu = document.querySelector('.overflow-menu-container');
        if (overflowMenu) {
            overflowMenu.style.display = isDesktop ? 'none' : 'flex';
        }

        // Header spacer (pushes overflow to right at mobile)
        var headerSpacer = document.querySelector('.header-spacer');
        if (headerSpacer) {
            if (isDesktop) {
                headerSpacer.style.display = 'none';
            } else {
                headerSpacer.style.display = 'block';
                headerSpacer.style.flex = '1 1 auto';
            }
        }

        // Filter section - ALWAYS visible
        var filtersSection = document.querySelector('.toolbar-filters-section');
        if (filtersSection) {
            filtersSection.style.display = 'flex';
            filtersSection.style.flexDirection = 'row';
            filtersSection.style.alignItems = 'center';
            filtersSection.style.gap = '6px';
            if (isDesktop) {
                filtersSection.style.width = 'auto';
                filtersSection.style.flex = '0 0 auto';
            } else {
                filtersSection.style.width = '100%';
                filtersSection.style.flex = '1 1 auto';
            }
            // Make filter dropdowns stretch evenly at mobile
            var filterInputs = filtersSection.querySelectorAll('.v-input, .solara-select, [class*="v-select"]');
            filterInputs.forEach(function(input) {
                if (isDesktop) {
                    input.style.flex = '0 0 auto';
                    input.style.minWidth = '120px';
                } else {
                    input.style.flex = '1 1 0';
                    input.style.minWidth = '0';
                    input.style.maxWidth = 'none';
                }
            });
            // Also target direct children divs (Solara wrappers)
            var filterDivs = filtersSection.querySelectorAll(':scope > div');
            filterDivs.forEach(function(div) {
                if (!isDesktop) {
                    div.style.flex = '1 1 0';
                    div.style.minWidth = '0';
                }
            });
        }

        // Toggles section - ALWAYS visible
        var togglesSection = document.querySelector('.toolbar-toggles-section');
        if (togglesSection) {
            togglesSection.style.display = 'flex';
            togglesSection.style.flexDirection = 'row';
            togglesSection.style.alignItems = 'center';
            togglesSection.style.gap = '4px';
            if (isDesktop) {
                togglesSection.style.width = 'auto';
                togglesSection.style.flex = '0 0 auto';
            } else {
                togglesSection.style.width = '100%';
                togglesSection.style.flex = '1 1 auto';
            }
            // Make toggle buttons stretch evenly at mobile
            var toggleBtns = togglesSection.querySelectorAll('.v-btn, button');
            toggleBtns.forEach(function(btn) {
                if (isDesktop) {
                    btn.style.flex = '0 0 auto';
                } else {
                    btn.style.flex = '1 1 0';
                    btn.style.minWidth = '0';
                }
            });
            // Also target direct children divs (Solara wrappers)
            var toggleDivs = togglesSection.querySelectorAll(':scope > div');
            toggleDivs.forEach(function(div) {
                if (!isDesktop) {
                    div.style.flex = '1 1 0';
                    div.style.minWidth = '0';
                }
            });
        }

        // Indicators section (STH, ENI, Reset, CSV) - desktop only
        var indicatorsSection = document.querySelector('.toolbar-indicators-section');
        if (indicatorsSection) {
            if (isDesktop) {
                indicatorsSection.style.display = 'flex';
                indicatorsSection.style.flexDirection = 'row';
                indicatorsSection.style.alignItems = 'center';
                indicatorsSection.style.gap = '4px';
                indicatorsSection.style.flexShrink = '0';
            } else {
                indicatorsSection.style.display = 'none';
            }
        }

        // Desktop-only elements (dividers, individual buttons)
        var desktopOnly = document.querySelectorAll('.desktop-only');
        desktopOnly.forEach(function(el) {
            el.style.display = isDesktop ? 'inline-flex' : 'none';
        });

        // Desktop spacers - only show at desktop
        var spacer = document.querySelector('.toolbar-spacer');
        if (spacer) {
            if (isDesktop) {
                spacer.style.display = 'block';
                spacer.style.flex = '1 1 auto';
            } else {
                spacer.style.display = 'none';
            }
        }

        // Desktop dividers
        var dividers = document.querySelectorAll('.toolbar-divider-desktop');
        dividers.forEach(function(el) {
            el.style.display = isDesktop ? 'block' : 'none';
        });

        // Superintendent dropdown - always visible (enough space at all sizes)
        var suptDropdown = document.querySelector('.supt-dropdown');
        if (suptDropdown) {
            suptDropdown.style.display = 'block';
        }
    }

    // Apply on load and resize
    function initToolbarResponsive() {
        // Initial application
        applyToolbarLayout();

        // Re-apply on resize (debounced)
        var resizeTimeout;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(applyToolbarLayout, 100);
        });

        // Re-apply periodically to catch Solara re-renders
        // Solara may re-render components and reset inline styles
        setInterval(applyToolbarLayout, 500);
    }

    // Wait for toolbar to exist
    function waitForToolbar() {
        if (document.querySelector('.toolbar-row')) {
            initToolbarResponsive();
        } else {
            setTimeout(waitForToolbar, 100);
        }
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', waitForToolbar);
    } else {
        waitForToolbar();
    }
})();
</script>

<!-- Bootstrap JavaScript execution via img onerror (workaround for innerHTML not executing scripts) -->
<img src="data:," onerror="
(function() {
    console.log('[TOOLBAR-BOOT] Bootstrapping toolbar responsive script...');

    // Re-inject the toolbar script as a proper script element
    var script = document.createElement('script');
    script.textContent = `
        (function() {
            console.log('[TOOLBAR] Script running via bootstrap');
            var DESKTOP_BREAKPOINT = 1200;

            function applyToolbarLayout() {
                var isDesktop = window.innerWidth > DESKTOP_BREAKPOINT;
                console.log('[TOOLBAR] Layout applied, isDesktop=' + isDesktop + ', width=' + window.innerWidth);

                var toolbarRow = document.querySelector('.toolbar-row');
                if (toolbarRow) {
                    if (isDesktop) {
                        toolbarRow.style.flexDirection = 'row';
                        toolbarRow.style.flexWrap = 'nowrap';
                        toolbarRow.style.alignItems = 'center';
                        toolbarRow.style.gap = '6px';
                        toolbarRow.style.padding = '0 12px';
                        toolbarRow.style.overflow = 'hidden';
                    } else {
                        toolbarRow.style.flexDirection = 'column';
                        toolbarRow.style.alignItems = 'stretch';
                        toolbarRow.style.gap = '8px';
                        toolbarRow.style.padding = '8px 12px';
                        toolbarRow.style.overflow = 'visible';
                    }
                }

                // Header section - shrink at desktop
                var headerSection = document.querySelector('.toolbar-header-section');
                if (headerSection) {
                    headerSection.style.display = 'flex';
                    headerSection.style.flexShrink = '0';
                    headerSection.style.width = isDesktop ? 'auto' : '100%';
                }

                // Hamburger - hide at desktop
                var hamburger = document.querySelector('.sidebar-toggle-btn');
                if (hamburger) hamburger.style.display = isDesktop ? 'none' : 'inline-flex';

                // Overflow menu - hide at desktop
                var overflow = document.querySelector('.overflow-menu-container');
                if (overflow) overflow.style.display = isDesktop ? 'none' : 'flex';

                // Header spacer - hide at desktop
                var spacer = document.querySelector('.header-spacer');
                if (spacer) {
                    spacer.style.display = isDesktop ? 'none' : 'block';
                    if (!isDesktop) spacer.style.flex = '1 1 auto';
                }

                // Filters section - shrinkable at desktop, full-width at mobile
                var filters = document.querySelector('.toolbar-filters-section');
                if (filters) {
                    filters.style.display = 'flex';
                    filters.style.flexDirection = 'row';
                    filters.style.flexWrap = 'nowrap';
                    filters.style.flexShrink = isDesktop ? '1' : '0';
                    filters.style.flexGrow = isDesktop ? '0' : '1';
                    filters.style.width = isDesktop ? 'auto' : '100%';
                    filters.style.gap = '4px';
                    filters.style.justifyContent = isDesktop ? 'flex-start' : 'stretch';
                    // Make dropdowns shrinkable at desktop, equal-stretch at mobile
                    filters.querySelectorAll(':scope > div').forEach(function(d) {
                        d.style.flex = isDesktop ? '1 1 100px' : '1 1 0';
                        d.style.minWidth = isDesktop ? '80px' : '0';
                        d.style.maxWidth = isDesktop ? '160px' : 'none';
                        d.style.width = isDesktop ? 'auto' : 'auto';
                    });
                    // Target the actual Vuetify inputs
                    filters.querySelectorAll('.v-input').forEach(function(inp) {
                        inp.style.flex = isDesktop ? '0 1 auto' : '1 1 0';
                        inp.style.minWidth = isDesktop ? '80px' : '0';
                        inp.style.maxWidth = isDesktop ? '160px' : 'none';
                        inp.style.width = isDesktop ? 'auto' : '100%';
                    });
                }

                // Toggles section - shrinkable at desktop, full-width at mobile
                var toggles = document.querySelector('.toolbar-toggles-section');
                if (toggles) {
                    toggles.style.display = 'flex';
                    toggles.style.flexDirection = 'row';
                    toggles.style.flexWrap = 'nowrap';
                    toggles.style.flexShrink = isDesktop ? '1' : '0';
                    toggles.style.flexGrow = isDesktop ? '0' : '1';
                    toggles.style.width = isDesktop ? 'auto' : '100%';
                    toggles.style.gap = '4px';
                    toggles.style.justifyContent = isDesktop ? 'flex-start' : 'stretch';
                    toggles.querySelectorAll(':scope > div').forEach(function(d) {
                        d.style.flex = isDesktop ? '0 1 auto' : '1 1 0';
                        d.style.minWidth = '0';
                    });
                    // Make buttons stretch to fill their containers on mobile
                    toggles.querySelectorAll('.v-btn').forEach(function(btn) {
                        btn.style.minWidth = isDesktop ? '50px' : '0';
                        btn.style.flex = isDesktop ? '0 0 auto' : '1 1 0';
                        btn.style.width = isDesktop ? 'auto' : '100%';
                        btn.style.paddingLeft = isDesktop ? '8px' : '10px';
                        btn.style.paddingRight = isDesktop ? '8px' : '10px';
                    });
                }

                // Indicators section - desktop only, shrinkable
                var indicators = document.querySelector('.toolbar-indicators-section');
                if (indicators) {
                    indicators.style.display = isDesktop ? 'flex' : 'none';
                    indicators.style.flexShrink = '0';
                    indicators.style.gap = '4px';
                }

                // Desktop-only elements
                document.querySelectorAll('.desktop-only').forEach(function(el) {
                    el.style.display = isDesktop ? 'inline-flex' : 'none';
                });

                // Toolbar spacer - HIDE to save space
                var tbSpacer = document.querySelector('.toolbar-spacer');
                if (tbSpacer) {
                    tbSpacer.style.display = 'none';
                }

                // Hide dividers at narrower widths to save space
                document.querySelectorAll('.toolbar-divider-desktop').forEach(function(el) {
                    el.style.display = (isDesktop && window.innerWidth > 1400) ? 'block' : 'none';
                });
            }

            function waitForToolbar() {
                if (document.querySelector('.toolbar-row')) {
                    applyToolbarLayout();
                    window.addEventListener('resize', function() { setTimeout(applyToolbarLayout, 100); });
                    setInterval(applyToolbarLayout, 500);
                } else {
                    setTimeout(waitForToolbar, 100);
                }
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', waitForToolbar);
            } else {
                waitForToolbar();
            }
        })();
    `;
    document.head.appendChild(script);
})();
" style="display:none;">
"""

# ============================================================================
# TOOLBAR COMPONENT
# ============================================================================

@solara.component
def Toolbar(
    borough_filter: solara.Reactive[str],
    district_filter: solara.Reactive[str],
    superintendent_filter: solara.Reactive[str],
    superintendent_options: list,
    sth_filter: solara.Reactive[bool],
    eni_filter: solara.Reactive[bool],
    search_query: solara.Reactive[str],
    sidebar_open: solara.Reactive[bool],
    overflow_open: solara.Reactive[bool],
    on_reset: callable,
    # Layer toggles
    fundamentals_enabled: solara.Reactive[bool] = None,
    lights_enabled: solara.Reactive[bool] = None,
    show_gaps: solara.Reactive[bool] = None,  # Show Gaps toggle
    show_offices: solara.Reactive[bool] = None,  # Show District Offices toggle
    # View mode and training toggle handler (for mutual exclusivity in choropleth)
    view_mode: solara.Reactive[str] = None,
    on_training_toggle: callable = None,
    # Autocomplete items for search
    school_items: list = None,
    # Direct school selection callback (navigates to school detail)
    on_school_select: callable = None,
):
    """Top toolbar - LEFT: title + search + sidebar toggle, RIGHT: filters (responsive).

    Note: view_mode and mode removed from toolbar - now controlled via:
    - view_mode: floating map control (Step 3)
    - mode: sidebar dropdown (Step 4)

    Responsive features:
    - Sidebar toggle button (hamburger) on left
    - Overflow menu (⋯) appears when items are hidden via CSS
    """

    # State
    sth_active = sth_filter.value
    eni_active = eni_filter.value
    search_expanded = solara.use_reactive(False)

    # Button style helper
    def btn_style(active=False, color="#6b7280", active_bg=None, active_border=None):
        return {
            "height": "30px",
            "min-height": "30px",
            "padding": "0 10px",
            "border-radius": "6px",
            "font-size": "12px",
            "font-weight": "600" if active else "500",
            "background": active_bg if active and active_bg else "#f8f9fa",
            "border": f"1px solid {active_border if active and active_border else '#e5e7eb'}",
            "color": color,
            "white-space": "nowrap",
            "display": "inline-flex",
            "align-items": "center",
            "justify-content": "center",
            "flex-shrink": "0",
        }

    # Outer container for the entire toolbar
    with solara.Column(
        style={
            "padding": "0",
            "margin": "0",
            "gap": "0",
        },
        classes=["toolbar-filters"]
    ):
        # Main toolbar container
        with solara.Column(
            classes=["toolbar-row"],
            style={
                "min-height": "52px",
                "background": "#ffffff",
                "border-bottom": "1px solid #e5e7eb",
                "padding": "0 16px",
                "margin": "0",
                "box-shadow": "0 1px 2px rgba(0,0,0,0.04)",
            }
        ):
            # ===== ROW 1 (MOBILE): Header Section - Hamburger + Search + Title + Overflow =====
            # IMPORTANT: Overflow menu is INSIDE this row so it stays on same line at mobile
            with solara.Row(
                classes=["toolbar-header-section"],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "gap": "8px",
                    "flex-shrink": "0",
                    "width": "100%",  # Stretch full width at mobile
                }
            ):
                # Sidebar toggle button (hamburger)
                solara.Button(
                    label="",
                    icon_name="mdi-menu",
                    on_click=lambda: sidebar_open.set(not sidebar_open.value),
                    classes=["sidebar-toggle-btn"],
                    style={
                        "width": "36px",
                        "height": "36px",
                        "min-width": "36px",
                        "padding": "0",
                        "background": "#f0f2f6" if sidebar_open.value else "transparent",
                        "border": "1px solid #e5e7eb" if sidebar_open.value else "none",
                        "border-radius": "6px",
                        "color": "#6B9080" if sidebar_open.value else "#6b7280",
                        "flex-shrink": "0",
                    }
                )

                # Clickable search icon that expands to input field
                if not search_expanded.value:
                    solara.Button(
                        label="",
                        icon_name="mdi-magnify",
                        on_click=lambda: search_expanded.set(True),
                        style={
                            "width": "32px",
                            "height": "32px",
                            "min-width": "32px",
                            "padding": "0",
                            "background": "transparent",
                            "border": "none",
                            "color": "#6B9080",
                        }
                    )
                    solara.HTML(unsafe_innerHTML="""
                        <span style="font-size: 15px; font-weight: 700; color: #1f2937; white-space: nowrap; letter-spacing: -0.3px;">
                            HTYPE Dashboard
                        </span>
                    """)
                else:
                    # Expanded state: Search autocomplete field
                    # Handler for autocomplete selection
                    def handle_school_selection(dbn):
                        if dbn and on_school_select:
                            on_school_select(dbn)
                            search_expanded.set(False)
                        elif not dbn:
                            search_query.set("")

                    rv.Autocomplete(
                        items=school_items or [],
                        item_text="text",
                        item_value="value",
                        v_model=search_query.value,
                        on_v_model=handle_school_selection,
                        placeholder="Type school name or DBN...",
                        clearable=True,
                        dense=True,
                        solo=True,
                        hide_no_data=True,
                        auto_select_first=True,
                        prepend_inner_icon="mdi-magnify",
                        return_object=False,
                        style_="flex: 1; min-width: 200px; max-width: 300px;",
                    )
                    solara.Button(
                        label="×",
                        on_click=lambda: (search_query.set(""), search_expanded.set(False)),
                        style={
                            "width": "24px",
                            "height": "24px",
                            "min-width": "24px",
                            "padding": "0",
                            "background": "transparent",
                            "border": "none",
                            "color": "#6b7280",
                            "font-size": "18px",
                        }
                    )

                # ===== SPACER: Pushes overflow menu to the right =====
                solara.HTML(
                    unsafe_innerHTML="<div style='flex: 1 1 auto; min-width: 8px;'></div>",
                    classes=["header-spacer"]
                )

                # ===== OVERFLOW MENU (⋯) - INSIDE header row =====
                # This button is visible only at tablet/mobile widths (via CSS)
                with solara.Column(style={
                    "position": "relative",
                    "flex-shrink": "0",
                }, classes=["overflow-menu-container"]):
                    solara.Button(
                        label="",
                        icon_name="mdi-dots-horizontal",
                        on_click=lambda: overflow_open.set(not overflow_open.value),
                        style={
                            "width": "32px",
                            "height": "30px",
                            "min-width": "32px",
                            "padding": "0",
                            "background": "#f8f9fa" if overflow_open.value else "transparent",
                            "border": "1px solid #e5e7eb",
                            "border-radius": "6px",
                            "color": "#6b7280",
                            "display": "inline-flex",
                            "align-items": "center",
                            "justify-content": "center",
                        },
                        classes=["overflow-btn"]
                    )

                    # Overflow dropdown menu (shown when overflow_open is True)
                    if overflow_open.value:
                        with solara.Column(style={
                            "position": "absolute",
                            "top": "36px",
                            "right": "0",
                            "background": "white",
                            "border": "1px solid #e5e7eb",
                            "border-radius": "8px",
                            "box-shadow": "0 4px 12px rgba(0,0,0,0.15)",
                            "padding": "8px",
                            "min-width": "180px",
                            "z-index": "9999",
                        }, classes=["overflow-dropdown"]):
                            # Label
                            solara.HTML(unsafe_innerHTML='''
                                <div style="font-size: 10px; font-weight: 600; color: #9ca3af;
                                            text-transform: uppercase; letter-spacing: 0.5px;
                                            padding: 4px 8px 8px; border-bottom: 1px solid #e5e7eb;">
                                    More Filters
                                </div>
                            ''')

                            # Superintendent dropdown - shows in overflow when toolbar version hides at 1000px
                            with solara.Row(style={
                                "padding": "8px",
                                "align-items": "center",
                                "gap": "8px",
                            }, classes=["overflow-show-supt"]):
                                solara.HTML(unsafe_innerHTML='<span style="font-size: 12px; color: #6b7280; min-width: 70px;">Superintendent</span>')
                                solara.Select(
                                    label="",
                                    value=superintendent_filter.value,
                                    on_value=lambda v: superintendent_filter.set(v),
                                    values=superintendent_options,
                                    style={"width": "100%", "flex": "1"}
                                )

                            # STH indicator toggle
                            solara.Button(
                                label="● STH" + (" ≥15%" if sth_active else ""),
                                on_click=lambda: sth_filter.set(not sth_filter.value),
                                style={
                                    "width": "100%",
                                    "padding": "8px 12px",
                                    "background": "rgba(255, 100, 100, 0.1)" if sth_active else "transparent",
                                    "border": "1px solid #ff6464" if sth_active else "1px solid #e5e7eb",
                                    "border-radius": "6px",
                                    "font-size": "12px",
                                    "color": "#ff6464",
                                    "text-align": "left",
                                    "justify-content": "flex-start",
                                    "margin-top": "4px",
                                },
                                classes=["overflow-show-at-1100"]
                            )

                            # ENI indicator toggle
                            solara.Button(
                                label="● ENI" + (" ≥74%" if eni_active else ""),
                                on_click=lambda: eni_filter.set(not eni_filter.value),
                                style={
                                    "width": "100%",
                                    "padding": "8px 12px",
                                    "background": "rgba(0, 220, 220, 0.1)" if eni_active else "transparent",
                                    "border": "1px solid #00dcdc" if eni_active else "1px solid #e5e7eb",
                                    "border-radius": "6px",
                                    "font-size": "12px",
                                    "color": "#00a8a8",
                                    "text-align": "left",
                                    "justify-content": "flex-start",
                                    "margin-top": "4px",
                                },
                                classes=["overflow-show-at-1100"]
                            )

                            # Show Gaps toggle
                            if show_gaps is not None:
                                gaps_active_overflow = show_gaps.value
                                solara.Button(
                                    label="👁 Gaps" if gaps_active_overflow else "Gaps",
                                    on_click=lambda: show_gaps.set(not show_gaps.value),
                                    style={
                                        "width": "100%",
                                        "padding": "8px 12px",
                                        "background": "rgba(100, 100, 100, 0.15)" if gaps_active_overflow else "transparent",
                                        "border": "1px solid #666666" if gaps_active_overflow else "1px solid #e5e7eb",
                                        "border-radius": "6px",
                                        "font-size": "12px",
                                        "color": "#666666",
                                        "text-align": "left",
                                        "justify-content": "flex-start",
                                        "margin-top": "4px",
                                    },
                                    classes=["overflow-show-at-900"]
                                )

                            # Show Offices toggle
                            if show_offices is not None:
                                offices_active_overflow = show_offices.value
                                solara.Button(
                                    label="🏢 Offices" if offices_active_overflow else "Offices",
                                    on_click=lambda: show_offices.set(not show_offices.value),
                                    style={
                                        "width": "100%",
                                        "padding": "8px 12px",
                                        "background": "rgba(107, 114, 128, 0.15)" if offices_active_overflow else "transparent",
                                        "border": "1px solid #6b7280" if offices_active_overflow else "1px solid #e5e7eb",
                                        "border-radius": "6px",
                                        "font-size": "12px",
                                        "color": "#6b7280",
                                        "text-align": "left",
                                        "justify-content": "flex-start",
                                        "margin-top": "4px",
                                    },
                                    classes=["overflow-show-at-600"]
                                )

                            # Divider before actions
                            solara.HTML(unsafe_innerHTML='''
                                <div style="height: 1px; background: #e5e7eb; margin: 8px 0;"></div>
                            ''')

                            # Reset button (mobile only)
                            solara.Button(
                                label="↺ Reset Filters",
                                on_click=on_reset,
                                style={
                                    "width": "100%",
                                    "padding": "8px 12px",
                                    "background": "transparent",
                                    "border": "1px solid #e5e7eb",
                                    "border-radius": "6px",
                                    "font-size": "12px",
                                    "color": "#6b7280",
                                    "text-align": "left",
                                    "justify-content": "flex-start",
                                },
                                classes=["overflow-mobile-only"]
                            )

                            # CSV Export button (mobile only)
                            solara.Button(
                                label="↓ Export CSV",
                                on_click=lambda: print("Export clicked"),
                                style={
                                    "width": "100%",
                                    "padding": "8px 12px",
                                    "background": "#6B9080",
                                    "border": "1px solid #6B9080",
                                    "border-radius": "6px",
                                    "font-size": "12px",
                                    "font-weight": "600",
                                    "color": "white",
                                    "text-align": "left",
                                    "justify-content": "flex-start",
                                    "margin-top": "4px",
                                },
                                classes=["overflow-mobile-only"]
                            )

            # ===== SPACER: Desktop only - pushes filters to the right =====
            solara.HTML(
                unsafe_innerHTML="<div style='flex: 1 1 auto; min-width: 12px;'></div>",
                classes=["toolbar-spacer"]
            )

            # ===== ROW 2 (MOBILE): Filters Section - Geography dropdowns =====
            # Each filter resets the others when changed (prevents conflicting empty results)
            def on_borough_change(value):
                borough_filter.set(value)
                if value != "All Boroughs":
                    district_filter.set("All Districts")
                    superintendent_filter.set("All Superintendents")

            def on_district_change(value):
                district_filter.set(value)
                if value != "All Districts":
                    borough_filter.set("All Boroughs")
                    superintendent_filter.set("All Superintendents")

            def on_superintendent_change(value):
                superintendent_filter.set(value)
                if value != "All Superintendents":
                    borough_filter.set("All Boroughs")
                    district_filter.set("All Districts")

            with solara.Row(
                classes=["toolbar-filters-section"],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "gap": "6px",
                    "flex": "1 1 auto",  # Allow stretching at mobile
                    "width": "100%",  # Take full width
                }
            ):
                solara.Select(
                    label="",
                    value=borough_filter.value,
                    on_value=on_borough_change,
                    values=["All Boroughs", "Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"],
                    style={"min-width": "90px", "flex": "1 1 auto"}
                )

                solara.Select(
                    label="",
                    value=district_filter.value,
                    on_value=on_district_change,
                    values=["All Districts"] + [f"D{i}" for i in range(1, 33)],
                    style={"min-width": "80px", "flex": "1 1 auto"}
                )

                solara.Select(
                    label="",
                    value=superintendent_filter.value,
                    on_value=on_superintendent_change,
                    values=superintendent_options,
                    style={"min-width": "100px", "flex": "1 1 auto"},
                    classes=["supt-dropdown"]
                )

            # Desktop divider between filters and toggles
            solara.HTML(
                unsafe_innerHTML='<div style="width: 1px; height: 26px; background: #e0e0e0; margin: 0 4px; flex-shrink: 0;"></div>',
                classes=["toolbar-divider-desktop"]
            )

            # ===== ROW 3 (MOBILE): Toggles Section - Training layers and view options =====
            is_choropleth = view_mode is not None and view_mode.value == "District Choropleth"

            with solara.Row(
                classes=["toolbar-toggles-section"],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "gap": "4px",
                    "flex": "1 1 auto",  # Allow stretching at mobile
                    "width": "100%",  # Take full width
                }
            ):
                # Fundamentals toggle
                if fundamentals_enabled is not None:
                    fund_active = fundamentals_enabled.value
                    fund_click = (
                        lambda: on_training_toggle('fundamentals', not fundamentals_enabled.value)
                        if on_training_toggle else lambda: fundamentals_enabled.set(not fundamentals_enabled.value)
                    )
                    solara.Button(
                        label="🔵 Fund" if fund_active else "Fund",
                        on_click=fund_click,
                        style=btn_style(
                            active=fund_active,
                            color="#4183C4",
                            active_bg="rgba(65, 131, 196, 0.15)",
                            active_border="#4183C4"
                        )
                    )

                # LIGHTS toggle
                if lights_enabled is not None:
                    lights_active = lights_enabled.value
                    lights_click = (
                        lambda: on_training_toggle('lights', not lights_enabled.value)
                        if on_training_toggle else lambda: lights_enabled.set(not lights_enabled.value)
                    )
                    solara.Button(
                        label="🟣 LIGHTS" if lights_active else "LIGHTS",
                        on_click=lights_click,
                        style=btn_style(
                            active=lights_active,
                            color="#9C66B2",
                            active_bg="rgba(156, 102, 178, 0.15)",
                            active_border="#9C66B2"
                        )
                    )

                # Sessions toggle (placeholder)
                with solara.Tooltip("Coming Soon - Student session tracking"):
                    solara.Button(
                        label="Sessions",
                        disabled=True,
                        style={
                            "height": "30px",
                            "min-height": "30px",
                            "padding": "0 8px",
                            "border-radius": "6px",
                            "font-size": "12px",
                            "font-weight": "500",
                            "background": "#f3f4f6",
                            "border": "1px solid #e5e7eb",
                            "color": "#9ca3af",
                            "cursor": "not-allowed",
                            "opacity": "0.6",
                            "white-space": "nowrap",
                        }
                    )

                # Gaps toggle
                if show_gaps is not None:
                    gaps_active = show_gaps.value
                    solara.Button(
                        label="👁 Gaps" if gaps_active else "Gaps",
                        on_click=lambda: show_gaps.set(not show_gaps.value),
                        style=btn_style(
                            active=gaps_active,
                            color="#666666",
                            active_bg="rgba(100, 100, 100, 0.15)",
                            active_border="#666666"
                        )
                    )

                # Offices toggle
                if show_offices is not None:
                    offices_active = show_offices.value
                    solara.Button(
                        label="🏢 Offices" if offices_active else "Offices",
                        on_click=lambda: show_offices.set(not show_offices.value),
                        style=btn_style(
                            active=offices_active,
                            color="#6b7280",
                            active_bg="rgba(107, 114, 128, 0.15)",
                            active_border="#6b7280"
                        ),
                        classes=["offices-btn"]
                    )

            # ===== DESKTOP ONLY: Vulnerability indicators and actions =====
            # These move to overflow menu on tablet/mobile (hidden via CSS class at ≤1200px)
            # Each element has .desktop-only class for individual hiding
            with solara.Row(
                classes=["toolbar-indicators-section"],
                style={
                    "align-items": "center",
                    "gap": "4px",
                    "flex-shrink": "0",
                }
            ):
                # Divider
                solara.HTML(
                    unsafe_innerHTML='<div style="width: 1px; height: 26px; background: #e0e0e0; margin: 0 4px; flex-shrink: 0;"></div>',
                    classes=["desktop-only"]
                )

                # STH toggle
                solara.Button(
                    label="🔴 STH" if sth_active else "STH",
                    on_click=lambda: sth_filter.set(not sth_filter.value),
                    style=btn_style(
                        active=sth_active,
                        color="#ff6464",
                        active_bg="rgba(255, 100, 100, 0.15)",
                        active_border="#ff6464"
                    ),
                    classes=["desktop-only"]
                )

                # ENI toggle
                solara.Button(
                    label="🔵 ENI" if eni_active else "ENI",
                    on_click=lambda: eni_filter.set(not eni_filter.value),
                    style=btn_style(
                        active=eni_active,
                        color="#00a0a0",
                        active_bg="rgba(0, 220, 220, 0.15)",
                        active_border="#00dcdc"
                    ),
                    classes=["desktop-only"]
                )

                # Divider
                solara.HTML(
                    unsafe_innerHTML='<div style="width: 1px; height: 26px; background: #e0e0e0; margin: 0 4px; flex-shrink: 0;"></div>',
                    classes=["desktop-only"]
                )

                # Reset button
                solara.Button(
                    label="↺",
                    on_click=on_reset,
                    style={
                        "height": "30px",
                        "width": "32px",
                        "min-width": "32px",
                        "padding": "0",
                        "border-radius": "6px",
                        "font-size": "16px",
                        "background": "transparent",
                        "border": "1px solid #e5e7eb",
                        "color": "#6b7280",
                        "align-items": "center",
                        "justify-content": "center",
                        "flex-shrink": "0",
                    },
                    classes=["desktop-only"]
                )

                # CSV Export button
                solara.Button(
                    label="↓ CSV",
                    on_click=lambda: print("Export clicked"),
                    style={
                        "height": "30px",
                        "padding": "0 12px",
                        "border-radius": "6px",
                        "font-size": "12px",
                        "font-weight": "600",
                        "background": "#6B9080",
                        "border": "1px solid #6B9080",
                        "color": "white",
                        "white-space": "nowrap",
                        "align-items": "center",
                        "justify-content": "center",
                        "flex-shrink": "0",
                    },
                    classes=["export-btn", "desktop-only"]
                )

# ============================================================================
# LAYER CONTROLS COMPONENT
# ============================================================================

@solara.component
def LayerControls(
    fundamentals_enabled: solara.Reactive[bool],
    lights_enabled: solara.Reactive[bool],
    sth_highlight: solara.Reactive[bool],
    eni_highlight: solara.Reactive[bool],
):
    """Layer control panel using Solara's native checkboxes.

    Uses Solara's Checkbox which properly handles reactive state
    without the observer stacking issue that ipywidgets has.
    """
    container_style = {
        "padding": "10px 12px",
        "border-bottom": "1px solid #e5e7eb",
        "background": "#ffffff",
    }

    with solara.Column(style=container_style, gap="8px"):
        # Training Layers header
        solara.HTML(unsafe_innerHTML="""
            <div style="font-size: 10px; font-weight: 600; color: #9ca3af;
                        text-transform: uppercase; letter-spacing: 0.5px;">
                Training Layers
            </div>
        """)

        # Training layer checkboxes
        with solara.Row(gap="12px", style={"flex-wrap": "wrap"}):
            solara.Checkbox(
                label="🔵 Fundamentals",
                value=fundamentals_enabled,
            )
            solara.Checkbox(
                label="🟣 LIGHTS",
                value=lights_enabled,
            )

        # Divider
        solara.HTML(unsafe_innerHTML="""
            <div style="height: 1px; background: #e5e7eb; margin: 4px 0;"></div>
        """)

        # Highlights header
        solara.HTML(unsafe_innerHTML="""
            <div style="font-size: 10px; font-weight: 600; color: #9ca3af;
                        text-transform: uppercase; letter-spacing: 0.5px;">
                Highlight Schools
            </div>
        """)

        # Highlight checkboxes
        with solara.Row(gap="12px", style={"flex-wrap": "wrap"}):
            solara.Checkbox(
                label="🔴 STH ≥15%",
                value=sth_highlight,
            )
            solara.Checkbox(
                label="🔵 ENI ≥74%",
                value=eni_highlight,
            )


# ============================================================================
# REDESIGNED SIDEBAR COMPONENTS (Dec 2025)
# ============================================================================
# Three distinct modes:
# - OverviewSidebar: Default citywide view
# - ClusterSidebar: Aggregate stats for filtered selection
# - SchoolSidebar: Detailed single school view with tabs
# ============================================================================

@solara.component
def OverviewSidebar(
    stats: dict,
    total_schools_citywide: int,
    show_offices: bool = False,  # Whether district offices are visible
):
    """
    Overview Mode sidebar - shown when no filters or selection active.

    Content:
    - High-level citywide statistics
    - Training coverage progress bars (three-layer model)
    - Guidance text for discoverability

    Note: View dropdown removed (Dec 2025) - replaced by "Show Gaps" toggle in toolbar
    which provides clearer visual differentiation without hiding schools.
    """
    # Get layer coverage percentages from stats
    fund_pct = stats.get('has_fund_pct', 0)
    lights_pct = stats.get('has_lights_pct', 0)
    students_pct = stats.get('has_students_pct', 0)
    fund_count = stats.get('has_fund_count', 0)
    lights_count = stats.get('has_lights_count', 0)
    students_count = stats.get('has_students_count', 0)

    # Entity counts for display
    school_count = stats.get('school_count', stats['total'])
    office_count = stats.get('office_count', 0)
    trained_count = stats.get('trained_count', 0)
    trained_pct = stats.get('trained_pct', 0)

    # Build count display - trained count with context
    if show_offices and office_count > 0:
        total_context = f"of {school_count:,} total + {office_count} offices"
    else:
        total_context = f"of {school_count:,} total"

    # Sidebar content
    with solara.Column(style={"padding": "16px", "height": "calc(100vh - 56px)", "overflow-y": "auto", "background": "#ffffff", "gap": "0px"}):

        # Training Coverage Section with Progress Bars - Improved alignment
        solara.HTML(unsafe_innerHTML=f"""
            <div style="background: #f9fafb; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;">
                <!-- Header row: label left, stats right -->
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
                    <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; padding-top: 4px;">
                        Training Coverage
                    </div>
                    <div style="text-align: right; line-height: 1.3;">
                        <div style="font-size: 22px; font-weight: 700; color: #262730; font-variant-numeric: tabular-nums;">{trained_count:,}</div>
                        <div style="font-size: 11px; color: #6b7280;">schools trained</div>
                        <div style="font-size: 10px; color: #9ca3af;">({total_context})</div>
                    </div>
                </div>

                <!-- Progress bars with consistent spacing and aligned numbers -->
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <!-- Fundamentals -->
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                <span style="color: #4183C4; font-size: 8px;">●</span> Fundamentals
                            </span>
                            <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                {fund_count:,} <span style="color: #9ca3af;">({fund_pct}%)</span>
                            </span>
                        </div>
                        <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; width: {fund_pct}%; background: #4183C4; border-radius: 3px;"></div>
                        </div>
                    </div>

                    <!-- LIGHTS ToT -->
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                <span style="color: #9C66B2; font-size: 8px;">●</span> LIGHTS ToT
                            </span>
                            <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                {lights_count:,} <span style="color: #9ca3af;">({lights_pct}%)</span>
                            </span>
                        </div>
                        <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; width: {lights_pct}%; background: #9C66B2; border-radius: 3px;"></div>
                        </div>
                    </div>

                    <!-- Student Sessions -->
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                <span style="color: #4CAF93; font-size: 8px;">●</span> Student Sessions
                            </span>
                            <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                {students_count:,} <span style="color: #9ca3af;">({students_pct}%)</span>
                            </span>
                        </div>
                        <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; width: {students_pct}%; background: #4CAF93; border-radius: 3px;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Training Gaps Overview -->
            <div style="background: #f9fafb; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;">
                <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                    Training Gaps
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <!-- Untouched Schools -->
                    <div style="display: flex; justify-content: space-between; align-items: baseline;" title="Schools with no training of any kind">
                        <span style="font-size: 11px; color: #374151; display: flex; align-items: center; gap: 6px;">
                            <span style="color: #B87D7D; font-size: 8px;">●</span> Untouched
                        </span>
                        <span style="font-size: 14px; font-weight: 600; color: #B87D7D; font-variant-numeric: tabular-nums;">{stats.get('no_training', 0):,}</span>
                    </div>
                    <!-- Need LIGHTS -->
                    <div style="display: flex; justify-content: space-between; align-items: baseline;" title="Schools with Fundamentals but no LIGHTS ToT">
                        <span style="font-size: 11px; color: #374151; display: flex; align-items: center; gap: 6px;">
                            <span style="color: #F59E0B; font-size: 8px;">●</span> Need LIGHTS
                        </span>
                        <span style="font-size: 14px; font-weight: 600; color: #F59E0B; font-variant-numeric: tabular-nums;">{stats.get('need_lights_count', 0):,}</span>
                    </div>
                    <!-- Sessions Submitted (of LIGHTS schools) -->
                    <div style="display: flex; justify-content: space-between; align-items: baseline;" title="LIGHTS schools that have submitted student session data">
                        <span style="font-size: 11px; color: #374151; display: flex; align-items: center; gap: 6px;">
                            <span style="color: #4CAF93; font-size: 8px;">●</span> Sessions Submitted
                        </span>
                        <span style="text-align: right; font-variant-numeric: tabular-nums;">
                            <span style="font-size: 14px; font-weight: 600; color: #4CAF93;">{round(students_count / lights_count * 100) if lights_count > 0 else 0}%</span>
                            <span style="color: #9ca3af; font-size: 10px;"> ({students_count} of {lights_count})</span>
                        </span>
                    </div>
                </div>
            </div>

            <!-- High-Need Schools Summary -->
            <div style="background: #f9fafb; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;">
                <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                    High-Need Schools
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div title="Students in Temporary Housing ≥15% - Top ~30% for housing instability">
                        <div style="font-size: 22px; font-weight: 700; color: #8B5CF6; font-variant-numeric: tabular-nums; line-height: 1.2;">{stats.get('high_sth', 0):,}</div>
                        <div style="font-size: 10px; color: #6b7280;">High STH (≥15%)</div>
                    </div>
                    <div title="Economic Need Index ≥74% - DOE's 'skewed toward lower incomes' cutoff">
                        <div style="font-size: 22px; font-weight: 700; color: #0D9488; font-variant-numeric: tabular-nums; line-height: 1.2;">{stats.get('high_eni', 0):,}</div>
                        <div style="font-size: 10px; color: #6b7280;">High ENI (≥74%)</div>
                    </div>
                </div>
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-size: 11px; color: #374151;">Priority (High-Need + Untrained)</span>
                        <span style="font-size: 16px; font-weight: 700; color: #DC2626; font-variant-numeric: tabular-nums;">{stats.get('priority', 0):,}</span>
                    </div>
                </div>
            </div>

            <!-- Guidance -->
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 14px;">
                <div style="display: flex; align-items: flex-start; gap: 10px;">
                    <span style="font-size: 16px;">💡</span>
                    <div>
                        <p style="margin: 0 0 6px 0; font-size: 12px; font-weight: 500; color: #1E40AF;">
                            Explore the data
                        </p>
                        <p style="margin: 0; font-size: 11px; color: #3B82F6; line-height: 1.5;">
                            Use the filters above to explore by borough, district, or superintendent.
                            Click any school marker on the map to see details.
                        </p>
                    </div>
                </div>
            </div>
    """)


@solara.component
def ClusterSidebar(
    stats: dict,
    stats_citywide: dict,
    df_filtered: pd.DataFrame,
    participant_df: pd.DataFrame,
    cluster_label: str,
    on_back: callable,
    # Unified filtering params (from toolbar)
    show_gaps: bool = False,
    fundamentals_enabled: bool = True,
    lights_enabled: bool = False,
    # Click handler for school rows
    on_school_select: callable = None,
):
    """
    Cluster Mode sidebar - shown when geographic/training filters are active.

    Content:
    - Back navigation link
    - Cluster identifier (borough/district/superintendent)
    - Training coverage stats with citywide comparison (tooltip)
    - Vulnerability stats
    - ALL schools list sorted by priority (unified with toolbar)
    - CSV export button

    Sorting Logic (unified with Gaps toggle):
    - Gaps OFF → sort by vulnerability only
    - Gaps ON → schools missing selected training first, then by vulnerability
    """
    # Calculate percentages (new three-layer model)
    total = stats['total']
    fund_pct = stats.get('has_fund_pct', 0)
    lights_pct = stats.get('has_lights_pct', 0)
    students_pct = stats.get('has_students_pct', 0)
    fund_count = stats.get('has_fund_count', 0)
    lights_count = stats.get('has_lights_count', 0)
    students_count = stats.get('has_students_count', 0)

    # Citywide percentages for comparison
    city_fund_pct = stats_citywide.get('has_fund_pct', 0)
    city_lights_pct = stats_citywide.get('has_lights_pct', 0)
    city_students_pct = stats_citywide.get('has_students_pct', 0)

    # ==========================================================================
    # UNIFIED SORTING: All schools, sorted by priority score
    # ==========================================================================
    all_schools = df_filtered.copy()

    # Calculate priority score for each school
    all_schools['priority_score'] = 0.0

    # 1. Missing selected training layers (if Gaps mode ON) - highest priority
    if show_gaps:
        if fundamentals_enabled:
            missing_fund = all_schools.get('has_fundamentals', pd.Series(['No'] * len(all_schools))) != 'Yes'
            all_schools.loc[missing_fund, 'priority_score'] += 100
        if lights_enabled:
            missing_lights = all_schools.get('has_lights', pd.Series(['No'] * len(all_schools))) != 'Yes'
            all_schools.loc[missing_lights, 'priority_score'] += 100

    # 2. High vulnerability (STH ≥15% or ENI ≥74%)
    if 'high_sth' in all_schools.columns:
        all_schools.loc[all_schools['high_sth'] == True, 'priority_score'] += 50
    if 'high_eni' in all_schools.columns:
        all_schools.loc[all_schools['high_eni'] == True, 'priority_score'] += 50

    # 3. Vulnerability severity (tiebreaker)
    if 'sth_pct' in all_schools.columns:
        all_schools['priority_score'] += all_schools['sth_pct'].fillna(0)
    if 'eni_score' in all_schools.columns:
        all_schools['priority_score'] += all_schools['eni_score'].fillna(0) * 100

    # Sort by priority score (highest first)
    all_schools = all_schools.sort_values('priority_score', ascending=False)

    # Build styled school table HTML (ALL schools, sorted by priority)
    school_rows_data = []  # Store row data for Solara rendering
    schools_to_show = all_schools.head(50)  # Show up to 50 schools

    if not schools_to_show.empty:
        for _, school in schools_to_show.iterrows():
            sth_val = school.get('sth_pct', 0) or 0
            eni_val = (school.get('eni_score', 0) or 0) * 100
            district = school.get('district', '')
            school_dbn = school.get('school_dbn', '')
            school_name = school.get('school_name', 'Unknown')
            priority_score = school.get('priority_score', 0)

            # Training status
            has_fund = school.get('has_fundamentals', 'No') == 'Yes'
            has_lights = school.get('has_lights', 'No') == 'Yes'

            # Priority classification
            is_high_need = sth_val >= 15 or eni_val >= 74
            is_missing_training = (show_gaps and
                ((fundamentals_enabled and not has_fund) or
                 (lights_enabled and not has_lights)))

            # Priority badge: 🔴 Critical, 🟡 Medium, 🟢 Good
            if is_missing_training and is_high_need:
                priority_badge = '🔴'
                priority_label = 'Critical'
                row_bg = 'background: #FEF2F2; border-left: 3px solid #DC2626;'
            elif is_missing_training:
                priority_badge = '🟡'
                priority_label = 'Missing training'
                row_bg = 'background: #FFFBEB; border-left: 3px solid #F59E0B;'
            elif is_high_need:
                priority_badge = '🟠'
                priority_label = 'High-need'
                row_bg = 'background: #FFF7ED; border-left: 3px solid #EA580C;'
            else:
                priority_badge = ''
                priority_label = ''
                row_bg = 'border-left: 3px solid transparent;'

            # Training badges (clearer than ●/○)
            fund_badge = '<span style="display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: 500; background: #DBEAFE; color: #1E40AF;">✓ Fund</span>' if has_fund else '<span style="display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: 500; background: #F3F4F6; color: #9CA3AF;">✗ Fund</span>'
            lights_badge = '<span style="display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: 500; background: #EDE9FE; color: #5B21B6;">✓ LIGHTS</span>' if has_lights else '<span style="display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: 500; background: #F3F4F6; color: #9CA3AF;">✗ LIGHTS</span>'

            school_rows_data.append({
                'dbn': school_dbn,
                'name': school_name,
                'district': district,
                'sth': sth_val,
                'eni': eni_val,
                'has_fund': has_fund,
                'has_lights': has_lights,
                'priority_badge': priority_badge,
                'priority_label': priority_label,
                'row_bg': row_bg,
                'fund_badge': fund_badge,
                'lights_badge': lights_badge,
            })

    # Main sidebar container - flex column to properly allocate scroll space
    with solara.Column(style={"height": "calc(100vh - 56px)", "overflow": "hidden", "background": "#ffffff", "display": "flex", "flex-direction": "column"}):
        # Header with functional back button (flex-shrink: 0 to maintain size)
        with solara.Column(style={"padding": "12px 16px", "border-bottom": "1px solid #e5e7eb", "gap": "8px", "flex-shrink": "0"}):
            # Functional back button (visible and clickable)
            solara.Button(
                "← Back to Overview",
                on_click=on_back,
                style={
                    "font-size": "12px",
                    "padding": "4px 8px",
                    "background": "transparent",
                    "border": "1px solid #e5e7eb",
                    "border-radius": "4px",
                    "color": "#3B82F6",
                    "cursor": "pointer",
                    "width": "fit-content",
                }
            )
            # Cluster title and info - show trained schools with total as context
            trained_count = stats.get('trained_count', 0)
            solara.HTML(unsafe_innerHTML=f"""
                <h2 style="margin: 0; font-size: 16px; font-weight: 600; color: #262730;">
                    📍 {cluster_label}
                </h2>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #6b7280;">
                    {trained_count:,} schools trained <span style="color: #9ca3af;">(of {total:,} total)</span>
                </p>
            """)

        # Scrollable content (min-height: 0 is critical for flex children to allow overflow)
        with solara.Column(style={"flex": "1", "overflow-y": "auto", "padding": "16px", "min-height": "0"}):
            # Training coverage with comparison tooltips - Improved alignment
            solara.HTML(unsafe_innerHTML=f"""
                <div style="background: #f9fafb; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;">
                    <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                        Training Coverage
                    </div>

                    <!-- Progress bars with consistent spacing and aligned numbers -->
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <!-- Fundamentals -->
                        <div title="Citywide: {city_fund_pct}%">
                            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                                <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                    <span style="color: #4183C4; font-size: 8px;">●</span> Fundamentals
                                </span>
                                <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                    {fund_count:,} <span style="color: #9ca3af;">({fund_pct}%)</span>
                                </span>
                            </div>
                            <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: {fund_pct}%; background: #4183C4; border-radius: 3px;"></div>
                            </div>
                        </div>

                        <!-- LIGHTS ToT -->
                        <div title="Citywide: {city_lights_pct}%">
                            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                                <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                    <span style="color: #9C66B2; font-size: 8px;">●</span> LIGHTS ToT
                                </span>
                                <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                    {lights_count:,} <span style="color: #9ca3af;">({lights_pct}%)</span>
                                </span>
                            </div>
                            <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: {lights_pct}%; background: #9C66B2; border-radius: 3px;"></div>
                            </div>
                        </div>

                        <!-- Student Sessions -->
                        <div title="Citywide: {city_students_pct}%">
                            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                                <span style="font-size: 12px; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 6px;">
                                    <span style="color: #4CAF93; font-size: 8px;">●</span> Student Sessions
                                </span>
                                <span style="font-size: 12px; color: #374151; font-variant-numeric: tabular-nums; min-width: 85px; text-align: right;">
                                    {students_count:,} <span style="color: #9ca3af;">({students_pct}%)</span>
                                </span>
                            </div>
                            <div style="height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: {students_pct}%; background: #4CAF93; border-radius: 3px;"></div>
                            </div>
                        </div>
                    </div>

                    <div style="margin-top: 8px; font-size: 10px; color: #9ca3af; font-style: italic;">
                        Hover bars for citywide comparison
                    </div>
                </div>

                <!-- Vulnerability -->
                <div style="background: #f9fafb; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
                    <div style="font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; margin-bottom: 10px;">
                        Vulnerability
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div title="Citywide avg: {stats_citywide.get('avg_sth', 0)}%">
                            <div style="font-size: 12px; color: #6b7280;">Avg STH</div>
                            <div style="font-size: 18px; font-weight: 600; color: #8B5CF6;">{stats.get('avg_sth', 0)}%</div>
                        </div>
                        <div title="Citywide avg: {stats_citywide.get('avg_eni', 0)}%">
                            <div style="font-size: 12px; color: #6b7280;">Avg ENI</div>
                            <div style="font-size: 18px; font-weight: 600; color: #0D9488;">{stats.get('avg_eni', 0)}%</div>
                        </div>
                    </div>
                    <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;"
                         title="High-Need = STH ≥15% (students in temporary housing) OR ENI ≥74% (economic need index)">
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-size: 12px; color: #374151; cursor: help; border-bottom: 1px dashed #9ca3af;">
                                High-Need Schools <span style="font-size: 10px; color: #9ca3af;">ⓘ</span>
                            </span>
                            <span style="font-size: 14px; font-weight: 600; color: #DC2626;">{stats.get('high_need_unique', 0)}</span>
                        </div>
                        <div style="font-size: 10px; color: #9ca3af; margin-top: 2px;">
                            of {total} schools in selection (STH ≥15% or ENI ≥74%)
                        </div>
                    </div>
                </div>
            """)

            # Schools section with prominent sort indicator
            # Build sort indicator chip
            if show_gaps:
                sort_chip = f"""
                    <span style="display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 12px; font-size: 10px; font-weight: 500; color: #92400E;">
                        <span>⬆️</span> Gaps First
                    </span>
                """
                sort_description = "Schools missing selected training types sorted to top"
            else:
                sort_chip = f"""
                    <span style="display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 12px; font-size: 10px; font-weight: 500; color: #6B7280;">
                        <span>📊</span> By Vulnerability
                    </span>
                """
                sort_description = "Highest vulnerability schools first"

            # Schools section header
            solara.HTML(unsafe_innerHTML=f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8px 8px 0 0; overflow: hidden;">
                    <div style="background: #f9fafb; padding: 10px 14px; border-bottom: 1px solid #e5e7eb;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-size: 12px; font-weight: 600; color: #374151;">
                                Schools ({total})
                            </span>
                            {sort_chip}
                        </div>
                        <div style="font-size: 10px; color: #6b7280;">
                            {sort_description}
                        </div>
                    </div>
                </div>
            """)

            # Clickable school rows container (Phase 4.4)
            # Removed max-height to let parent container handle scrolling
            with solara.Column(style={
                "border": "1px solid #e5e7eb",
                "border-top": "none",
                "border-radius": "0 0 8px 8px",
                "margin-top": "-1px",
            }):
                if not school_rows_data:
                    solara.HTML(unsafe_innerHTML='<div style="font-size: 12px; color: #6b7280; padding: 16px; text-align: center;">No schools in selection</div>')
                else:
                    for row in school_rows_data:
                        # Each row is a clickable button styled to look like a list item
                        school_dbn = row['dbn']

                        # Determine styling based on priority
                        bg_color = '#fff'
                        border_left = '3px solid transparent'
                        if 'background:' in row['row_bg']:
                            bg_parts = row['row_bg'].split(';')
                            for part in bg_parts:
                                if 'background:' in part:
                                    bg_color = part.replace('background:', '').strip()
                                if 'border-left:' in part:
                                    border_left = part.replace('border-left:', '').strip()

                        # Build row content HTML with improved grid layout
                        # 3-column grid: [School Info (flex)] [Metrics (fixed 70px)] [Chevron (16px)]
                        # Handle NaN values for STH/ENI
                        sth_raw = row['sth'] if pd.notna(row['sth']) else 0
                        eni_raw = row['eni'] if pd.notna(row['eni']) else 0
                        sth_color = '#DC2626' if sth_raw >= 15 else '#6b7280'
                        sth_weight = '600' if sth_raw >= 15 else '400'
                        eni_color = '#DC2626' if eni_raw >= 74 else '#6b7280'
                        eni_weight = '600' if eni_raw >= 74 else '400'

                        # Format values as integers (use -- for missing data)
                        sth_val = int(sth_raw) if pd.notna(row['sth']) else '--'
                        eni_val = int(eni_raw) if pd.notna(row['eni']) else '--'

                        row_html = f"""
                            <div style="display: grid; grid-template-columns: 1fr 70px 16px; gap: 6px; align-items: center; width: 100%;">
                                <!-- Column 1: School Info -->
                                <div style="min-width: 0; text-align: left;">
                                    <div style="font-size: 12px; font-weight: 500; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.3;">
                                        {row['priority_badge']} {row['name'][:30]}{'…' if len(row['name']) > 30 else ''}
                                    </div>
                                    <div style="display: flex; gap: 6px; align-items: center; margin-top: 4px; flex-wrap: wrap;">
                                        <span style="font-size: 10px; color: #6b7280; font-weight: 500;">D{row['district']}</span>
                                        {row['fund_badge']}
                                        {row['lights_badge']}
                                    </div>
                                </div>
                                <!-- Column 2: Metrics with inline-block fixed widths -->
                                <div style="text-align: right; font-family: 'SF Mono', 'Menlo', 'Courier New', monospace; font-size: 10px; line-height: 1.5;">
                                    <div><span style="color: #9ca3af;">STH</span><span style="display: inline-block; width: 4ch; text-align: right; color: {sth_color}; font-weight: {sth_weight};">{sth_val}%</span></div>
                                    <div><span style="color: #9ca3af;">ENI</span><span style="display: inline-block; width: 4ch; text-align: right; color: {eni_color}; font-weight: {eni_weight};">{eni_val}%</span></div>
                                </div>
                                <!-- Column 3: Chevron indicator -->
                                <div style="color: #9ca3af; font-size: 12px; display: flex; align-items: center; justify-content: center;">›</div>
                            </div>
                        """

                        # Use a button that contains the row HTML
                        def make_click_handler(dbn):
                            return lambda: on_school_select(dbn) if on_school_select else None

                        # Determine CSS classes for hover states
                        priority_class = ""
                        if row['priority_label'] == 'Critical':
                            priority_class = "priority-critical"
                        elif row['priority_label'] == 'Missing training':
                            priority_class = "priority-missing"
                        elif row['priority_label'] == 'High-need':
                            priority_class = "priority-highneed"

                        solara.Button(
                            children=[solara.HTML(unsafe_innerHTML=row_html)],
                            on_click=make_click_handler(school_dbn),
                            classes=["school-row-button", priority_class] if priority_class else ["school-row-button"],
                            style={
                                "width": "100%",
                                "padding": "8px 12px",
                                "border": "none",
                                "border-bottom": "1px solid #f3f4f6",
                                "border-left": border_left,
                                "background": bg_color,
                                "cursor": "pointer",
                                "text-align": "left",
                                "border-radius": "0",
                            }
                        )

            # Export section - prepare CSV data (all schools, sorted by priority)
            export_df = all_schools
            export_cols = ['school_dbn', 'school_name', 'borough', 'district', 'has_fundamentals', 'has_lights']
            if 'superintendent' in export_df.columns:
                export_cols.append('superintendent')
            if 'sth_pct' in export_df.columns:
                export_cols.append('sth_pct')
            if 'eni_score' in export_df.columns:
                export_cols.append('eni_score')

            export_data = export_df[[c for c in export_cols if c in export_df.columns]].copy()
            csv_buffer = io.StringIO()
            export_data.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            csv_filename = f"schools_{cluster_label.replace(' ', '_')}_{timestamp}.csv"

            with solara.Row(style={"margin-top": "16px", "padding-bottom": "16px"}):
                solara.FileDownload(
                    data=csv_content.encode('utf-8'),
                    filename=csv_filename,
                    label="📥 Export Priority Schools (CSV)",
                )


@solara.component
def SchoolSidebar(
    school_data: pd.Series,
    participant_df: pd.DataFrame,
    on_back: callable,
    back_label: str,
    on_locate: callable = None,
):
    """
    School Mode sidebar - shown when a school marker is clicked.

    Content:
    - Back navigation link
    - School name and training status badge
    - Tabbed interface: Fundamentals | LIGHTS | Student Sessions
    - Participants grouped by role within each tab
    - Vulnerability indicators (numeric with context)
    - Locate button
    """
    # Active tab state
    active_tab, set_active_tab = solara.use_state("Fundamentals")

    school_name = school_data.get('school_name', 'Unknown School')
    school_dbn = school_data.get('school_dbn', '')
    training_status = school_data.get('training_status', 'Unknown')

    # Status badge styling - map internal status to display labels
    # "Complete" means has both Fundamentals AND LIGHTS (renamed for clarity)
    status_colors = {
        'Complete': ('#6B9080', '#ECFDF5'),          # Green - has both
        'Fundamentals Only': ('#4183C4', '#EFF6FF'), # Blue - has Fund only
        'LIGHTS Only': ('#9C66B2', '#F5F3FF'),       # Purple - has LIGHTS only
        'No Training': ('#B87D7D', '#FEF2F2'),       # Rose - neither
    }
    # Map training_status to clearer display labels
    status_display_labels = {
        'Complete': 'Fund + LIGHTS',
        'Fundamentals Only': 'Fundamentals',
        'LIGHTS Only': 'LIGHTS Only',
        'No Training': 'No Training',
    }
    display_label = status_display_labels.get(training_status, training_status)
    badge_text_color, badge_bg_color = status_colors.get(training_status, ('#6b7280', '#f3f4f6'))

    # Get participants for this school
    school_participants = pd.DataFrame()
    if participant_df is not None and not participant_df.empty and school_dbn:
        school_participants = participant_df[participant_df['school_dbn'] == school_dbn]

    # Filter by training type for each tab
    fundamentals_participants = school_participants[
        school_participants['training_type'].str.contains('Fundamentals', case=False, na=False)
    ] if not school_participants.empty else pd.DataFrame()

    lights_participants = school_participants[
        school_participants['training_type'].str.contains('LIGHTS', case=False, na=False)
    ] if not school_participants.empty else pd.DataFrame()

    # Group participants by role
    def group_by_role(df):
        if df.empty:
            return {}
        groups = {}
        for role, group in df.groupby('role_display'):
            groups[role] = group.sort_values('training_date', ascending=False)
        return groups

    fund_by_role = group_by_role(fundamentals_participants)
    lights_by_role = group_by_role(lights_participants)

    # Priority role order
    priority_roles = ['SAPIS', 'Social Worker', 'Student Service Manager', 'School Counselor']

    def sort_roles(roles_dict):
        """Sort roles with priority roles first."""
        sorted_roles = []
        for pr in priority_roles:
            if pr in roles_dict:
                sorted_roles.append((pr, roles_dict[pr]))
        for role in sorted(roles_dict.keys()):
            if role not in priority_roles:
                sorted_roles.append((role, roles_dict[role]))
        return sorted_roles

    # Build participant table HTML for a tab (Phase 4.2)
    def build_participant_table(by_role_dict):
        """Build an HTML table of participants sorted by priority roles."""
        if not by_role_dict:
            return '<div style="padding: 16px; color: #9ca3af; font-size: 12px; text-align: center;">No participants recorded</div>'

        # Flatten all participants into a single list with role info
        all_participants = []
        for role, participants in sort_roles(by_role_dict):
            for _, p in participants.iterrows():
                all_participants.append({
                    'first_name': p.get('first_name', '') or '',
                    'last_name': p.get('last_name', '') or '',
                    'role': role,
                    'date': p.get('training_date'),
                })

        # Build table HTML
        html = """
            <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                <thead>
                    <tr style="background: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                        <th style="text-align: left; padding: 8px 6px; font-weight: 600; color: #6b7280;">Name</th>
                        <th style="text-align: left; padding: 8px 6px; font-weight: 600; color: #6b7280;">Role</th>
                        <th style="text-align: right; padding: 8px 6px; font-weight: 600; color: #6b7280;">Date</th>
                    </tr>
                </thead>
                <tbody>
        """

        for i, p in enumerate(all_participants):
            row_bg = '#f0f4f8' if i % 2 == 1 else '#ffffff'  # Increased contrast for alternating rows
            date_str = p['date'].strftime('%m/%d/%y') if pd.notna(p['date']) else '—'
            name = f"{p['first_name']} {p['last_name']}".strip() or '—'

            html += f"""
                <tr style="background: {row_bg}; border-bottom: 1px solid #f3f4f6;">
                    <td style="padding: 8px 6px; color: #374151;">{name}</td>
                    <td style="padding: 8px 6px; color: #6b7280;">{p['role']}</td>
                    <td style="padding: 8px 6px; color: #9ca3af; text-align: right;">{date_str}</td>
                </tr>
            """

        html += """
                </tbody>
            </table>
        """
        return html

    fund_html = build_participant_table(fund_by_role)
    lights_html = build_participant_table(lights_by_role)

    # Vulnerability indicators
    sth_val = school_data.get('sth_pct', 0) or 0
    eni_val = (school_data.get('eni_score', 0) or 0) * 100

    # High thresholds: STH ≥15%, ENI ≥74% (DOE cutoffs)
    sth_level = "high" if sth_val >= 15 else "moderate" if sth_val >= 5 else "low"
    eni_level = "high" if eni_val >= 74 else "moderate" if eni_val >= 50 else "low"

    level_colors = {'high': '#DC2626', 'moderate': '#F59E0B', 'low': '#22C55E'}

    with solara.Column(style={"height": "calc(100vh - 56px)", "overflow": "hidden", "background": "#ffffff"}, classes=["school-sidebar-container"]):
        # Header with functional back button
        with solara.Column(style={"padding": "12px 16px", "border-bottom": "1px solid #e5e7eb", "gap": "8px"}):
            # Functional back button (visible and clickable)
            solara.Button(
                f"← {back_label}",
                on_click=on_back,
                style={
                    "font-size": "12px",
                    "padding": "4px 8px",
                    "background": "transparent",
                    "border": "1px solid #e5e7eb",
                    "border-radius": "4px",
                    "color": "#3B82F6",
                    "cursor": "pointer",
                    "width": "fit-content",
                }
            )
            # School name and info
            solara.HTML(unsafe_innerHTML=f"""
                <h2 style="margin: 0 0 4px 0; font-size: 15px; font-weight: 600; color: #262730; line-height: 1.3;">
                    🏫 {school_name}
                </h2>
                <p style="margin: 0 0 8px 0; font-size: 11px; color: #6b7280;">
                    DBN: {school_dbn}
                </p>
                <div style="
                    display: inline-block;
                    padding: 4px 10px;
                    background: {badge_bg_color};
                    color: {badge_text_color};
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                ">
                    {'🔵🟣' if training_status == 'Complete' else '🔵' if training_status == 'Fundamentals Only' else '🟣' if training_status == 'LIGHTS Only' else '⚪'} {display_label}
                </div>
            """)

        # Training Depth Bars (Phase 4.1)
        fund_count = len(fundamentals_participants)
        lights_count = len(lights_participants)
        student_sessions = 0  # Coming soon

        # Calculate bar widths as percentage of max expected values
        fund_pct = min(100, (fund_count / 50) * 100) if fund_count > 0 else 0
        lights_pct = min(100, (lights_count / 20) * 100) if lights_count > 0 else 0

        with solara.Column(style={"padding": "12px 16px", "border-bottom": "1px solid #e5e7eb", "gap": "8px"}):
            solara.HTML(unsafe_innerHTML=f"""
                <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">
                    Training Depth
                </div>

                <!-- Fundamentals Bar -->
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="font-size: 10px; color: #4183C4; width: 10px;">●</span>
                    <span style="font-size: 10px; color: #374151; width: 70px;">Fundamentals</span>
                    <div style="flex: 1; height: 8px; background: #E5E7EB; border-radius: 4px; overflow: hidden;">
                        <div style="width: {fund_pct}%; height: 100%; background: #4183C4; border-radius: 4px;"></div>
                    </div>
                    <span style="font-size: 11px; font-weight: 600; color: #374151; width: 24px; text-align: right;">{fund_count}</span>
                </div>

                <!-- LIGHTS Bar -->
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span style="font-size: 10px; color: #9C66B2; width: 10px;">●</span>
                    <span style="font-size: 10px; color: #374151; width: 70px;">LIGHTS ToT</span>
                    <div style="flex: 1; height: 8px; background: #E5E7EB; border-radius: 4px; overflow: hidden;">
                        <div style="width: {lights_pct}%; height: 100%; background: #9C66B2; border-radius: 4px;"></div>
                    </div>
                    <span style="font-size: 11px; font-weight: 600; color: #374151; width: 24px; text-align: right;">{lights_count}</span>
                </div>

                <!-- Students Bar (Coming Soon) -->
                <div style="display: flex; align-items: center; gap: 8px; opacity: 0.5;" title="Student session tracking coming soon">
                    <span style="font-size: 10px; color: #9CA3AF; width: 10px;">●</span>
                    <span style="font-size: 10px; color: #9CA3AF; width: 70px;">Students</span>
                    <div style="flex: 1; height: 8px; background: #F3F4F6; border-radius: 4px;"></div>
                    <span style="font-size: 9px; color: #9CA3AF; width: 55px; text-align: right; font-style: italic;">Coming Soon</span>
                </div>
            """)

        # Tabs
        with solara.Row(style={"padding": "0 16px", "gap": "0", "border-bottom": "1px solid #e5e7eb"}):
            for tab_name in ["Fundamentals", "LIGHTS", "Students"]:
                is_active = active_tab == tab_name
                solara.Button(
                    tab_name,
                    on_click=lambda t=tab_name: set_active_tab(t),
                    style={
                        "border": "none",
                        "background": "transparent",
                        "padding": "10px 14px",
                        "font-size": "12px",
                        "font-weight": "600" if is_active else "400",
                        "color": "#3B82F6" if is_active else "#6b7280",
                        "border-bottom": f"2px solid {'#3B82F6' if is_active else 'transparent'}",
                        "border-radius": "0",
                        "cursor": "pointer",
                    }
                )

        # Tab content (Phase 4.2/4.3 - tables and improved styling)
        with solara.Column(style={"flex": "1", "overflow-y": "auto", "padding": "16px"}, classes=["school-sidebar-tab-content"]):
            if active_tab == "Fundamentals":
                # Table header is built into the table, just render it
                solara.HTML(unsafe_innerHTML=f"""{fund_html}""")
            elif active_tab == "LIGHTS":
                # Table header is built into the table, just render it
                solara.HTML(unsafe_innerHTML=f"""{lights_html}""")
            else:  # Students tab (Phase 4.3 - improved styling)
                solara.HTML(unsafe_innerHTML="""
                    <div style="padding: 32px 20px; text-align: center;">
                        <div style="font-size: 40px; margin-bottom: 16px;">📚</div>
                        <div style="font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 4px;">
                            Student Sessions
                        </div>
                        <div style="font-size: 12px; color: #9ca3af;">
                            Coming Soon
                        </div>
                        <div style="margin-top: 16px; padding: 12px; background: #f9fafb; border-radius: 8px; font-size: 11px; color: #6b7280; line-height: 1.5;">
                            Student session tracking will show the number of students reached
                            by trained LIGHTS educators at this school.
                        </div>
                    </div>
                """)

            # Vulnerability section with tooltips
            solara.HTML(unsafe_innerHTML=f"""
                <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                    <div style="font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; margin-bottom: 10px;">
                        Vulnerability Indicators
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div style="background: #f9fafb; padding: 10px; border-radius: 6px; cursor: help;"
                             title="Students in Temporary Housing (STH)&#10;&#10;High: ≥15% (top ~30% of schools)&#10;Moderate: 5-15%&#10;Low: &lt;5%">
                            <div style="font-size: 11px; color: #6b7280;">STH</div>
                            <div style="font-size: 16px; font-weight: 600; color: {level_colors[sth_level]};">
                                {sth_val:.1f}%
                                <span style="font-size: 10px; font-weight: 400;">({sth_level})</span>
                            </div>
                        </div>
                        <div style="background: #f9fafb; padding: 10px; border-radius: 6px; cursor: help;"
                             title="Economic Need Index (ENI)&#10;&#10;High: ≥74% (DOE's cutoff)&#10;Moderate: 50-74%&#10;Low: &lt;50%">
                            <div style="font-size: 11px; color: #6b7280;">ENI</div>
                            <div style="font-size: 16px; font-weight: 600; color: {level_colors[eni_level]};">
                                {eni_val:.0f}%
                                <span style="font-size: 10px; font-weight: 400;">({eni_level})</span>
                            </div>
                        </div>
                    </div>
                </div>
            """)

        # Locate button at bottom
        if on_locate:
            with solara.Row(style={"padding": "12px 16px", "border-top": "1px solid #e5e7eb"}):
                lat = school_data.get('latitude')
                lon = school_data.get('longitude')
                if pd.notna(lat) and pd.notna(lon):
                    solara.Button(
                        "🎯 Locate on Map",
                        on_click=lambda: on_locate(lat, lon),
                        style={"width": "100%", "font-size": "12px"}
                    )


@solara.component
def SidebarRouter(
    sidebar_mode: solara.Reactive[str],
    stats: dict,
    stats_citywide: dict,
    df_filtered: pd.DataFrame,
    df_raw: pd.DataFrame,
    selected_school: solara.Reactive[str],
    participant_df: pd.DataFrame,
    on_back: callable,
    on_locate: callable,
    cluster_label: str,
    # Unified filtering params (from toolbar)
    show_gaps: bool = False,
    show_offices: bool = False,  # Whether district offices are visible
    fundamentals_enabled: bool = True,
    lights_enabled: bool = False,
    # School selection handler
    on_school_select: callable = None,
):
    """
    Routes to the appropriate sidebar component based on sidebar_mode.

    Modes:
    - "overview": OverviewSidebar
    - "cluster": ClusterSidebar
    - "school": SchoolSidebar
    """
    current_mode = sidebar_mode.value

    if current_mode == "school" and selected_school.value:
        # Get school data
        school_row = df_raw[df_raw['school_dbn'] == selected_school.value]
        if not school_row.empty:
            school_data = school_row.iloc[0]

            # Determine back label based on whether filters are active
            # (Check if df_filtered is smaller than df_raw)
            has_filters = len(df_filtered) < len(df_raw)
            back_label = f"Back to {cluster_label}" if has_filters else "Back to Overview"

            SchoolSidebar(
                school_data=school_data,
                participant_df=participant_df,
                on_back=on_back,
                back_label=back_label,
                on_locate=on_locate,
            )
        else:
            # School not found, show overview
            OverviewSidebar(stats=stats_citywide, total_schools_citywide=len(df_raw), show_offices=show_offices)

    elif current_mode == "cluster":
        ClusterSidebar(
            stats=stats,
            stats_citywide=stats_citywide,
            df_filtered=df_filtered,
            participant_df=participant_df,
            cluster_label=cluster_label,
            on_back=on_back,
            show_gaps=show_gaps,
            fundamentals_enabled=fundamentals_enabled,
            lights_enabled=lights_enabled,
            on_school_select=on_school_select,
        )

    else:  # "overview" or default
        OverviewSidebar(stats=stats_citywide, total_schools_citywide=len(df_raw), show_offices=show_offices)


# ============================================================================
# INFO PANEL COMPONENT (Left sidebar) - LEGACY, being replaced by SidebarRouter
# ============================================================================

@solara.component
def InfoPanel(
    stats: dict,
    mode: solara.Reactive[str],
    selected_school: solara.Reactive[str],
    df: pd.DataFrame,
    sidebar_open: solara.Reactive[bool] = None,
    on_locate: callable = None,
    # Layer controls
    fundamentals_enabled: solara.Reactive[bool] = None,
    lights_enabled: solara.Reactive[bool] = None,
    sth_highlight: solara.Reactive[bool] = None,
    eni_highlight: solara.Reactive[bool] = None,
    # Participant data for enhanced school details
    participant_df: pd.DataFrame = None,
):
    """Left info panel - matching mockup design.

    Args:
        sidebar_open: Optional reactive bool to control sidebar visibility on narrow screens.
                      When False and screen is narrow (<900px), sidebar slides out.
        fundamentals_enabled: Toggle for Fundamentals training layer
        lights_enabled: Toggle for LIGHTS ToT training layer
        sth_highlight: Toggle for STH ≥30% highlight mode
        eni_highlight: Toggle for ENI ≥85% highlight mode
        participant_df: DataFrame with training participant details for selected school view
    """

    # State for collapsible sections
    borough_open = solara.use_reactive(True)
    priority_open = solara.use_reactive(False)
    selected_open = solara.use_reactive(True)
    cluster_open = solara.use_reactive(True)  # Cluster stats section

    # Auto-detect view mode: single school vs cluster
    # - If a school is selected → show single school view
    # - If filtered to multiple schools without selection → show cluster stats
    is_single_school_view = bool(selected_school.value)
    is_cluster_view = len(df) > 1 and not selected_school.value

    # Auto-open "Selected School" when a school is clicked on the map
    def watch_selected_school():
        if selected_school.value:
            selected_open.set(True)

    # Use effect to watch for changes (runs when selected_school changes)
    solara.use_effect(watch_selected_school, [selected_school.value])

    # Determine CSS classes for responsive sidebar behavior
    panel_classes = ["info-panel-container"]
    if sidebar_open is not None and not sidebar_open.value:
        panel_classes.append("sidebar-closed")

    # Panel layout: Fixed header sections (ModeSelector, SummaryStats) + scrollable content area
    # Key: outer panel is a flex column with overflow:hidden, inner scrollable area has flex:1
    panel_style = {
        "height": "calc(100vh - 56px)",
        "display": "flex",
        "flex-direction": "column",
        "overflow": "hidden",  # Contain content, let inner Column scroll
        "background": "#ffffff",
        "box-sizing": "border-box",
        "border-right": "1px solid #e5e7eb",
    }

    with solara.Column(gap="0px", style=panel_style, classes=panel_classes):
        # View mode dropdown (Sprint 6: converted from 2x2 grid)
        ModeSelector(mode)

        # Summary statistics
        SummaryStats(stats)

        # Scrollable collapsible sections
        # CRITICAL: All scroll properties must be inline styles (not CSS classes) to override Solara defaults
        scrollable_style = {
            "padding": "8px 0",
            "flex": "1 1 0",          # Grow to fill, shrink if needed, base height 0
            "min-height": "0",        # Allow shrinking below content height
            "overflow-y": "auto",     # Enable vertical scrolling
            "overflow-x": "hidden",   # No horizontal scroll
        }
        with solara.Column(style=scrollable_style, classes=["sidebar-scrollable"]):
            # Borough Breakdown
            BoroughBreakdown(df, borough_open)

            # Priority Schools
            PrioritySchools(df, priority_open)

            # Auto-detect: Show either single school or cluster stats
            if is_single_school_view:
                # Single school selected → show detailed school view
                SelectedSchoolSection(
                    selected_school, df, selected_open,
                    on_locate=on_locate,
                    participant_df=participant_df
                )
            elif is_cluster_view:
                # Multiple schools filtered → show aggregate cluster stats
                ClusterStatsSection(
                    df_filtered=df,
                    participant_df=participant_df,
                    is_open=cluster_open,
                )
            else:
                # Default: show empty school selection prompt
                SelectedSchoolSection(
                    selected_school, df, selected_open,
                    on_locate=on_locate,
                    participant_df=participant_df
                )


@solara.component
def ModeSelector(mode: solara.Reactive[str]):
    """Compact dropdown for mode selection - saves vertical space.

    Sprint 6: Converted from 2x2 button grid to dropdown per user request.
    """

    container_style = {
        "padding": "10px 12px",
        "border-bottom": "1px solid #e5e7eb",
        "background": "#f8f9fa",
    }

    with solara.Column(style=container_style, gap="4px", classes=["mode-selector-container"]):
        # Label
        solara.HTML(unsafe_innerHTML="""
            <div style="font-size: 10px; font-weight: 600; color: #9ca3af;
                        text-transform: uppercase; letter-spacing: 0.5px;">
                View Mode
            </div>
        """)

        # Dropdown selector - filters schools by training status
        # Works with toolbar toggles: Trained/Untrained respects which layers are active
        solara.Select(
            label="",
            value=mode,
            values=["All Schools", "Trained", "Untrained"],
            style={"width": "100%"}
        )


@solara.component
def SummaryStats(stats: dict):
    """Summary statistics - compact 2x4 grid with minimal vertical space."""

    solara.HTML(unsafe_innerHTML=f"""
        <div style="padding: 10px 12px; border-bottom: 1px solid #e5e7eb;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px;">
                    Summary
                </span>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6px;">
                <!-- Row 1: Training Status (4 cards) -->
                <div style="background: #f0f2f6; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 16px; font-weight: 600; color: #262730;">{stats['total']}</div>
                    <div style="font-size: 9px; color: #9ca3af;">schools</div>
                </div>

                <div style="background: #f0f2f6; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 16px; font-weight: 600; color: #6B9080;">{stats['complete']}</div>
                    <div style="font-size: 9px; color: #9ca3af;">LIGHTS</div>
                </div>

                <div style="background: #f0f2f6; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 16px; font-weight: 600; color: #D4A574;">{stats['fundamentals']}</div>
                    <div style="font-size: 9px; color: #9ca3af;">Fund.</div>
                </div>

                <div style="background: #f0f2f6; padding: 6px 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 16px; font-weight: 600; color: #B87D7D;">{stats['no_training']}</div>
                    <div style="font-size: 9px; color: #9ca3af;">None</div>
                </div>
            </div>

            <!-- Row 2: Vulnerability Indicators (4 compact cards) -->
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6px; margin-top: 6px;">
                <div style="background: rgba(184, 125, 125, 0.1); padding: 6px 8px; border-radius: 6px; text-align: center; border: 1px solid rgba(184, 125, 125, 0.2);">
                    <div style="font-size: 14px; font-weight: 600; color: #B87D7D;">{stats['priority']}</div>
                    <div style="font-size: 8px; color: #9ca3af;">⚠️ Priority</div>
                </div>

                <div style="background: rgba(0, 220, 220, 0.08); padding: 6px 8px; border-radius: 6px; text-align: center; border: 1px solid rgba(0, 220, 220, 0.2);">
                    <div style="font-size: 14px; font-weight: 600; color: #00a8a8;">{stats['high_eni']}</div>
                    <div style="font-size: 8px; color: #9ca3af;">Hi ENI</div>
                </div>

                <div style="background: rgba(255, 100, 100, 0.08); padding: 6px 8px; border-radius: 6px; text-align: center; border: 1px solid rgba(255, 100, 100, 0.2);">
                    <div style="font-size: 14px; font-weight: 600; color: #ff6464;">{stats['avg_sth']}%</div>
                    <div style="font-size: 8px; color: #9ca3af;">Avg STH</div>
                </div>

                <div style="background: rgba(0, 220, 220, 0.08); padding: 6px 8px; border-radius: 6px; text-align: center; border: 1px solid rgba(0, 220, 220, 0.2);">
                    <div style="font-size: 14px; font-weight: 600; color: #00a8a8;">{stats['avg_eni']}%</div>
                    <div style="font-size: 8px; color: #9ca3af;">Avg ENI</div>
                </div>
            </div>
        </div>
    """)


@solara.component
def BoroughBreakdown(df: pd.DataFrame, is_open: solara.Reactive[bool]):
    """Borough breakdown with stacked progress bars - collapsible."""

    # Calculate borough stats (case-insensitive comparison)
    borough_data = []
    for borough in ['Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island']:
        borough_df = df[df['borough'].str.upper() == borough.upper()]
        total = len(borough_df)
        if total == 0:
            continue
        complete = len(borough_df[borough_df['training_status'] == 'Complete'])
        fund = len(borough_df[borough_df['training_status'] == 'Fundamentals Only'])
        none_ = len(borough_df[borough_df['training_status'] == 'No Training'])

        borough_data.append({
            'name': borough[:10] + ('.' if len(borough) > 10 else ''),
            'total': total,
            'complete_pct': round(complete / total * 100),
            'fund_pct': round(fund / total * 100),
            'none_pct': round(none_ / total * 100),
        })

    bars_html = ""
    for b in borough_data:
        bars_html += f"""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                <span style="width: 80px; font-size: 13px; color: #6b7280;">{b['name']}</span>
                <div style="flex: 1; height: 20px; background: #f0f2f6; border-radius: 4px; overflow: hidden; display: flex;">
                    <div style="width: {b['complete_pct']}%; height: 100%; background: #6B9080;"></div>
                    <div style="width: {b['fund_pct']}%; height: 100%; background: #D4A574;"></div>
                    <div style="width: {b['none_pct']}%; height: 100%; background: #B87D7D;"></div>
                </div>
                <span style="width: 40px; text-align: right; font-size: 12px; font-weight: 500; color: #262730;">{b['total']}</span>
            </div>
        """

    chevron_rotation = "rotate(90deg)" if is_open.value else "rotate(0deg)"
    chevron_html = f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="2" style="transform: {chevron_rotation}; transition: transform 0.2s;"><path d="m9 18 6-6-6-6"/></svg>'

    with solara.Column(style={"border-bottom": "1px solid #e5e7eb"}):
        # Clickable header using Solara Button with proper label
        with solara.Row(style={"padding": "0", "margin": "0"}):
            solara.Button(
                label=f"▸ Borough Breakdown" if not is_open.value else f"▾ Borough Breakdown",
                on_click=lambda: is_open.set(not is_open.value),
                style={
                    "width": "100%",
                    "padding": "12px 16px",
                    "background": "transparent",
                    "border": "none",
                    "cursor": "pointer",
                    "text-align": "left",
                    "font-size": "13px",
                    "font-weight": "600",
                    "color": "#262730",
                    "justify-content": "flex-start",
                }
            )

        # Content (shown only when open)
        if is_open.value:
            solara.HTML(unsafe_innerHTML=f"""
                <div style="padding: 0 16px 16px;">
                    {bars_html}
                </div>
            """)


@solara.component
def PrioritySchools(df: pd.DataFrame, is_open: solara.Reactive[bool]):
    """Priority schools table with ENI percentages - collapsible."""

    # Get schools with no training (sorted alphabetically for demo)
    priority = df[df['training_status'] == 'No Training'].head(5)

    rows_html = ""
    for _, school in priority.iterrows():
        name = school['school_name'][:25] + ('...' if len(school['school_name']) > 25 else '')
        rows_html += f"""
            <tr style="cursor: pointer;">
                <td style="padding: 8px 4px; border-bottom: 1px solid #e5e7eb; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    {name}
                </td>
                <td style="padding: 8px 4px; border-bottom: 1px solid #e5e7eb;">
                    85%
                </td>
                <td style="padding: 8px 4px; border-bottom: 1px solid #e5e7eb;">
                    <span style="display: inline-block; padding: 2px 6px; background: rgba(184, 125, 125, 0.1); color: #B87D7D; border-radius: 4px; font-size: 10px; font-weight: 600;">
                        High ENI
                    </span>
                </td>
            </tr>
        """

    with solara.Column(style={"border-bottom": "1px solid #e5e7eb"}):
        # Clickable header using Solara Button with proper label
        with solara.Row(style={"padding": "0", "margin": "0"}):
            solara.Button(
                label=f"▸ Priority Schools ({len(priority)})" if not is_open.value else f"▾ Priority Schools ({len(priority)})",
                on_click=lambda: is_open.set(not is_open.value),
                style={
                    "width": "100%",
                    "padding": "12px 16px",
                    "background": "transparent",
                    "border": "none",
                    "cursor": "pointer",
                    "text-align": "left",
                    "font-size": "13px",
                    "font-weight": "600",
                    "color": "#262730",
                    "justify-content": "flex-start",
                }
            )

        # Content (shown only when open)
        if is_open.value:
            solara.HTML(unsafe_innerHTML=f"""
                <div style="padding: 0 16px 16px;">
                    <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                        <thead>
                            <tr>
                                <th style="text-align: left; padding: 8px 4px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #6b7280; font-size: 11px;">School</th>
                                <th style="text-align: left; padding: 8px 4px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #6b7280; font-size: 11px;">ENI</th>
                                <th style="text-align: left; padding: 8px 4px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #6b7280; font-size: 11px;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                    <a href="#" style="display: block; text-align: center; margin-top: 12px; font-size: 12px; color: #6B9080; text-decoration: none; cursor: pointer;">
                        View all priority schools →
                    </a>
                </div>
            """)


@solara.component
def SelectedSchoolSection(
    selected_school: solara.Reactive[str],
    df: pd.DataFrame,
    is_open: solara.Reactive[bool],
    on_locate: callable = None,
    participant_df: pd.DataFrame = None
):
    """
    Enhanced school detail card with training participants and vulnerability indicators.

    Displays:
    1. School header with name, DBN, and Locate button
    2. Training status (primary) with participant counts
    3. Participants by role (priority roles first: SAPIS, Social Worker, SSM)
    4. Vulnerability indicators with numeric context
    """

    # Get school data if selected
    school_data = None
    school_participants = pd.DataFrame()

    if selected_school.value:
        school_row = df[df['school_dbn'] == selected_school.value]
        if not school_row.empty:
            school_data = school_row.iloc[0]

            # Get participants for this school
            if participant_df is not None and not participant_df.empty:
                school_participants = participant_df[
                    participant_df['school_dbn'] == selected_school.value
                ]

    with solara.Column(style={"border-bottom": "1px solid #e5e7eb"}):
        # Clickable header using Solara Button with proper label
        with solara.Row(style={"padding": "0", "margin": "0"}):
            solara.Button(
                label="▸ Selected School" if not is_open.value else "▾ Selected School",
                on_click=lambda: is_open.set(not is_open.value),
                style={
                    "width": "100%",
                    "padding": "12px 16px",
                    "background": "transparent",
                    "border": "none",
                    "cursor": "pointer",
                    "text-align": "left",
                    "font-size": "13px",
                    "font-weight": "600",
                    "color": "#262730",
                    "justify-content": "flex-start",
                }
            )

        # Content (shown only when open)
        if is_open.value:
            with solara.Column(style={"padding": "0 16px 16px"}):
                if school_data is not None:
                    school = school_data
                    status_color = {
                        'Complete': '#6B9080',
                        'Fundamentals Only': '#D4A574',
                        'No Training': '#B87D7D'
                    }.get(school['training_status'], '#6b7280')

                    # Card container
                    with solara.Column(style={
                        "background": "#f0f2f6",
                        "border-radius": "8px",
                        "padding": "12px",
                        "gap": "12px"
                    }):
                        # ====== 1. HEADER: School name + DBN + Locate button ======
                        with solara.Row(style={
                            "justify-content": "space-between",
                            "align-items": "flex-start",
                        }):
                            with solara.Column(gap="4px"):
                                solara.HTML(unsafe_innerHTML=f"""
                                    <div style="font-size: 14px; font-weight: 600;">{school['school_name']}</div>
                                    <div style="font-size: 12px; color: #9ca3af;">{school['school_dbn']}</div>
                                """)

                            # Locate button
                            solara.Button(
                                label="📍 Locate",
                                on_click=lambda: on_locate(school['latitude'], school['longitude']) if on_locate else None,
                                style={
                                    "padding": "4px 8px",
                                    "background": "white",
                                    "border": "1px solid #e5e7eb",
                                    "border-radius": "4px",
                                    "font-size": "11px",
                                    "color": "#6b7280",
                                }
                            )

                        # ====== 2. TRAINING STATUS (Primary) ======
                        # Count participants by training type
                        fundamentals_count = 0
                        lights_count = 0
                        if not school_participants.empty and 'training_type' in school_participants.columns:
                            fundamentals_count = len(school_participants[
                                school_participants['training_type'].str.contains('Fundamental', case=False, na=False)
                            ])
                            lights_count = len(school_participants[
                                school_participants['training_type'].str.contains('LIGHTS', case=False, na=False)
                            ])

                        solara.HTML(unsafe_innerHTML=f"""
                            <div style="border-left: 3px solid {status_color}; padding-left: 12px; background: white; border-radius: 0 4px 4px 0; padding: 8px 12px;">
                                <div style="font-weight: 600; font-size: 13px; color: {status_color};">{school['training_status']}</div>
                                <div style="color: #6b7280; font-size: 11px; margin-top: 2px;">
                                    {fundamentals_count} Fundamentals · {lights_count} LIGHTS ToT
                                </div>
                            </div>
                        """)

                        # ====== 3. PARTICIPANTS BY ROLE ======
                        if not school_participants.empty:
                            # Separate priority and other roles
                            priority_mask = school_participants['is_priority_role'] if 'is_priority_role' in school_participants.columns else pd.Series([False] * len(school_participants))
                            priority_participants = school_participants[priority_mask]
                            other_participants = school_participants[~priority_mask]

                            participants_html = '<div style="border-top: 1px solid #e5e7eb; padding-top: 8px;">'
                            participants_html += '<div style="font-size: 11px; font-weight: 600; color: #374151; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;">Trained Staff</div>'

                            # Build HTML for each role group (priority first)
                            for participants_group in [priority_participants, other_participants]:
                                if participants_group.empty:
                                    continue

                                role_col = 'role_display' if 'role_display' in participants_group.columns else 'role_standardized'
                                if role_col not in participants_group.columns:
                                    continue

                                for role, group in participants_group.groupby(role_col):
                                    if pd.isna(role) or role == 'Unknown':
                                        continue
                                    is_priority = 'is_priority_role' in group.columns and group['is_priority_role'].any()
                                    role_color = '#059669' if is_priority else '#6b7280'  # Green for priority
                                    role_icon = '⭐' if is_priority else ''

                                    participants_html += f'<div style="margin-bottom: 6px;">'
                                    participants_html += f'<div style="font-size: 11px; font-weight: 600; color: {role_color};">{role_icon} {role} ({len(group)})</div>'

                                    # List individual participants
                                    for _, p in group.iterrows():
                                        first = p.get('first_name', '') or ''
                                        last = p.get('last_name', '') or ''
                                        name = f"{first} {last}".strip() or 'Unknown'
                                        training = p.get('training_type', '') or ''
                                        date_val = p.get('training_date')
                                        date_str = ''
                                        if pd.notna(date_val):
                                            try:
                                                date_str = pd.to_datetime(date_val).strftime('%m/%d/%y')
                                            except:
                                                date_str = str(date_val)[:10]

                                        participants_html += f'''
                                            <div style="font-size: 10px; color: #4b5563; padding-left: 12px; margin-top: 2px;">
                                                {name}
                                                <span style="color: #9ca3af;">· {training} {date_str}</span>
                                            </div>
                                        '''
                                    participants_html += '</div>'

                            participants_html += '</div>'
                            solara.HTML(unsafe_innerHTML=participants_html)
                        else:
                            # No participant records
                            solara.HTML(unsafe_innerHTML="""
                                <div style="border-top: 1px solid #e5e7eb; padding-top: 8px;">
                                    <div style="font-size: 11px; color: #9ca3af; font-style: italic;">
                                        No participant records available
                                    </div>
                                </div>
                            """)

                        # ====== 4. VULNERABILITY INDICATORS ======
                        sth_val = school.get('sth_pct') if 'sth_pct' in school.index else school.get('sth_percent', None)
                        eni_val = school.get('eni_score') if 'eni_score' in school.index else school.get('economic_need_index', None)

                        def format_indicator(value, name, high_threshold, unit='%'):
                            if pd.isna(value):
                                return f'<span style="color: #9ca3af;">{name}: N/A</span>'

                            # Handle both 0-1 scale and 0-100 scale
                            if name == 'STH':
                                pct = value if value > 1 else value * 100  # STH might be in % already
                                level = 'high' if pct >= 30 else ('moderate' if pct >= 15 else 'low')
                            else:  # ENI
                                pct = value * 100 if value <= 1 else value  # ENI is 0-1 scale
                                level = 'high' if pct >= 85 else ('moderate' if pct >= 50 else 'low')

                            level_color = {'high': '#dc2626', 'moderate': '#d97706', 'low': '#059669'}[level]
                            return f'{name}: <b>{pct:.1f}{unit}</b> <span style="color: {level_color}; font-size: 10px;">({level})</span>'

                        vuln_html = f'''
                            <div style="background: white; padding: 8px; border-radius: 4px; font-size: 11px;">
                                <div style="font-weight: 600; color: #374151; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; font-size: 10px;">Vulnerability Indicators</div>
                                <div style="margin-bottom: 2px;">{format_indicator(sth_val, 'STH', 30)}</div>
                                <div>{format_indicator(eni_val, 'ENI', 85)}</div>
                            </div>
                        '''
                        solara.HTML(unsafe_innerHTML=vuln_html)

                        # ====== 5. LOCATION INFO ======
                        solara.HTML(unsafe_innerHTML=f"""
                            <div style="border-top: 1px solid #e5e7eb; padding-top: 8px; font-size: 11px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span style="color: #6b7280;">Borough</span>
                                    <span style="font-weight: 500;">{school['borough']}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between;">
                                    <span style="color: #6b7280;">District</span>
                                    <span style="font-weight: 500;">{school['district']}</span>
                                </div>
                            </div>
                        """)
                else:
                    # No school selected
                    solara.HTML(unsafe_innerHTML="""
                        <div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 13px; background: #f0f2f6; border-radius: 8px;">
                            <div style="margin-bottom: 4px;">ℹ️</div>
                            Click a school on the map to view details
                        </div>
                    """)


# ============================================================================
# CLUSTER STATS SECTION (Aggregate view for filtered selections)
# ============================================================================

@solara.component
def ClusterStatsSection(
    df_filtered: pd.DataFrame,
    participant_df: pd.DataFrame,
    is_open: solara.Reactive[bool],
):
    """
    Aggregate statistics for filtered school selection (cluster view).

    Displays:
    1. Training coverage breakdown (% complete, fundamentals only, untrained)
    2. Vulnerability distribution (ranges, high-need counts)
    3. Priority targeting list (high-need + untrained, ranked by vulnerability)
    4. Grouped by superintendent for outreach coordination
    5. Export buttons (CSV + Excel)
    """
    total = len(df_filtered)
    if total == 0:
        return

    # ====== CALCULATE STATISTICS ======

    # Training coverage breakdown
    complete = len(df_filtered[df_filtered['training_status'] == 'Complete'])
    fund_only = len(df_filtered[df_filtered['training_status'] == 'Fundamentals Only'])
    untrained = len(df_filtered[df_filtered['training_status'] == 'No Training'])

    complete_pct = round(complete / total * 100, 1) if total > 0 else 0
    fund_pct = round(fund_only / total * 100, 1) if total > 0 else 0
    untrained_pct = round(untrained / total * 100, 1) if total > 0 else 0

    # Vulnerability statistics (STH ≥15%, ENI ≥74%)
    high_sth_mask = df_filtered['sth_pct'] >= 15 if 'sth_pct' in df_filtered.columns else pd.Series([False] * total)
    high_eni_mask = df_filtered['eni_score'] >= 0.74 if 'eni_score' in df_filtered.columns else pd.Series([False] * total)

    high_sth_count = high_sth_mask.sum()
    high_eni_count = high_eni_mask.sum()

    avg_sth = df_filtered['sth_pct'].mean() if 'sth_pct' in df_filtered.columns else 0
    avg_eni = df_filtered['eni_score'].mean() * 100 if 'eni_score' in df_filtered.columns else 0

    # Priority schools (high need + untrained)
    untrained_mask = df_filtered['training_status'] == 'No Training'
    priority_mask = (high_sth_mask | high_eni_mask) & untrained_mask
    priority_schools = df_filtered[priority_mask].copy()

    # Calculate vulnerability score for sorting
    if not priority_schools.empty:
        sth_col = priority_schools['sth_pct'] if 'sth_pct' in priority_schools.columns else 0
        eni_col = priority_schools['eni_score'] * 100 if 'eni_score' in priority_schools.columns else 0
        priority_schools['vuln_score'] = sth_col.fillna(0) + eni_col.fillna(0)
        priority_schools = priority_schools.sort_values('vuln_score', ascending=False)

    with solara.Column(style={"border-bottom": "1px solid #e5e7eb"}):
        # Clickable header
        with solara.Row(style={"padding": "0", "margin": "0"}):
            solara.Button(
                label="▸ Cluster Statistics" if not is_open.value else "▾ Cluster Statistics",
                on_click=lambda: is_open.set(not is_open.value),
                style={
                    "width": "100%",
                    "padding": "12px 16px",
                    "background": "transparent",
                    "border": "none",
                    "cursor": "pointer",
                    "text-align": "left",
                    "font-size": "13px",
                    "font-weight": "600",
                    "color": "#262730",
                    "justify-content": "flex-start",
                }
            )

        # Content (shown only when open)
        if is_open.value:
            with solara.Column(style={"padding": "0 16px 16px", "gap": "12px"}):
                # ====== 1. COVERAGE BREAKDOWN ======
                coverage_html = f'''
                    <div style="background: #f0f2f6; border-radius: 8px; padding: 12px;">
                        <div style="font-size: 11px; font-weight: 600; color: #374151; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">
                            Training Coverage ({total} schools)
                        </div>
                        <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                            <div style="flex: 1; background: white; border-radius: 4px; padding: 8px; text-align: center;">
                                <div style="font-size: 18px; font-weight: 700; color: #6B9080;">{complete_pct}%</div>
                                <div style="font-size: 10px; color: #6b7280;">Complete ({complete})</div>
                            </div>
                            <div style="flex: 1; background: white; border-radius: 4px; padding: 8px; text-align: center;">
                                <div style="font-size: 18px; font-weight: 700; color: #D4A574;">{fund_pct}%</div>
                                <div style="font-size: 10px; color: #6b7280;">Fundamentals ({fund_only})</div>
                            </div>
                            <div style="flex: 1; background: white; border-radius: 4px; padding: 8px; text-align: center;">
                                <div style="font-size: 18px; font-weight: 700; color: #B87D7D;">{untrained_pct}%</div>
                                <div style="font-size: 10px; color: #6b7280;">Untrained ({untrained})</div>
                            </div>
                        </div>
                    </div>
                '''
                solara.HTML(unsafe_innerHTML=coverage_html)

                # ====== 2. VULNERABILITY DISTRIBUTION ======
                vuln_html = f'''
                    <div style="background: #f0f2f6; border-radius: 8px; padding: 12px;">
                        <div style="font-size: 11px; font-weight: 600; color: #374151; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">
                            Vulnerability Distribution
                        </div>
                        <div style="font-size: 12px; margin-bottom: 4px;">
                            <span style="color: #dc2626; font-weight: 600;">🔴 High STH (≥15%):</span> {high_sth_count} schools
                            <span style="color: #9ca3af; margin-left: 8px;">avg: {avg_sth:.1f}%</span>
                        </div>
                        <div style="font-size: 12px;">
                            <span style="color: #2563eb; font-weight: 600;">🔵 High ENI (≥74%):</span> {high_eni_count} schools
                            <span style="color: #9ca3af; margin-left: 8px;">avg: {avg_eni:.0f}%</span>
                        </div>
                    </div>
                '''
                solara.HTML(unsafe_innerHTML=vuln_html)

                # ====== 3. PRIORITY TARGETING LIST ======
                if len(priority_schools) > 0:
                    priority_html = f'''
                        <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px;">
                            <div style="font-size: 11px; font-weight: 600; color: #991b1b; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">
                                ⚠️ Priority Schools ({len(priority_schools)} high-need + untrained)
                            </div>
                    '''

                    # Group by superintendent
                    supt_col = 'superintendent' if 'superintendent' in priority_schools.columns else 'superintendent_name'
                    if supt_col in priority_schools.columns:
                        for supt, group in priority_schools.groupby(supt_col):
                            supt_display = supt if pd.notna(supt) and supt else 'Unknown'
                            priority_html += f'''
                                <div style="margin-bottom: 8px;">
                                    <div style="font-size: 11px; font-weight: 600; color: #374151; margin-bottom: 4px;">
                                        📋 {supt_display} ({len(group)} schools)
                                    </div>
                            '''
                            # Show top 5 schools per superintendent
                            for _, school in group.head(5).iterrows():
                                sth_val = school.get('sth_pct', 0)
                                eni_val = school.get('eni_score', 0) * 100 if 'eni_score' in school.index else 0
                                priority_html += f'''
                                    <div style="font-size: 10px; color: #4b5563; padding-left: 12px; margin-top: 2px;">
                                        {school['school_name'][:40]}...
                                        <span style="color: #dc2626; font-size: 9px;">
                                            STH: {sth_val:.0f}% · ENI: {eni_val:.0f}%
                                        </span>
                                    </div>
                                '''
                            if len(group) > 5:
                                priority_html += f'''
                                    <div style="font-size: 9px; color: #9ca3af; padding-left: 12px; margin-top: 2px;">
                                        ... and {len(group) - 5} more
                                    </div>
                                '''
                            priority_html += '</div>'
                    else:
                        # No superintendent column - just list schools
                        for _, school in priority_schools.head(10).iterrows():
                            sth_val = school.get('sth_pct', 0)
                            eni_val = school.get('eni_score', 0) * 100 if 'eni_score' in school.index else 0
                            priority_html += f'''
                                <div style="font-size: 10px; color: #4b5563; margin-top: 2px;">
                                    {school['school_name'][:45]}...
                                    <span style="color: #dc2626; font-size: 9px;">
                                        STH: {sth_val:.0f}% · ENI: {eni_val:.0f}%
                                    </span>
                                </div>
                            '''

                    priority_html += '</div>'
                    solara.HTML(unsafe_innerHTML=priority_html)
                else:
                    solara.HTML(unsafe_innerHTML='''
                        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px;">
                            <div style="font-size: 12px; color: #166534;">
                                ✅ No high-need untrained schools in this selection
                            </div>
                        </div>
                    ''')

                # ====== 4. EXPORT FUNCTIONALITY ======
                # Prepare export data
                export_df = priority_schools if not priority_schools.empty else df_filtered

                # Select columns for export
                export_cols = ['school_dbn', 'school_name', 'borough', 'district', 'training_status']
                if 'superintendent' in export_df.columns:
                    export_cols.append('superintendent')
                if 'sth_pct' in export_df.columns:
                    export_cols.append('sth_pct')
                if 'eni_score' in export_df.columns:
                    export_cols.append('eni_score')

                export_data = export_df[[c for c in export_cols if c in export_df.columns]].copy()

                # Generate CSV content
                csv_buffer = io.StringIO()
                export_data.to_csv(csv_buffer, index=False)
                csv_content = csv_buffer.getvalue()

                # Generate filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                csv_filename = f"priority_schools_{timestamp}.csv"

                # Export section with extra bottom padding to ensure full visibility when scrolling
                with solara.Row(gap="8px", style={"margin-top": "8px", "padding-bottom": "24px"}):
                    # CSV Download using Solara FileDownload
                    solara.FileDownload(
                        data=csv_content.encode('utf-8'),
                        filename=csv_filename,
                        label="📥 Export CSV",
                    )

                    # Excel export (requires openpyxl, fallback to CSV if not available)
                    try:
                        excel_buffer = io.BytesIO()
                        export_data.to_excel(excel_buffer, index=False, engine='openpyxl')
                        excel_content = excel_buffer.getvalue()
                        excel_filename = f"priority_schools_{timestamp}.xlsx"

                        solara.FileDownload(
                            data=excel_content,
                            filename=excel_filename,
                            label="📊 Export Excel",
                        )
                    except Exception:
                        # openpyxl not available, skip Excel export
                        pass


# ============================================================================
# ACTIVE FILTERS BAR COMPONENT
# ============================================================================

@solara.component
def ActiveFiltersBar(
    borough_filter: solara.Reactive[str],
    district_filter: solara.Reactive[str],
    superintendent_filter: solara.Reactive[str],
    sth_filter: solara.Reactive[bool],
    eni_filter: solara.Reactive[bool],
    mode: solara.Reactive[str],
    total_count: int,
    filtered_count: int,
    on_clear_all: callable
):
    """Secondary row below toolbar showing active filters as removable pills + count."""

    # Check if any filters are active
    has_active = (
        borough_filter.value != "All Boroughs" or
        district_filter.value != "All Districts" or
        superintendent_filter.value != "All Superintendents" or
        sth_filter.value or
        eni_filter.value or
        mode.value != "All Schools"
    )

    if not has_active:
        return  # Don't render anything

    # Calculate percentage
    pct = round(filtered_count / total_count * 100, 1) if total_count > 0 else 0

    bar_style = {
        "background": "#fafafa",
        "border-bottom": "1px solid #e5e7eb",
        "padding": "6px 16px",
        "display": "flex",
        "align-items": "center",
        "gap": "8px",
        "flex-wrap": "wrap",
    }

    with solara.Row(style=bar_style):
        # Count badge (shows filtered count / percentage)
        solara.HTML(unsafe_innerHTML=f'''
            <div style="
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 10px;
                background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                border: 1px solid #90caf9;
                border-radius: 16px;
                font-size: 11px;
                color: #1565c0;
                font-weight: 600;
            ">
                <span>{filtered_count} schools</span>
                <span style="
                    background: #1976d2;
                    color: white;
                    padding: 1px 6px;
                    border-radius: 8px;
                    font-size: 10px;
                ">{pct}%</span>
            </div>
        ''')

        # Borough pill
        if borough_filter.value != "All Boroughs":
            solara.Button(
                label=f"📍 {borough_filter.value} ×",
                on_click=lambda: borough_filter.set("All Boroughs"),
                style={
                    "padding": "4px 10px",
                    "border-radius": "16px",
                    "font-size": "12px",
                    "font-weight": "500",
                    "background": "white",
                    "border": "1px solid #e5e7eb",
                    "color": "#262730",
                }
            )

        # District pill
        if district_filter.value != "All Districts":
            solara.Button(
                label=f"🏫 {district_filter.value} ×",
                on_click=lambda: district_filter.set("All Districts"),
                style={
                    "padding": "4px 10px",
                    "border-radius": "16px",
                    "font-size": "12px",
                    "font-weight": "500",
                    "background": "white",
                    "border": "1px solid #e5e7eb",
                    "color": "#262730",
                }
            )

        # Superintendent pill
        if superintendent_filter.value != "All Superintendents":
            # Truncate long names for pill display
            supt_name = superintendent_filter.value
            if len(supt_name) > 12:
                supt_name = supt_name.split()[-1][:10] + "..."  # Show last name truncated
            solara.Button(
                label=f"👤 {supt_name} ×",
                on_click=lambda: superintendent_filter.set("All Superintendents"),
                style={
                    "padding": "4px 10px",
                    "border-radius": "16px",
                    "font-size": "12px",
                    "font-weight": "500",
                    "background": "white",
                    "border": "1px solid #e5e7eb",
                    "color": "#262730",
                }
            )

        # Note: Mode (Trained/Untrained) does NOT get a pill - it's a view filter in the sidebar,
        # not a geographic filter. It only affects which markers are visible on the map.

        # STH pill
        if sth_filter.value:
            solara.Button(
                label="● STH ≥30% ×",
                on_click=lambda: sth_filter.set(False),
                style={
                    "padding": "4px 10px",
                    "border-radius": "16px",
                    "font-size": "12px",
                    "font-weight": "500",
                    "background": "rgba(255, 100, 100, 0.1)",
                    "border": "1px solid #ff6464",
                    "color": "#ff6464",
                }
            )

        # ENI pill
        if eni_filter.value:
            solara.Button(
                label="● ENI ≥85% ×",
                on_click=lambda: eni_filter.set(False),
                style={
                    "padding": "4px 10px",
                    "border-radius": "16px",
                    "font-size": "12px",
                    "font-weight": "500",
                    "background": "rgba(0, 220, 220, 0.1)",
                    "border": "1px solid #00dcdc",
                    "color": "#00a8a8",
                }
            )

        # Spacer
        solara.HTML(unsafe_innerHTML="<div style='flex-grow: 1;'></div>")

        # Clear all button
        solara.Button(
            label="Clear all",
            on_click=on_clear_all,
            style={
                "padding": "4px 12px",
                "border-radius": "16px",
                "font-size": "12px",
                "font-weight": "500",
                "background": "transparent",
                "border": "1px solid #e5e7eb",
                "color": "#6b7280",
            }
        )


# ============================================================================
# FILTER SUMMARY CHIP COMPONENT
# ============================================================================

@solara.component
def FilterSummaryChip(
    borough: str,
    district: str,
    mode: str,
    total_count: int,
    filtered_count: int
):
    """Blue chip above map showing active GEOGRAPHIC filter summary + count.

    Note: mode (Trained/Untrained) is NOT a geographic filter - it only affects
    which markers are shown, not the geographic scope. The chip should only
    appear when borough/district filters narrow the geographic area.
    """

    # Build filter text (geographic filters only)
    parts = []
    if borough != "All Boroughs":
        parts.append(borough)
    if district != "All Districts":
        parts.append(district.replace("District ", "D"))

    # Don't render if no GEOGRAPHIC filters active (mode doesn't count)
    if not parts:
        return

    filter_text = " • ".join(parts)

    pct = round(filtered_count / total_count * 100, 1) if total_count > 0 else 0

    solara.HTML(unsafe_innerHTML=f"""
        <div style="
            display: flex;
            justify-content: flex-end;
            padding: 8px 16px;
            background: transparent;
        ">
            <div style="
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 12px;
                background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                border: 1px solid #90caf9;
                border-radius: 16px;
                font-size: 12px;
                color: #1565c0;
            ">
                <span style="font-weight: 500;">🔍 {filter_text}</span>
                <span style="
                    background: #1976d2;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-weight: 600;
                    font-size: 11px;
                ">{filtered_count} ({pct}%)</span>
            </div>
        </div>
    """)


# ============================================================================
# MAP COMPONENT
# ============================================================================

def create_school_markers(
    df_mappable: pd.DataFrame,
    selected_school_setter: callable,
    fundamentals_enabled: bool,
    lights_enabled: bool,
    sth_active: bool,
    eni_active: bool,
    show_gaps: bool = False,
    show_offices: bool = False,  # Show/hide district superintendent offices
) -> list:
    """
    Creates a list of ipyleaflet.CircleMarker INSTANCES (not Elements).

    CRITICAL: We use imperative widget creation so we can call .on_click() method.
    The .element() declarative pattern doesn't support method-based event registration
    because on_click is a METHOD, not a traitlet.

    Reference: Gemini research on Solara + ipyleaflet click handling patterns.
    See: outputs/geographic-dashboard/solara-prototype/Solara ipyleaflet Click Handler Research.MD

    Args:
        df_mappable: DataFrame of schools with valid lat/lon
        selected_school_setter: Callable to update selected_school reactive state
        fundamentals_enabled: Whether Fundamentals layer is visible
        lights_enabled: Whether LIGHTS layer is visible
        sth_active: Whether STH highlight is active
        eni_active: Whether ENI highlight is active
        show_gaps: Whether to show gaps (untrained schools as hollow circles)

    Returns:
        List of ipyleaflet.CircleMarker widget instances with click handlers attached
    """
    import ipyleaflet

    markers = []

    # Filter out district offices if show_offices is False
    # District offices have is_office=True (added by data_loader.py)
    if not show_offices and 'is_office' in df_mappable.columns:
        df_to_render = df_mappable[~df_mappable['is_office']]
    else:
        df_to_render = df_mappable

    # Factory function to capture DBN by value (avoids Python closure trap)
    def make_click_handler(dbn: str):
        def on_click_callback(**kwargs):
            # kwargs contains 'coordinates', 'type', etc. from Leaflet
            logger.info(f"Marker clicked: {dbn}")
            selected_school_setter(dbn)
        return on_click_callback

    for _, row in df_to_render.iterrows():
        # Check if this is a district office (for special styling)
        is_office = row.get('is_office', False) if 'is_office' in row.index else False

        # Compute visual properties based on layer/highlight/gaps state
        props = compute_marker_properties(
            row,
            fundamentals_enabled=fundamentals_enabled,
            lights_enabled=lights_enabled,
            sth_highlight=sth_active,
            eni_highlight=eni_active,
            show_gaps=show_gaps,
        )

        if not props.get('visible', True):
            continue

        # Override styling for district offices - use light straw color to distinguish from schools
        # Keep computed radius for responsive sizing based on participant count
        if is_office:
            props['fill_color'] = '#F5DEB3'  # Wheat/light straw color
            props['border_color'] = '#8B7355'  # Dark tan border
            props['fill_opacity'] = 0.9
            props['weight'] = 1  # Thinner outline

        dbn = row['school_dbn']

        # Get weight from props (defaults to 1, but 2.5 for hollow gap circles)
        weight = props.get('weight', 1)

        # Create IMPERATIVE widget instance (NOT .element()!)
        marker = ipyleaflet.CircleMarker(
            location=(row['latitude'], row['longitude']),
            radius=props['radius'],
            color=props['border_color'],
            fill_color=props['fill_color'],
            fill_opacity=props['fill_opacity'],
            weight=weight,
        )

        # Store DBN on marker for potential highlighting later
        marker._school_dbn = dbn

        # Attach handler using METHOD call (this is why .element() didn't work!)
        marker.on_click(make_click_handler(dbn))

        # Track if this is a gap marker for z-ordering
        marker._is_gap = (props.get('fill_opacity', 1) == 0)

        markers.append(marker)

    # Sort markers so gaps (hollow circles) render LAST (on top)
    # This ensures gaps are visible even when co-located with trained schools
    if show_gaps:
        markers.sort(key=lambda m: m._is_gap)  # False (solid) first, True (gaps) last

    logger.info(f"Created {len(markers)} markers with click handlers")
    return markers


@solara.component
def SchoolMap(
    df: pd.DataFrame,
    selected_school: solara.Reactive[str],
    map_center: solara.Reactive[tuple],  # Reactive center for two-way binding
    map_zoom: solara.Reactive[int],      # Reactive zoom for two-way binding
    view_mode: str = "School Points",
    on_view_mode_change: callable = None,
    sth_active: bool = False,
    eni_active: bool = False,
    # Multi-layer parameters
    fundamentals_enabled: bool = True,
    lights_enabled: bool = True,
    show_gaps: bool = False,
    show_offices: bool = False,  # Show/hide 32 district superintendent offices
    on_fund_change: callable = None,
    on_lights_change: callable = None,
    on_sth_change: callable = None,
    on_eni_change: callable = None,
):
    """Map with multi-layer training visualization and legend overlay.

    Uses IMPERATIVE marker creation with .on_click() method calls for click handling.
    The .element() pattern doesn't support method-based event registration because
    on_click is a METHOD, not a traitlet.

    Supports two view modes:
    - "School Points": CircleMarkers with depth encoding (color + size by participant count)
    - "District Choropleth": GeoJSON layer with district boundaries colored by coverage

    Multi-layer system:
    - Fundamentals layer (blue gradient) - toggleable
    - LIGHTS layer (purple gradient) - toggleable
    - STH/ENI highlight mode - fades non-matching schools

    Legend is dynamic and shows active layers and indicators.
    """
    import ipyleaflet

    # Filter to mappable schools (valid lat/lon)
    df_mappable = df[df['latitude'].notna() & df['longitude'].notna()]

    # ==========================================================================
    # MEMOIZED MARKER CREATION - Critical for performance and click handler persistence
    # ==========================================================================
    # We use solara.use_memo to:
    # 1. Avoid recreating 1,679 markers on every render (performance)
    # 2. Preserve attached .on_click() handlers across renders (functionality)
    #
    # Dependencies list ensures markers ARE recreated when visual properties change
    # (filters, layer toggles) - this is acceptable as it only happens on user action.
    # ==========================================================================
    marker_layers = solara.use_memo(
        lambda: create_school_markers(
            df_mappable,
            selected_school.set,
            fundamentals_enabled,
            lights_enabled,
            sth_active,
            eni_active,
            show_gaps,
            show_offices,  # Filter district offices when False
        ) if view_mode == "School Points" else [],
        dependencies=[
            len(df_mappable),  # Recreate if filtered data changes
            view_mode,
            fundamentals_enabled,
            lights_enabled,
            sth_active,
            eni_active,
            show_gaps,
            show_offices,  # Recreate when offices toggle changes
        ]
    )

    # ==========================================================================
    # SELECTION HIGHLIGHTING - Update marker styles when selection changes
    # ==========================================================================
    # This effect runs whenever selected_school changes, updating the visual
    # appearance of markers to highlight the selected school.
    # ==========================================================================
    def update_marker_highlight():
        """Update marker styles to highlight the selected school."""
        selected_dbn = selected_school.value

        for marker in marker_layers:
            marker_dbn = getattr(marker, '_school_dbn', None)
            original_color = getattr(marker, '_original_fill_color', marker.fill_color)
            original_border = getattr(marker, '_original_color', marker.color)
            original_radius = getattr(marker, '_original_radius', marker.radius)

            # Store original values if not already stored
            if not hasattr(marker, '_original_fill_color'):
                marker._original_fill_color = marker.fill_color
                marker._original_color = marker.color
                marker._original_radius = marker.radius

            if marker_dbn == selected_dbn:
                # HIGHLIGHT: Selected marker - bright yellow/gold with black border
                # Distinct from STH (red), ENI (cyan), Fundamentals (blue), LIGHTS (purple)
                marker.fill_color = '#FFD700'   # Gold fill
                marker.color = '#000000'        # Black border for maximum contrast
                marker.radius = max(original_radius + 4, 12)  # Larger
                marker.weight = 3               # Thicker border
                marker.fill_opacity = 1.0       # Fully opaque
            else:
                # RESET: Restore original style
                marker.fill_color = marker._original_fill_color
                marker.color = marker._original_color
                marker.radius = marker._original_radius
                marker.weight = 1
                marker.fill_opacity = 0.8

    # Run the highlight update as a side effect when selection changes
    solara.use_effect(
        update_marker_highlight,
        dependencies=[selected_school.value]
    )

    # ==========================================================================
    # SINGLETON POPUP - Shows school name when marker clicked
    # ==========================================================================
    # Create ONE popup instance (memoized) and update it imperatively via use_effect.
    # This avoids infinite render loops that occur when creating popups in render body.
    # Pattern: Create once → update via traitlet changes → no identity change → no loop
    # ==========================================================================
    import ipywidgets

    def create_popup():
        """Factory for singleton popup - created once, reused."""
        label_widget = ipywidgets.HTML(
            value="",
            layout=ipywidgets.Layout(min_width="150px")
        )
        popup = ipyleaflet.Popup(
            location=(0, 0),
            child=label_widget,
            close_button=False,
            auto_close=False,
            close_on_escape_key=False,
            auto_pan=True,
            max_width=300,
        )
        return popup, label_widget

    popup_layer, popup_content = solara.use_memo(create_popup, dependencies=[])

    # Update popup when selection changes
    def update_popup():
        """Update popup location and content based on selection."""
        school_dbn = selected_school.value

        if not school_dbn:
            # No selection - hide popup by moving off-screen and clearing content
            popup_content.value = ""
            popup_layer.location = (0, 0)
            return

        # Find school data
        school_row = df[df['school_dbn'] == school_dbn]
        if school_row.empty:
            popup_content.value = ""
            popup_layer.location = (0, 0)
            return

        school = school_row.iloc[0]

        # Update popup content (school name - simple identifier)
        popup_content.value = f"<b style='font-size: 13px;'>{school['school_name']}</b>"

        # Move popup to school location
        popup_layer.location = (school['latitude'], school['longitude'])

    solara.use_effect(update_popup, dependencies=[selected_school.value])

    # ==========================================================================
    # SINGLETON LEGEND CONTROL - Uses WidgetControl to avoid clipping during zoom
    # ==========================================================================
    # The legend is placed inside Leaflet's protected control container via WidgetControl.
    # This avoids the clipping issue caused by overflow:hidden on the map container.
    # Pattern: Create widget once → update value via use_effect → control stays stable
    # ==========================================================================

    def create_legend_control():
        """Factory for singleton legend control - created once, reused."""
        legend_widget = ipywidgets.HTML(
            value="",  # Will be updated via use_effect
            layout=ipywidgets.Layout(min_width="180px")
        )
        control = ipyleaflet.WidgetControl(
            widget=legend_widget,
            position='topright'  # Changed from bottomright to prevent overflow below map
        )
        return control, legend_widget

    legend_control, legend_widget = solara.use_memo(create_legend_control, dependencies=[])

    # Update legend content when view mode or layer toggles change
    def update_legend_content():
        """Update legend HTML content based on current state."""
        # max-height ensures legend doesn't extend beyond map bounds; overflow allows scrolling
        if view_mode == "District Choropleth":
            # Determine training type and colors based on toggle state
            if lights_enabled and not fundamentals_enabled:
                training_label = "LIGHTS Coverage"
                # Purple gradient (dark to light for high to low)
                color_very_high = "#4a2369"  # ≥80%
                color_high = "#6a3480"       # 60-79%
                color_med = "#9C66B2"        # 40-59%
                color_low = "#c7a8d6"        # 20-39%
                color_very_low = "#ebe1f0"   # <20%
            else:
                training_label = "Fundamentals Coverage"
                # Blue gradient (current colors)
                color_very_high = "#1F5284"  # ≥80%
                color_high = "#2D64A0"       # 60-79%
                color_med = "#4183C4"        # 40-59%
                color_low = "#93BAE1"        # 20-39%
                color_very_low = "#DCE6F0"   # <20%

            html = f"""
            <div style="padding: 12px 12px 16px 12px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;
                        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                        min-width: 180px; max-height: 400px; overflow-y: auto;">
                <div style="font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">
                    {training_label}
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
                        <span style="width: 20px; height: 12px; background: {color_very_high}; flex-shrink: 0;"></span>
                        ≥80%
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
                        <span style="width: 20px; height: 12px; background: {color_high}; flex-shrink: 0;"></span>
                        60-79%
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
                        <span style="width: 20px; height: 12px; background: {color_med}; flex-shrink: 0;"></span>
                        40-59%
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
                        <span style="width: 20px; height: 12px; background: {color_low}; flex-shrink: 0;"></span>
                        20-39%
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 11px;">
                        <span style="width: 20px; height: 12px; background: {color_very_low}; flex-shrink: 0;"></span>
                        &lt;20%
                    </div>
                </div>
            </div>
            """
        else:
            # School points legend - dynamic multi-layer with depth encoding
            layer_sections = ""

            if fundamentals_enabled:
                layer_sections += """
                <div style="margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #4183C4;"></span>
                        <span style="font-size: 11px; font-weight: 500;">Fundamentals</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 4px; margin-left: 16px;">
                        <span style="width: 6px; height: 6px; border-radius: 50%; background: #93bae1;"></span>
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #4183C4;"></span>
                        <span style="width: 14px; height: 14px; border-radius: 50%; background: #1f5284;"></span>
                        <span style="font-size: 9px; color: #9ca3af; margin-left: 4px;">1-5 / 6-20 / 20+</span>
                    </div>
                </div>"""

            if lights_enabled:
                layer_sections += """
                <div style="margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #9C66B2;"></span>
                        <span style="font-size: 11px; font-weight: 500;">LIGHTS ToT</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 4px; margin-left: 16px;">
                        <span style="width: 6px; height: 6px; border-radius: 50%; background: #c7a8d6;"></span>
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #9C66B2;"></span>
                        <span style="width: 14px; height: 14px; border-radius: 50%; background: #6a3480;"></span>
                        <span style="font-size: 9px; color: #9ca3af; margin-left: 4px;">1-3 / 4-10 / 10+</span>
                    </div>
                </div>"""

            if not fundamentals_enabled and not lights_enabled:
                layer_sections = """
                <div style="font-size: 11px; color: #9ca3af; font-style: italic;">
                    No layers enabled
                </div>"""

            # Add gaps mode indicator
            gaps_section = ""
            if show_gaps:
                gaps_section = """
                <div style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;">
                    <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
                        Gaps Mode
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        <div style="display: flex; align-items: center; gap: 6px; font-size: 11px;">
                            <span style="width: 12px; height: 12px; border-radius: 50%; border: 2px solid #4183C4; background: transparent;"></span>
                            Missing training
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px; font-size: 11px;">
                            <span style="width: 10px; height: 10px; border-radius: 50%; background: #b0b0b0; opacity: 0.4;"></span>
                            Has training
                        </div>
                    </div>
                </div>"""

            highlight_section = ""
            if sth_active or eni_active:
                highlight_items = ""
                if sth_active:
                    highlight_items += """
                    <div style="display: flex; align-items: center; gap: 6px; font-size: 11px;">
                        <span style="width: 12px; height: 12px; border-radius: 50%; background: #ff6464;"></span>
                        STH ≥15%
                    </div>"""
                if eni_active:
                    highlight_items += """
                    <div style="display: flex; align-items: center; gap: 6px; font-size: 11px;">
                        <span style="width: 12px; height: 12px; border-radius: 50%; background: #00dcdc;"></span>
                        ENI ≥74%
                    </div>"""

                highlight_section = f"""
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                    <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
                        Highlighted
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        {highlight_items}
                    </div>
                </div>"""

            html = f"""
            <div style="padding: 12px 12px 16px 12px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;
                        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                        min-width: 180px; max-height: 400px; overflow-y: auto;">
                <div style="font-size: 10px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">
                    Training Layers
                </div>
                {layer_sections}
                {gaps_section}
                {highlight_section}
            </div>
            """

        legend_widget.value = html

    solara.use_effect(
        update_legend_content,
        dependencies=[view_mode, fundamentals_enabled, lights_enabled, sth_active, eni_active, show_gaps]
    )

    # Build Choropleth layer for district view
    # Using ipyleaflet.Choropleth which is designed for this use case
    # (GeoJSON with style_callback doesn't work reliably with Solara's .element() pattern)
    choropleth_layers = []
    if view_mode == "District Choropleth":
        raw_geojson = load_district_geojson()
        if raw_geojson is not None:
            # Determine which training type to show based on toggle state
            # In choropleth mode, only one toggle should be active (mutual exclusivity)
            if lights_enabled and not fundamentals_enabled:
                training_type = 'lights'
            else:
                training_type = 'fundamentals'  # Default to Fundamentals

            # Aggregate school data by district for selected training type
            district_stats = aggregate_by_district(df, training_type=training_type)

            # Build choro_data dict: {district_number: coverage_pct}
            choro_data = {}
            for _, row in district_stats.iterrows():
                try:
                    district_num = int(row['district'])
                    choro_data[district_num] = float(row['coverage_pct'])
                except (ValueError, TypeError):
                    continue

            # IMPORTANT: ipyleaflet Choropleth does direct key access: feature[key_on]
            # It does NOT parse nested paths like 'properties.SchoolDist'
            # Solution: Modify GeoJSON to set feature['id'] = SchoolDist, then use key_on='id'
            import copy
            modified_geojson = copy.deepcopy(raw_geojson)
            for feature in modified_geojson.get('features', []):
                district_num = feature.get('properties', {}).get('SchoolDist')
                if district_num is not None:
                    feature['id'] = int(district_num)

            # Select colormap based on training type
            # Blues_09 for Fundamentals, Purples_09 for LIGHTS
            colormap = linear.Purples_09 if training_type == 'lights' else linear.Blues_09

            choropleth_layer = ipyleaflet.Choropleth.element(
                geo_data=modified_geojson,
                choro_data=choro_data,
                colormap=colormap,
                key_on='id',
                value_min=0,
                value_max=100,
                border_color='#666666',
                style={'fillOpacity': 0.7, 'weight': 1}
            )
            choropleth_layers.append(choropleth_layer)

    # Basemap tile layer - use build_url() to resolve placeholders like {s}, {variant}
    basemap = ipyleaflet.basemaps.CartoDB.Positron
    tile_url = basemap.build_url()
    tile_layer = ipyleaflet.TileLayer.element(url=tile_url)

    # Combine all layers
    # NOTE: popup_layer is handled separately via use_effect to avoid render issues
    all_layers = [tile_layer] + choropleth_layers + marker_layers

    # Create zoom control element (topleft to avoid overlapping with legend in topright)
    zoom_control = ipyleaflet.ZoomControl.element(position='topleft')

    # ==========================================================================
    # HOME BUTTON CONTROL - Resets map to default NYC view
    # ==========================================================================
    # Uses ipywidgets.Button wrapped in WidgetControl to integrate with Leaflet's
    # control system. Positioned at topleft, below the zoom control.
    # ==========================================================================
    def create_home_control():
        """Factory for home button control - created once, reused."""
        home_btn = ipywidgets.Button(
            description='',
            icon='home',
            tooltip='Reset to NYC view',
            layout=ipywidgets.Layout(width='30px', height='30px', padding='0')
        )
        home_btn.style.button_color = 'white'
        home_btn.style.font_weight = 'bold'

        def on_home_click(b):
            map_center.set((40.7128, -73.89))  # NYC 5-borough center
            map_zoom.set(11)  # Default zoom level

        home_btn.on_click(on_home_click)

        control = ipyleaflet.WidgetControl(
            widget=home_btn,
            position='topleft'  # Same position as zoom - Leaflet stacks them vertically
        )
        return control

    home_control = solara.use_memo(create_home_control, dependencies=[])

    # Create the Map using .element() for proper Solara reactive binding
    # on_center and on_zoom enable two-way binding - updates flow both directions
    # NOTE: zoom_control=False disables the default zoom control - we add our own explicitly
    map_element = ipyleaflet.Map.element(
        center=map_center.value,
        on_center=map_center.set,
        zoom=map_zoom.value,
        on_zoom=map_zoom.set,
        scroll_wheel_zoom=True,
        zoom_control=False,  # Disable default - we add our own in controls list
        layout=Layout(width='100%', height='calc(100vh - 56px)'),
        layers=all_layers,
        controls=[zoom_control, home_control, legend_control],
    )

    # ==========================================================================
    # LAYOUT: Map with view toggle overlay
    # ==========================================================================
    # Legend is now rendered via WidgetControl (see singleton pattern above)
    # which places it in Leaflet's protected control container, avoiding clipping.
    # ==========================================================================
    with solara.Column(style={"position": "relative", "width": "100%", "height": "100%"}):
        # The map element (includes zoom, home, and legend controls via controls parameter)
        map_element

        # View toggle overlay - positioned bottom-left (only if callback provided)
        if on_view_mode_change is not None:
            with solara.Row(style={
                "position": "absolute",
                "bottom": "20px",
                "left": "20px",
                "z-index": "1000",
                "background": "white",
                "border-radius": "8px",
                "padding": "4px",
                "box-shadow": "0 2px 4px rgba(0,0,0,0.1)",
                "border": "1px solid #e5e7eb"
            }):
                solara.Button(
                    "📍 Points",
                    on_click=lambda: on_view_mode_change("School Points"),
                    outlined=view_mode != "School Points",
                    color="primary" if view_mode == "School Points" else None,
                    style={"min-width": "90px"}
                )
                solara.Button(
                    "🗺️ Districts",
                    on_click=lambda: on_view_mode_change("District Choropleth"),
                    outlined=view_mode != "District Choropleth",
                    color="primary" if view_mode == "District Choropleth" else None,
                    style={"min-width": "90px"}
                )


# ============================================================================
# LOGIN COMPONENT (for password-protected access)
# ============================================================================

# Session-level authentication state (persists across page renders)
_authenticated = solara.reactive(False)
_auth_error = solara.reactive("")
_is_logging_in = solara.reactive(False)  # Loading state between login and dashboard


@solara.component
def LoadingScreen():
    """
    Elegant loading screen shown while dashboard initializes after login.
    Features a pulsing animation and auto-transitions to dashboard.
    """
    import threading

    # Track if transition has been scheduled
    transition_scheduled, set_transition_scheduled = solara.use_state(False)

    # Schedule transition to dashboard after a brief loading period
    def schedule_transition():
        if not transition_scheduled:
            set_transition_scheduled(True)

            def delayed_transition():
                import time
                time.sleep(2.5)  # Show loading for 2.5 seconds
                _is_logging_in.set(False)  # This triggers re-render to show dashboard

            t = threading.Thread(target=delayed_transition, daemon=True)
            t.start()

    # Schedule transition on mount
    solara.use_effect(schedule_transition, [])

    with solara.Column(
        style={
            "min-height": "100vh",
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "padding": "20px",
        }
    ):
        with solara.Column(
            style={
                "text-align": "center",
                "color": "white",
            }
        ):
            # Animated logo
            solara.HTML(tag="div", unsafe_innerHTML="""
                <style>
                    @keyframes pulse {
                        0%, 100% { transform: scale(1); opacity: 1; }
                        50% { transform: scale(1.1); opacity: 0.8; }
                    }
                    @keyframes spin {
                        from { transform: rotate(0deg); }
                        to { transform: rotate(360deg); }
                    }
                    .loading-logo {
                        font-size: 64px;
                        animation: pulse 2s ease-in-out infinite;
                        margin-bottom: 24px;
                    }
                    .loading-spinner {
                        width: 40px;
                        height: 40px;
                        border: 3px solid rgba(255,255,255,0.3);
                        border-top: 3px solid white;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin: 0 auto 24px auto;
                    }
                    .loading-title {
                        font-size: 24px;
                        font-weight: 600;
                        margin-bottom: 8px;
                        color: white;
                    }
                    .loading-subtitle {
                        font-size: 14px;
                        color: rgba(255,255,255,0.8);
                        margin-bottom: 32px;
                    }
                    .loading-message {
                        font-size: 14px;
                        color: rgba(255,255,255,0.9);
                        min-height: 20px;
                    }
                    @keyframes fadeInOut {
                        0%, 100% { opacity: 0.6; }
                        50% { opacity: 1; }
                    }
                    .loading-dots {
                        display: inline-block;
                        animation: fadeInOut 1.5s ease-in-out infinite;
                    }
                </style>
                <div class="loading-logo">🗺️</div>
                <div class="loading-spinner"></div>
                <div class="loading-title">HTYPE Geographic Dashboard</div>
                <div class="loading-subtitle">NYC Human Trafficking Prevention Education</div>
                <div class="loading-message">Loading dashboard<span class="loading-dots">...</span></div>
            """)


@solara.component
def LoginPage():
    """
    Simple login page with password field.
    Shows when DASHBOARD_PASSWORD is set and user is not authenticated.
    """
    password_input, set_password_input = solara.use_state("")
    is_submitting, set_is_submitting = solara.use_state(False)

    def do_login():
        """Perform login check and update auth state."""
        if is_submitting:
            return  # Prevent double-submit

        set_is_submitting(True)
        logger.info(f"Login attempt with password length: {len(password_input)}")

        if password_input == DASHBOARD_PASSWORD:
            logger.info("Login successful")
            _auth_error.set("")
            _is_logging_in.set(True)  # Show loading screen
            _authenticated.set(True)  # Trigger dashboard load
        else:
            logger.info("Login failed - incorrect password")
            _auth_error.set("Incorrect password. Please try again.")
            set_password_input("")
            set_is_submitting(False)

    # Outer container with gradient background
    with solara.Column(
        style={
            "min-height": "100vh",
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "padding": "20px",
        }
    ):
        # Login card
        with solara.Card(
            style={
                "max-width": "400px",
                "width": "100%",
                "padding": "40px",
                "border-radius": "12px",
                "text-align": "center",
            }
        ):
            # Logo and title
            solara.HTML(tag="div", unsafe_innerHTML="""
                <div style="font-size: 48px; margin-bottom: 8px;">🗺️</div>
                <h1 style="margin: 0 0 8px 0; font-size: 24px; color: #1f2937; font-weight: 600;">
                    HTYPE Geographic Dashboard
                </h1>
                <p style="margin: 0 0 24px 0; color: #6b7280; font-size: 14px;">
                    NYC Human Trafficking Prevention Education
                </p>
            """)

            # Error message
            if _auth_error.value:
                rv.Alert(
                    type="error",
                    dense=True,
                    children=[_auth_error.value],
                    style_="margin-bottom: 16px;",
                )

            # Password field using ipyvuetify for proper binding
            rv.TextField(
                v_model=password_input,
                on_v_model=set_password_input,
                label="Password",
                type="password",
                outlined=True,
                style_="margin-bottom: 16px;",
            )

            # Sign In button - using solara.Button which works reliably
            solara.Button(
                label="Sign In",
                on_click=do_login,
                color="primary",
                style={"width": "100%", "height": "44px"},
            )

            # Footer
            solara.HTML(tag="p", unsafe_innerHTML="""
                <p style="margin: 24px 0 0 0; color: #9ca3af; font-size: 12px;">
                    Access restricted to authorized personnel.
                </p>
            """)


# ============================================================================
# MAIN PAGE - Custom Layout
# ============================================================================

@solara.component
def Page():
    """
    Custom layout matching mockup v2 with full reactive filtering.

    Structure:
    ┌─────────────────────────────────────────────────────────────────────┐
    │ TOOLBAR (white, 56px)                                               │
    ├───────────────────────────────────────┬─────────────────────────────┤
    │ INFO PANEL (360px)                    │ MAP                         │
    │ - Mode tabs (2x2)                     │ (fills remaining space)     │
    │ - Summary stats                       │                             │
    │ - Borough breakdown                   │                             │
    │ - Priority schools                    │                             │
    │ - Selected school                     │                             │
    └───────────────────────────────────────┴─────────────────────────────┘
    """
    # ====== AUTHENTICATION CHECK ======
    # Show loading screen during login transition (after password accepted, before dashboard ready)
    if DASHBOARD_PASSWORD:
        if _is_logging_in.value:
            LoadingScreen()
            return
        if not _authenticated.value:
            LoginPage()
            return

    # ====== MAIN DASHBOARD (authenticated or no password set) ======

    # Reactive state - filters
    mode = solara.use_reactive("All Schools")  # Training status filter: All Schools, Trained, Untrained
    selected_school = solara.use_reactive("")
    borough_filter = solara.use_reactive("All Boroughs")
    district_filter = solara.use_reactive("All Districts")
    superintendent_filter = solara.use_reactive("All Superintendents")
    sth_filter = solara.use_reactive(False)  # STH ≥30% toggle (highlight mode)
    eni_filter = solara.use_reactive(False)  # ENI ≥85% toggle (highlight mode)
    view_mode = solara.use_reactive("School Points")  # School Points or District Choropleth

    # Sidebar mode state (NEW - for redesigned sidebar)
    # Values: "overview" (default), "cluster" (filters active), "school" (marker clicked)
    sidebar_mode = solara.use_reactive("overview")
    previous_sidebar_mode = solara.use_reactive("overview")  # For back navigation

    # Multi-layer training toggles (for depth encoding)
    fundamentals_enabled = solara.use_reactive(True)  # Show Fundamentals layer
    lights_enabled = solara.use_reactive(True)  # Show LIGHTS layer
    show_gaps = solara.use_reactive(False)  # Show Gaps mode: highlight untrained schools as hollow circles
    show_offices = solara.use_reactive(False)  # Show District Offices: 32 superintendent offices (hidden by default)
    search_query = solara.use_reactive("")  # Search box query

    # Handler for training toggle with mutual exclusivity in choropleth mode
    def handle_training_toggle(toggle_type: str, new_value: bool):
        """
        Handle training toggle changes with mutual exclusivity in choropleth mode.

        In 'School Points' mode: Both toggles can be on/off independently
        In 'District Choropleth' mode: Toggles are mutually exclusive (radio behavior)
        """
        if view_mode.value == "District Choropleth":
            # Mutual exclusivity: turning one on turns the other off
            if toggle_type == 'fundamentals' and new_value:
                fundamentals_enabled.set(True)
                lights_enabled.set(False)
            elif toggle_type == 'lights' and new_value:
                fundamentals_enabled.set(False)
                lights_enabled.set(True)
            elif not new_value:
                # Prevent both being off in choropleth mode - keep current one on
                # (do nothing, effectively preventing deselection)
                pass
        else:
            # School Points mode: normal independent toggle behavior
            if toggle_type == 'fundamentals':
                fundamentals_enabled.set(new_value)
            else:
                lights_enabled.set(new_value)

    # Effect to sync toggles when switching TO choropleth mode
    def sync_choropleth_on_mode_change():
        if view_mode.value == "District Choropleth":
            # When entering choropleth mode with both toggles on,
            # default to Fundamentals (turn off LIGHTS)
            if fundamentals_enabled.value and lights_enabled.value:
                lights_enabled.set(False)
            # If only one is on, that's fine
            # If neither is on (shouldn't happen), default to Fundamentals
            elif not fundamentals_enabled.value and not lights_enabled.value:
                fundamentals_enabled.set(True)

    solara.use_effect(sync_choropleth_on_mode_change, dependencies=[view_mode.value])

    # Reactive state - UI controls (responsive)
    sidebar_open = solara.use_reactive(True)  # Sidebar visibility toggle
    overflow_open = solara.use_reactive(False)  # Overflow menu open state

    # Auto-open sidebar when a school is selected (critical for mobile UX)
    def auto_open_sidebar_on_selection():
        if selected_school.value:
            sidebar_open.set(True)
            sidebar_mode.set("school")

    solara.use_effect(auto_open_sidebar_on_selection, dependencies=[selected_school.value])

    # Reactive state - map position (for Locate button)
    # NYC 5-borough center: shifted east from Hudson to show Queens/Brooklyn, less NJ
    map_center = solara.use_reactive((40.7128, -73.89))  # Default: NYC 5-borough center
    map_zoom = solara.use_reactive(11)  # Default zoom

    # Track last applied filter state to avoid re-applying zoom on every render
    # This prevents the map from "freezing" when user tries to manually zoom/pan
    last_filter_key = solara.use_reactive("")  # String key representing current filter state

    # Locate handler - zooms map to school location
    def on_locate(lat: float, lon: float):
        # Set a unique filter key so we don't immediately override with filter bounds
        last_filter_key.set(f"locate:{lat},{lon}")
        map_center.set((lat, lon))
        map_zoom.set(15)  # Zoom in close to see the school

    # Reset function - clears all filters
    def reset_all_filters():
        borough_filter.set("All Boroughs")
        district_filter.set("All Districts")
        superintendent_filter.set("All Superintendents")
        sth_filter.set(False)
        eni_filter.set(False)
        fundamentals_enabled.set(True)  # Reset layer toggles
        lights_enabled.set(True)
        show_gaps.set(False)  # Reset gaps mode
        show_offices.set(False)  # Reset offices visibility
        view_mode.set("School Points")
        mode.set("All Schools")
        selected_school.set("")
        search_query.set("")  # Reset search
        sidebar_mode.set("overview")  # Reset sidebar mode
        previous_sidebar_mode.set("overview")
        last_filter_key.set("reset")  # Mark as reset
        map_center.set((40.7128, -73.89))  # Reset to NYC 5-borough center
        map_zoom.set(11)  # Reset zoom

    # School selection handler - navigates directly to school detail view
    def handle_school_select(dbn: str):
        """Called when user selects a school from autocomplete - navigates to detail view."""
        if not dbn:
            return
        selected_school.set(dbn)
        sidebar_mode.set("school")
        # Clear search query since we're navigating directly
        search_query.set("")
        # Try to zoom to the school if we can find its location
        # (will be handled after df_raw is loaded below)

    # Load raw data
    df_raw = load_school_data()

    # Load participant data for enhanced school details
    participant_df = load_participant_data()

    # Build autocomplete items list for search (all schools)
    # Use dict format: display shows "School Name (DBN)", value stores just DBN
    # This way when user selects, only the DBN is stored in search_query
    school_items = []
    if df_raw is not None and len(df_raw) > 0:
        school_items = [
            {"text": f"{row['school_name']} ({row['school_dbn']})", "value": row['school_dbn']}
            for _, row in df_raw.iterrows()
            if pd.notna(row.get('school_name')) and pd.notna(row.get('school_dbn'))
        ]
        school_items = sorted(school_items, key=lambda x: x['text'])  # Alphabetical order

    # Apply filters to create filtered dataframe
    df = df_raw.copy()

    # Borough filter (case-insensitive - CSV has uppercase, dropdown has title case)
    if borough_filter.value != "All Boroughs":
        df = df[df['borough'].str.upper() == borough_filter.value.upper()]

    # District filter
    if district_filter.value != "All Districts":
        district_num = district_filter.value.replace("D", "").replace("istrict ", "")
        df = df[df['district'] == int(district_num)]

    # Superintendent filter
    if superintendent_filter.value != "All Superintendents" and 'superintendent' in df.columns:
        df = df[df['superintendent'] == superintendent_filter.value]

    # Mode filter - respects active toolbar toggles with AND logic
    # Trained = has ALL active layers; Untrained = missing ANY active layer
    if mode.value == "Trained":
        # Ensure columns exist with defaults
        if 'has_fundamentals' not in df.columns:
            df = df.copy()
            df['has_fundamentals'] = 'No'
        if 'has_lights' not in df.columns:
            df = df.copy()
            df['has_lights'] = 'No'

        fund_on = fundamentals_enabled.value
        lights_on = lights_enabled.value

        if fund_on and lights_on:
            # AND logic: must have BOTH layers
            df = df[(df['has_fundamentals'] == 'Yes') & (df['has_lights'] == 'Yes')]
        elif fund_on:
            # Only Fundamentals toggle active
            df = df[df['has_fundamentals'] == 'Yes']
        elif lights_on:
            # Only LIGHTS toggle active
            df = df[df['has_lights'] == 'Yes']
        # If neither toggle is on, show nothing (edge case)
        else:
            df = df.head(0)

    elif mode.value == "Untrained":
        # Ensure columns exist with defaults
        if 'has_fundamentals' not in df.columns:
            df = df.copy()
            df['has_fundamentals'] = 'No'
        if 'has_lights' not in df.columns:
            df = df.copy()
            df['has_lights'] = 'No'

        fund_on = fundamentals_enabled.value
        lights_on = lights_enabled.value

        if fund_on and lights_on:
            # Missing EITHER layer (not fully trained in both)
            df = df[(df['has_fundamentals'] != 'Yes') | (df['has_lights'] != 'Yes')]
        elif fund_on:
            # Missing Fundamentals
            df = df[df['has_fundamentals'] != 'Yes']
        elif lights_on:
            # Missing LIGHTS
            df = df[df['has_lights'] != 'Yes']
        # If neither toggle is on, show all (nothing to filter by)

    # "All Schools" shows all - no additional filtering

    # Search filter - matches school name or DBN (case-insensitive)
    if search_query.value.strip():
        query = search_query.value.strip().lower()
        df = df[
            df['school_name'].str.lower().str.contains(query, na=False) |
            df['school_dbn'].str.lower().str.contains(query, na=False)
        ]

    # Note: STH/ENI filters would need actual data columns
    # For now they're toggles that could highlight on the map

    # Calculate stats on filtered data AND citywide (for comparison)
    stats = get_stats(df)
    stats_citywide = get_stats(df_raw)

    # Build cluster label for sidebar (describes active filter)
    cluster_parts = []
    if borough_filter.value != "All Boroughs":
        cluster_parts.append(borough_filter.value)
    if district_filter.value != "All Districts":
        cluster_parts.append(district_filter.value)
    if superintendent_filter.value != "All Superintendents":
        # Truncate long superintendent names
        supt_name = superintendent_filter.value
        if len(supt_name) > 25:
            supt_name = supt_name[:22] + "..."
        cluster_parts.append(f"Supt: {supt_name}")
    if mode.value != "All Schools":
        cluster_parts.append(mode.value)
    if search_query.value.strip():
        cluster_parts.append(f'Search: "{search_query.value.strip()[:15]}"')

    cluster_label = " · ".join(cluster_parts) if cluster_parts else "All Schools"

    # ==========================================================================
    # SIDEBAR MODE AUTO-DETECTION
    # ==========================================================================
    # Determines which sidebar view to show based on current state:
    # - "school": A school marker is selected
    # - "cluster": Filters are active (no school selected)
    # - "overview": Default view (no filters, no selection)
    # ==========================================================================

    def update_sidebar_mode():
        """Auto-detect sidebar mode based on selection and filter state."""
        # Check if any geographic/training filters are active
        # Note: mode (All Schools/Trained/Untrained) is NOT a geographic filter
        # It only affects which markers are shown on the map, not the sidebar mode
        has_active_filters = (
            borough_filter.value != "All Boroughs" or
            district_filter.value != "All Districts" or
            superintendent_filter.value != "All Superintendents" or
            search_query.value.strip() != ""
        )

        if selected_school.value:
            # School is selected → switch to school mode
            if sidebar_mode.value != "school":
                previous_sidebar_mode.set(sidebar_mode.value)
                sidebar_mode.set("school")
        elif has_active_filters:
            # Filters active, no school selected → cluster mode
            if sidebar_mode.value != "cluster":
                sidebar_mode.set("cluster")
        else:
            # No filters, no selection → overview mode
            if sidebar_mode.value != "overview":
                sidebar_mode.set("overview")

    # Run mode detection when any relevant state changes
    # Note: mode.value is NOT a dependency - it only affects map filtering, not sidebar mode
    solara.use_effect(
        update_sidebar_mode,
        dependencies=[
            selected_school.value,
            borough_filter.value,
            district_filter.value,
            superintendent_filter.value,
            search_query.value
        ]
    )

    # Handler for "Back" navigation in sidebar
    def handle_sidebar_back():
        """Navigate back from school mode to previous mode."""
        if sidebar_mode.value == "school":
            selected_school.set("")  # Clear selection
            # Mode will auto-switch via use_effect above

    def handle_school_select(school_dbn: str):
        """Handle school selection from sidebar list - navigate to school detail view."""
        if school_dbn:
            selected_school.set(school_dbn)
            sidebar_mode.set("school")

    # Build a unique key representing current GEOGRAPHIC filter state
    # This detects when geographic filters change vs. re-renders from map interaction
    # Note: mode (Trained/Untrained) is NOT included - it doesn't change geographic scope
    current_filter_key = f"{borough_filter.value}|{district_filter.value}|{superintendent_filter.value}|{search_query.value.strip()}"

    # Check if any GEOGRAPHIC filters are active (mode is NOT a geographic filter)
    filters_active = (
        borough_filter.value != "All Boroughs" or
        district_filter.value != "All Districts" or
        superintendent_filter.value != "All Superintendents" or
        search_query.value.strip() != ""
    )

    # Only apply zoom when filter state CHANGES - not on every render
    # This allows user to manually zoom/pan after filter is applied
    if filters_active and current_filter_key != last_filter_key.value:
        # Get schools with valid coordinates
        df_valid = df[df['latitude'].notna() & df['longitude'].notna()]

        if len(df_valid) == 1:
            # Single school - zoom in close
            lat = df_valid.iloc[0]['latitude']
            lon = df_valid.iloc[0]['longitude']
            logger.info(f"[ZOOM] Single school at ({lat:.4f}, {lon:.4f})")
            map_center.set((lat, lon))
            map_zoom.set(16)
            last_filter_key.set(current_filter_key)
        elif len(df_valid) > 1:
            # Multiple schools - calculate center and appropriate zoom
            min_lat = df_valid['latitude'].min()
            max_lat = df_valid['latitude'].max()
            min_lon = df_valid['longitude'].min()
            max_lon = df_valid['longitude'].max()

            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            lat_span = max_lat - min_lat
            lon_span = max_lon - min_lon
            effective_span = max(lat_span, lon_span * 0.76)

            # Calculate zoom level based on span - VERY AGGRESSIVE
            # Goal: Zoom tight enough that filtered points fill most of the viewport
            if effective_span < 0.001:
                new_zoom = 18  # Single block
            elif effective_span < 0.003:
                new_zoom = 17  # Few blocks
            elif effective_span < 0.008:
                new_zoom = 16  # Neighborhood
            elif effective_span < 0.02:
                new_zoom = 15  # Small district
            elif effective_span < 0.05:
                new_zoom = 14  # District (most D## filters)
            elif effective_span < 0.10:
                new_zoom = 13  # Large district
            elif effective_span < 0.18:
                new_zoom = 12  # Borough (D1, Manhattan)
            elif effective_span < 0.30:
                new_zoom = 11  # Large borough (Brooklyn, Queens)
            else:
                new_zoom = 10  # All NYC

            logger.info(f"[ZOOM] {len(df_valid)} schools, center=({center_lat:.4f}, {center_lon:.4f}), zoom={new_zoom}")
            map_center.set((center_lat, center_lon))
            map_zoom.set(new_zoom)
            last_filter_key.set(current_filter_key)

    # Global styles
    solara.HTML(unsafe_innerHTML=GLOBAL_CSS)

    # Open Graph meta tags for URL preview when sharing
    # Image hosted on GitHub raw for reliable access
    OG_IMAGE_URL = "https://raw.githubusercontent.com/upcollective/nyc-htype-geographic-dashboard/solara-stable/solara-prototype/assets/og-preview.png"
    solara.Meta(property="og:title", content="HTYPE Dashboard - NYC Schools")
    solara.Meta(property="og:description", content="Human Trafficking Prevention Education training coverage across 1,647 NYC schools. Geographic analysis and compliance tracking.")
    solara.Meta(property="og:image", content=OG_IMAGE_URL)
    solara.Meta(property="og:url", content="https://htype-geographic-dashboard-386102540093.us-east1.run.app")
    solara.Meta(property="og:type", content="website")
    solara.Meta(name="twitter:card", content="summary_large_image")
    solara.Meta(name="twitter:title", content="HTYPE Dashboard - NYC Schools")
    solara.Meta(name="twitter:description", content="Human Trafficking Prevention Education training coverage across 1,647 NYC schools.")
    solara.Meta(name="twitter:image", content=OG_IMAGE_URL)

    # Get unique superintendent list from data
    superintendent_options = ["All Superintendents"]
    if 'superintendent' in df_raw.columns:
        superintendent_options += sorted(df_raw['superintendent'].dropna().unique().tolist())

    # Main layout - use flexbox for proper height distribution on mobile
    with solara.Column(gap="0px", classes=["main-app-container"], style={"height": "100vh", "display": "flex", "flex-direction": "column", "overflow": "hidden"}):
        # Toolbar row (full width)
        Toolbar(
            borough_filter=borough_filter,
            district_filter=district_filter,
            superintendent_filter=superintendent_filter,
            superintendent_options=superintendent_options,
            sth_filter=sth_filter,
            eni_filter=eni_filter,
            search_query=search_query,
            sidebar_open=sidebar_open,
            overflow_open=overflow_open,
            on_reset=reset_all_filters,
            # Layer toggles
            fundamentals_enabled=fundamentals_enabled,
            lights_enabled=lights_enabled,
            show_gaps=show_gaps,
            show_offices=show_offices,  # Show/hide 32 district superintendent offices
            # View mode and toggle handler for mutual exclusivity in choropleth
            view_mode=view_mode,
            on_training_toggle=handle_training_toggle,
            # Autocomplete items for search
            school_items=school_items,
            on_school_select=handle_school_select,
        )

        # Active Filters Bar (shows only when filters are active)
        ActiveFiltersBar(
            borough_filter=borough_filter,
            district_filter=district_filter,
            superintendent_filter=superintendent_filter,
            sth_filter=sth_filter,
            eni_filter=eni_filter,
            mode=mode,
            total_count=len(df_raw),
            filtered_count=len(df),
            on_clear_all=reset_all_filters
        )

        # Content row (sidebar + map) - flex: 1 fills remaining space after toolbar
        with solara.Row(gap="0px", classes=["content-row"], style={"flex": "1", "min-height": "0", "overflow": "hidden", "position": "relative"}):
            # Left sidebar - REDESIGNED with three modes (Overview, Cluster, School)
            # CSS classes control responsive width; inline style only for non-width properties
            sidebar_classes = ["info-panel-container"]
            if not sidebar_open.value:
                sidebar_classes.append("sidebar-closed")

            with solara.Column(
                classes=sidebar_classes,
                style={
                    "flex-shrink": "0",
                    "border-right": "1px solid #e5e7eb",
                    "height": "100%",  # Parent row handles height calculation
                    "overflow": "hidden",
                    "background": "#ffffff",
                }
            ):
                # Drag handle for bottom sheet (only visible on phones <600px)
                # Uses Solara Button with native on_click - bypasses JavaScript limitations
                solara.Button(
                    label="",  # Empty label, styled via CSS
                    on_click=lambda: sidebar_open.set(False),
                    classes=["bottom-sheet-handle"],
                    style={
                        "width": "100%",
                        "min-height": "28px",
                        "height": "28px",
                        "background": "transparent",
                        "box-shadow": "none",
                        "border": "none",
                        "border-radius": "16px 16px 0 0",
                        "display": "flex",
                        "justify-content": "center",
                        "align-items": "center",
                        "cursor": "pointer",
                        "padding": "0",
                        "margin": "0",
                    }
                )

                SidebarRouter(
                    sidebar_mode=sidebar_mode,
                    stats=stats,
                    stats_citywide=stats_citywide,
                    df_filtered=df,
                    df_raw=df_raw,
                    selected_school=selected_school,
                    participant_df=participant_df,
                    on_back=handle_sidebar_back,
                    on_locate=on_locate,
                    cluster_label=cluster_label,
                    # Unified filtering params
                    show_gaps=show_gaps.value,
                    show_offices=show_offices.value,  # Pass office visibility to sidebar
                    fundamentals_enabled=fundamentals_enabled.value,
                    lights_enabled=lights_enabled.value,
                    # School selection from sidebar list
                    on_school_select=handle_school_select,
                )

            # Map area (fills remaining space)
            with solara.Column(style={"flex": "1", "overflow": "hidden", "position": "relative"}):
                SchoolMap(
                    df,
                    selected_school,
                    map_center=map_center,  # Pass reactive object for two-way binding
                    map_zoom=map_zoom,      # Pass reactive object for two-way binding
                    view_mode=view_mode.value,
                    on_view_mode_change=lambda mode: view_mode.set(mode),
                    sth_active=sth_filter.value,
                    eni_active=eni_filter.value,
                    # Multi-layer parameters (controlled via InfoPanel)
                    fundamentals_enabled=fundamentals_enabled.value,
                    lights_enabled=lights_enabled.value,
                    show_gaps=show_gaps.value,
                    show_offices=show_offices.value,  # Show/hide district superintendent offices
                )
