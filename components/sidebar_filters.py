"""
Sidebar filter components for the geographic dashboard.
Provides filtering controls for boroughs, districts, training status, etc.
Designed to scale as more indicator variables are added.

Multi-layer training system: Each training type (Fundamentals, LIGHTS, Student Sessions)
can be toggled independently with depth filtering.

SIDEBAR STRUCTURE (Redesigned Dec 2025):
1. Analysis Mode (TOP - always visible, not in expander)
2. Search + Quick Filters
3. Geography (expander) - with cascading filters
4. Indicator Highlights (expander)
5. Map Layers (expander - ONLY shown on Map tab)
"""
import streamlit as st
import pandas as pd
from typing import Optional, Dict

# Import layer color info for UI
from utils.color_schemes import TRAINING_LAYER_COLORS, get_layer_hex_color
from utils.data_loader import get_filter_options


def render_analysis_mode() -> str:
    """
    Render the Analysis Mode selector (always visible at top of sidebar).

    This is the PRIMARY control - it determines what you're analyzing.
    Each mode provides a tailored stats panel for that workflow.

    Modes:
    - 📊 Overview: Full picture (all 1,656 schools)
    - ✅ Trained Schools: Progress view (schools with any training)
    - 🎯 Need Fundamentals: Outreach targets (no training at all)
    - 🎯 Need LIGHTS: Next step ready (have Fundamentals, need LIGHTS)

    Returns:
        Selected mode string
    """
    st.sidebar.markdown("### 📊 Analysis Mode")

    mode = st.sidebar.radio(
        "Analysis Mode",
        options=[
            "📊 Overview",           # Default: full picture, all schools
            "✅ Trained Schools",    # Progress: schools with any training
            "🎯 Need Fundamentals",  # Outreach: no training at all
            "🎯 Need LIGHTS",        # Next step: have Fundamentals, need LIGHTS
        ],
        index=0,
        key="global_training_status",
        help="Select your analysis mode. Each mode shows tailored metrics.",
        label_visibility="collapsed"
    )

    # Show description of current selection
    descriptions = {
        "📊 Overview": "Full picture: all schools with training breakdown",
        "✅ Trained Schools": "Progress: schools with Fundamentals and/or LIGHTS",
        "🎯 Need Fundamentals": "Outreach targets: schools with no training",
        "🎯 Need LIGHTS": "Next step: schools ready for LIGHTS ToT"
    }
    st.sidebar.caption(descriptions.get(mode, ''))

    return mode


def render_indicator_highlight(
    label: str,
    key_prefix: str,
    min_val: int = 0,
    max_val: int = 100,
    default_val: int = 30,
    step: int = 5,
    help_text: str = ""
) -> Optional[float]:
    """
    Indicator highlight component with checkbox and conditional slider.

    This is a VISUAL control - it doesn't filter data, but marks schools
    that meet the threshold with a visual indicator (ring/border) on the map.

    Uses simple stacked layout that works reliably in narrow sidebar.

    Args:
        label: Display label for the indicator (include emoji)
        key_prefix: Unique key prefix for session state
        min_val: Minimum slider value
        max_val: Maximum slider value
        default_val: Default threshold value
        step: Slider step size
        help_text: Help tooltip text

    Returns:
        Threshold value as float (0-1) if enabled, None otherwise
    """
    enabled = st.checkbox(
        label,
        key=f"{key_prefix}_enabled",
        help=help_text
    )

    if enabled:
        threshold = st.slider(
            f"Threshold ≥",
            min_value=min_val,
            max_value=max_val,
            value=default_val,
            step=step,
            key=f"{key_prefix}_slider",
            format="%d%%"
        )
        return threshold / 100
    else:
        return None


def render_training_layer_controls(training_status: str = 'All Schools') -> Dict:
    """
    Map layer controls with view toggle and training type visibility.

    Uses simple checkbox+label layout that works reliably in narrow sidebar.

    Returns:
        Dict with 'map_view' ('schools' or 'districts') and layer configs
    """
    result = {}

    # === VIEW MODE TOGGLE (top) ===
    show_districts = st.toggle(
        "📊 District View",
        value=st.session_state.get('map_view_mode', False),
        key="map_view_mode",
        help="Toggle between school points and district choropleth"
    )
    result['map_view'] = 'districts' if show_districts else 'schools'

    st.divider()  # Visual separator

    # Determine layer availability based on analysis mode
    layers_disabled = training_status == '🎯 Need Fundamentals'

    if layers_disabled:
        st.caption("ℹ️ Showing untrained schools only")
        result['fundamentals'] = {'enabled': False, 'min_depth': 0}
        result['lights'] = {'enabled': False, 'min_depth': 0}
        result['student_sessions'] = {'enabled': False, 'placeholder': True}
        return result

    # === TRAINING LAYERS ===
    fund_default = True
    lights_default = training_status not in ['🎯 Need LIGHTS']

    # Fundamentals
    fund_enabled = st.checkbox(
        "🔵 Fundamentals",
        value=fund_default,
        key="layer_fundamentals",
        help="Show schools with Fundamentals training"
    )
    if fund_enabled:
        fund_min_depth = st.slider(
            "Min ≥",
            min_value=0, max_value=30, value=0, step=5,
            key="fund_min_depth",
            format="%d staff"
        )
    else:
        fund_min_depth = 0
    result['fundamentals'] = {'enabled': fund_enabled, 'min_depth': fund_min_depth}

    # LIGHTS
    lights_enabled = st.checkbox(
        "🟣 LIGHTS ToT",
        value=lights_default,
        key="layer_lights",
        help="Show schools with LIGHTS trainers"
    )
    if lights_enabled:
        lights_min_depth = st.slider(
            "Min ≥",
            min_value=0, max_value=15, value=0, step=1,
            key="lights_min_depth",
            format="%d trainers"
        )
    else:
        lights_min_depth = 0
    result['lights'] = {'enabled': lights_enabled, 'min_depth': lights_min_depth}

    # Student Sessions (placeholder - disabled)
    st.checkbox(
        "🟢 Students",
        value=False,
        key="layer_students",
        disabled=True,
        help="Coming soon"
    )
    result['student_sessions'] = {'enabled': False, 'placeholder': True}

    return result


def render_sidebar_filters(df: pd.DataFrame) -> dict:
    """
    Render sidebar filter controls and return selected filter values.

    SIDEBAR STRUCTURE:
    1. Analysis Mode (TOP - always visible)
    2. Search + Quick Filters
    3. Geography (expander) - with cascading filters
    4. Indicator Highlights (expander)
    5. Map Layers (expander - ONLY on Map tab)

    Args:
        df: Full school DataFrame for computing cascading filter options

    Returns:
        Dictionary of selected filter values
    """
    # Handle clear request from PREVIOUS run (must happen BEFORE widgets render)
    if st.session_state.get('_clear_filters_requested', False):
        # Reset all filter widgets to their default values
        st.session_state['filter_search'] = ""
        st.session_state['filter_boroughs'] = []
        st.session_state['filter_districts'] = []
        st.session_state['filter_superintendent'] = 'All'
        st.session_state['filter_school_type'] = 'All'
        # Analysis mode - default to Overview
        st.session_state['global_training_status'] = '📊 Overview'
        # Map display controls (visual only - don't filter data)
        st.session_state['layer_fundamentals'] = True
        st.session_state['layer_lights'] = True
        st.session_state['layer_students'] = False
        st.session_state['fund_min_depth'] = 0
        st.session_state['lights_min_depth'] = 0
        st.session_state['map_view_mode'] = False  # False = schools, True = districts
        # Indicators
        st.session_state['sth_enabled'] = False
        st.session_state['eni_enabled'] = False
        st.session_state['quick_filter'] = None
        st.session_state['_clear_filters_requested'] = False

    # ════════════════════════════════════════════════════════════════════════════
    # 1. SEARCH + QUICK FILTERS (with Clear All in header)
    # ════════════════════════════════════════════════════════════════════════════
    # Header row: Title on left, Clear All on right
    header_col1, header_col2 = st.sidebar.columns([3, 1])
    with header_col1:
        st.markdown("### 🔍 Filters")
    with header_col2:
        clear_filters = st.button("✕", key="qf_clear", help="Clear all filters")

    # Search box
    search_query = st.sidebar.text_input(
        "Search Schools",
        placeholder="Enter school name or DBN...",
        help="Search by school name or DBN code",
        key="filter_search",
        label_visibility="collapsed"
    )

    # Quick Filter Buttons - full width 2-column layout
    col1, col2 = st.sidebar.columns(2)
    with col1:
        no_training = st.button("No Training", use_container_width=True, key="qf_no_training")
    with col2:
        priority_btn = st.button("⚠️ Priority", use_container_width=True, type="primary", key="qf_priority")

    # ════════════════════════════════════════════════════════════════════════════
    # 2. ANALYSIS MODE (after quick filters, outside expander)
    # ════════════════════════════════════════════════════════════════════════════
    st.sidebar.divider()
    analysis_mode = render_analysis_mode()

    # ════════════════════════════════════════════════════════════════════════════
    # 3. GEOGRAPHY (expander) - with CASCADING FILTERS
    # ════════════════════════════════════════════════════════════════════════════
    with st.sidebar.expander("📍 Geography", expanded=False):
        # Read CURRENT selections from session state for cascading
        current_boroughs = st.session_state.get('filter_boroughs', [])
        current_districts = st.session_state.get('filter_districts', [])

        # Get cascading filter options based on current selections
        filter_options = get_filter_options(
            df,
            selected_boroughs=current_boroughs,
            selected_districts=current_districts
        )

        # Boroughs (always show all - top level)
        selected_boroughs = st.multiselect(
            "Boroughs",
            options=filter_options.get('boroughs', []),
            default=[],
            placeholder="All boroughs",
            key="filter_boroughs"
        )

        # Districts (filtered by selected boroughs)
        # Clean up any previously selected districts that are no longer valid
        valid_districts = filter_options.get('districts', [])
        current_district_selection = [d for d in current_districts if d in valid_districts]

        selected_districts = st.multiselect(
            "Districts",
            options=valid_districts,
            default=current_district_selection,
            placeholder="All districts" if not selected_boroughs else "Districts in selection",
            key="filter_districts"
        )

        # Superintendent Filter (filtered by borough/district)
        superintendents = filter_options.get('superintendents', [])
        selected_superintendent = None
        if superintendents:
            # Check if current selection is still valid
            current_sup = st.session_state.get('filter_superintendent', 'All')
            if current_sup != 'All' and current_sup not in superintendents:
                st.session_state['filter_superintendent'] = 'All'

            selected_superintendent = st.selectbox(
                "Superintendent",
                options=['All'] + superintendents,
                index=0,
                key="filter_superintendent"
            )
            if selected_superintendent == 'All':
                selected_superintendent = None

        # School Type Filter (filtered by borough/district)
        school_types = filter_options.get('school_types', [])
        selected_school_type = None
        if school_types:
            # Check if current selection is still valid
            current_type = st.session_state.get('filter_school_type', 'All')
            if current_type != 'All' and current_type not in school_types:
                st.session_state['filter_school_type'] = 'All'

            selected_school_type = st.selectbox(
                "School Type",
                options=['All'] + school_types,
                index=0,
                key="filter_school_type"
            )
            if selected_school_type == 'All':
                selected_school_type = None

    # ════════════════════════════════════════════════════════════════════════════
    # 4. INDICATOR HIGHLIGHTS (expander) - Compact design
    # ════════════════════════════════════════════════════════════════════════════
    with st.sidebar.expander("📊 Indicator Highlights", expanded=False):
        st.caption("Highlight high-need schools on map")

        # STH Indicator - compact inline
        highlight_sth = render_indicator_highlight(
            label="🏠 STH",
            key_prefix="sth",
            min_val=0,
            max_val=50,
            default_val=30,
            step=5,
            help_text="Students in Temporary Housing"
        )

        # ENI Indicator - compact inline
        highlight_eni = render_indicator_highlight(
            label="💰 ENI",
            key_prefix="eni",
            min_val=50,
            max_val=100,
            default_val=85,
            step=5,
            help_text="Economic Need Index"
        )

    # ════════════════════════════════════════════════════════════════════════════
    # 5. MAP LAYERS (expander - ONLY shown on Map tab)
    # ════════════════════════════════════════════════════════════════════════════
    # Check if we're on the Map tab
    # IMPORTANT: Use 'tab_selector' (widget key) not 'active_tab' (derived value)
    # Widget keys are updated by Streamlit BEFORE script runs, so they're current
    # 'active_tab' is set AFTER sidebar renders, so it would be stale here
    active_tab = st.session_state.get('tab_selector', '🗺️ Map')
    is_map_tab = active_tab == '🗺️ Map'

    # Only render Map Layers controls when on Map tab
    if is_map_tab:
        with st.sidebar.expander("🗺️ Map Layers", expanded=False):
            layer_config = render_training_layer_controls(analysis_mode)
    else:
        # Provide default layer config when not on map tab
        # (preserves any existing session state values)
        layer_config = {
            'map_view': 'districts' if st.session_state.get('map_view_mode', False) else 'schools',
            'fundamentals': {
                'enabled': st.session_state.get('layer_fundamentals', True),
                'min_depth': st.session_state.get('fund_min_depth', 0)
            },
            'lights': {
                'enabled': st.session_state.get('layer_lights', True),
                'min_depth': st.session_state.get('lights_min_depth', 0)
            },
            'student_sessions': {'enabled': False, 'placeholder': True}
        }

    # Extract map_view from layer_config
    map_view = layer_config.get('map_view', 'schools')

    # Build filters dictionary
    filters = {
        'search_query': search_query if search_query else None,
        # Analysis mode (affects ALL views)
        'global_training_status': analysis_mode,
        # Map view mode and layer settings
        'map_view': map_view,
        'layer_config': layer_config,
        # Geographic filters
        'boroughs': selected_boroughs if selected_boroughs else None,
        'districts': selected_districts if selected_districts else None,
        'superintendent': selected_superintendent,
        'school_type': selected_school_type,
        # Indicator highlights (visual only - affects map markers)
        'highlight_sth': highlight_sth,
        'highlight_eni': highlight_eni,
        'high_eni_only': False,  # Set by Priority quick filter (ENI ≥85% + no training)
    }

    # Handle quick filter buttons using session state
    if 'quick_filter' not in st.session_state:
        st.session_state.quick_filter = None

    if no_training:
        st.session_state.quick_filter = 'no_training'
    elif priority_btn:
        st.session_state.quick_filter = 'priority'
    elif clear_filters:
        st.session_state.quick_filter = None
        # Set flag to clear indicator checkboxes on NEXT run (before widgets render)
        st.session_state['_clear_filters_requested'] = True
        st.rerun()  # Trigger rerun to apply the clear

    # Apply quick filter - override analysis_mode when quick filter is active
    if st.session_state.quick_filter == 'no_training':
        filters['global_training_status'] = '🎯 Need Fundamentals'
    elif st.session_state.quick_filter == 'priority':
        # Priority schools: high ENI (≥85%) + no training
        # ENI is a composite vulnerability indicator that includes STH
        filters['global_training_status'] = '🎯 Need Fundamentals'
        filters['high_eni_only'] = True

    return filters


def render_filter_summary(filters: dict, total_count: int, filtered_count: int, style: str = 'chip'):
    """
    Display filter summary showing active filters and school count.

    Args:
        filters: Current filter settings
        total_count: Total number of schools
        filtered_count: Number of schools after filtering
        style: 'chip' for map (compact pill above map), 'banner' for other tabs

    Only renders when filters are active (not default Overview mode).
    """
    active_filters = []

    if filters.get('search_query'):
        active_filters.append(f"'{filters['search_query']}'")
    if filters.get('boroughs'):
        active_filters.append(', '.join(filters['boroughs']))
    if filters.get('districts'):
        districts_str = ', '.join(map(str, filters['districts'][:3]))
        if len(filters['districts']) > 3:
            districts_str += f" +{len(filters['districts']) - 3}"
        active_filters.append(f"D{districts_str}")
    if filters.get('global_training_status') and filters['global_training_status'] != '📊 Overview':
        active_filters.append(filters['global_training_status'])
    if filters.get('superintendent'):
        active_filters.append(filters['superintendent'][:15] + "..." if len(filters['superintendent']) > 15 else filters['superintendent'])
    if filters.get('has_fundamentals') is False:
        active_filters.append("No Fund.")
    if filters.get('has_lights') is False:
        active_filters.append("No LIGHTS")
    if filters.get('high_eni_only'):
        active_filters.append("Hi ENI")

    if active_filters:
        pct = (filtered_count / total_count * 100) if total_count > 0 else 0
        filter_text = ' • '.join(active_filters)

        if style == 'chip':
            # Compact chip - right-aligned pill above map
            st.markdown(
                f"""<div style="display: flex; justify-content: flex-end; margin-bottom: 4px;">
                    <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 4px 12px; border-radius: 16px; font-size: 12px; display: inline-flex; gap: 8px; align-items: center; border: 1px solid #90caf9; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <span style="color: #1565c0;">🔍 {filter_text}</span>
                        <span style="background: #1976d2; color: white; padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 11px;">{filtered_count:,} ({pct:.0f}%)</span>
                    </div>
                </div>""",
                unsafe_allow_html=True
            )
        else:
            # Banner style for non-map tabs (Statistics, Indicators)
            st.markdown(
                f"""<div class="filter-banner">
                    <span class="filter-text">🔍 {filter_text}</span>
                    <span class="filter-count">{filtered_count:,} ({pct:.0f}%)</span>
                </div>""",
                unsafe_allow_html=True
            )
