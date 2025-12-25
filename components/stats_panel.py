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


def _render_responsive_metrics(metrics: list, highlight_last: bool = False):
    """
    Render metrics using responsive HTML grid instead of st.columns.
    This ensures proper wrapping at all viewport sizes.

    Args:
        metrics: List of dicts with 'label' and 'value' keys
        highlight_last: If True, render last metric with yellow highlight style
    """
    # Build HTML for each metric card
    cards_html = []
    for i, m in enumerate(metrics):
        is_highlight = highlight_last and i == len(metrics) - 1

        if is_highlight and 'highlight_style' in m:
            # Special highlighted card (e.g., "Remaining")
            cards_html.append(f'''
                <div class="stat-card stat-card-highlight">
                    <div class="stat-label">{m['label']}</div>
                    <div class="stat-value">{m['value']}</div>
                    {f"<div class='stat-sublabel'>{m.get('sublabel', '')}</div>" if m.get('sublabel') else ""}
                </div>
            ''')
        else:
            cards_html.append(f'''
                <div class="stat-card">
                    <div class="stat-label">{m['label']}</div>
                    <div class="stat-value">{m['value']}</div>
                </div>
            ''')

    # Responsive CSS Grid - the key to proper wrapping
    html = f'''
    <style>
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }}
        @media (max-width: 1400px) {{
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        @media (max-width: 1000px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 500px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }}
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            min-width: 0;
        }}
        .stat-card-highlight {{
            background: #fff3cd;
            border-left: 3px solid #ffc107;
        }}
        .stat-label {{
            font-size: 0.7rem;
            color: #666;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 2px;
        }}
        .stat-value {{
            font-size: 1.4rem;
            font-weight: 600;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .stat-sublabel {{
            font-size: 0.65rem;
            color: #856404;
            margin-top: 2px;
        }}
        @media (max-width: 1000px) {{
            .stat-value {{ font-size: 1.2rem; }}
            .stat-label {{ font-size: 0.65rem; }}
        }}
        @media (max-width: 600px) {{
            .stat-value {{ font-size: 1rem; }}
            .stat-label {{ font-size: 0.6rem; }}
        }}
    </style>
    <div class="stats-grid">
        {"".join(cards_html)}
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)


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
    Uses responsive HTML grid instead of st.columns for better mobile support.
    """
    # Row 1: Training status metrics
    metrics_row1 = [
        {"label": "Total Schools", "value": f"{stats['total_schools']:,}"},
        {"label": "LIGHTS Trained", "value": f"{stats['lights_trained']:,} ({stats['lights_trained_pct']}%)"},
        {"label": "Fundamentals Only", "value": f"{stats['fundamentals_only']:,} ({stats['fundamentals_only_pct']}%)"},
        {"label": "Not Started", "value": f"{stats['not_started']:,} ({stats['not_started_pct']}%)"},
    ]
    _render_responsive_metrics(metrics_row1)

    # Row 2: Vulnerability indicators
    _render_indicator_row(stats)


def _render_trained_schools_stats(stats: dict):
    """
    ✅ Trained Schools Mode: Progress view with remaining reference.
    Uses responsive HTML grid.
    """
    remaining = stats.get('remaining', 0)
    metrics_row1 = [
        {"label": "Total Trained", "value": f"{stats['total_schools']:,}"},
        {"label": "LIGHTS Trained", "value": f"{stats['lights_trained']:,} ({stats['lights_trained_pct']}%)"},
        {"label": "Fundamentals Only", "value": f"{stats['fundamentals_only']:,} ({stats['fundamentals_only_pct']}%)"},
        {"label": "🎯 Remaining", "value": f"{remaining:,}", "sublabel": "Awaiting outreach", "highlight_style": True},
    ]
    _render_responsive_metrics(metrics_row1, highlight_last=True)

    # Indicator metrics row
    _render_indicator_row(stats)


def _render_need_fundamentals_stats(stats: dict):
    """
    🎯 Need Fundamentals Mode: Outreach targets with priority focus.
    Uses responsive HTML grid.
    """
    priority = stats.get('priority_schools', 0)
    high_sth = stats.get('high_sth_count', 0)
    prereq = stats.get('prereq_issues', 0)
    avg_eni = stats.get('avg_eni')
    avg_sth = stats.get('avg_sth_percent')

    metrics_row1 = [
        {"label": "Total Targets", "value": f"{stats['total_schools']:,}"},
        {"label": "⚠️ Priority (High ENI)", "value": f"{priority:,}"},
        {"label": "🏠 High STH", "value": f"{high_sth:,}"},
        {"label": "✓ Prereq Check" if prereq == 0 else "⚠️ Prereq Issues", "value": "OK" if prereq == 0 else f"{prereq:,}"},
    ]
    _render_responsive_metrics(metrics_row1)

    # Row 2: Averages
    metrics_row2 = [
        {"label": "Avg ENI", "value": f"{avg_eni:.1%}" if avg_eni else "N/A"},
        {"label": "Avg STH", "value": f"{avg_sth:.1%}" if avg_sth else "N/A"},
    ]
    _render_responsive_metrics(metrics_row2)


def _render_need_lights_stats(stats: dict):
    """
    🎯 Need LIGHTS Mode: Next step ready with high school focus.
    Uses responsive HTML grid.
    """
    high_schools = stats.get('high_schools_count', 0)
    high_eni = stats.get('high_eni_count', 0)
    high_sth = stats.get('high_sth_count', 0)
    avg_eni = stats.get('avg_eni')
    avg_sth = stats.get('avg_sth_percent')

    metrics_row1 = [
        {"label": "Total Ready", "value": f"{stats['total_schools']:,}"},
        {"label": "🏫 High Schools", "value": f"{high_schools:,}"},
        {"label": "⚠️ High ENI", "value": f"{high_eni:,}"},
        {"label": "🏠 High STH", "value": f"{high_sth:,}"},
    ]
    _render_responsive_metrics(metrics_row1)

    # Row 2: Averages
    metrics_row2 = [
        {"label": "Avg ENI", "value": f"{avg_eni:.1%}" if avg_eni else "N/A"},
        {"label": "Avg STH", "value": f"{avg_sth:.1%}" if avg_sth else "N/A"},
    ]
    _render_responsive_metrics(metrics_row2)


def _render_indicator_row(stats: dict):
    """
    Render vulnerability indicator metrics row (common to Overview and Trained Schools modes).
    Uses responsive HTML grid.
    """
    if stats.get('avg_sth_percent') is not None or stats.get('avg_eni') is not None:
        priority = stats.get('priority_schools', 0)
        high_sth = stats.get('high_sth_count', 0)
        avg_sth = stats.get('avg_sth_percent')
        avg_eni = stats.get('avg_eni')

        metrics = [
            {"label": "⚠️ Priority Schools", "value": f"{priority:,}"},
            {"label": "🏠 High STH", "value": f"{high_sth:,}"},
            {"label": "Avg STH", "value": f"{avg_sth:.1%}" if avg_sth else "N/A"},
            {"label": "Avg ENI", "value": f"{avg_eni:.1%}" if avg_eni else "N/A"},
        ]
        _render_responsive_metrics(metrics)


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
