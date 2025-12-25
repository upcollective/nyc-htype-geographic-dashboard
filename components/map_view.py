"""
Map visualization component using Pydeck (Deck.gl for Python).
Renders interactive map of NYC schools with training status colors.

Multi-layer system: Each training type (Fundamentals, LIGHTS, Student Sessions)
can be rendered as an independent layer with depth-based dot sizing.
"""
import streamlit as st
import pydeck as pdk
import pandas as pd
from typing import Optional, Dict, List

from utils.color_schemes import (
    get_layer_color,
    get_layer_hex_color,
    get_layer_name,
    calculate_dot_radius,
    TRAINING_LAYER_COLORS
)
from utils.data_loader import apply_layer_filter
from utils.district_aggregator import (
    load_district_geojson,
    prepare_choropleth_geojson,
    get_district_summary
)


# NYC center coordinates - tighter default focused on NYC proper
NYC_CENTER = {
    'latitude': 40.7128,
    'longitude': -73.9500,  # Shifted east to better center on NYC (was -74.0060)
    'zoom': 10.8  # Tighter default zoom (was 10)
}

# NYC bounding box for clamping (prevents zooming out too far)
NYC_BOUNDS = {
    'min_lat': 40.49,
    'max_lat': 40.92,
    'min_lng': -74.27,
    'max_lng': -73.68,
}

# CartoDB Positron - free basemap, no API key required
MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

# Path to NYC mask GeoJSON (grey overlay for areas outside NYC)
NYC_MASK_PATH = "data/geo/nyc_mask.geojson"


def load_nyc_mask() -> Optional[dict]:
    """
    Load the NYC mask GeoJSON file.

    The mask is an inverted polygon - a large rectangle covering the
    viewable area with NYC cut out as a "hole". When rendered as a
    semi-transparent grey layer, it effectively greys out everything
    outside NYC while keeping NYC clear.

    Returns:
        GeoJSON dict or None if file not found
    """
    import json
    from pathlib import Path

    mask_path = Path(__file__).parent.parent / NYC_MASK_PATH

    if not mask_path.exists():
        return None

    try:
        with open(mask_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.warning(f"Could not load NYC mask: {e}")
        return None


def create_mask_layer(opacity: float = 0.6) -> Optional[pdk.Layer]:
    """
    Create a GeoJSON layer that masks (greys out) areas outside NYC.

    This layer should be rendered BELOW school points and district
    choropleth layers but ABOVE the basemap. It creates a professional
    look by de-emphasizing New Jersey, Long Island, Westchester, etc.

    Args:
        opacity: Opacity of the grey mask (0.0-1.0). Default 0.6.

    Returns:
        Pydeck GeoJsonLayer or None if mask not available
    """
    mask_geojson = load_nyc_mask()

    if mask_geojson is None:
        return None

    # Light grey color with configurable opacity
    # RGB values create a neutral grey that works with Positron basemap
    fill_color = [220, 220, 220, int(opacity * 255)]

    return pdk.Layer(
        "GeoJsonLayer",
        data=mask_geojson,
        get_fill_color=fill_color,
        get_line_color=[180, 180, 180, 100],
        line_width_min_pixels=0,
        pickable=False,  # Not interactive
        opacity=1.0,  # Opacity handled by fill_color alpha
        stroked=False,
        filled=True,
        extruded=False,
    )


def calculate_view_state(df: pd.DataFrame, padding: float = 0.15) -> dict:
    """
    Calculate optimal view state (center + zoom) to fit all schools in the DataFrame.

    Dynamically adjusts zoom level based on the geographic spread of the data.
    Ensures the map viewport efficiently frames the data without wasted space.

    Args:
        df: DataFrame with latitude and longitude columns
        padding: Extra padding around bounds (0.15 = 15% on each side)

    Returns:
        Dict with 'latitude', 'longitude', 'zoom' keys
    """
    # Filter to schools with valid coordinates
    map_df = df[df['has_coordinates'] == True]

    if len(map_df) == 0:
        return NYC_CENTER.copy()

    # Calculate bounding box
    min_lat = map_df['latitude'].min()
    max_lat = map_df['latitude'].max()
    min_lng = map_df['longitude'].min()
    max_lng = map_df['longitude'].max()

    # Calculate center
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2

    # Calculate span with padding
    lat_span = (max_lat - min_lat) * (1 + padding * 2)
    lng_span = (max_lng - min_lng) * (1 + padding * 2)

    # Handle edge case of single point or very tight cluster
    if lat_span < 0.01:
        lat_span = 0.02
    if lng_span < 0.01:
        lng_span = 0.02

    # Calculate zoom level from span
    # Formula derived from Mapbox/Deck.gl zoom levels
    # At zoom 0, the world is ~360 degrees wide
    # Each zoom level doubles the resolution
    import math

    # Use the larger span to ensure all points fit
    # Adjust for typical map aspect ratio (wider than tall)
    lat_zoom = math.log2(180 / lat_span) - 0.5
    lng_zoom = math.log2(360 / lng_span) - 0.5

    # Use the smaller zoom (wider view) to ensure everything fits
    zoom = min(lat_zoom, lng_zoom)

    # Clamp zoom to reasonable range for NYC
    zoom = max(10.5, min(zoom, 15.5))  # Min 10.5 (city-wide), Max 15.5 (block level)

    return {
        'latitude': center_lat,
        'longitude': center_lng,
        'zoom': zoom
    }


def create_school_layer(df: pd.DataFrame, radius: int = 80) -> pdk.Layer:
    """
    Create a ScatterplotLayer for school points.

    Args:
        df: DataFrame with latitude, longitude, and color columns
        radius: Point radius in meters

    Returns:
        Pydeck ScatterplotLayer
    """
    # Filter to schools with valid coordinates
    map_df = df[df['has_coordinates'] == True].copy()

    if len(map_df) == 0:
        return None

    # Format indicator data for tooltip display
    if 'sth_percent' in map_df.columns:
        map_df['sth_display'] = map_df['sth_percent'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['sth_display'] = "N/A"

    if 'economic_need_index' in map_df.columns:
        map_df['eni_display'] = map_df['economic_need_index'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['eni_display'] = "N/A"

    return pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        get_radius=radius,
        pickable=True,
        opacity=0.8,
        stroked=True,
        get_line_color=[60, 60, 60, 100],
        line_width_min_pixels=1,
        auto_highlight=True,
        highlight_color=[255, 255, 0, 128],
    )


# =============================================================================
# MULTI-LAYER TRAINING VISUALIZATION
# =============================================================================

def create_training_layer(
    df: pd.DataFrame,
    layer_type: str,
    layer_config: dict,
    base_radius: int = 60,
    highlight_config: Optional[Dict] = None
) -> Optional[pdk.Layer]:
    """
    Create a ScatterplotLayer for a specific training type.

    Each layer uses its own color family and encodes depth (participant count)
    through both color intensity and dot size. Schools meeting indicator
    thresholds receive a colored border (ring) for visual emphasis.

    Args:
        df: Full DataFrame with school data
        layer_type: 'fundamentals', 'lights', or 'student_sessions'
        layer_config: Dict with 'enabled', 'filter', 'min_depth' keys
        base_radius: Base radius in meters for dots
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold' for visual highlights

    Returns:
        Pydeck ScatterplotLayer or None if no data
    """
    # Apply the layer-specific filter
    layer_df = apply_layer_filter(df, layer_type, layer_config)

    # Filter to schools with valid coordinates
    map_df = layer_df[layer_df['has_coordinates'] == True].copy()

    if len(map_df) == 0:
        return None

    # Map layer type to participant count column
    count_columns = {
        'fundamentals': 'fundamentals_participants',
        'lights': 'lights_participants',
        'student_sessions': 'student_sessions_count',
    }
    count_col = count_columns.get(layer_type, 'fundamentals_participants')

    # Get participant count (default to 0 if column missing)
    if count_col in map_df.columns:
        map_df['participant_count'] = pd.to_numeric(
            map_df[count_col], errors='coerce'
        ).fillna(0).astype(int)
    else:
        map_df['participant_count'] = 0

    # Calculate color and radius based on depth
    map_df['layer_color'] = map_df['participant_count'].apply(
        lambda x: get_layer_color(layer_type, x)
    )
    map_df['layer_radius'] = map_df['participant_count'].apply(
        lambda x: calculate_dot_radius(x, base_radius)
    )

    # Add layer type for tooltip
    map_df['layer_type'] = get_layer_name(layer_type)

    # Format indicator data for tooltip display
    if 'sth_percent' in map_df.columns:
        map_df['sth_display'] = map_df['sth_percent'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['sth_display'] = "N/A"

    if 'economic_need_index' in map_df.columns:
        map_df['eni_display'] = map_df['economic_need_index'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['eni_display'] = "N/A"

    # Apply indicator highlights (colored border/ring)
    # Default: neutral gray border
    default_line_color = [60, 60, 60, 120]

    # Calculate highlight status for each school
    def get_highlight_color(row):
        """Determine border color based on indicator thresholds."""
        if highlight_config:
            sth_threshold = highlight_config.get('sth_threshold')
            eni_threshold = highlight_config.get('eni_threshold')

            # Check STH threshold (red highlight)
            if sth_threshold is not None and 'sth_percent' in row.index:
                sth_val = row.get('sth_percent')
                if pd.notna(sth_val) and sth_val >= sth_threshold:
                    return [220, 53, 69, 255]  # Bootstrap danger red

            # Check ENI threshold (orange highlight)
            if eni_threshold is not None and 'economic_need_index' in row.index:
                eni_val = row.get('economic_need_index')
                if pd.notna(eni_val) and eni_val >= eni_threshold:
                    return [255, 140, 0, 255]  # Dark orange

        return default_line_color

    # Apply highlight colors
    map_df['line_color'] = map_df.apply(get_highlight_color, axis=1)

    # Determine if any highlights are active (for thicker borders)
    has_highlights = (
        highlight_config and
        (highlight_config.get('sth_threshold') is not None or
         highlight_config.get('eni_threshold') is not None)
    )
    line_width = 2 if has_highlights else 1

    return pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        id=f"layer_{layer_type}",
        get_position=["longitude", "latitude"],
        get_fill_color="layer_color",
        get_radius="layer_radius",
        pickable=True,
        opacity=0.85,
        stroked=True,
        get_line_color="line_color",
        line_width_min_pixels=line_width,
        auto_highlight=True,
        highlight_color=[255, 255, 0, 160],
    )


def create_training_layers(
    df: pd.DataFrame,
    layer_config: Dict,
    highlight_config: Optional[Dict] = None,
    base_radius: int = 60
) -> List[pdk.Layer]:
    """
    Create all enabled training layers for the map.

    Layers are rendered in order: fundamentals (bottom), lights, student_sessions (top).
    This ensures more specialized training appears on top of foundational training.

    Args:
        df: Full DataFrame with school data
        layer_config: Dict with config for each layer type
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold' for visual highlights
        base_radius: Base radius in meters for dots

    Returns:
        List of Pydeck layers (empty if none enabled)
    """
    layers = []

    # Layer order matters: fundamentals first (bottom), specialized on top
    for layer_type in ['fundamentals', 'lights', 'student_sessions']:
        config = layer_config.get(layer_type, {})

        # Skip disabled or placeholder layers
        if not config.get('enabled', False) or config.get('placeholder', False):
            continue

        layer = create_training_layer(df, layer_type, config, base_radius, highlight_config)
        if layer is not None:
            layers.append(layer)

    return layers


def create_multi_layer_tooltip() -> dict:
    """Create enhanced tooltip for multi-layer training view."""
    return {
        "html": """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 10px; min-width: 240px;">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">{school_name}</div>
            <div style="font-size: 11px; color: #666; margin-bottom: 8px;">DBN: {school_dbn} • District {district}</div>

            <hr style="margin: 8px 0; border: none; border-top: 1px solid #eee;">

            <div style="font-size: 12px; font-weight: 600; margin-bottom: 6px; color: #333;">
                📚 {layer_type}
            </div>
            <div style="font-size: 12px; margin-bottom: 8px;">
                <span style="color: #555;">Participants:</span>
                <strong>{participant_count}</strong>
            </div>

            <hr style="margin: 8px 0; border: none; border-top: 1px solid #eee;">

            <div style="font-size: 11px; color: #666;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                    <span>🏠 STH:</span> <strong>{sth_display}</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>💰 ENI:</span> <strong>{eni_display}</strong>
                </div>
            </div>
        </div>
        """,
        "style": {
            "backgroundColor": "white",
            "color": "#333",
            "borderRadius": "8px",
            "boxShadow": "0 2px 10px rgba(0,0,0,0.18)",
            "maxWidth": "300px"
        }
    }


def create_tooltip() -> dict:
    """Create tooltip configuration for school hover."""
    return {
        "html": """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 8px;">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">{school_name}</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 8px;">DBN: {school_dbn}</div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #eee;">
            <div style="font-size: 12px;">
                <div><strong>Training Status:</strong> {training_status}</div>
                <div><strong>Borough:</strong> {borough}</div>
                <div><strong>District:</strong> {district}</div>
                <div><strong>Participants:</strong> {total_participants}</div>
            </div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #eee;">
            <div style="font-size: 12px; color: #666;">
                <div><strong>STH:</strong> {sth_display}</div>
                <div><strong>ENI:</strong> {eni_display}</div>
            </div>
        </div>
        """,
        "style": {
            "backgroundColor": "white",
            "color": "#333",
            "borderRadius": "8px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.15)",
            "maxWidth": "320px"
        }
    }


def render_map(
    df: pd.DataFrame,
    center: Optional[dict] = None,
    zoom: int = 10,
    height: int = 600
) -> None:
    """
    Render the interactive map with school points.

    Args:
        df: DataFrame with school data including coordinates and colors
        center: Optional center coordinates (defaults to NYC center)
        zoom: Initial zoom level
        height: Map height in pixels
    """
    if center is None:
        center = NYC_CENTER

    # Calculate dynamic center based on data if available
    map_df = df[df['has_coordinates'] == True]
    if len(map_df) > 0:
        center = {
            'latitude': map_df['latitude'].mean(),
            'longitude': map_df['longitude'].mean(),
            'zoom': zoom
        }

    # Start with the mask layer (greys out areas outside NYC)
    layers = []
    mask_layer = create_mask_layer(opacity=0.55)
    if mask_layer is not None:
        layers.append(mask_layer)

    # Create the school layer
    school_layer = create_school_layer(df)

    if school_layer is None:
        st.warning("No schools with valid coordinates to display on map.")
        return

    layers.append(school_layer)

    # Create the view state
    view_state = pdk.ViewState(
        latitude=center['latitude'],
        longitude=center['longitude'],
        zoom=zoom,
        pitch=0,
        bearing=0
    )

    # Create the deck with mask layer below schools
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=create_tooltip(),
        map_style=MAP_STYLE,
    )

    # Render the map
    st.pydeck_chart(deck, use_container_width=True, height=height)


def create_neutral_layer(
    df: pd.DataFrame,
    highlight_config: Optional[Dict] = None,
    base_radius: int = 60
) -> Optional[pdk.Layer]:
    """
    Create a neutral ScatterplotLayer for schools without training data.

    Used when viewing untrained schools (Training Status = "No Training")
    where training-specific layers don't apply.

    Args:
        df: DataFrame with school data
        highlight_config: Dict with indicator highlight thresholds
        base_radius: Base radius in meters for dots

    Returns:
        Pydeck ScatterplotLayer or None if no data
    """
    # Filter to schools with valid coordinates
    map_df = df[df['has_coordinates'] == True].copy()

    if len(map_df) == 0:
        return None

    # Neutral gray color for untrained schools
    map_df['layer_color'] = [[142, 153, 164, 180]] * len(map_df)  # Cool slate
    map_df['layer_radius'] = base_radius
    map_df['layer_type'] = 'No Training'
    map_df['participant_count'] = 0

    # Format indicator data for tooltip display
    if 'sth_percent' in map_df.columns:
        map_df['sth_display'] = map_df['sth_percent'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['sth_display'] = "N/A"

    if 'economic_need_index' in map_df.columns:
        map_df['eni_display'] = map_df['economic_need_index'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
    else:
        map_df['eni_display'] = "N/A"

    # Apply indicator highlights (colored border/ring) - same logic as training layers
    default_line_color = [60, 60, 60, 120]

    def get_highlight_color(row):
        if highlight_config:
            sth_threshold = highlight_config.get('sth_threshold')
            eni_threshold = highlight_config.get('eni_threshold')

            if sth_threshold is not None and 'sth_percent' in row.index:
                sth_val = row.get('sth_percent')
                if pd.notna(sth_val) and sth_val >= sth_threshold:
                    return [220, 53, 69, 255]  # Red

            if eni_threshold is not None and 'economic_need_index' in row.index:
                eni_val = row.get('economic_need_index')
                if pd.notna(eni_val) and eni_val >= eni_threshold:
                    return [255, 140, 0, 255]  # Orange

        return default_line_color

    map_df['line_color'] = map_df.apply(get_highlight_color, axis=1)

    has_highlights = (
        highlight_config and
        (highlight_config.get('sth_threshold') is not None or
         highlight_config.get('eni_threshold') is not None)
    )
    line_width = 2 if has_highlights else 1

    return pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        id="layer_neutral",
        get_position=["longitude", "latitude"],
        get_fill_color="layer_color",
        get_radius="layer_radius",
        pickable=True,
        opacity=0.75,
        stroked=True,
        get_line_color="line_color",
        line_width_min_pixels=line_width,
        auto_highlight=True,
        highlight_color=[255, 255, 0, 160],
    )


def render_map_with_layers(
    df: pd.DataFrame,
    layer_config: Dict,
    highlight_config: Optional[Dict] = None,
    height: int = 600
) -> None:
    """
    Render interactive map with multi-layer training visualization.

    Each enabled training type is rendered as a separate layer with its own
    color family and depth-based dot sizing. Schools meeting indicator
    thresholds are highlighted with colored rings.

    Map viewport dynamically fits to the filtered data - zooming in for
    smaller geographic areas (boroughs, districts) and out for city-wide views.

    When no training layers are enabled (e.g., viewing untrained schools),
    a neutral layer is shown instead.

    Args:
        df: DataFrame with school data including coordinates
        layer_config: Dict with config for each layer type
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold' for visual highlights
        height: Map height in pixels
    """
    # Calculate dynamic view state based on filtered data bounds
    # This ensures the map frames the data efficiently (zooms to Brooklyn when Brooklyn is filtered, etc.)
    view_config = calculate_view_state(df)

    # Start with the mask layer (greys out areas outside NYC)
    # This layer renders at the bottom, below school points
    layers = []
    mask_layer = create_mask_layer(opacity=0.55)
    if mask_layer is not None:
        layers.append(mask_layer)

    # Create all enabled training layers with indicator highlights
    training_layers = create_training_layers(df, layer_config, highlight_config=highlight_config)

    # If no training layers (e.g., viewing untrained schools), show neutral layer
    if len(training_layers) == 0:
        neutral_layer = create_neutral_layer(df, highlight_config)
        if neutral_layer is not None:
            layers.append(neutral_layer)
        elif len(layers) == 0:
            st.warning("No schools with valid coordinates to display.")
            return
    else:
        layers.extend(training_layers)

    # Create the view state using dynamically calculated bounds
    view_state = pdk.ViewState(
        latitude=view_config['latitude'],
        longitude=view_config['longitude'],
        zoom=view_config['zoom'],
        pitch=0,
        bearing=0
    )

    # Create the deck with multi-layer tooltip
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=create_multi_layer_tooltip(),
        map_style=MAP_STYLE,
    )

    # Render the map
    st.pydeck_chart(deck, use_container_width=True, height=height)


def render_layer_legend(layer_config: Dict, highlight_config: Optional[Dict] = None) -> None:
    """
    Render dynamic legend based on enabled training layers and indicator highlights.

    Shows color families for each enabled layer with depth encoding explanation.
    Also shows highlight indicators (red/orange rings) when active.

    Args:
        layer_config: Dict with config for each layer type
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold' for visual highlights
    """
    enabled_layers = []
    for layer_type in ['fundamentals', 'lights', 'student_sessions']:
        config = layer_config.get(layer_type, {})
        if config.get('enabled', False) and not config.get('placeholder', False):
            enabled_layers.append(layer_type)

    # If no training layers enabled, show neutral legend
    if not enabled_layers:
        # Build highlight legend for neutral view
        highlight_items = []
        if highlight_config:
            sth_threshold = highlight_config.get('sth_threshold')
            eni_threshold = highlight_config.get('eni_threshold')

            if sth_threshold is not None:
                pct = int(sth_threshold * 100)
                highlight_items.append(
                    f'<span style="display:flex;align-items:center;gap:4px;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #dc3545;"></span>'
                    f'🏠 STH ≥{pct}%</span>'
                )
            if eni_threshold is not None:
                pct = int(eni_threshold * 100)
                highlight_items.append(
                    f'<span style="display:flex;align-items:center;gap:4px;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #ff8c00;"></span>'
                    f'💰 ENI ≥{pct}%</span>'
                )

        # Neutral dot legend
        neutral_legend = (
            '<span style="display:flex;align-items:center;gap:4px;">'
            '<span style="width:12px;height:12px;border-radius:50%;background:#8E99A4;border:1px solid #666;"></span>'
            '⚪ Untrained Schools</span>'
        )

        highlight_html = ''
        if highlight_items:
            highlight_html = (
                '<span style="display:flex;align-items:center;gap:12px;margin-left:16px;padding-left:16px;border-left:1px solid #ddd;">'
                + ''.join(highlight_items) + '</span>'
            )

        html = f'<div style="display:flex;gap:20px;font-size:12px;margin-bottom:6px;flex-wrap:wrap;align-items:center;">{neutral_legend}{highlight_html}</div>'
        st.markdown(html, unsafe_allow_html=True)
        return

    # Build legend HTML - NO WHITESPACE to avoid markdown code block detection
    legend_items = []
    for layer_type in enabled_layers:
        color = get_layer_hex_color(layer_type)
        name = get_layer_name(layer_type)
        emoji = {'fundamentals': '🔵', 'lights': '🟣', 'student_sessions': '🟢'}.get(layer_type, '●')
        legend_items.append(
            f'<span style="display:flex;align-items:center;gap:4px;">'
            f'<span style="width:12px;height:12px;border-radius:50%;background:{color};border:1px solid #666;"></span>'
            f'{emoji} {name}</span>'
        )

    # Size legend - compact single line
    size_legend = (
        '<span style="display:flex;align-items:center;gap:6px;margin-left:16px;padding-left:16px;border-left:1px solid #ddd;">'
        '<span style="font-size:10px;color:#666;">Size = depth:</span>'
        '<span style="width:6px;height:6px;border-radius:50%;background:#888;"></span>'
        '<span style="width:10px;height:10px;border-radius:50%;background:#888;"></span>'
        '<span style="width:14px;height:14px;border-radius:50%;background:#888;"></span>'
        '</span>'
    )

    # Build highlight legend if any highlights are active
    highlight_items = []
    if highlight_config:
        sth_threshold = highlight_config.get('sth_threshold')
        eni_threshold = highlight_config.get('eni_threshold')

        if sth_threshold is not None:
            pct = int(sth_threshold * 100)
            highlight_items.append(
                f'<span style="display:flex;align-items:center;gap:4px;">'
                f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #dc3545;"></span>'
                f'🏠 STH ≥{pct}%</span>'
            )
        if eni_threshold is not None:
            pct = int(eni_threshold * 100)
            highlight_items.append(
                f'<span style="display:flex;align-items:center;gap:4px;">'
                f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #ff8c00;"></span>'
                f'💰 ENI ≥{pct}%</span>'
            )

    highlight_legend = ''
    if highlight_items:
        highlight_legend = (
            '<span style="display:flex;align-items:center;gap:12px;margin-left:16px;padding-left:16px;border-left:1px solid #ddd;">'
            + ''.join(highlight_items) + '</span>'
        )

    html = f'<div style="display:flex;gap:20px;font-size:12px;margin-bottom:6px;flex-wrap:wrap;align-items:center;">{"".join(legend_items)}{size_legend}{highlight_legend}</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_map_legend():
    """Render a compact inline legend for the map colors."""
    st.markdown("""
    <div style="display:flex; gap:20px; font-size:12px; margin-bottom:6px; flex-wrap:wrap;">
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="width:10px; height:10px; border-radius:50%; background:#6B9080; border:1px solid #999;"></span>
            Complete
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="width:10px; height:10px; border-radius:50%; background:#D4A574; border:1px solid #999;"></span>
            Partial
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="width:10px; height:10px; border-radius:50%; background:#B87D7D; border:1px solid #999;"></span>
            No Training
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="width:10px; height:10px; border-radius:50%; background:#8E99A4; border:1px solid #999;"></span>
            Unknown
        </span>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# DISTRICT CHOROPLETH VISUALIZATION
# =============================================================================

def create_choropleth_layer(
    df: pd.DataFrame,
    layer_type: str = 'fundamentals',
    layer_filter_config: dict = None
) -> Optional[pdk.Layer]:
    """
    Create a GeoJsonLayer for district choropleth visualization.

    Districts are colored by training coverage percentage within the
    layer type's color family. Respects filter settings (Has Training/Missing Training).

    Args:
        df: School DataFrame with district column
        layer_type: Training type to visualize
        layer_filter_config: Filter config with 'filter' and 'min_depth' keys

    Returns:
        Pydeck GeoJsonLayer or None if GeoJSON not available
    """
    try:
        geojson = load_district_geojson()
    except FileNotFoundError:
        return None

    # Prepare GeoJSON with embedded statistics, applying filter settings
    enhanced_geojson = prepare_choropleth_geojson(df, geojson, layer_type, layer_filter_config)

    return pdk.Layer(
        "GeoJsonLayer",
        data=enhanced_geojson,
        get_fill_color="properties.fill_color",
        get_line_color=[80, 80, 80, 200],
        line_width_min_pixels=1,
        pickable=True,
        opacity=0.7,
        stroked=True,
        filled=True,
        extruded=False,
        auto_highlight=True,
        highlight_color=[255, 255, 0, 100],
    )


def create_choropleth_tooltip() -> dict:
    """Create tooltip for district choropleth hover."""
    return {
        "html": '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:10px;min-width:200px;">'
                '<div style="font-weight:600;font-size:14px;margin-bottom:6px;">District {district}</div>'
                '<hr style="margin:6px 0;border:none;border-top:1px solid #eee;">'
                '<div style="font-size:12px;">'
                '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                '<span>Schools:</span><strong>{total_schools}</strong></div>'
                '<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                '<span>With Training:</span><strong>{schools_with_training}</strong></div>'
                '<div style="display:flex;justify-content:space-between;margin-bottom:4px;color:#4183C4;">'
                '<span>Coverage:</span><strong>{coverage_pct}%</strong></div>'
                '<div style="display:flex;justify-content:space-between;">'
                '<span>Total Participants:</span><strong>{total_participants}</strong></div>'
                '</div></div>',
        "style": {
            "backgroundColor": "white",
            "color": "#333",
            "borderRadius": "8px",
            "boxShadow": "0 2px 10px rgba(0,0,0,0.18)",
            "maxWidth": "280px"
        }
    }


def render_choropleth_map(
    df: pd.DataFrame,
    layer_type: str = 'fundamentals',
    layer_filter_config: dict = None,
    height: int = 600
) -> None:
    """
    Render district choropleth map showing training coverage by district.

    Map viewport dynamically fits to the filtered data bounds.

    Args:
        df: School DataFrame
        layer_type: Training type to visualize
        layer_filter_config: Filter config with 'filter' and 'min_depth' keys
        height: Map height in pixels
    """
    # Calculate dynamic view state based on filtered data bounds
    view_config = calculate_view_state(df)

    # Start with the mask layer (greys out areas outside NYC)
    layers = []
    mask_layer = create_mask_layer(opacity=0.55)
    if mask_layer is not None:
        layers.append(mask_layer)

    # Create choropleth layer with filter settings
    choropleth_layer = create_choropleth_layer(df, layer_type, layer_filter_config)

    if choropleth_layer is None:
        st.warning("District boundaries not available. Please ensure nyc_school_districts.geojson is in data/geo/")
        return

    layers.append(choropleth_layer)

    # Create view state using dynamically calculated bounds
    view_state = pdk.ViewState(
        latitude=view_config['latitude'],
        longitude=view_config['longitude'],
        zoom=view_config['zoom'],
        pitch=0,
        bearing=0
    )

    # Create deck with mask layer below choropleth
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=create_choropleth_tooltip(),
        map_style=MAP_STYLE,
    )

    st.pydeck_chart(deck, use_container_width=True, height=height)


def render_choropleth_legend(layer_type: str = 'fundamentals') -> None:
    """Render legend for choropleth coverage levels."""
    color_hex = get_layer_hex_color(layer_type)
    name = get_layer_name(layer_type)

    html = (
        f'<div style="display:flex;gap:16px;font-size:12px;margin-bottom:6px;flex-wrap:wrap;align-items:center;">'
        f'<span style="font-weight:600;">{name} Coverage:</span>'
        '<span style="display:flex;align-items:center;gap:4px;">'
        '<span style="width:16px;height:12px;background:rgba(220,230,240,0.8);border:1px solid #999;"></span>&lt;20%</span>'
        '<span style="display:flex;align-items:center;gap:4px;">'
        '<span style="width:16px;height:12px;background:rgba(147,186,225,0.8);border:1px solid #999;"></span>20-40%</span>'
        '<span style="display:flex;align-items:center;gap:4px;">'
        '<span style="width:16px;height:12px;background:rgba(65,131,196,0.8);border:1px solid #999;"></span>40-60%</span>'
        '<span style="display:flex;align-items:center;gap:4px;">'
        '<span style="width:16px;height:12px;background:rgba(45,100,160,0.9);border:1px solid #999;"></span>60-80%</span>'
        '<span style="display:flex;align-items:center;gap:4px;">'
        '<span style="width:16px;height:12px;background:rgba(31,82,132,0.95);border:1px solid #999;"></span>&gt;80%</span>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_map_info_bar(
    layer_config: Dict,
    highlight_config: Optional[Dict] = None,
    map_view: str = 'schools',
    choropleth_layer: str = 'fundamentals',
    filter_info: Optional[Dict] = None
) -> None:
    """
    Render unified info bar containing legend and active filter chip.

    Displays on a single line with:
    - Left: Training layer legend (color codes)
    - Right: Active filter chip (when filters applied)

    All wrapped in a subtle boxed container for better visibility.

    Args:
        layer_config: Dict with config for each layer type
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold'
        map_view: 'schools' or 'districts'
        choropleth_layer: Which training layer to show in choropleth mode
        filter_info: Dict with 'active_filters', 'filtered_count', 'total_count'
    """
    # Build legend HTML based on view type
    if map_view == 'districts':
        legend_html = _build_choropleth_legend_html(choropleth_layer)
    else:
        legend_html = _build_layer_legend_html(layer_config, highlight_config)

    # Build filter chip HTML (right side) - all on one line to avoid Streamlit rendering issues
    filter_chip_html = ''
    if filter_info and filter_info.get('active_filters'):
        filter_list = filter_info['active_filters']
        filtered_count = filter_info.get('filtered_count', 0)
        total_count = filter_info.get('total_count', 0)
        pct = (filtered_count / total_count * 100) if total_count > 0 else 0
        filter_text = ' • '.join(filter_list)
        filter_chip_html = f'<div style="background:linear-gradient(135deg,#e3f2fd 0%,#bbdefb 100%);padding:3px 10px;border-radius:12px;font-size:11px;display:inline-flex;gap:6px;align-items:center;border:1px solid #90caf9;white-space:nowrap;"><span style="color:#1565c0;">🔍 {filter_text}</span><span style="background:#1976d2;color:white;padding:1px 6px;border-radius:8px;font-weight:600;font-size:10px;">{filtered_count:,} ({pct:.0f}%)</span></div>'

    # Combine into thin info strip (minimal height) - single line HTML
    html = f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;margin-bottom:2px;border-bottom:1px solid #e8e8e8;"><div style="display:flex;align-items:center;gap:16px;">{legend_html}</div>{filter_chip_html}</div>'
    st.markdown(html, unsafe_allow_html=True)


def _build_layer_legend_html(layer_config: Dict, highlight_config: Optional[Dict] = None) -> str:
    """Build HTML for training layer legend (schools view)."""
    enabled_layers = []
    for layer_type in ['fundamentals', 'lights', 'student_sessions']:
        config = layer_config.get(layer_type, {})
        if config.get('enabled', False) and not config.get('placeholder', False):
            enabled_layers.append(layer_type)

    # If no training layers enabled, show neutral legend
    if not enabled_layers:
        highlight_items = []
        if highlight_config:
            sth_threshold = highlight_config.get('sth_threshold')
            eni_threshold = highlight_config.get('eni_threshold')

            if sth_threshold is not None:
                pct = int(sth_threshold * 100)
                highlight_items.append(
                    f'<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #dc3545;"></span>'
                    f'🏠 STH ≥{pct}%</span>'
                )
            if eni_threshold is not None:
                pct = int(eni_threshold * 100)
                highlight_items.append(
                    f'<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
                    f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #ff8c00;"></span>'
                    f'💰 ENI ≥{pct}%</span>'
                )

        neutral_legend = (
            '<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
            '<span style="width:12px;height:12px;border-radius:50%;background:#8E99A4;border:1px solid #666;"></span>'
            '⚪ Untrained Schools</span>'
        )

        highlight_html = ''
        if highlight_items:
            highlight_html = '<span style="display:flex;align-items:center;gap:12px;margin-left:12px;padding-left:12px;border-left:1px solid #ddd;">' + ''.join(highlight_items) + '</span>'

        return neutral_legend + highlight_html

    # Build training layer legend
    legend_items = []
    for layer_type in enabled_layers:
        color = get_layer_hex_color(layer_type)
        name = get_layer_name(layer_type)
        emoji = {'fundamentals': '🔵', 'lights': '🟣', 'student_sessions': '🟢'}.get(layer_type, '●')
        legend_items.append(
            f'<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
            f'<span style="width:12px;height:12px;border-radius:50%;background:{color};border:1px solid #666;"></span>'
            f'{emoji} {name}</span>'
        )

    # Size legend
    size_legend = (
        '<span style="display:flex;align-items:center;gap:6px;margin-left:12px;padding-left:12px;border-left:1px solid #ddd;font-size:12px;">'
        '<span style="font-size:10px;color:#666;">Size = depth:</span>'
        '<span style="width:6px;height:6px;border-radius:50%;background:#888;"></span>'
        '<span style="width:10px;height:10px;border-radius:50%;background:#888;"></span>'
        '<span style="width:14px;height:14px;border-radius:50%;background:#888;"></span>'
        '</span>'
    )

    # Highlight legend
    highlight_items = []
    if highlight_config:
        sth_threshold = highlight_config.get('sth_threshold')
        eni_threshold = highlight_config.get('eni_threshold')

        if sth_threshold is not None:
            pct = int(sth_threshold * 100)
            highlight_items.append(
                f'<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
                f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #dc3545;"></span>'
                f'🏠 STH ≥{pct}%</span>'
            )
        if eni_threshold is not None:
            pct = int(eni_threshold * 100)
            highlight_items.append(
                f'<span style="display:flex;align-items:center;gap:4px;font-size:12px;">'
                f'<span style="width:12px;height:12px;border-radius:50%;background:transparent;border:2px solid #ff8c00;"></span>'
                f'💰 ENI ≥{pct}%</span>'
            )

    highlight_html = ''
    if highlight_items:
        highlight_html = '<span style="display:flex;align-items:center;gap:12px;margin-left:12px;padding-left:12px;border-left:1px solid #ddd;">' + ''.join(highlight_items) + '</span>'

    return ''.join(legend_items) + size_legend + highlight_html


def _build_choropleth_legend_html(layer_type: str = 'fundamentals') -> str:
    """Build HTML for choropleth coverage legend (districts view)."""
    color_hex = get_layer_hex_color(layer_type)
    name = get_layer_name(layer_type)

    return (
        f'<span style="font-weight:600;font-size:12px;">{name} Coverage:</span>'
        '<span style="display:flex;align-items:center;gap:4px;font-size:11px;">'
        '<span style="width:16px;height:12px;background:rgba(220,230,240,0.8);border:1px solid #999;"></span>&lt;20%</span>'
        '<span style="display:flex;align-items:center;gap:4px;font-size:11px;">'
        '<span style="width:16px;height:12px;background:rgba(147,186,225,0.8);border:1px solid #999;"></span>20-40%</span>'
        '<span style="display:flex;align-items:center;gap:4px;font-size:11px;">'
        '<span style="width:16px;height:12px;background:rgba(65,131,196,0.8);border:1px solid #999;"></span>40-60%</span>'
        '<span style="display:flex;align-items:center;gap:4px;font-size:11px;">'
        '<span style="width:16px;height:12px;background:rgba(45,100,160,0.9);border:1px solid #999;"></span>60-80%</span>'
        '<span style="display:flex;align-items:center;gap:4px;font-size:11px;">'
        '<span style="width:16px;height:12px;background:rgba(31,82,132,0.95);border:1px solid #999;"></span>&gt;80%</span>'
    )


def render_map_with_view_toggle(
    df: pd.DataFrame,
    layer_config: Dict,
    map_view: str = 'schools',
    choropleth_layer: str = 'fundamentals',
    highlight_config: Optional[Dict] = None,
    height: int = 600,
    filter_info: Optional[Dict] = None
) -> None:
    """
    Render map with support for both schools and district choropleth views.

    Args:
        df: School DataFrame
        layer_config: Layer configuration from sidebar
        map_view: 'schools' or 'districts'
        choropleth_layer: Which training layer to show in choropleth mode
        highlight_config: Dict with 'sth_threshold' and 'eni_threshold' for visual highlights
        height: Map height in pixels
        filter_info: Dict with active filter details for info bar display
    """
    # Render unified info bar with legend + filter chip
    render_map_info_bar(
        layer_config=layer_config,
        highlight_config=highlight_config,
        map_view=map_view,
        choropleth_layer=choropleth_layer,
        filter_info=filter_info
    )

    # Render the appropriate map type
    if map_view == 'districts':
        layer_type = choropleth_layer or 'fundamentals'
        layer_filter_config = layer_config.get(layer_type, {})
        render_choropleth_map(df, layer_type, layer_filter_config, height=height)
    else:
        render_map_with_layers(df, layer_config, highlight_config=highlight_config, height=height)
