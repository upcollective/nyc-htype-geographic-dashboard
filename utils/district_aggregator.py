"""
District-level aggregation utilities for choropleth visualization.

Aggregates school-level training data to district boundaries for
geographic pattern visualization.
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_district_geojson(geo_path: Optional[Path] = None) -> dict:
    """
    Load NYC School Districts GeoJSON boundaries.

    Args:
        geo_path: Path to GeoJSON file (defaults to data/geo/)

    Returns:
        GeoJSON dict with district polygons
    """
    if geo_path is None:
        geo_path = Path(__file__).parent.parent / 'data' / 'geo' / 'nyc_school_districts.geojson'

    if not geo_path.exists():
        raise FileNotFoundError(f"District GeoJSON not found: {geo_path}")

    with open(geo_path, 'r') as f:
        return json.load(f)


def aggregate_by_district(
    df: pd.DataFrame,
    layer_type: str = 'fundamentals',
    layer_filter_config: dict = None
) -> pd.DataFrame:
    """
    Aggregate school training data by district.

    Respects filter settings:
    - "All Schools": Shows all schools, calculates coverage as % with training
    - "Has Training": Only shows schools with training (coverage = 100%)
    - "Missing Training": Only shows schools without training (coverage = 0%)

    Args:
        df: School DataFrame with 'district' column
        layer_type: Training type to aggregate ('fundamentals', 'lights', 'student_sessions')
        layer_filter_config: Optional filter config with 'filter' and 'min_depth' keys

    Returns:
        DataFrame with district-level statistics
    """
    if 'district' not in df.columns:
        return pd.DataFrame()

    # Map layer type to column names
    column_map = {
        'fundamentals': ('has_fundamentals', 'fundamentals_participants'),
        'lights': ('has_lights', 'lights_participants'),
        'student_sessions': ('has_student_sessions', 'student_sessions_count'),
    }
    has_col, count_col = column_map.get(layer_type, column_map['fundamentals'])

    # Apply filter from layer config
    filter_type = 'All Schools'
    min_depth = 0
    if layer_filter_config:
        filter_type = layer_filter_config.get('filter', 'All Schools')
        min_depth = layer_filter_config.get('min_depth', 0)

    # Create a working copy
    working_df = df.copy()

    # Apply filter type
    if filter_type == 'Has Training' and has_col in working_df.columns:
        working_df = working_df[working_df[has_col] == 'Yes']
    elif filter_type == 'Missing Training' and has_col in working_df.columns:
        working_df = working_df[working_df[has_col] == 'No']

    # Apply depth filter
    if min_depth > 0 and count_col in working_df.columns:
        working_df = working_df[
            pd.to_numeric(working_df[count_col], errors='coerce').fillna(0) >= min_depth
        ]

    # Group by district
    district_stats = working_df.groupby('district').agg(
        total_schools=('school_dbn', 'count'),
        schools_with_training=(has_col, lambda x: (x == 'Yes').sum() if has_col in working_df.columns else 0),
        total_participants=(count_col, lambda x: pd.to_numeric(x, errors='coerce').fillna(0).sum() if count_col in working_df.columns else 0),
    ).reset_index()

    # Calculate coverage percentage
    district_stats['coverage_pct'] = (
        district_stats['schools_with_training'] / district_stats['total_schools'] * 100
    ).round(1)

    # Calculate average participants per trained school
    district_stats['avg_participants'] = (
        district_stats['total_participants'] / district_stats['schools_with_training'].replace(0, 1)
    ).round(1)

    return district_stats


def get_choropleth_color(coverage_pct: float, layer_type: str = 'fundamentals') -> list:
    """
    Get RGBA color for choropleth based on coverage percentage.

    Uses a gradient from light (low coverage) to dark (high coverage)
    within the layer's color family.

    Args:
        coverage_pct: Percentage of schools with training (0-100)
        layer_type: Training type for color family

    Returns:
        RGBA color list [R, G, B, A]
    """
    # Base colors by layer type (matching TRAINING_LAYER_COLORS)
    color_ranges = {
        'fundamentals': {
            'low': [220, 230, 240, 120],    # Very light blue
            'mid_low': [147, 186, 225, 150],
            'mid': [65, 131, 196, 180],
            'mid_high': [45, 100, 160, 200],
            'high': [31, 82, 132, 220],     # Dark blue
        },
        'lights': {
            'low': [235, 225, 240, 120],    # Very light purple
            'mid_low': [199, 168, 214, 150],
            'mid': [156, 102, 178, 180],
            'mid_high': [130, 75, 150, 200],
            'high': [106, 52, 128, 220],    # Dark purple
        },
        'student_sessions': {
            'low': [225, 240, 235, 120],    # Very light teal
            'mid_low': [158, 213, 197, 150],
            'mid': [76, 175, 147, 180],
            'mid_high': [50, 150, 120, 200],
            'high': [26, 125, 97, 220],     # Dark teal
        },
    }

    colors = color_ranges.get(layer_type, color_ranges['fundamentals'])

    if coverage_pct < 20:
        return colors['low']
    elif coverage_pct < 40:
        return colors['mid_low']
    elif coverage_pct < 60:
        return colors['mid']
    elif coverage_pct < 80:
        return colors['mid_high']
    else:
        return colors['high']


def prepare_choropleth_geojson(
    df: pd.DataFrame,
    geojson: dict,
    layer_type: str = 'fundamentals',
    layer_filter_config: dict = None
) -> dict:
    """
    Prepare GeoJSON with embedded district statistics for choropleth rendering.

    Merges school aggregation data into GeoJSON properties for each district.
    Respects filter settings (Has Training/Missing Training).

    Args:
        df: School DataFrame
        geojson: District boundaries GeoJSON
        layer_type: Training type to visualize
        layer_filter_config: Optional filter config with 'filter' and 'min_depth' keys

    Returns:
        Enhanced GeoJSON with training statistics in properties
    """
    # Aggregate school data by district, respecting filter settings
    district_stats = aggregate_by_district(df, layer_type, layer_filter_config)

    # Create lookup dict (district number -> stats)
    stats_lookup = {}
    for _, row in district_stats.iterrows():
        stats_lookup[int(row['district'])] = {
            'total_schools': int(row['total_schools']),
            'schools_with_training': int(row['schools_with_training']),
            'coverage_pct': float(row['coverage_pct']),
            'total_participants': int(row['total_participants']),
            'avg_participants': float(row['avg_participants']),
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

        # Get stats for this district
        stats = stats_lookup.get(district_num, {
            'total_schools': 0,
            'schools_with_training': 0,
            'coverage_pct': 0,
            'total_participants': 0,
            'avg_participants': 0,
        })

        # Calculate fill color based on coverage
        fill_color = get_choropleth_color(stats['coverage_pct'], layer_type)

        # Create enhanced feature
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


def get_district_summary(df: pd.DataFrame, layer_type: str = 'fundamentals') -> Dict:
    """
    Get high-level summary of district coverage.

    Args:
        df: School DataFrame
        layer_type: Training type to summarize

    Returns:
        Dict with summary statistics
    """
    district_stats = aggregate_by_district(df, layer_type)

    if len(district_stats) == 0:
        return {
            'total_districts': 0,
            'full_coverage': 0,
            'partial_coverage': 0,
            'no_coverage': 0,
            'avg_coverage_pct': 0,
        }

    return {
        'total_districts': len(district_stats),
        'full_coverage': (district_stats['coverage_pct'] >= 80).sum(),
        'partial_coverage': ((district_stats['coverage_pct'] > 0) & (district_stats['coverage_pct'] < 80)).sum(),
        'no_coverage': (district_stats['coverage_pct'] == 0).sum(),
        'avg_coverage_pct': district_stats['coverage_pct'].mean(),
        'min_coverage_pct': district_stats['coverage_pct'].min(),
        'max_coverage_pct': district_stats['coverage_pct'].max(),
    }
