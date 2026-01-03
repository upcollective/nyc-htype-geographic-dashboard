"""
Utilities for the Solara HTYPE Geographic Dashboard.

Modules:
- data_loader: Google Sheets API connection and data processing
- color_schemes: Multi-layer training color system
- vulnerability_loader: STH/ENI indicator data loading
"""

from .data_loader import (
    load_school_data,
    load_participant_data,
    load_from_google_sheets,
    get_filter_options,
    filter_schools,
    filter_by_training_status,
    calculate_summary_stats,
    GOOGLE_SHEET_ID,
    SHEET_TABS,
)

from .color_schemes import (
    TRAINING_COLORS,
    TRAINING_COLORS_HEX,
    TRAINING_LAYER_COLORS,
    DEPTH_THRESHOLDS,
    get_color_for_status,
    get_hex_for_status,
    normalize_training_status,
    get_layer_color,
    get_layer_color_hex,  # For depth-based hex colors
    get_layer_hex_color,
    get_layer_name,
    calculate_dot_radius,
)

from .vulnerability_loader import (
    load_vulnerability_data,
    merge_vulnerability_with_training,
    calculate_vulnerability_stats,
    HIGH_STH_THRESHOLD,
    HIGH_ENI_THRESHOLD,
)

__all__ = [
    # Data loader
    'load_school_data',
    'load_participant_data',
    'load_from_google_sheets',
    'get_filter_options',
    'filter_schools',
    'filter_by_training_status',
    'calculate_summary_stats',
    'GOOGLE_SHEET_ID',
    'SHEET_TABS',
    # Color schemes
    'TRAINING_COLORS',
    'TRAINING_COLORS_HEX',
    'TRAINING_LAYER_COLORS',
    'DEPTH_THRESHOLDS',
    'get_color_for_status',
    'get_hex_for_status',
    'normalize_training_status',
    'get_layer_color',
    'get_layer_color_hex',
    'get_layer_hex_color',
    'get_layer_name',
    'calculate_dot_radius',
    # Vulnerability
    'load_vulnerability_data',
    'merge_vulnerability_with_training',
    'calculate_vulnerability_stats',
    'HIGH_STH_THRESHOLD',
    'HIGH_ENI_THRESHOLD',
]
