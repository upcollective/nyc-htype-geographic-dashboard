# Solara Prototype - HTYPE Geographic Dashboard

A Solara-based interactive dashboard for visualizing HTYPE training coverage across NYC schools.

## Quick Start

```bash
cd outputs/geographic-dashboard/solara-prototype

# Create virtual environment (first time only)
python3 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
solara run app.py --port 8765
```

Then open: http://localhost:8765

## Why Solara?

| Problem | Streamlit | Solara |
|---------|-----------|--------|
| Re-render on interaction | Full script re-run | Component-level updates only |
| Layout paradigm | Document (vertical scroll) | Application (fixed viewport) |
| Sticky toolbar | CSS hacks, brittle | Native `AppBar` component |
| Sidebar | `st.sidebar` (limited) | Native `Sidebar` (collapsible) |
| Map interactivity | Limited (no click handlers) | Full ipyleaflet integration |

## Current Status

**Production-Ready Dashboard** - Full ipyleaflet map with live Google Sheets data:

### Implemented Features

- [x] AppLayout with AppBar (toolbar) + Sidebar (info panel)
- [x] ipyleaflet map with 1,656 NYC schools
- [x] **Live Google Sheets integration** via service account
- [x] CircleMarkers color-coded by training status
- [x] Click school → details in sidebar with "Locate" button
- [x] **Multi-layer filtering**: Borough, District, Superintendent, School Type
- [x] **Training status filter**: Complete, Fundamentals Only, No Training
- [x] **Vulnerability indicators**: STH (Students in Temporary Housing), ENI (Economic Need Index)
- [x] **View modes**: School Points vs District Choropleth
- [x] **Layer toggles**: Enable/disable Fundamentals, LIGHTS, vulnerability overlays
- [x] **Dynamic legend** via ipyleaflet WidgetControl
- [x] Collapsible sidebar sections
- [x] Auto-zoom to filtered data bounds

### Not Yet Implemented

- [ ] Enhanced sidebar with participant details (see plan file)
- [ ] Cluster aggregate statistics view
- [ ] Export functionality (CSV/Excel)
- [ ] Search by school name

## Known Issues

### Legend Clipping (Cosmetic)

**Status**: Deferred - cosmetic issue, does not affect functionality

**Description**: The bottom-right legend may clip at the bottom edge of the map in certain states, particularly when:
- Multiple layers are enabled (Fundamentals + LIGHTS + vulnerability indicators)
- The legend becomes tall enough to extend near map bounds

**Technical Background**:
- Leaflet internally applies `overflow: hidden` to its tile container
- We've implemented the correct architectural solution: `ipyleaflet.WidgetControl` which injects content into Leaflet's protected `leaflet-control-container`
- This works for most cases, but edge cases remain when legend content is very tall

**Workaround**: The legend includes `max-height: 400px; overflow-y: auto` to allow scrolling if content exceeds bounds

**Research**: See `research/Solara Ipyleaflet Map Overlay Clipping.md` for detailed analysis

## Files

```
solara-prototype/
├── app.py                  # Main application (~3000 lines)
├── requirements.txt        # Dependencies
├── README.md               # This file
├── utils/
│   └── data_loader.py      # Google Sheets integration
├── .credentials/           # Service account (git-ignored)
└── research/               # Technical research documents
    ├── Solara ipyleaflet Click Handler Research.MD
    ├── Solara ipyleaflet Dynamic Popup.md
    ├── Solara Ipyleaflet Map Overlay Clipping.md
    └── Solara Map Interactivity Research.md
```

## Color Scheme

### Training Status (Base Layer)

| Training Status | Color | Hex |
|----------------|-------|-----|
| Complete | Sage green | #6B9080 |
| Fundamentals Only | Warm tan | #D4A574 |
| No Training | Dusty rose | #B87D7D |

### Vulnerability Indicators (Outline Rings)

| Indicator | Active | Outline Color |
|-----------|--------|---------------|
| High STH | Students in Temporary Housing ≥ 5% | Purple (#8B5CF6) |
| High ENI | Economic Need Index ≥ 80% | Teal (#0D9488) |
| Both | Both indicators present | Magenta (#DB2777) |

## Development Notes

### Reactive State Architecture

The app uses Solara's reactive state system:
- `solara.reactive()` for scalar values (selected_school, view_mode)
- `solara.use_state()` for component-local state
- `solara.use_memo()` for expensive computations (data filtering, marker creation)
- `solara.use_effect()` for side effects (legend updates, map zoom)

### Key Patterns

1. **Singleton Widgets**: Create widgets once via `use_memo`, update imperatively via `use_effect`
2. **Traitlet Updates**: Modify widget properties directly instead of recreating
3. **Dependency Tracking**: Explicit dependencies in hooks to control re-execution

## Next Steps

See plan file at `~/.claude/plans/jaunty-crunching-goose.md` for enhanced sidebar implementation:
1. Load participant detail data
2. Enhanced single-school view with training participants
3. Cluster statistics view for filtered selections
4. Export functionality
