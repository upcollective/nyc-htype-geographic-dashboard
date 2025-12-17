"""
Export functionality for the geographic dashboard.
Provides CSV download of filtered school data.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Optional


def get_export_columns() -> List[str]:
    """Get the list of columns to include in exports."""
    return [
        'school_dbn',
        'school_name',
        'borough',
        'district',
        'superintendent_name',
        'training_status',
        'has_fundamentals',
        'has_lights',
        'total_participants',
        'fundamentals_participants',
        'lights_participants',
        'last_training_date',
        'school_type',
        'grade_levels',
        'primary_address',
    ]


def prepare_export_data(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare DataFrame for export with clean column names."""
    export_cols = get_export_columns()

    # Filter to available columns
    available_cols = [col for col in export_cols if col in df.columns]

    export_df = df[available_cols].copy()

    # Clean up column names for export
    column_renames = {
        'school_dbn': 'DBN',
        'school_name': 'School Name',
        'borough': 'Borough',
        'district': 'District',
        'superintendent_name': 'Superintendent',
        'training_status': 'Training Status',
        'has_fundamentals': 'Has Fundamentals',
        'has_lights': 'Has LIGHTS',
        'total_participants': 'Total Participants',
        'fundamentals_participants': 'Fundamentals Participants',
        'lights_participants': 'LIGHTS Participants',
        'last_training_date': 'Last Training Date',
        'school_type': 'School Type',
        'grade_levels': 'Grade Levels',
        'primary_address': 'Address',
    }

    export_df = export_df.rename(columns={k: v for k, v in column_renames.items() if k in export_df.columns})

    return export_df


def render_export_panel(df: pd.DataFrame, filters_summary: str = ""):
    """
    Render the export panel with download button.

    Args:
        df: Filtered DataFrame to export
        filters_summary: Optional string describing active filters
    """
    st.subheader("📥 Export Data")

    export_df = prepare_export_data(df)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"htype_schools_export_{timestamp}.csv"

    # Convert to CSV
    csv = export_df.to_csv(index=False)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.download_button(
            label=f"⬇️ Download CSV ({len(export_df):,} schools)",
            data=csv,
            file_name=filename,
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        if st.button("📋 Copy to Clipboard", use_container_width=True):
            st.toast("Data copied! (Use the download button for best results)", icon="✅")

    # Preview
    with st.expander("Preview Export Data"):
        st.dataframe(
            export_df.head(20),
            use_container_width=True,
            height=300
        )

        if len(export_df) > 20:
            st.caption(f"Showing first 20 of {len(export_df):,} rows")


def render_quick_exports(df: pd.DataFrame):
    """Render quick export buttons for common views."""
    st.subheader("Quick Exports")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Schools with no training
        no_training = df[df['training_status'] == 'No Training']
        if len(no_training) > 0:
            csv = prepare_export_data(no_training).to_csv(index=False)
            st.download_button(
                label=f"🔴 No Training ({len(no_training)})",
                data=csv,
                file_name=f"schools_no_training_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("🔴 No Training (0)", disabled=True, use_container_width=True)

    with col2:
        # Schools missing Fundamentals
        no_fund = df[df['has_fundamentals'] == 'No']
        if len(no_fund) > 0:
            csv = prepare_export_data(no_fund).to_csv(index=False)
            st.download_button(
                label=f"🟡 No Fundamentals ({len(no_fund)})",
                data=csv,
                file_name=f"schools_no_fundamentals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("🟡 No Fundamentals (0)", disabled=True, use_container_width=True)

    with col3:
        # Schools missing LIGHTS
        no_lights = df[df['has_lights'] == 'No']
        if len(no_lights) > 0:
            csv = prepare_export_data(no_lights).to_csv(index=False)
            st.download_button(
                label=f"🟠 No LIGHTS ({len(no_lights)})",
                data=csv,
                file_name=f"schools_no_lights_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("🟠 No LIGHTS (0)", disabled=True, use_container_width=True)
