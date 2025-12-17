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


def render_stats_panel(stats: dict, df: pd.DataFrame):
    """
    Render the main statistics panel with key metrics.

    Args:
        stats: Dictionary of summary statistics from calculate_summary_stats()
        df: Filtered DataFrame for charts
    """
    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Schools",
            value=f"{stats['total_schools']:,}",
            help="Number of schools matching current filters"
        )

    with col2:
        st.metric(
            label="Complete Training",
            value=f"{stats['complete']:,}",
            delta=f"{stats['complete_pct']}%",
            delta_color="normal"
        )

    with col3:
        st.metric(
            label="Partial Training",
            value=f"{stats['partial']:,}",
            delta=f"{stats['partial_pct']}%",
            delta_color="off"
        )

    with col4:
        st.metric(
            label="No Training",
            value=f"{stats['no_training']:,}",
            delta=f"{stats['no_training_pct']}%",
            delta_color="inverse"
        )

    # Indicator metrics row (if data available)
    if stats.get('avg_sth_percent') is not None or stats.get('avg_eni') is not None:
        col5, col6, col7, col8 = st.columns(4)

        with col5:
            priority = stats.get('priority_schools', 0)
            st.metric(
                label="⚠️ Priority Schools",
                value=f"{priority:,}",
                help="High STH (≥30%) + No training"
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
    """Render a table of priority schools (high STH + no training)."""
    if 'sth_percent' not in df.columns or 'training_status' not in df.columns:
        st.info("Priority school data not available.")
        return

    # Filter to priority schools: high STH (≥30%) + no training
    priority_mask = (df['sth_percent'] >= 0.30) & (df['training_status'] == 'No Training')
    priority_df = df[priority_mask].copy()

    if len(priority_df) == 0:
        st.success("✅ No priority schools found - all high-STH schools have training!")
        return

    # Sort by STH percent descending
    priority_df = priority_df.sort_values('sth_percent', ascending=False)

    # Select display columns
    display_cols = ['school_dbn', 'school_name', 'borough', 'district']

    # Add formatted STH column
    priority_df['STH %'] = priority_df['sth_percent'].apply(
        lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
    )
    display_cols.append('STH %')

    # Add formatted ENI column if available
    if 'economic_need_index' in priority_df.columns:
        priority_df['ENI %'] = priority_df['economic_need_index'].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )
        display_cols.append('ENI %')

    st.warning(f"⚠️ {len(priority_df)} Priority Schools (High STH ≥30% + No Training)")
    st.dataframe(
        priority_df[display_cols].head(limit),
        use_container_width=True,
        hide_index=True
    )
