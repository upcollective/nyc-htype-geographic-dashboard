"""
Color schemes for the Solara geographic dashboard.
Uses muted, design-conscious colors based on color theory principles.

Multi-layer system: Each training type gets its own color family with
light/medium/dark variants for depth encoding.

Ported from Streamlit version - identical color values for visual consistency.
"""

# =============================================================================
# LEGACY: Combined Training Status Colors (kept for backward compatibility)
# =============================================================================
TRAINING_COLORS = {
    'Complete': [107, 144, 128, 200],      # Soft Sage #6B9080
    'Fundamentals Only': [212, 165, 116, 200],  # Warm Amber #D4A574
    'LIGHTS Only': [212, 165, 116, 200],   # Warm Amber (same as partial)
    'No Training': [184, 125, 125, 200],   # Dusty Rose #B87D7D
    'Unknown': [142, 153, 164, 180],       # Cool Slate #8E99A4
}

TRAINING_COLORS_HEX = {
    'Complete': '#6B9080',
    'Fundamentals Only': '#D4A574',
    'LIGHTS Only': '#D4A574',
    'No Training': '#B87D7D',
    'Unknown': '#8E99A4',
}

# =============================================================================
# NEW: Multi-Layer Training Colors (one family per training type)
# =============================================================================
# Each training type has its own distinct color family with depth variants

TRAINING_LAYER_COLORS = {
    'fundamentals': {
        'name': 'Fundamentals',
        'hex': '#4183C4',
        'base': [65, 131, 196, 200],        # Primary Blue
        'none': [220, 230, 240, 100],       # Very light wash (no training)
        'light': [147, 186, 225, 160],      # Light Blue (1-5 participants)
        'medium': [65, 131, 196, 200],      # Medium Blue (6-20 participants)
        'dark': [31, 82, 132, 220],         # Dark Blue (20+ participants)
    },
    'lights': {
        'name': 'LIGHTS ToT',
        'hex': '#9C66B2',
        'base': [156, 102, 178, 200],       # Primary Purple
        'none': [235, 225, 240, 100],       # Very light wash (no training)
        'light': [199, 168, 214, 160],      # Light Purple (1-3 participants)
        'medium': [156, 102, 178, 200],     # Medium Purple (4-10 participants)
        'dark': [106, 52, 128, 220],        # Dark Purple (10+ participants)
    },
    'student_sessions': {
        'name': 'Student Sessions',
        'hex': '#4CAF93',
        'base': [76, 175, 147, 200],        # Primary Teal
        'none': [225, 240, 235, 100],       # Very light wash (no sessions)
        'light': [158, 213, 197, 160],      # Light Teal (1-2 sessions)
        'medium': [76, 175, 147, 200],      # Medium Teal (3-5 sessions)
        'dark': [26, 125, 97, 220],         # Dark Teal (5+ sessions)
    },
}

# Depth thresholds for each training type
DEPTH_THRESHOLDS = {
    'fundamentals': {'low': 5, 'high': 20, 'max': 50},   # Participant counts
    'lights': {'low': 3, 'high': 10, 'max': 20},         # Trainer counts
    'student_sessions': {'low': 2, 'high': 5, 'max': 10},  # Session counts
}

# =============================================================================
# CHOROPLETH GRADIENT COLORS (for district coverage view)
# =============================================================================
# These are the hex colors used in the district choropleth legend
# Ordered from high coverage (dark) to low coverage (light)

CHOROPLETH_GRADIENTS = {
    'fundamentals': {
        'name': 'Fundamentals Coverage',
        'very_high': '#1F5284',   # ≥80%
        'high': '#2D64A0',        # 60-79%
        'medium': '#4183C4',      # 40-59%
        'low': '#93BAE1',         # 20-39%
        'very_low': '#DCE6F0',    # <20%
    },
    'lights': {
        'name': 'LIGHTS Coverage',
        'very_high': '#4a2369',   # ≥80%
        'high': '#6a3480',        # 60-79%
        'medium': '#9C66B2',      # 40-59%
        'low': '#c7a8d6',         # 20-39%
        'very_low': '#ebe1f0',    # <20%
    },
    'student_sessions': {
        'name': 'Student Sessions Coverage',
        'very_high': '#1a7d61',   # ≥80%
        'high': '#2a9d7d',        # 60-79%
        'medium': '#4CAF93',      # 40-59%
        'low': '#9ed5c5',         # 20-39%
        'very_low': '#e5f5f0',    # <20%
    },
}


def get_choropleth_gradient(training_type: str) -> dict:
    """Get gradient color dict for choropleth legend."""
    return CHOROPLETH_GRADIENTS.get(training_type, CHOROPLETH_GRADIENTS['fundamentals'])


# Vulnerability layer colors (blue-purple gradient, doesn't conflict with training)
VULNERABILITY_COLORS = {
    'low': [173, 198, 216, 150],       # Light Steel Blue
    'medium': [119, 136, 180, 180],    # Muted Periwinkle
    'high': [128, 90, 140, 200],       # Dusty Purple
    'very_high': [102, 51, 102, 220],  # Deep Plum
}

# Borough colors for charts
BOROUGH_COLORS = {
    'MANHATTAN': '#7B9EA8',
    'BROOKLYN': '#A8907B',
    'BRONX': '#8A9B7B',
    'QUEENS': '#9B8A9B',
    'STATEN ISLAND': '#9B9B8A',
}

# Indicator highlight colors (for STH/ENI visual overlays)
INDICATOR_COLORS = {
    'sth_highlight': '#ff6464',  # Coral for STH
    'eni_highlight': '#00dcdc',  # Cyan for ENI
    'priority': '#ff4444',       # Red for priority schools
}


def get_color_for_status(status: str) -> list:
    """Get RGBA color list for a training status."""
    return TRAINING_COLORS.get(status, TRAINING_COLORS['Unknown'])


def get_hex_for_status(status: str) -> str:
    """Get hex color for a training status (for UI elements)."""
    return TRAINING_COLORS_HEX.get(status, TRAINING_COLORS_HEX['Unknown'])


def normalize_training_status(status: str) -> str:
    """Normalize various status strings to standard categories."""
    if not status or str(status).lower() in ['nan', 'none', '']:
        return 'Unknown'

    status_lower = str(status).lower().strip()

    if 'complete' in status_lower:
        return 'Complete'
    elif 'fundamentals only' in status_lower:
        return 'Fundamentals Only'
    elif 'lights only' in status_lower:
        return 'LIGHTS Only'
    elif 'no training' in status_lower:
        return 'No Training'
    else:
        return 'Unknown'


# =============================================================================
# Multi-Layer Helper Functions
# =============================================================================

def get_layer_color(layer_type: str, depth_value: int) -> list:
    """
    Get RGBA color for a training layer based on depth (participant/session count).

    Args:
        layer_type: 'fundamentals', 'lights', or 'student_sessions'
        depth_value: Number of participants/sessions at the school

    Returns:
        RGBA color list [R, G, B, A]
    """
    colors = TRAINING_LAYER_COLORS.get(layer_type, TRAINING_LAYER_COLORS['fundamentals'])
    thresholds = DEPTH_THRESHOLDS.get(layer_type, DEPTH_THRESHOLDS['fundamentals'])

    if depth_value == 0 or depth_value is None:
        return colors['none']
    elif depth_value < thresholds['low']:
        return colors['light']
    elif depth_value < thresholds['high']:
        return colors['medium']
    else:
        return colors['dark']


def get_layer_color_hex(layer_type: str, depth_value: int) -> str:
    """
    Get hex color string for a training layer based on depth.

    Useful for ipyleaflet markers which use hex colors.
    """
    colors = TRAINING_LAYER_COLORS.get(layer_type, TRAINING_LAYER_COLORS['fundamentals'])
    thresholds = DEPTH_THRESHOLDS.get(layer_type, DEPTH_THRESHOLDS['fundamentals'])

    if depth_value == 0 or depth_value is None:
        return '#dce6f0'  # Very light
    elif depth_value < thresholds['low']:
        # Convert RGBA to hex (approximate)
        return {
            'fundamentals': '#93bae1',
            'lights': '#c7a8d6',
            'student_sessions': '#9ed5c5',
        }.get(layer_type, '#93bae1')
    elif depth_value < thresholds['high']:
        return colors['hex']
    else:
        return {
            'fundamentals': '#1f5284',
            'lights': '#6a3480',
            'student_sessions': '#1a7d61',
        }.get(layer_type, '#1f5284')


def calculate_dot_radius(participant_count: int, base_radius: int = 6) -> int:
    """
    Calculate dot radius based on participant count.

    Uses sqrt scaling for better visual perception of differences.
    Larger counts = larger dots, but capped to prevent overwhelming.

    Args:
        participant_count: Number of participants at school
        base_radius: Base radius in pixels for minimum dot size

    Returns:
        Radius in pixels for ipyleaflet CircleMarker
    """
    if participant_count == 0 or participant_count is None:
        return int(base_radius * 0.7)  # Small dot for no training

    # Sqrt scaling: proportional but not overwhelming
    # 1 participant = 0.85x base, 10 = 1.6x base, 50 = 3x base
    scale_factor = 0.7 + (participant_count ** 0.4) * 0.3
    return int(base_radius * min(scale_factor, 2.5))  # Cap at 2.5x


def get_layer_hex_color(layer_type: str) -> str:
    """Get hex color for a training layer (for UI elements like legends)."""
    colors = TRAINING_LAYER_COLORS.get(layer_type, TRAINING_LAYER_COLORS['fundamentals'])
    return colors['hex']


def get_layer_name(layer_type: str) -> str:
    """Get display name for a training layer."""
    colors = TRAINING_LAYER_COLORS.get(layer_type, TRAINING_LAYER_COLORS['fundamentals'])
    return colors['name']
