# Handoff: Map Auto-Zoom and Basemap Display Issues

## Context

The Solara prototype dashboard at `outputs/geographic-dashboard/solara-prototype/app.py` displays a map of NYC schools using ipyleaflet. The user requested two fixes:

1. **Auto-zoom when filtering**: When selecting a borough (e.g., "Bronx"), the map should zoom to tightly frame the filtered schools
2. **No duplicate controls**: The legend and view toggle were appearing multiple times

## Current State

### What's Broken Now
1. **The basemap (CartoDB Positron tiles) is NOT displaying** - only the data points (CircleMarkers) are visible
2. The auto-zoom might be working but is hard to verify without seeing the map

### What Was Attempted
I rewrote `SchoolMap` to use Solara's recommended `.element()` pattern based on the [Solara ipyleaflet advanced example](https://github.com/widgetti/solara/blob/master/solara/website/pages/documentation/examples/libraries/ipyleaflet_advanced.py).

The key change was from:
```python
# OLD - Direct widget creation (causes issues with reacton reconciliation)
map_widget = Map(center=..., zoom=..., ...)
map_widget.add(marker)
solara.display(map_widget)
```

To:
```python
# NEW - Using .element() for proper reactive binding
tile_layer = ipyleaflet.TileLayer.element(url=basemap_url)
marker = ipyleaflet.CircleMarker.element(location=..., ...)
ipyleaflet.Map.element(
    center=map_center.value,
    on_center=map_center.set,
    zoom=map_zoom.value,
    on_zoom=map_zoom.set,
    layers=[tile_layer, marker, ...],
)
```

## Specific Technical Issues

### Issue 1: Basemap Not Appearing
The TileLayer element is being created with:
```python
url = ipyleaflet.basemaps.CartoDB.Positron["url"]
tile_layer = ipyleaflet.TileLayer.element(url=url)
```

But the tiles don't render. The CircleMarkers DO render, so the Map.element() itself is working.

**Questions to investigate:**
- Is the URL format correct for TileLayer.element()?
- Does TileLayer.element() work the same way as regular TileLayer?
- Are there any CORS or other network issues with the tile server?

### Issue 2: Previous Duplicate Controls Issue
Before my rewrite, the map had duplicate legends and view toggles stacking up. This was because:
- Each render added controls/layers to the same map widget
- Reacton was reconciling the widget but controls kept accumulating

The `.element()` approach should fix this by treating layers declaratively.

## Key Documentation Needed

1. **Solara ipyleaflet integration**:
   - https://solara.dev/documentation/examples/libraries/ipyleaflet
   - https://solara.dev/documentation/examples/libraries/ipyleaflet_advanced

2. **Solara use_effect and get_widget**:
   - https://solara.dev/documentation/api/hooks/use_effect
   - For imperative widget operations after render

3. **ipyleaflet Map.fit_bounds() race condition**:
   - https://github.com/jupyter-widgets/ipyleaflet/issues/807
   - `fit_bounds()` fails if called before widget is synced to browser

4. **ipyleaflet TileLayer and basemaps**:
   - https://ipyleaflet.readthedocs.io/en/latest/map_and_basemaps/map.html

## File Locations

- **Main app**: `outputs/geographic-dashboard/solara-prototype/app.py`
- **SchoolMap component**: Lines 1981-2299 (approximately)
- **Page component**: Lines 2302-2600 (approximately)
- **Server logs**: Run `tail -f /tmp/solara_output.log` or check background task output

## Server Commands

```bash
# From project root
cd outputs/geographic-dashboard/solara-prototype
source .venv/bin/activate
solara run app.py --port 8504
```

Dashboard URL: http://localhost:8504

## What Works

1. Data loading from Google Sheets (1,679 schools, 1,680 vulnerability records)
2. CircleMarker rendering (points show on map)
3. Center/zoom reactive binding (logs show `[MAP] Setting center to...`)
4. Filter calculations (logs show `[ZOOM] 383 schools, bounds:...`)

## What the User Wants

1. When selecting a borough filter (e.g., "Bronx"), the map should zoom to show ONLY that borough's schools - not the entire metro area
2. The basemap tiles should be visible (CartoDB Positron)
3. No duplicate controls/legends
4. Markers should be clickable to select schools

## Server Log Example (New Code)

```
INFO:__main__:[ZOOM] 32 schools, bounds: lat=[40.7114, 40.8347], lon=[-73.9904, -73.9408]
INFO:__main__:[MAP] Setting center to (40.773075698323495, -73.96558096528099), zoom to 10
```

This shows the new code IS running and calculating bounds correctly. The issue is the TileLayer not rendering.
