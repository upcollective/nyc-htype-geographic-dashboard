# HTYPE Geographic Intelligence Dashboard

An interactive visualization tool for mapping Human Trafficking Prevention Education (HTYPE) training coverage across NYC's 1,656 public schools.

## Features

- **Interactive Map**: View all NYC schools color-coded by training status
- **District View**: Toggle to choropleth view showing district-level coverage
- **Multi-Layer Filtering**: Filter by borough, district, superintendent, training status, school type
- **Vulnerability Indicators**: STH (Students in Temporary Housing) and ENI (Economic Need Index) overlays
- **Priority Schools**: Automatic identification of high-need, untrained schools
- **Statistics**: Real-time metrics and charts updating with filters
- **Export**: Download filtered school lists as CSV

## Quick Start

### Prerequisites

- Python 3.9+
- Google Cloud service account with Sheets API access
- Access to the HTYPE data Google Sheets

### Installation

```bash
# Navigate to dashboard directory
cd outputs/geographic-dashboard

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Google Sheets Setup

1. **Create a Google Cloud service account** with Sheets API enabled
2. **Download the JSON credentials** and save to `.credentials/service-account.json`
3. **Share the data Google Sheets** with the service account email:
   - HTYPE PowerBI Export sheet (training data)
   - NYC Schools Reference Data sheet (vulnerability indicators)

```bash
# Set secure permissions on credentials
chmod 600 .credentials/service-account.json
```

### Run Locally

```bash
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`

## Project Structure

```
geographic-dashboard/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .gitignore              # Git ignore rules
├── .credentials/           # Service account credentials (NOT committed)
│   └── service-account.json
├── .streamlit/
│   └── config.toml         # Streamlit theme configuration
│
├── data/
│   └── geo/                # Geographic reference data
│       └── nyc_school_districts.geojson
│
├── components/             # UI components
│   ├── sidebar_filters.py  # Filter controls
│   ├── map_view.py         # Pydeck map rendering
│   ├── stats_panel.py      # Statistics and charts
│   └── export_panel.py     # CSV export functionality
│
├── scripts/                # Utility scripts
│   ├── apps_script_refresh.js   # Google Apps Script for auto-refresh
│   └── setup_reference_sheet.py # Initial data upload script
│
└── utils/
    ├── data_loader.py          # Google Sheets data loading
    ├── vulnerability_loader.py # STH/ENI indicator loading
    └── color_schemes.py        # Muted color palettes
```

## Data Architecture

### Live Data from Google Sheets

All data is loaded directly from Google Sheets via the Sheets API:

| Sheet | Purpose | Key Fields |
|-------|---------|------------|
| **HTYPE PowerBI Export** | Training data | school_dbn, geo_coordinates, training_status |
| **NYC Schools Reference Data** | Vulnerability indicators | ENI, STH by school |

### Auto-Refresh with Apps Script

The `scripts/apps_script_refresh.js` can be added to the Reference Data sheet to automatically pull fresh data from NYC Open Data APIs:
- Economic Need Index (ENI) from DOE Demographic Snapshot
- Students in Temporary Housing (STH) from DOE data

## Color Scheme

Training status uses a muted, design-conscious palette:

| Status | Color | Hex |
|--------|-------|-----|
| Complete (Both) | Soft Sage | `#6B9080` |
| Partial (One) | Warm Amber | `#D4A574` |
| No Training | Dusty Rose | `#B87D7D` |
| Unknown | Cool Slate | `#8E99A4` |

## Deployment

### Streamlit Cloud

1. Push this project to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select the repository and `app.py` as the main file
5. Add secrets in the Streamlit Cloud dashboard:
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "your-service-account@project.iam.gserviceaccount.com"
   # ... rest of service account JSON fields
   ```

### Password Protection (Optional)

To add password protection, create `.streamlit/secrets.toml`:

```toml
[passwords]
admin = "secure-password-here"
```

## Development

### Adding New Filters

1. Add filter UI in `components/sidebar_filters.py`
2. Add filter logic in `utils/data_loader.py` → `filter_schools()`
3. Update filter options in `get_filter_options()`

### Adding New Vulnerability Indicators

1. Add data source in `utils/vulnerability_loader.py`
2. Update `merge_vulnerability_with_training()` to include new fields
3. Add visualization in `components/stats_panel.py`

## Contact

**NYC DOE Office of Safety and Youth Development**
- Donna Brailsford (Project Lead)
- Jarrett Davis (Data Analyst)

---

*Built with Streamlit, Pydeck, Plotly, and Google Sheets API*
