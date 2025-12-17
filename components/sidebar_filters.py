"""
Sidebar filter components for the geographic dashboard.
Provides filtering controls for boroughs, districts, training status, etc.
Designed to scale as more indicator variables are added.

Multi-layer training system: Each training type (Fundamentals, LIGHTS, Student Sessions)
can be toggled independently with depth filtering.
"""
import streamlit as st
from typing import Optional, Dict

# Import layer color info for UI
from utils.color_schemes import TRAINING_LAYER_COLORS, get_layer_hex_color


def render_training_status_filter() -> str:
    """
    Render task-oriented view mode filter (affects ALL views).

    This is the primary filter for "what am I trying to analyze?"
    Options are framed around user tasks, not just data attributes.

    Returns:
        Selected view mode string
    """
    status = st.radio(
        "View Mode",
        options=[
            "Training Coverage",        # Default: where we've trained
            "Outreach Targets",         # Where we need to train
            "Fundamentals Only",        # Schools with only Fundamentals
            "LIGHTS Only",              # Schools with only LIGHTS
            "Complete Training",        # Schools with both
            "All Schools (Reference)",  # Full universe, uniform display
        ],
        index=0,
        key="global_training_status",
        help="Select what you want to analyze. Affects all views.",
        label_visibility="collapsed"
    )

    # Show description of current selection
    descriptions = {
        "Training Coverage": "🎯 Schools with training (color = type, size = depth)",
        "Outreach Targets": "📍 Schools needing training (uniform gray dots)",
        "Fundamentals Only": "🔵 Schools with Fundamentals training",
        "LIGHTS Only": "🟣 Schools with LIGHTS ToT training",
        "Complete Training": "✅ Schools with BOTH Fundamentals AND LIGHTS",
        "All Schools (Reference)": "📋 Full school universe (uniform display, reference only)"
    }
    st.caption(descriptions.get(status, ''))

    return status


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
        enabled = st.checkbox("", key=f"{key_prefix}_enabled", label_visibility="collapsed")

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
    They do NOT filter the underlying data - use the global Training Status
    filter for that.

    Layer availability auto-adjusts based on training_status:
    - "No Training": Layers disabled (no trained schools to show)
    - "Has Fundamentals": Fundamentals relevant, LIGHTS may be subset
    - "Has LIGHTS": LIGHTS relevant, Fundamentals may be subset
    - Others: All layers available

    Args:
        training_status: Current global training status filter value

    Returns:
        Dict with layer visibility and depth configuration
    """
    layers = {}

    # Determine which layers are relevant based on training status
    # "Outreach Targets" and "All Schools (Reference)" show uniform dots, no training layers
    layers_disabled = training_status in ['Outreach Targets', 'All Schools (Reference)']
    fund_default = training_status not in ['LIGHTS Only']  # Default on unless only LIGHTS selected
    lights_default = training_status not in ['Fundamentals Only']  # Default on unless only Fund selected

    if layers_disabled:
        if training_status == 'Outreach Targets':
            st.caption("ℹ️ Showing untrained schools (uniform gray)")
        else:
            st.caption("ℹ️ Reference view (uniform display, no training encoding)")
        layers['fundamentals'] = {'enabled': False, 'min_depth': 0}
        layers['lights'] = {'enabled': False, 'min_depth': 0}
        layers['student_sessions'] = {'enabled': False, 'placeholder': True}
        return layers

    # === FUNDAMENTALS LAYER ===
    col_toggle, col_label = st.columns([1, 5])
    with col_toggle:
        fund_enabled = st.checkbox(
            "fund_layer",
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
            "lights_layer",
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
            "students_layer",
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
        # Global training status filter - default to Training Coverage
        st.session_state['global_training_status'] = 'Training Coverage'
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

    st.sidebar.header("🔍 Filters")

    # Search box (always visible)
    search_query = st.sidebar.text_input(
        "Search Schools",
        placeholder="Enter school name or DBN...",
        help="Search by school name or DBN code",
        key="filter_search"
    )

    # Quick Filter Buttons (always visible)
    st.sidebar.markdown("##### Quick Filters")

    col1, col2, col3 = st.sidebar.columns(3)

    with col1:
        no_training = st.button("No Training", use_container_width=True, key="qf_no_training")
    with col2:
        priority_btn = st.button("⚠️ Priority", use_container_width=True, type="primary", key="qf_priority")
    with col3:
        clear_filters = st.button("Clear All", use_container_width=True, key="qf_clear")

    st.sidebar.divider()

    # === GLOBAL TRAINING STATUS FILTER (NEW - affects ALL views) ===
    with st.sidebar.expander("📚 Training Status", expanded=True):
        st.caption("Filter by training completion (affects all views)")
        global_training_status = render_training_status_filter()

    # === MAP LAYERS SECTION (visual only - affects map tab only) ===
    with st.sidebar.expander("🗺️ Map Layers", expanded=False):
        st.caption("Toggle training types to show on map (visual only)")
        layer_config = render_training_layer_controls(global_training_status)

    # === GEOGRAPHY SECTION ===
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

    # === INDICATORS SECTION (Visual Highlights - Map Only) ===
    with st.sidebar.expander("📊 Indicators", expanded=False):
        st.caption("Highlight high-need schools on map (visual only)")

        # STH Indicator - now a visual highlight, not a filter
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

        # ENI Indicator - now a visual highlight, not a filter
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

        # Placeholder for future indicators
        st.markdown("---")
        st.caption("*More indicators coming soon*")

    # Build filters dictionary
    filters = {
        'search_query': search_query if search_query else None,
        # Global training status filter (affects ALL views)
        'global_training_status': global_training_status,
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
        'high_sth_only': False,  # Set by Priority quick filter (this still filters data)
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

    # Apply quick filter - override global_training_status when quick filter is active
    if st.session_state.quick_filter == 'no_training':
        filters['global_training_status'] = 'Outreach Targets'
    elif st.session_state.quick_filter == 'priority':
        # Priority schools: high STH + no training
        filters['global_training_status'] = 'Outreach Targets'
        filters['high_sth_only'] = True

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
    if filters.get('global_training_status') and filters['global_training_status'] != 'Training Coverage':
        active_filters.append(filters['global_training_status'])
    if filters.get('superintendent'):
        active_filters.append(filters['superintendent'][:15] + "..." if len(filters['superintendent']) > 15 else filters['superintendent'])
    if filters.get('has_fundamentals') is False:
        active_filters.append("No Fund.")
    if filters.get('has_lights') is False:
        active_filters.append("No LIGHTS")
    if filters.get('high_sth_only'):
        active_filters.append("Hi STH")
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
