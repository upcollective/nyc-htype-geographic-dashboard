"""
HTYPE Geographic Intelligence Dashboard

An interactive visualization tool for NYC schools showing:
- Human trafficking prevention education (HTYPE) training coverage
- Geographic distribution across 1,656 schools
- Filtering and export capabilities for OSYD team

Built with Streamlit + Pydeck for the NYC Department of Education.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.data_loader import (
    load_school_data,
    get_filter_options,
    filter_schools,
    filter_by_training_status,
    calculate_summary_stats
)
from components.sidebar_filters import render_sidebar_filters, render_filter_summary
from components.map_view import (
    render_map, render_map_legend, render_map_with_layers,
    render_layer_legend, render_map_with_view_toggle
)
from components.stats_panel import (
    render_stats_panel,
    render_training_status_chart,
    render_borough_breakdown,
    render_sth_distribution,
    render_eni_distribution,
    render_priority_schools_table
)
from components.export_panel import render_export_panel, render_quick_exports


# Page configuration
st.set_page_config(
    page_title="HTYPE Geographic Dashboard",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for compact, map-first design
st.markdown("""
<style>
    /* Eliminate ALL top padding/margins */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
    }

    /* Minimize Streamlit's default header but KEEP sidebar toggle visible */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: auto !important;
        min-height: 0 !important;
    }
    /* Hide the decorative/branding parts but keep functional buttons */
    header[data-testid="stHeader"] [data-testid="stDecoration"] {
        display: none !important;
    }

    /* Remove top margin from first element */
    .main > div:first-child {
        padding-top: 0 !important;
    }

    /* Compact metrics */
    [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        line-height: 1.1 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.65rem !important;
    }
    [data-testid="stMetric"] {
        padding: 0.25rem 0 !important;
    }

    /* Mobile responsive: Force 2-column grid for metrics on small screens */
    @media (max-width: 768px) {
        /* Target horizontal blocks containing metrics - force 2-column grid */
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 0.5rem !important;
        }
        /* Ensure each column fills its grid cell */
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
            width: 100% !important;
            flex: none !important;
        }
        /* Slightly smaller metrics on mobile for better fit */
        [data-testid="stMetricValue"] {
            font-size: 1rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.6rem !important;
        }
    }

    /* Style horizontal radio as tabs */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stRadio"]) {
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 0.5rem;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stRadio"] > div {
        gap: 0 !important;
    }
    div[data-testid="stRadio"] label {
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 0.5rem 1rem !important;
        margin: 0 !important;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    div[data-testid="stRadio"] label:hover {
        background: #f0f2f6;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        border-bottom: 2px solid #ff4b4b;
        font-weight: 600;
    }
    /* Hide radio circles */
    div[data-testid="stRadio"] input[type="radio"] {
        display: none;
    }

    /* Minimal dividers */
    hr {
        margin: 0.5rem 0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Fix sidebar top spacing - AGGRESSIVE approach */
    /* Hide logo spacer with multiple techniques */
    [data-testid="stLogoSpacer"] {
        display: none !important;
        height: 0 !important;
        max-height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: hidden !important;
        visibility: hidden !important;
    }
    /* Collapse the sidebar header container */
    [data-testid="stSidebarHeader"] {
        height: auto !important;
        min-height: 0 !important;
        padding: 0.25rem 0.5rem !important;
        margin: 0 !important;
    }
    /* Pull sidebar content up with negative margin if needed */
    [data-testid="stSidebarUserContent"] {
        padding-top: 0 !important;
        margin-top: -1rem !important;
    }
    /* Also target the direct wrapper */
    section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] > div:first-child {
        display: none !important;
    }

    /* Dashboard header styling */
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid #eee;
        margin-bottom: 0.5rem;
    }
    .dashboard-header h4 {
        margin: 0 !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Load and cache school data from Google Sheets.

    Cache version: 7 - Added vulnerability data fallback debugging
    """
    try:
        df = load_school_data()
        # Debug: Show vulnerability columns status
        vuln_cols = ['sth_percent', 'economic_need_index', 'high_sth', 'high_eni']
        loaded_cols = [c for c in vuln_cols if c in df.columns]
        print(f"[CACHE] Data loaded. Vulnerability columns present: {loaded_cols}")
        if 'sth_percent' in df.columns:
            sth_count = df['sth_percent'].notna().sum()
            print(f"[CACHE] sth_percent has {sth_count} non-null values")
        if 'economic_need_index' in df.columns:
            eni_count = df['economic_need_index'].notna().sum()
            print(f"[CACHE] economic_need_index has {eni_count} non-null values")
        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        import traceback
        st.error(traceback.format_exc())
        st.stop()


def main():
    """Main application entry point."""

    # No header - title shows in browser tab, tabs provide context
    # This maximizes map space (Google Maps approach)

    # Load data
    with st.spinner("Loading school data..."):
        df = load_data()

    # Get filter options
    filter_options = get_filter_options(df)

    # Render sidebar filters
    filters = render_sidebar_filters(filter_options)

    # Subtle data refresh at bottom of sidebar
    with st.sidebar:
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.caption("Data cached 1hr")
        with col2:
            if st.button("↻ Refresh", key="refresh_data", help="Clear cache and reload from Google Sheets"):
                st.cache_data.clear()
                st.rerun()

    # Apply geographic filters (indicators are now visual-only, not filters)
    geo_filtered_df = filter_schools(
        df,
        boroughs=filters.get('boroughs'),
        districts=filters.get('districts'),
        superintendent=filters.get('superintendent'),
        school_type=filters.get('school_type'),
        search_query=filters.get('search_query'),
        high_eni_only=filters.get('high_eni_only', False),  # Priority quick filter (ENI ≥85%)
    )

    # Get indicator highlight thresholds (visual only - affects map markers)
    highlight_config = {
        'sth_threshold': filters.get('highlight_sth'),
        'eni_threshold': filters.get('highlight_eni'),
    }

    # Apply global training status mode (affects ALL views: Map, Stats, Indicators, Data Table)
    # This is now a "mode" selector, not just a filter - each mode has tailored stats
    mode = filters.get('global_training_status', '📊 Overview')
    filtered_df = filter_by_training_status(geo_filtered_df, mode)

    # Get map display settings (visual only - don't affect data filtering)
    layer_config = filters.get('layer_config', {})

    # Calculate stats - pass both filtered and geo-only filtered for universe metrics
    # (priority_schools and remaining should always show the big picture)
    stats = calculate_summary_stats(filtered_df, full_df=geo_filtered_df, mode=mode)

    # Show filter summary if filters are active
    render_filter_summary(filters, len(df), len(filtered_df))

    # Dashboard header
    st.markdown(
        f'''<div class="dashboard-header">
            <h4 style="margin:0;color:#333;">🗺️ HTYPE Geographic Dashboard</h4>
            <span style="color:#666;font-size:13px;">{len(filtered_df):,} / {len(df):,} schools</span>
        </div>''',
        unsafe_allow_html=True
    )

    # Tab navigation with session state persistence
    # Using st.radio instead of st.tabs to maintain selection across filter changes
    TAB_OPTIONS = ["🗺️ Map", "📊 Statistics", "📈 Indicators", "📥 Export", "📋 Data Table"]

    # Initialize session state for active tab
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = TAB_OPTIONS[0]

    # Render tab selector (horizontal radio styled as tabs)
    active_tab = st.radio(
        "Navigation",
        options=TAB_OPTIONS,
        index=TAB_OPTIONS.index(st.session_state.active_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="tab_selector"
    )

    # Update session state when tab changes
    st.session_state.active_tab = active_tab

    # Render content based on active tab (conditional rendering for persistence)
    if active_tab == "🗺️ Map":
        # Compact stats at top (no divider - flows directly into map)
        # Mode determines which tailored stats panel to show
        render_stats_panel(stats, filtered_df, mode=mode)

        # Get layer config from filters
        layer_config = filters.get('layer_config', {})

        # Map view toggle - compact switch directly above map
        col_toggle, col_spacer = st.columns([3, 7])
        with col_toggle:
            show_districts = st.toggle(
                "📊 District View",
                value=False,
                key="map_view_mode",
                help="Switch between individual schools and district choropleth"
            )
        map_view = 'districts' if show_districts else 'schools'

        # Derive choropleth layer from layer_config (first enabled layer)
        choropleth_layer = 'fundamentals'  # default
        for lt in ['fundamentals', 'lights', 'student_sessions']:
            config = layer_config.get(lt, {})
            if config.get('enabled', False) and not config.get('placeholder', False):
                choropleth_layer = lt
                break

        # Render map with view toggle (handles legend + map for both modes)
        render_map_with_view_toggle(
            filtered_df, layer_config, map_view, choropleth_layer,
            highlight_config=highlight_config, height=700
        )

        # Minimal caption with context-aware info
        if map_view == 'districts':
            layer_names = {'fundamentals': 'Fundamentals', 'lights': 'LIGHTS ToT', 'student_sessions': 'Student Sessions'}
            layer_name = layer_names.get(choropleth_layer, 'Fundamentals')
            st.caption(
                f"33 districts • {layer_name} coverage • Hover for details"
            )
        else:
            enabled_count = sum(
                1 for lt in ['fundamentals', 'lights', 'student_sessions']
                if layer_config.get(lt, {}).get('enabled', False)
                and not layer_config.get(lt, {}).get('placeholder', False)
            )
            st.caption(
                f"{stats['mappable_schools']:,} schools mapped • {enabled_count} layer(s) active • Click for details"
            )

    elif active_tab == "📊 Statistics":
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Training Status Distribution")
            render_training_status_chart(filtered_df)

        with col2:
            st.subheader("Borough Breakdown")
            render_borough_breakdown(filtered_df)

        st.divider()

        # Additional metrics
        st.subheader("Key Metrics")
        render_stats_panel(stats, filtered_df)

    elif active_tab == "📈 Indicators":
        st.subheader("School-Level Indicators")
        st.caption("Each indicator is shown separately for independent analysis")

        # Indicator cards in a grid layout
        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.markdown("#### 🏠 Students in Temporary Housing (STH)")
                st.caption("% of students experiencing housing instability")

                if 'sth_percent' in filtered_df.columns:
                    sth_data = filtered_df['sth_percent'].dropna()
                    if len(sth_data) > 0:
                        m1, m2 = st.columns(2)
                        with m1:
                            st.metric("Average", f"{sth_data.mean():.1%}")
                            st.metric("Schools with Data", f"{len(sth_data):,}")
                        with m2:
                            st.metric("Maximum", f"{sth_data.max():.1%}")
                            high_sth = (filtered_df['sth_percent'] >= 0.30).sum()
                            st.metric("High STH (≥30%)", f"{high_sth:,}")

                        # Mini histogram
                        render_sth_distribution(filtered_df)
                    else:
                        st.info("No STH data available for current filter.")
                else:
                    st.warning("STH data not loaded.")

        with col2:
            with st.container(border=True):
                st.markdown("#### 💰 Economic Need Index (ENI)")
                st.caption("DOE composite measure of economic disadvantage")

                if 'economic_need_index' in filtered_df.columns:
                    eni_data = filtered_df['economic_need_index'].dropna()
                    if len(eni_data) > 0:
                        m1, m2 = st.columns(2)
                        with m1:
                            st.metric("Average", f"{eni_data.mean():.1%}")
                            st.metric("Schools with Data", f"{len(eni_data):,}")
                        with m2:
                            st.metric("Maximum", f"{eni_data.max():.1%}")
                            high_eni = (filtered_df['economic_need_index'] >= 0.85).sum()
                            st.metric("High ENI (≥85%)", f"{high_eni:,}")

                        # ENI histogram
                        render_eni_distribution(filtered_df)
                    else:
                        st.info("No ENI data available for current filter.")
                else:
                    st.warning("ENI data not loaded.")

        st.divider()

        # Priority Schools section - high STH + no training
        # Uses geo_filtered_df (not training-filtered) so priority schools always visible
        with st.container(border=True):
            st.markdown("#### ⚠️ Priority Schools for Outreach")
            st.caption("Schools with **HIGH ENI (≥85%)** and **NO training** — highest priority for HTYPE deployment")
            render_priority_schools_table(geo_filtered_df)

    elif active_tab == "📥 Export":
        render_quick_exports(df)  # Use full df for quick exports

        st.divider()

        render_export_panel(filtered_df)

    elif active_tab == "📋 Data Table":
        st.subheader("School Data Table")

        # Column selector
        all_cols = filtered_df.columns.tolist()
        default_cols = ['school_dbn', 'school_name', 'borough', 'district',
                       'training_status', 'total_participants', 'has_fundamentals', 'has_lights']
        selected_cols = st.multiselect(
            "Select columns to display",
            options=all_cols,
            default=[c for c in default_cols if c in all_cols]
        )

        if selected_cols:
            st.dataframe(
                filtered_df[selected_cols],
                use_container_width=True,
                height=500
            )
        else:
            st.info("Select columns to display the data table.")

    # Minimal footer
    st.caption(
        f"HTYPE Dashboard • NYC DOE OSYD • {pd.Timestamp.now().strftime('%B %Y')}"
    )


if __name__ == "__main__":
    main()
