"""
Statistics panel component for the geographic dashboard.
Displays summary metrics and charts for the filtered data.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

from utils.color_schemes import TRAINING_COLORS_HEX, BOROUGH_COLORS


def render_stats_panel(stats: dict, df: pd.DataFrame, mode: str = '📊 Overview'):
    """
    Render the main statistics panel with mode-specific metrics.

    Each mode shows tailored stats for that workflow:
    - 📊 Overview: Full breakdown (LIGHTS Trained, Fundamentals Only, Not Started)
    - ✅ Trained Schools: Progress view with "Remaining" reference
    - 🎯 Need Fundamentals: Outreach targets with Priority counts
    - 🎯 Need LIGHTS: Next step ready with High School focus

    Args:
        stats: Dictionary of summary statistics from calculate_summary_stats()
        df: Filtered DataFrame for charts
        mode: Current view mode (determines which metrics to show)
    """
    # Route to mode-specific rendering
    if mode == '📊 Overview':
        _render_overview_stats(stats)
    elif mode == '✅ Trained Schools':
        _render_trained_schools_stats(stats)
    elif mode == '🎯 Need Fundamentals':
        _render_need_fundamentals_stats(stats)
    elif mode == '🎯 Need LIGHTS':
        _render_need_lights_stats(stats)
    else:
        _render_overview_stats(stats)  # Fallback


def _render_overview_stats(stats: dict):
    """
    📊 Overview Mode: Full picture with training breakdown.
    Row 1: Total Schools | LIGHTS Trained | Fundamentals Only | Not Started
    Row 2: Priority (High ENI) | High STH | Avg STH | Avg ENI
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Schools",
            value=f"{stats['total_schools']:,}",
            help="Number of schools matching current filters"
        )

    with col2:
        st.metric(
            label="LIGHTS Trained",
            value=f"{stats['lights_trained']:,} ({stats['lights_trained_pct']}%)",
            help="Schools with ≥1 person who completed LIGHTS ToT"
        )

    with col3:
        st.metric(
            label="Fundamentals Only",
            value=f"{stats['fundamentals_only']:,} ({stats['fundamentals_only_pct']}%)",
            help="Schools with Fundamentals training, ready for LIGHTS"
        )

    with col4:
        st.metric(
            label="Not Started",
            value=f"{stats['not_started']:,} ({stats['not_started_pct']}%)",
            help="Schools with no HTYPE training recorded"
        )

    # Indicator metrics row (vulnerability context)
    _render_indicator_row(stats)


def _render_trained_schools_stats(stats: dict):
    """
    ✅ Trained Schools Mode: Progress view with remaining reference.
    Row 1: Total Trained | LIGHTS Trained | Fundamentals Only | 🎯 Remaining (global)
    Row 2: Priority (High ENI) | High STH | Avg STH | Avg ENI
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Trained",
            value=f"{stats['total_schools']:,}",
            help="Schools with Fundamentals and/or LIGHTS training"
        )

    with col2:
        st.metric(
            label="LIGHTS Trained",
            value=f"{stats['lights_trained']:,} ({stats['lights_trained_pct']}%)",
            help="Schools with ≥1 person who completed LIGHTS ToT"
        )

    with col3:
        st.metric(
            label="Fundamentals Only",
            value=f"{stats['fundamentals_only']:,} ({stats['fundamentals_only_pct']}%)",
            help="Schools with Fundamentals training, ready for LIGHTS"
        )

    with col4:
        # Show remaining (global count) as reference
        remaining = stats.get('remaining', 0)
        st.markdown(
            f"""<div style="background: #fff3cd; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #ffc107;">
            <p style="font-size: 0.75rem; color: #856404; margin-bottom: 2px; font-weight: 500;">🎯 Remaining</p>
            <p style="font-size: 1.25rem; font-weight: 600; color: #856404; margin: 0;">{remaining:,}</p>
            <p style="font-size: 0.7rem; color: #856404; margin: 0;">Schools awaiting outreach</p>
            </div>""",
            unsafe_allow_html=True
        )

    # Indicator metrics row (from filtered trained schools)
    _render_indicator_row(stats)


def _render_need_fundamentals_stats(stats: dict):
    """
    🎯 Need Fundamentals Mode: Outreach targets with priority focus.
    Row 1: Total Targets | Priority (High ENI) | High STH | ⚠️ Prereq Issues
    Row 2: Avg ENI | Avg STH | - | -
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Targets",
            value=f"{stats['total_schools']:,}",
            help="Schools with no training at all - outreach targets"
        )

    with col2:
        priority = stats.get('priority_schools', 0)
        st.metric(
            label="⚠️ Priority (High ENI)",
            value=f"{priority:,}",
            help="High ENI (≥85%) + No training - most vulnerable schools"
        )

    with col3:
        high_sth = stats.get('high_sth_count', 0)
        st.metric(
            label="🏠 High STH",
            value=f"{high_sth:,}",
            help="Schools with STH ≥ 30%"
        )

    with col4:
        prereq = stats.get('prereq_issues', 0)
        if prereq > 0:
            st.markdown(
                f"""<div style="background: #f8d7da; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #dc3545;">
                <p style="font-size: 0.75rem; color: #721c24; margin-bottom: 2px; font-weight: 500;">⚠️ Prereq Issues</p>
                <p style="font-size: 1.25rem; font-weight: 600; color: #721c24; margin: 0;">{prereq:,}</p>
                <p style="font-size: 0.7rem; color: #721c24; margin: 0;">LIGHTS without Fundamentals</p>
                </div>""",
                unsafe_allow_html=True
            )
        else:
            st.metric(
                label="✓ Prereq Check",
                value="OK",
                help="No schools have LIGHTS without Fundamentals"
            )

    # Vulnerability indicators row (slimmed down)
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        avg_eni = stats.get('avg_eni')
        st.metric(
            label="Avg ENI",
            value=f"{avg_eni:.1%}" if avg_eni else "N/A",
            help="Average Economic Need Index (targets)"
        )

    with col6:
        avg_sth = stats.get('avg_sth_percent')
        st.metric(
            label="Avg STH",
            value=f"{avg_sth:.1%}" if avg_sth else "N/A",
            help="Average % Students in Temporary Housing (targets)"
        )


def _render_need_lights_stats(stats: dict):
    """
    🎯 Need LIGHTS Mode: Next step ready with high school focus.
    Row 1: Total Ready | 🏫 High Schools | Priority (High ENI) | High STH
    Row 2: Avg ENI | Avg STH | - | -
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Ready",
            value=f"{stats['total_schools']:,}",
            help="Schools with Fundamentals, ready for LIGHTS ToT"
        )

    with col2:
        high_schools = stats.get('high_schools_count', 0)
        st.metric(
            label="🏫 High Schools",
            value=f"{high_schools:,}",
            help="High Schools needing LIGHTS - highest priority for student curriculum"
        )

    with col3:
        # Priority count from filtered Need LIGHTS schools (high ENI in this subset)
        high_eni = stats.get('high_eni_count', 0)
        st.metric(
            label="⚠️ High ENI",
            value=f"{high_eni:,}",
            help="High ENI (≥85%) schools in this set"
        )

    with col4:
        high_sth = stats.get('high_sth_count', 0)
        st.metric(
            label="🏠 High STH",
            value=f"{high_sth:,}",
            help="Schools with STH ≥ 30%"
        )

    # Vulnerability indicators row (slimmed down)
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        avg_eni = stats.get('avg_eni')
        st.metric(
            label="Avg ENI",
            value=f"{avg_eni:.1%}" if avg_eni else "N/A",
            help="Average Economic Need Index"
        )

    with col6:
        avg_sth = stats.get('avg_sth_percent')
        st.metric(
            label="Avg STH",
            value=f"{avg_sth:.1%}" if avg_sth else "N/A",
            help="Average % Students in Temporary Housing"
        )


def _render_indicator_row(stats: dict):
    """
    Render vulnerability indicator metrics row (common to Overview and Trained Schools modes).
    Row: Priority (High ENI) | High STH | Avg STH | Avg ENI
    """
    if stats.get('avg_sth_percent') is not None or stats.get('avg_eni') is not None:
        col5, col6, col7, col8 = st.columns(4)

        with col5:
            priority = stats.get('priority_schools', 0)
            st.metric(
                label="⚠️ Priority Schools",
                value=f"{priority:,}",
                help="High ENI (≥85%) + No training - vulnerable schools needing outreach (global)"
            )

        with col6:
            high_sth = stats.get('high_sth_count', 0)
            st.metric(
                label="🏠 High STH",
                value=f"{high_sth:,}",
                help="Schools with STH ≥ 30%"
            )

        with col7:
            avg_sth = stats.get('avg_sth_percent')
            st.metric(
                label="Avg STH",
                value=f"{avg_sth:.1%}" if avg_sth else "N/A",
                help="Average % Students in Temporary Housing"
            )

        with col8:
            avg_eni = stats.get('avg_eni')
            st.metric(
                label="Avg ENI",
                value=f"{avg_eni:.1%}" if avg_eni else "N/A",
                help="Average Economic Need Index"
            )


def render_training_status_chart(df: pd.DataFrame):
    """Render a donut chart of training status distribution."""
    status_counts = df['training_status'].value_counts()

    colors = [TRAINING_COLORS_HEX.get(status, '#8E99A4') for status in status_counts.index]

    fig = go.Figure(data=[go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        hole=0.5,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='outside',
        pull=[0.02] * len(status_counts)
    )])

    fig.update_layout(
        showlegend=False,
        margin=dict(t=20, b=20, l=20, r=20),
        height=300,
        font=dict(size=12)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_borough_breakdown(df: pd.DataFrame):
    """Render training status breakdown by borough."""
    if 'borough' not in df.columns:
        return

    # Create crosstab
    borough_status = pd.crosstab(df['borough'], df['training_status'])

    # Reorder columns
    col_order = ['Complete', 'Fundamentals Only', 'LIGHTS Only', 'No Training', 'Unknown']
    borough_status = borough_status.reindex(columns=[c for c in col_order if c in borough_status.columns])

    # Create stacked bar chart
    fig = go.Figure()

    colors = [TRAINING_COLORS_HEX.get(col, '#8E99A4') for col in borough_status.columns]

    for i, col in enumerate(borough_status.columns):
        fig.add_trace(go.Bar(
            name=col,
            x=borough_status.index,
            y=borough_status[col],
            marker_color=colors[i]
        ))

    fig.update_layout(
        barmode='stack',
        xaxis_title="Borough",
        yaxis_title="Number of Schools",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        margin=dict(t=50, b=50, l=50, r=20),
        height=350
    )

    st.plotly_chart(fig, use_container_width=True)


def render_district_heatmap(df: pd.DataFrame):
    """Render a heatmap of training coverage by district."""
    if 'district' not in df.columns:
        return

    # Calculate completion rate by district
    district_stats = df.groupby('district').agg({
        'school_dbn': 'count',
        'training_status': lambda x: (x == 'Complete').sum()
    }).rename(columns={'school_dbn': 'total', 'training_status': 'complete'})

    district_stats['completion_rate'] = (district_stats['complete'] / district_stats['total'] * 100).round(1)
    district_stats = district_stats.reset_index()

    fig = px.bar(
        district_stats,
        x='district',
        y='completion_rate',
        color='completion_rate',
        color_continuous_scale=['#B87D7D', '#D4A574', '#6B9080'],
        labels={'district': 'District', 'completion_rate': 'Completion Rate (%)'},
        hover_data={'total': True, 'complete': True}
    )

    fig.update_layout(
        xaxis_title="District",
        yaxis_title="Completion Rate (%)",
        coloraxis_showscale=False,
        margin=dict(t=20, b=50, l=50, r=20),
        height=300
    )

    st.plotly_chart(fig, use_container_width=True)


def render_sth_distribution(df: pd.DataFrame):
    """Render a histogram of STH (Students in Temporary Housing) distribution."""
    if 'sth_percent' not in df.columns:
        return

    sth_data = df['sth_percent'].dropna() * 100  # Convert to percentage

    if len(sth_data) == 0:
        return

    fig = px.histogram(
        sth_data,
        nbins=20,
        labels={'value': 'STH %', 'count': 'Schools'},
        color_discrete_sequence=['#6B9080']
    )

    # Add vertical line at 30% threshold
    fig.add_vline(x=30, line_dash="dash", line_color="#B87D7D",
                  annotation_text="High (30%)", annotation_position="top right")

    fig.update_layout(
        xaxis_title="STH %",
        yaxis_title="Schools",
        showlegend=False,
        margin=dict(t=30, b=40, l=40, r=20),
        height=200
    )

    st.plotly_chart(fig, use_container_width=True)


def render_eni_distribution(df: pd.DataFrame):
    """Render a histogram of ENI (Economic Need Index) distribution."""
    if 'economic_need_index' not in df.columns:
        return

    eni_data = df['economic_need_index'].dropna() * 100  # Convert to percentage

    if len(eni_data) == 0:
        return

    fig = px.histogram(
        eni_data,
        nbins=20,
        labels={'value': 'ENI %', 'count': 'Schools'},
        color_discrete_sequence=['#D4A574']
    )

    # Add vertical line at 85% threshold
    fig.add_vline(x=85, line_dash="dash", line_color="#B87D7D",
                  annotation_text="High (85%)", annotation_position="top left")

    fig.update_layout(
        xaxis_title="ENI %",
        yaxis_title="Schools",
        showlegend=False,
        margin=dict(t=30, b=40, l=40, r=20),
        height=200
    )

    st.plotly_chart(fig, use_container_width=True)


def render_priority_schools_table(df: pd.DataFrame, limit: int = 20):
    """
    Render a table of priority schools (high ENI + no training).

    Priority is based on ENI (Economic Need Index) ≥85% because it's a composite
    indicator that captures multiple vulnerability factors including STH.
    """
    if 'economic_need_index' not in df.columns or 'training_status' not in df.columns:
        st.info("Priority school data not available (ENI data required).")
        return

    # Filter to priority schools: high ENI (≥85%) + no training
    priority_mask = (df['economic_need_index'] >= 0.85) & (df['training_status'] == 'No Training')
    priority_df = df[priority_mask].copy()

    if len(priority_df) == 0:
        st.success("✅ No priority schools found - all high-ENI schools have training!")
        return

    # Sort by ENI descending (highest need first)
    priority_df = priority_df.sort_values('economic_need_index', ascending=False)

    # Select display columns
    display_cols = ['school_dbn', 'school_name', 'borough', 'district']

    # Add formatted ENI column (primary indicator)
    priority_df['ENI %'] = priority_df['economic_need_index'].apply(
        lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
    )
    display_cols.append('ENI %')

    # Add formatted STH column if available (secondary context)
    if 'sth_percent' in priority_df.columns:
        priority_df['STH %'] = priority_df['sth_percent'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
        display_cols.append('STH %')

    st.warning(f"⚠️ {len(priority_df)} Priority Schools (High ENI ≥85% + No Training)")
    st.dataframe(
        priority_df[display_cols].head(limit),
        use_container_width=True,
        hide_index=True
    )
