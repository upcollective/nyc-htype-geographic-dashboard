"""
Sidebar filter components for the geographic dashboard.
Provides filtering controls for boroughs, districts, training status, etc.
Designed to scale as more indicator variables are added.

Multi-layer training system: Each training type (Fundamentals, LIGHTS, Student Sessions)
can be toggled independently with depth filtering.

SIDEBAR STRUCTURE (Redesigned Dec 2025):
1. Analysis Mode (TOP - always visible, not in expander)
2. Search + Quick Filters
3. Geography (expander)
4. Indicator Highlights (expander)
5. Map Layers (expander - ONLY shown on Map tab)
"""
import streamlit as st
from typing import Optional, Dict

# Import layer color info for UI
from utils.color_schemes import TRAINING_LAYER_COLORS, get_layer_hex_color


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
    Reusable indicator highlight component with checkbox + slider.

    This is a VISUAL control - it doesn't filter data, but marks schools
    that meet the threshold with a visual indicator (ring/border) on the map.

    Args:
        label: Display label for the indicator
        key_prefix: Unique key prefix for session state
        min_val: Minimum slider value
        max_val: Maximum slider value
        default_val: Default threshold value
        step: Slider step size
        help_text: Help tooltip text

    Returns:
        Threshold value as float (0-1) if enabled, None otherwise
    """
    col1, col2 = st.columns([1, 3])

    with col1:
        # Provide actual label for accessibility (hidden visually)
        enabled = st.checkbox(
            f"Enable {label} highlight",
            key=f"{key_prefix}_enabled",
            label_visibility="collapsed"
        )

    with col2:
        if enabled:
            threshold = st.slider(
                f"Highlight {label}",
                min_value=min_val,
                max_value=max_val,
                value=default_val,
                step=step,
                help=help_text,
                key=f"{key_prefix}_slider",
                label_visibility="collapsed"
            )
            st.caption(f"🔴 Highlight {label} ≥ {threshold}%")
            return threshold / 100
        else:
            st.caption(f"{label}")
            return None


def render_training_layer_controls(training_status: str = 'All Schools') -> Dict:
    """
    Render map layer visibility toggles with optional depth filters (visual only).

    These controls ONLY affect which colored dots appear on the map.
    They do NOT filter the underlying data - use the Analysis Mode for that.

    Layer availability auto-adjusts based on training_status:
    - "Need Fundamentals": Layers disabled (no trained schools to show)
    - "Need LIGHTS": Only Fundamentals layer shown (schools have Fundamentals)
    - Others: All layers available

    Args:
        training_status: Current analysis mode value

    Returns:
        Dict with layer visibility and depth configuration
    """
    layers = {}

    # Determine which layers are relevant based on analysis mode
    # "Need Fundamentals" shows untrained schools (no training layers needed)
    layers_disabled = training_status == '🎯 Need Fundamentals'
    fund_default = True  # Fundamentals layer on by default for most modes
    lights_default = training_status not in ['🎯 Need LIGHTS']  # LIGHTS layer off for Need LIGHTS mode

    if layers_disabled:
        st.caption("ℹ️ Showing untrained schools (uniform gray)")
        layers['fundamentals'] = {'enabled': False, 'min_depth': 0}
        layers['lights'] = {'enabled': False, 'min_depth': 0}
        layers['student_sessions'] = {'enabled': False, 'placeholder': True}
        return layers

    # === FUNDAMENTALS LAYER ===
    col_toggle, col_label = st.columns([1, 5])
    with col_toggle:
        fund_enabled = st.checkbox(
            "Fundamentals layer",
            value=fund_default,
            key="layer_fundamentals",
            label_visibility="collapsed"
        )
    with col_label:
        color_hex = get_layer_hex_color('fundamentals')
        st.markdown(f"<span style='color:{color_hex}; font-weight:600;'>🔵 Fundamentals</span>", unsafe_allow_html=True)

    # Depth filter for Fundamentals (only show if layer enabled)
    fund_min_depth = 0
    if fund_enabled:
        fund_min_depth = st.slider(
            "Min participants",
            min_value=0, max_value=30, value=0, step=5,
            key="fund_min_depth",
            help="Only show schools with at least this many trained participants",
            label_visibility="collapsed"
        )
        if fund_min_depth > 0:
            st.caption(f"Showing schools with {fund_min_depth}+ participants")

    layers['fundamentals'] = {'enabled': fund_enabled, 'min_depth': fund_min_depth}

    # === LIGHTS ToT LAYER ===
    col_toggle, col_label = st.columns([1, 5])
    with col_toggle:
        lights_enabled = st.checkbox(
            "LIGHTS layer",
            value=lights_default,
            key="layer_lights",
            label_visibility="collapsed"
        )
    with col_label:
        color_hex = get_layer_hex_color('lights')
        st.markdown(f"<span style='color:{color_hex}; font-weight:600;'>🟣 LIGHTS ToT</span>", unsafe_allow_html=True)

    # Depth filter for LIGHTS (only show if layer enabled)
    lights_min_depth = 0
    if lights_enabled:
        lights_min_depth = st.slider(
            "Min trainers",
            min_value=0, max_value=15, value=0, step=1,
            key="lights_min_depth",
            help="Only show schools with at least this many LIGHTS trainers",
            label_visibility="collapsed"
        )
        if lights_min_depth > 0:
            st.caption(f"Showing schools with {lights_min_depth}+ trainers")

    layers['lights'] = {'enabled': lights_enabled, 'min_depth': lights_min_depth}

    # === STUDENT SESSIONS LAYER (PLACEHOLDER) ===
    col_toggle, col_label = st.columns([1, 5])
    with col_toggle:
        st.checkbox(
            "Student Sessions layer",
            value=False,
            key="layer_students",
            disabled=True,
            label_visibility="collapsed"
        )
    with col_label:
        color_hex = get_layer_hex_color('student_sessions')
        st.markdown(f"<span style='color:{color_hex}; font-weight:600;'>🟢 Student Sessions</span> <span style='color:#888; font-size:0.8em;'>(Coming Soon)</span>", unsafe_allow_html=True)

    layers['student_sessions'] = {'enabled': False, 'placeholder': True}

    return layers


def render_sidebar_filters(filter_options: dict) -> dict:
    """
    Render sidebar filter controls and return selected filter values.

    SIDEBAR STRUCTURE:
    1. Analysis Mode (TOP - always visible)
    2. Search + Quick Filters
    3. Geography (expander)
    4. Indicator Highlights (expander)
    5. Map Layers (expander - ONLY on Map tab)

    Args:
        filter_options: Dictionary of available filter options from get_filter_options()

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
    # 1. SEARCH + QUICK FILTERS
    # ════════════════════════════════════════════════════════════════════════════
    st.sidebar.markdown("### 🔍 Search & Filter")

    # Search box
    search_query = st.sidebar.text_input(
        "Search Schools",
        placeholder="Enter school name or DBN...",
        help="Search by school name or DBN code",
        key="filter_search"
    )

    # Quick Filter Buttons
    st.sidebar.caption("Quick Filters")
    col1, col2, col3 = st.sidebar.columns(3)

    with col1:
        no_training = st.button("No Training", use_container_width=True, key="qf_no_training")
    with col2:
        priority_btn = st.button("⚠️ Priority", use_container_width=True, type="primary", key="qf_priority")
    with col3:
        clear_filters = st.button("Clear All", use_container_width=True, key="qf_clear")

    # ════════════════════════════════════════════════════════════════════════════
    # 2. ANALYSIS MODE (after quick filters, outside expander)
    # ════════════════════════════════════════════════════════════════════════════
    st.sidebar.divider()
    analysis_mode = render_analysis_mode()

    # ════════════════════════════════════════════════════════════════════════════
    # 3. GEOGRAPHY (expander)
    # ════════════════════════════════════════════════════════════════════════════
    with st.sidebar.expander("📍 Geography", expanded=False):
        selected_boroughs = st.multiselect(
            "Boroughs",
            options=filter_options.get('boroughs', []),
            default=[],
            placeholder="All boroughs",
            key="filter_boroughs"
        )

        selected_districts = st.multiselect(
            "Districts",
            options=filter_options.get('districts', []),
            default=[],
            placeholder="All districts",
            key="filter_districts"
        )

        # Superintendent Filter (if available)
        superintendents = filter_options.get('superintendents', [])
        selected_superintendent = None
        if superintendents:
            selected_superintendent = st.selectbox(
                "Superintendent",
                options=['All'] + superintendents,
                index=0,
                key="filter_superintendent"
            )
            if selected_superintendent == 'All':
                selected_superintendent = None

        # School Type Filter (if available)
        school_types = filter_options.get('school_types', [])
        selected_school_type = None
        if school_types:
            selected_school_type = st.selectbox(
                "School Type",
                options=['All'] + school_types,
                index=0,
                key="filter_school_type"
            )
            if selected_school_type == 'All':
                selected_school_type = None

    # ════════════════════════════════════════════════════════════════════════════
    # 4. INDICATOR HIGHLIGHTS (expander)
    # ════════════════════════════════════════════════════════════════════════════
    with st.sidebar.expander("📊 Indicator Highlights", expanded=False):
        st.caption("Highlight high-need schools on map (visual only)")

        # STH Indicator - visual highlight
        st.markdown("**🏠 Students in Temp Housing (STH)**")
        highlight_sth = render_indicator_highlight(
            label="STH",
            key_prefix="sth",
            min_val=0,
            max_val=50,
            default_val=30,
            step=5,
            help_text="Highlight schools with high housing instability"
        )

        st.markdown("---")

        # ENI Indicator - visual highlight
        st.markdown("**💰 Economic Need Index (ENI)**")
        highlight_eni = render_indicator_highlight(
            label="ENI",
            key_prefix="eni",
            min_val=50,
            max_val=100,
            default_val=85,
            step=5,
            help_text="Highlight schools with high economic need"
        )

        st.markdown("---")
        st.caption("*More indicators coming soon*")

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
            st.caption("Toggle training types to show on map")
            layer_config = render_training_layer_controls(analysis_mode)
    else:
        # Provide default layer config when not on map tab
        # (preserves any existing session state values)
        layer_config = {
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

    # Build filters dictionary
    filters = {
        'search_query': search_query if search_query else None,
        # Analysis mode (affects ALL views)
        'global_training_status': analysis_mode,
        # Map layer settings (visual only - affects map tab only)
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


def render_filter_summary(filters: dict, total_count: int, filtered_count: int):
    """Display a compact inline badge showing active filters."""
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
    # Note: highlight_sth and highlight_eni are visual-only, not shown in filter summary

    if active_filters:
        # Calculate percentage
        pct = (filtered_count / total_count * 100) if total_count > 0 else 0

        # Compact inline badge
        filter_text = ' • '.join(active_filters)
        st.markdown(
            f"""<div style="background:#f0f2f6; padding:6px 12px; border-radius:4px;
                font-size:12px; display:flex; justify-content:space-between; align-items:center;
                margin-bottom:8px;">
                <span style="color:#555;">🔍 {filter_text}</span>
                <span style="font-weight:600; color:#333;">{filtered_count:,} schools ({pct:.0f}%)</span>
            </div>""",
            unsafe_allow_html=True
        )
