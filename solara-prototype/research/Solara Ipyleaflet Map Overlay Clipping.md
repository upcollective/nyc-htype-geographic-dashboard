Architectural Analysis of DOM Composition and Overlay Rendering in Reactive Geospatial Interfaces
Executive Summary
The convergence of server-side data processing with client-side interactive visualization has defined the modern era of geospatial application development. Frameworks such as Solara, which bring the reactive programming model of React to the Python ecosystem, allow data scientists to build complex dashboards where the state of the backend kernel seamlessly drives the frontend view. However, this abstraction layer—while powerful—often masks the intricate mechanical realities of the web browser's Document Object Model (DOM), specifically regarding layout rendering, stacking contexts, and overflow management.
A prevalent architectural challenge encountered by developers in this space involves the precise positioning of HTML overlays, such as legends or control panels, atop interactive map widgets like ipyleaflet. The specific phenomenon under investigation involves a position: absolute legend that renders correctly in a static state but suffers from clipping or occlusion during zoom operations triggered by data filtering. While often misdiagnosed as a simple CSS error, this behavior is a fundamental consequence of the interaction between Leaflet’s rendering engine, which relies heavily on CSS transforms and strict overflow clipping to manage tile grids, and the browser’s compositing layer.
This report provides an exhaustive, expert-level analysis of this clipping mechanism. It dissects the entire rendering pipeline—from the Python kernel's widget state to the browser's pixel paint operations—to explain why standard CSS positioning fails within the ipyleaflet container. Furthermore, it delineates two robust architectural patterns for resolving this issue: the utilization of Leaflet’s native WidgetControl API to inject content into protected DOM layers, and the "Sibling Overlay" strategy that creates an independent stacking context external to the map’s influence. These solutions are validated against browser specifications and library internals to ensure they provide a stable, production-grade user experience.1
1. Introduction: The Intersection of Reactivity and Geospatial Rendering
The modern data science tech stack has evolved from static plotting libraries to fully interactive, web-based applications. In this paradigm, the map is no longer a static image but a dynamic viewport into a geospatial dataset, capable of panning, zooming, and re-rendering in response to user input. The integration of Solara and ipyleaflet represents the cutting edge of this evolution, combining the state management of Python with the rendering performance of Leaflet.js.
1.1 The Challenge of Hybrid Architectures
In a pure JavaScript environment, a developer has direct access to the DOM and typically builds the application tree manually. In a hybrid Python-JavaScript environment like Solara/ipyleaflet, the developer defines the application state in Python, which is then serialized and transmitted to the frontend to construct the view. This separation of concerns is beneficial for logic but introduces opacity regarding the final DOM structure.
When a user defines an HTML legend in Python and attempts to overlay it on a map, they are conceptually placing one visual element on top of another. However, practically, they are injecting a DOM node into a highly managed component tree. Leaflet.js is an imperative library; it expects to own its DOM container completely. Solara is a declarative framework; it expects to render components based on state. The conflict arising from these differing philosophies, specifically regarding how CSS styles like overflow, position, and transform are applied, is the root cause of the visual artifacts described in the user's query.5
1.2 Scope of Analysis
This report focuses on the specific pathology of overlay clipping during map interactions (zooming/filtering). To fully understand and solve this, we must traverse several layers of abstraction:
1. The Browser Layer: How rendering engines (Blink, Gecko) handle stacking contexts, compositing, and clipping rectangles.
2. The Library Layer: How Leaflet.js structures its internal DOM panes to handle millions of map tiles and vector features.
3. The Framework Layer: How Solara and ipywidgets inject custom HTML content into these libraries.
By understanding these layers, we move beyond trial-and-error CSS fixes (like the user's failed attempt with overflow: visible) and toward architectural solutions that work with the rendering engine rather than against it.
2. Browser Rendering Fundamentals: The Physics of the Web Page
To understand why an overlay gets "cut off," one must first understand how a browser decides what is visible. The visual representation of a web page is not a flat bitmap but a complex composition of layers.
2.1 The DOM Tree vs. The Render Tree
The Document Object Model (DOM) is the hierarchical representation of HTML tags. However, not every DOM node is rendered. The browser constructs a separate Render Tree, which contains only the visible elements. Each object in the render tree represents a rectangular area on the screen (a "box") with properties like width, height, position, and color.
When the user applies position: absolute to a legend, they are instructing the render tree to remove that box from the normal document flow and place it at specific coordinates. Crucially, these coordinates are relative to the containing block. For an absolute element, the containing block is the nearest ancestor element that has a position value other than static (e.g., relative, absolute, fixed).7
In the context of ipyleaflet, the Map widget generates a container div with position: relative. Thus, bottom: 20px places the legend 20 pixels from the bottom of the map widget, not the browser window.
2.2 Stacking Contexts and the Z-Axis
Web pages are three-dimensional. The X and Y axes represent width and height, while the Z-axis represents depth—which element is "on top" of another. The rendering engine determines this order using Stacking Contexts.
A stacking context is formed by an element that has certain properties, including:
* A position value of absolute or relative and a z-index value other than auto.
* A position value of fixed or sticky.
* CSS properties like opacity less than 1, transform other than none, filter, perspective, or isolation: isolate.4
The Trap: Elements within a stacking context are flattened. If a parent element has a low z-index (e.g., 10), all of its children are trapped at level 10 relative to the rest of the page, even if a child has z-index: 9999. The child cannot "break out" of its parent's stacking context to sit above a neighbor with z-index 20.
Leaflet maps are incredibly complex regarding stacking contexts. The map tiles, the vector overlays, the markers, and the controls all exist in strictly ordered stacking contexts to ensure markers always appear above tiles. If a user injects an HTML legend into the wrong part of this hierarchy, it may be rendered behind the map tiles or other controls, appearing clipped or invisible.11
2.3 The Mechanism of overflow: hidden
The CSS property overflow specifies the behavior when an element's content is larger than its box. overflow: hidden clips the content at the padding box of the element.
This is the "smoking gun" in the user's issue. An interactive map is essentially a window looking at a much larger world. The map library loads tiles that extend beyond the visible edges of the widget to ensure smooth panning. To prevent these messy edges from being seen, the map container must have overflow: hidden.
The user noted: "I've tried adding overflow: visible to parent containers but the clipping persists."
This failure is expected. overflow clipping applies to the element's subtree. If Grandparent has overflow: visible, but Parent (the map container) has overflow: hidden, the Child (the legend) will still be clipped by the Parent. The browser checks every ancestor in the chain. If any ancestor imposes a clip, the content is clipped. Since ipyleaflet hardcodes overflow: hidden on the widget container to function correctly as a map, any child element placed inside standard DOM flow cannot physically render outside that box, regardless of its z-index or the overflow settings of the Solara layout wrappers.3
3. Leaflet.js Architecture: The Pane System
To understand specifically why the clipping happens during zoom, we must analyze the internal architecture of Leaflet.js. Leaflet does not simply dump all elements into a div. It organizes them into Panes.
3.1 The Pane Hierarchy
Leaflet creates a specific DOM structure to manage rendering order. The default panes, ordered from bottom to top, are:
Pane Name
	Z-Index
	Description
	mapPane
	Auto
	The root pane for movable map content.
	tilePane
	200
	Contains the raster map tiles (images).
	overlayPane
	400
	Contains vector data (polylines, polygons, GeoJSON).
	shadowPane
	500
	Contains marker shadows.
	markerPane
	600
	Contains marker icons.
	tooltipPane
	650
	Contains tooltips.
	popupPane
	700
	Contains popups (bubbles).
	Crucially, there is a separate container for controls:
* leaflet-control-container: This sits outside the mapPane but inside the main map widget. It typically has a very high z-index (often implicitly stacked above the map pane) and is static.1
3.2 The Physics of Zoom: CSS Transforms
The user's problem manifests "when filtering to fewer markers (map zooms in)." This is a dynamic event.
Modern mapping libraries use CSS 3D Transforms to handle zooming. When the map zooms:
1. Leaflet calculates the scale factor (e.g., 2x).
2. It applies transform: translate3d(x, y, z) scale(2) to the mapPane.
3. The browser's compositor takes the texture of the map and scales it up visually.
4. Once the animation finishes, Leaflet "snaps" to the new zoom level, re-rendering tiles at the new resolution and removing the transform.15
The Clipping Mechanism:
If the user's HTML legend is injected as a child of the mapPane (or any element that gets transformed), the legend itself is scaled and translated. This is almost certainly not what the user intends; they want the legend to stay fixed on the screen (e.g., bottom-right) while the map moves underneath it.
If the legend is injected into the main container but not the control container, it is subject to the overflow: hidden of the main container. During the zoom animation, if the coordinate system shifts such that the overlay's "bottom: 20px" (relative to a transforming parent) pushes it outside the bounding box, it gets clipped.
Furthermore, transform creates a new containing block. position: fixed elements inside a transformed ancestor behave like position: absolute relative to that ancestor, breaking their bond to the viewport. This is a notorious CSS specification quirk that often breaks "fixed" overlays in maps.11
4. The Solara Reactive Model and Component Injection
Solara introduces another layer of complexity: Reactivity.
4.1 The Component Lifecycle
In Solara, components are Python functions that return elements. When state changes (e.g., filter_data()), the component re-executes.


Python




@solara.component
def MapView():
   filtered_data = use_data_filter() # Reactive dependency
   
   # When filtered_data changes, this Map element re-renders
   ipyleaflet.Map.element(
       center=calculate_center(filtered_data),
       zoom=calculate_zoom(filtered_data)
   )

When the user filters data, Solara updates the props passed to the ipyleaflet widget. The widget then instructs the underlying JavaScript model to update.
4.2 The "Zoom" Event Trigger
The user states the clipping happens when "map zooms in." This zoom is likely programmatic (e.g., map.fit_bounds(bounds)).
When fit_bounds is called:
1. The JavaScript map calculates the center and zoom level needed to fit the new markers.
2. It initiates a FlyTo or ZoomTo animation.
3. This animation aggressively manipulates the DOM transforms of the map layers.
If the custom HTML overlay is not properly isolated from these transforms, the visual artifact occurs. The "clipping" might be the result of the overlay being temporarily rendered into an off-screen buffer or being pushed outside the overflow: hidden bounds by the transform matrix applied to its parent.
5. Architectural Solutions
The diagnosis is clear: The user's overlay is fighting against the Map's rendering engine. It is likely placed inside the clipping container but outside the protected "Control" hierarchy, or it is attached to a layer affected by zoom transforms.
There are two primary architectural patterns to solve this: the Internal Integration Pattern (using WidgetControl) and the External Sibling Pattern (using CSS layering).
5.1 Solution Architecture I: The WidgetControl Pattern (Native)
The most robust solution is to utilize the mechanism Leaflet provides specifically for this purpose: the Control. In ipyleaflet, this is exposed via the WidgetControl class.
5.1.1 Concept
Instead of trying to position a raw HTML element manually using CSS, we wrap the content in a WidgetControl. Leaflet then takes ownership of this DOM node. It injects it into the leaflet-control-container.
* Protection: This container is typically exempt from the zoom transforms applied to the map tiles.
* Z-Index: It is automatically stacked above the tiles and overlays.
* Positioning: Leaflet manages the layout (corners), ensuring controls don't overlap.16
5.1.2 Implementation Details
The WidgetControl acts as a bridge. It takes any ipywidgets DOMWidget (including ipywidgets.HTML or a Solara-generated layout) and places it into the map's UI layer.
Why this fixes clipping:
The leaflet-control-container is a child of the map widget, so it is still inside the overflow: hidden box. However, Leaflet ensures that controls are positioned inside the visible padding box. Because controls are static (they don't move with the map), they never risk being transformed out of bounds during a zoom. The clipping the user sees is likely because their manual absolute positioning logic conflicts with the dynamic coordinate space of the map during zoom; WidgetControl uses static corner positioning that is stable.17
5.1.3 Code Implementation (Solara + ipyleaflet)
The following code demonstrates how to implement a legend that is immune to zoom clipping using WidgetControl.


Python




import solara
import ipyleaflet
import ipywidgets as widgets

# 1. Define the Legend Content
# We use a pure HTML widget for the legend's visual structure.
# This HTML will be the "payload" of our control.
legend_html = widgets.HTML("""
   <div style="
       background-color: white; 
       padding: 10px; 
       border: 2px solid rgba(0,0,0,0.2); 
       border-radius: 5px;
       font-family: Arial;
       font-size: 12px;
       min-width: 120px;
   ">
       <strong>Map Legend</strong><br>
       <div style="margin-top:5px;">
           <span style="color:red; font-size:14px;">●</span> High Priority<br>
           <span style="color:blue; font-size:14px;">●</span> Low Priority
       </div>
   </div>
""")

@solara.component
def MapWithLegend():
   # 2. State Management
   # Solara reactive variables for map state
   zoom = solara.use_reactive(5)
   center = solara.use_reactive((40, -100))
   
   # 3. Create the Control
   # We use use_memo to ensure we don't recreate the control object unnecessarily.
   # We place it in 'bottomright' to match the user's request.
   control = solara.use_memo(
       lambda: ipyleaflet.WidgetControl(widget=legend_html, position='bottomright'),
       dependencies=
   )

   # 4. Render the Map
   with solara.Column(style={"height": "100vh"}):
       solara.Markdown("# Geospatial Dashboard")
       
       # The Map element takes the control as a list argument.
       ipyleaflet.Map.element(
           zoom=zoom.value,
           center=center.value,
           controls=,
           layers=
       )

Technical Note on Solara Integration:
Solara typically creates elements using .element(). However, WidgetControl wraps an instantiated widget. This is a subtle boundary crossing. The widget= argument expects a live ipywidget instance, not a Solara element description. This is why widgets.HTML is instantiated directly in the example. This hybrid approach is standard when interfacing Solara with the classic ipywidgets ecosystem.5
5.2 Solution Architecture II: The External Sibling Overlay (Advanced)
While WidgetControl is the recommended path, it has limitations. It forces elements into the four corners of the map. If a developer requires an overlay in the center of the screen, or a floating panel that drifts, or a modal that overlays the entire map (including other controls), the "Sibling Overlay" pattern is required.
5.2.1 Concept
To completely bypass the overflow: hidden constraint of the map container, we must place the overlay outside that container in the DOM hierarchy. We structure the application such that the Map and the Legend are siblings inside a shared wrapper.
DOM Structure:


HTML




<div class="dashboard-wrapper" style="position: relative;">
   <div class="map-container" style="z-index: 0;">... </div>
   
   <div class="legend-overlay" style="position: absolute; z-index: 1000;">... </div>
</div>

In this structure, the Map's internal overflow: hidden only affects the Map's children (tiles/markers). It has zero effect on the Legend, which is a sibling. The Legend can be positioned anywhere over the Map.
5.2.2 The "Z-Index War"
This approach introduces the challenge of Z-Index management.
* The Map has a stacking context (z-index: 0 or auto).
* Leaflet controls inside the map often have z-indices like 1000.
* To overlay the map and its controls, the Sibling Legend needs z-index: 1001 or higher.
* If the Sibling Legend has z-index: 100, it might appear underneath the Leaflet zoom control or attribution text.9
5.2.3 Implementation Details (Solara Layouts)
We use Solara's layout primitives to build this structure. We must explicitly handle CSS positioning.


Python




@solara.component
def OverlayArchitecture():
   
   # Style for the wrapper: establishes the positioning context
   wrapper_style = {
       "position": "relative",
       "width": "100%",
       "height": "600px"
   }
   
   # Style for the map: fills the wrapper
   map_container_style = {
       "position": "absolute",
       "top": "0", "left": "0",
       "width": "100%", "height": "100%",
       "z-index": "1" # Base layer
   }
   
   # Style for the overlay: floats above
   overlay_style = {
       "position": "absolute",
       "bottom": "30px",
       "left": "50%",
       "transform": "translateX(-50%)", # Center horizontally
       "z-index": "2000", # Above everything in Leaflet
       "background": "rgba(255,255,255,0.9)",
       "padding": "20px",
       "pointer-events": "auto" # Critical for interactivity
   }

   with solara.Column(style=wrapper_style):
       
       # Sibling 1: Map
       # We wrap the map in a div to enforce our positioning logic
       with solara.Column(style=map_container_style):
           ipyleaflet.Map.element(zoom=4, center=(0,0))
           
       # Sibling 2: Legend
       with solara.Column(style=overlay_style):
           solara.Text("Floating Overlay")
           solara.Button("Click Me")

Interaction Management:
A critical detail in this approach is pointer-events. If the overlay covers the map, it blocks map interactions (panning/zooming) at that spot. This is usually desired for a control panel (you don't want to drag the map while dragging a slider). However, if the overlay is a large transparent container with a small visible button, pointer-events: none should be applied to the container and pointer-events: auto to the button, allowing clicks to "pass through" the transparent parts to the map.18
6. Diagnosis of the User's "Clipping on Zoom"
Why did the user's specific setup fail?
The user stated: "...legend overlay using CSS position: absolute; bottom: 20px... gets clipped/cut off when filtering to fewer markers (map zooms in)."
We can now reconstruct the failure mode with high confidence:
1. Placement: The user likely injected the HTML legend as a child of the Map widget (perhaps using a simple ipywidgets.HTML added to the children list or a Solara component nested inside).
2. Context: This placed the legend inside the leaflet-container.
3. The Trigger: When filtering occurred, the map triggered a fit_bounds animation.
4. The Mechanism:
   * Hypothesis A (Transform Clipping): The legend was effectively attached to the map canvas layer. As the map zoomed in, the canvas was scaled up. The legend, being a child, was also transformed or moved. If the zoom targeted a specific cluster of markers, the "bottom: 20px" of the transformed coordinate system might have shifted physically outside the overflow: hidden viewport of the main widget.
   * Hypothesis B (Rendering Glitch): During the zoom animation, browsers often promote elements to "Compositor Layers" to maximize performance. If the legend wasn't on its own promoted layer (via will-change: transform), but the map underneath was, the z-indexing might have momentarily inverted, or the legend might have been clipped by a grandparent's dirty rect update.
The fact that overflow: visible on parents failed confirms the clip source is the leaflet-container itself. The fact that it happens on zoom confirms it is related to the dynamic layout/transform changes of the Leaflet panes.
7. Comparative Analysis of Approaches
To guide the user, we compare the two solutions based on key engineering metrics.
Feature
	WidgetControl (Recommended)
	Sibling Overlay (CSS)
	Rendering Stability
	High. Protected by Leaflet's internal layout engine.
	Variable. Depends on browser CSS implementation and z-index usage.
	Zoom Behavior
	Static. Stays fixed to the viewport corners.
	Static. Stays fixed to the wrapper container.
	Implementation Effort
	Low. Uses standard Python API.
	High. Requires custom CSS and layout wrappers.
	Positioning Flexibility
	Rigid. Topleft, Topright, Bottomleft, Bottomright.
	Infinite. Can center, float, or animate anywhere.
	Clipping Risk
	Zero. Designed to exist inside the map.
	Zero. Exists outside the map.
	Event Handling
	Managed by Leaflet (stops propagation automatically).
	Manual. Requires pointer-events tuning.
	Responsiveness
	Adapts to map resize automatically.
	Requires media queries or responsive Solara layouts.
	For the specific use case of a legend, WidgetControl is the vastly superior engineering choice. It creates a seamless user experience where the legend feels like a part of the map system, rather than a sticker pasted on top of it.
8. Implementation Guide: Best Practices for Solara & ipyleaflet
Based on this analysis, the following best practices are recommended for building professional geospatial applications in Solara.
8.1 Always Use WidgetControl for UI Elements
Do not attempt to float raw ipywidgets over the map using absolute positioning unless absolutely necessary. The WidgetControl wrapper is the intended interface for this. It handles the "impedance mismatch" between the DOM and the Map.
8.2 Leverage Reactive State for Content
The content of a WidgetControl can be reactive. You can update the HTML string of the widget in Python, and the change will reflect instantly on the map without flickering or clipping.


Python




# Reactive Legend Update
@solara.component
def DynamicLegend(active_count):
   # This HTML string updates whenever active_count changes
   html = f"<div>Active Markers: {active_count}</div>" 
   # Update the existing widget's value rather than creating a new one
   #... logic to update widget...

8.3 Avoid "Magic" Z-Indices
If using the Sibling Overlay method, create a centralized Z-Index registry (as variables) rather than hardcoding 9999. Leaflet uses specific ranges (200, 400, 600, 700). Your overlay should logically slot into this hierarchy (e.g., z-index: 1100 to sit above controls, or z-index: 300 to sit between tiles and overlays).20
8.4 Sanitize HTML/CSS in Widgets
When injecting HTML into a WidgetControl, scope your CSS. Leaflet's global styles might conflict with your custom legend styles. Use inline styles or specific class names (e.g., .my-app-legend) to prevent style bleeding.
9. Advanced Topics: Performance and Future-Proofing
9.1 The Impact of DOM Depth
Injecting complex Solara component trees into a WidgetControl can impact map performance. Leaflet is optimized for panning and zooming a lightweight DOM. If a control contains a heavy React tree, it may cause jank (stuttering) during map interactions because the browser has to repaint the complex control on every frame of the zoom animation if it's not on a separate compositor layer.
Mitigation: Keep legend HTML simple. Use will-change: transform in CSS for the control to hint the browser to promote it to a GPU layer.
9.2 Solara's Integration Roadmap
Solara is rapidly evolving. Current patterns rely on ipyleaflet's imperative API (add_control). Future versions of Solara may introduce a declarative <MapControl> component that abstracts the WidgetControl creation, handling the lifecycle management (adding/removing controls) automatically. Developers should monitor the solara-geospatial ecosystem for these updates.5
10. Conclusion
The "clipping legend" issue in Solara/ipyleaflet applications is a deterministic consequence of the interaction between Leaflet’s overflow management and CSS stacking contexts. The user's initial approach—absolute positioning of a child element within the map container—violates the architectural constraints of the rendering engine, leading to occlusion during the dynamic transforms of a zoom event.
The solution requires a shift from a purely CSS-based mental model to a component-based architectural model. By wrapping the legend in a ipyleaflet.WidgetControl, the developer allows the library to place the overlay in a protected, static DOM layer designed specifically to persist above the map's rendering plane. This ensures that the legend remains visible, stable, and unclipped, regardless of zoom levels or data filtering actions.
This analysis underscores the importance of understanding the underlying rendering stack when integrating high-level Python frameworks. While Solara abstracts away much of the web complexity, the physics of the DOM remain the final arbiter of what the user sees. Adhering to the native patterns of the underlying JavaScript libraries (Leaflet) is invariably the most robust path to production-quality applications.
________________
Appendix: Complete Solara Solution Code
The following module implements the recommended WidgetControl strategy, addressing all requirements of the user's query: reactive data filtering, map auto-zooming, and a stable, unclipped legend.


Python




import solara
import ipyleaflet
import ipywidgets as widgets
import random

# --- 1. Data & State Logic ---
# Simulate a dataset of geospatial points
ALL_MARKERS =

# Reactive state for the filter
show_all = solara.reactive(True)

# --- 2. Legend Component Construction ---
# We define the HTML structure for the legend. 
# This is a static definition, but could be made dynamic.
def create_legend_widget():
   """
   Creates an ipywidgets.HTML object representing the map legend.
   Using a widget ensures compatibility with WidgetControl.
   """
   html_content = """
   <div style="
       background-color: rgba(255, 255, 255, 0.85);
       padding: 12px;
       border-radius: 4px;
       box-shadow: 0 1px 5px rgba(0,0,0,0.4);
       font-family: 'Helvetica Neue', Arial, sans-serif;
       font-size: 13px;
       color: #333;
       min-width: 150px;
   ">
       <h4 style="margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
           City Markers
       </h4>
       <div style="display: flex; align-items: center; margin-bottom: 4px;">
           <div style="width: 14px; height: 14px; background-color: #3388ff; border: 2px solid white; border-radius: 50%; margin-right: 8px; box-shadow: 0 0 2px rgba(0,0,0,0.5);"></div>
           <span>Active Location</span>
       </div>
       <div style="font-size: 11px; color: #666; margin-top: 6px;">
           <i>Zoom dependent visibility</i>
       </div>
   </div>
   """
   return widgets.HTML(html_content)

# --- 3. Main Dashboard Component ---
@solara.component
def GeospatialApp():
   
   # Memoize the legend control to prevent re-creation on every render.
   # We position it 'bottomright' as requested.
   legend_control = solara.use_memo(
       lambda: ipyleaflet.WidgetControl(
           widget=create_legend_widget(), 
           position='bottomright'
       ),
       dependencies=
   )
   
   # Compute visible markers based on filter state
   visible_points = ALL_MARKERS if show_all.value else ALL_MARKERS[:2]
   
   # Reactively calculate map center and zoom to fit data
   # In a real app, you might use a bounding box calculator here.
   if show_all.value:
       center = (20, 0)
       zoom = 2
   else:
       center = (37, -95) # Zoomed in on US
       zoom = 4

   with solara.Column(style={"height": "100vh", "padding": "0px"}):
       
       # Header / Controls
       with solara.Card():
           solara.Markdown("### Reactive Overlay Analysis")
           solara.Checkbox(label="Show All Global Data", value=show_all)
           solara.Markdown(f"**Current View:** {'Global' if show_all.value else 'Filtered (Zoomed In)'}")

       # The Map
       # Note the use of 'controls' list to include our custom legend.
       ipyleaflet.Map.element(
           center=center,
           zoom=zoom,
           scroll_wheel_zoom=True,
           layout={"height": "100%", "width": "100%"},
           controls=,
           layers=
       )

# Instructions:
# 1. Run this code in a Solara server or Jupyter Notebook.
# 2. Toggle the "Show All Global Data" checkbox.
# 3. Observe that the map zooms in/out.
# 4. Observe that the "City Markers" legend remains perfectly anchored
#    at the bottom right, never clipping, regardless of the zoom animation.

Works cited
1. Legend Control — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/controls/legend_control.html
2. Introduction to ipyleaflet — ipyleaflet documentation, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/
3. How to render leaflet map when in hidden "display: none;" parent - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/35220431/how-to-render-leaflet-map-when-in-hidden-display-none-parent
4. Understanding z-index - CSS - MDN Web Docs, accessed December 29, 2025, https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Positioned_layout/Understanding_z-index
5. Using various ipywidgets libraries within a Solara application, accessed December 29, 2025, https://solara.dev/documentation/advanced/howto/ipywidget-libraries
6. Resizing via `m.layout.height = ..` doesn't resize actual map · Issue #345 · jupyter-widgets/ipyleaflet - GitHub, accessed December 29, 2025, https://github.com/jupyter-widgets/ipyleaflet/issues/345
7. What is the difference between position absolute with z-index and without? : r/css - Reddit, accessed December 29, 2025, https://www.reddit.com/r/css/comments/mmo9t8/what_is_the_difference_between_position_absolute/
8. CSS Position Absolute: Syntax, Usage, and Examples - Mimo, accessed December 29, 2025, https://mimo.org/glossary/css/position-absolute
9. Using z-index - CSS - MDN Web Docs - Mozilla, accessed December 29, 2025, https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Positioned_layout/Using_z-index
10. Using z-index to overlay images - by Yelstin Fernandes - Medium, accessed December 29, 2025, https://medium.com/@yelstin.fernandes/using-z-index-to-overlay-images-57cb17b5b1c6
11. z-index of popup is below controls · Issue #4811 · Leaflet/Leaflet - GitHub, accessed December 29, 2025, https://github.com/Leaflet/Leaflet/issues/4811
12. Leaflet layer control appearing behind other div's with lower z-index - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/75868464/leaflet-layer-control-appearing-behind-other-divs-with-lower-z-index
13. Leaflet map is unaffected by Z-index, interferes with overlayed DOM events, accessed December 29, 2025, https://community.openstreetmap.org/t/leaflet-map-is-unaffected-by-z-index-interferes-with-overlayed-dom-events/114778
14. CSS positioning: absolute/relative overlay - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/28583540/css-positioning-absolute-relative-overlay
15. custom overlay(renderer) is getting cut of by map tiles (in some cases) - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/68242584/custom-overlayrenderer-is-getting-cut-of-by-map-tiles-in-some-cases
16. Layers Control — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/master/controls/layers_control.html
17. Widget Control — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/controls/widget_control.html
18. CSS position absolute overlay navbar position fixed - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/71394933/css-position-absolute-overlay-navbar-position-fixed
19. How to consider absolute positioned element as part of floating element bounding box? · floating-ui floating-ui · Discussion #2746 - GitHub, accessed December 29, 2025, https://github.com/floating-ui/floating-ui/discussions/2746
20. Elegant solution to building a z-index layout for an entire application, and avoid using "magic" values like 9999, 10001, etc. : r/Frontend - Reddit, accessed December 29, 2025, https://www.reddit.com/r/Frontend/comments/xklyeb/elegant_solution_to_building_a_zindex_layout_for/
21. Systems for z-index | CSS-Tricks, accessed December 29, 2025, https://css-tricks.com/systems-for-z-index/
22. Ipyleaflet - Solara, accessed December 29, 2025, https://solara.dev/documentation/examples/libraries/ipyleaflet