Architectural Patterns for Reactive Geospatial Visualizations in Solara: Integrating Dynamic Popups with High-Volume Imperative Markers
Executive Summary
The convergence of reactive web frameworks and interactive geospatial libraries represents a significant advancement in scientific computing and data visualization dashboard design. However, this integration presents substantial architectural challenges, particularly when managing high-cardinality datasets—such as maps containing thousands of interactive markers—while maintaining a responsive user interface and adhering to strict reactive state management principles. This report addresses a specific, critical architectural pattern: bridging the gap between an imperative marker generation strategy, which is optimized for initial load performance, and a reactive state management system, which is optimized for user experience and code maintainability.
The focal problem involves a Solara application rendering 1,700 CircleMarker widgets where the selection state is managed externally (e.g., via a sidebar or imperative click handlers), requiring a visual feedback mechanism—specifically, a singleton popup or tooltip—on the map to identify the selected entity. The research indicates that naive implementations, such as declarative list rendering for popups or binding individual popups to every marker, lead to severe performance degradation and application instability, most notably in the form of infinite render loops.
The primary objective of this analysis is to define a robust implementation strategy for a "Singleton Dynamic Popup." This approach avoids the performance pitfalls of declarative list rendering for large datasets by decoupling the popup's lifecycle from the marker's lifecycle and binding it instead to the application's global selection state. By leveraging the use_effect hook to manage side effects, we can achieve O(1) complexity for selection updates, ensuring scalability and stability. The following sections provide an exhaustive examination of the underlying technologies, the specific nature of the "infinite loop" risk in Solara/React, the internal mechanics of ipyleaflet's widget synchronization, and a detailed, code-centric solution that fulfills all user requirements.
1. Introduction: The Intersection of Reactivity and Geospatial Engineering
The modern landscape of Python-based web application development has shifted dramatically with the advent of libraries like Solara, which bring the component-based, reactive paradigms of React.js into the Python ecosystem. This shift offers developers the ability to create complex, state-driven applications with clean, declarative code. However, when these reactive patterns intersect with heavy client-side libraries like Leaflet.js (wrapped via ipyleaflet), an "impedance mismatch" often occurs. This mismatch is characterized by the friction between the declarative desire to define the UI as a pure function of state ($UI = f(state)$) and the imperative necessity of manipulating heavy, stateful objects like map layers to ensure performance.
1.1 The Challenge of High-Cardinality Geospatial Data
In the context of the user's application, the rendering of 1,700 CircleMarker widgets constitutes a high-cardinality visualization scenario. While modern browsers can render thousands of SVG or Canvas elements, the management of these elements within a reactive framework is the bottleneck. In a purely declarative Solara approach, a change in application state (such as selecting a school) would typically trigger a re-render of the component tree. If the list of 1,700 markers is part of this render cycle, the framework must perform a "diff" operation—comparing the old list of 1,700 widget objects against a new list—to determine what changed.1
This process, known as reconciliation, is computationally expensive. Even if the markers themselves have not changed, the overhead of object instantiation, attribute comparison, and dependency tracking can introduce perceptible lag. The user has correctly identified this bottleneck and employed a solution: memoization via solara.use_memo. By memoizing the list of markers, the application ensures that the expensive marker generation logic runs only once. However, this creates a rigid structure. The markers are now static resources. Introducing dynamic behavior—such as a popup that appears on selection—requires a mechanism to bypass this rigidity without breaking the reactive loop or forcing a full re-initialization of the map.
1.2 The "Infinite Loop" Pathology in Reactive Maps
One of the most insidious issues in integrating ipyleaflet with Solara is the infinite render loop. This occurs when the act of rendering the map triggers a state change, which in turn triggers a new render.3 In the user's specific case, attempting to add a Popup widget purely declaratively (e.g., as a child of the map in the main render body) often leads to this cycle. The mechanism is as follows:
1. Render: The component executes, creating a new Popup widget instance.
2. Side Effect: The Popup is added to the map's layer list.
3. Synchronization: Ipyleaflet detects a change in the layer list and synchronizes with the frontend.
4. Feedback: The frontend confirms the layer addition, potentially updating a traitlet on the Map model (like layers).
5. Re-Render: Solara detects the change in the Map model's traits and schedules a re-render.
6. Loop: The cycle repeats, freezing the browser or crashing the kernel.5
Avoiding this requires a deep understanding of the use_effect hook, which allows developers to perform side effects (like updating a map) after the render phase is complete and only when specific dependencies change, effectively breaking the loop.2
2. Theoretical Framework: Declarative Systems vs. Imperative Wrappers
To engineer a robust solution, one must first deconstruct the interacting systems: the Solara/React execution model and the Jupyter Widget synchronization protocol.
2.1 The Solara/React Execution Model
Solara operates on a Virtual DOM (Document Object Model) principle. The user's Python code defines a tree of components. On every state change, Solara re-executes the component functions to generate a new virtual tree. It then calculates the minimum number of operations required to transform the current tree into the new tree.
* Reconciliation and Diffing: When dealing with lists of widgets (like map markers), the "diffing" algorithm is critical. If the list is recreated on every render, Solara sees 1,700 new objects, even if their data is identical. This forces the framework to detach the old widgets and attach the new ones, which is a heavy operation for the ipywidgets communication channel.6
* Memoization (use_memo): This hook caches the result of a function call. In the user's architecture, use_memo is used to cache the list of marker widgets. This "locks" the markers in memory. They are created once and persist across re-renders. This is the correct optimization for static data layers but necessitates a different strategy for dynamic elements like popups.2
* Effect Hooks (use_effect): This hook allows the execution of imperative code in response to state changes, outside the synchronous render flow. It is the designated "escape hatch" for integrating with non-React libraries or performing side effects like network requests or manual DOM manipulations. In the context of ipyleaflet, use_effect is the primary tool for updating the map state (e.g., moving a popup) without triggering a full component re-render.2
2.2 The Jupyter Widget Synchronization Protocol
Ipyleaflet is built upon the ipywidgets infrastructure, which uses a client-server architecture.
* Kernel Side (Python): The Widget objects (Map, Marker, Popup) exist as Python objects with "traitlets" (typed attributes).
* Client Side (JavaScript): Corresponding Backbone.js models exist in the browser.
* The Comm Channel: A websocket-based communication channel (Comm) synchronizes the state. When popup.location is updated in Python, a JSON patch is sent to the browser. Conversely, when a user clicks a map, a message is sent to Python.8
The critical insight for this report is that imperative updates to traitlets are cheap. Updating popup.location = (lat, lon) sends a tiny message. In contrast, declarative updates to the layer list are expensive. Reconstructing Map(layers=[...]) forces a comparison of the entire list. Therefore, the optimal architecture uses declarative patterns for the initial setup (the static markers) and imperative patterns (via use_effect) for high-frequency dynamic updates (the popup).
2.3 The "Impedance Mismatch" Analysis
The user's query highlights a classic friction point. The map is rendered declaratively using Map.element(layers=...).10 However, the click handlers on the markers are imperative (marker.on_click(...)). The user wants to bridge these worlds. If they attempt to add the popup by modifying the declarative layers list passed to Map.element, they break the memoization of the marker list or force a re-evaluation of the entire map. If they try to manage the popup entirely imperatively, they risk it falling out of sync with the application state (e.g., if the user refreshes the page or if the selection is cleared elsewhere). The solution requires a hybrid approach: a Singleton Declarative Resource (the Popup widget itself) managed by an Imperative Controller (the use_effect hook).
3. Component Deep Dive: The ipyleaflet Popup
Before synthesizing the solution, it is necessary to analyze the capabilities and limitations of the ipyleaflet.Popup widget, specifically comparing it to alternatives like WidgetControl or Marker.popup.
3.1 ipyleaflet.Popup Class Attributes and Behaviors
The Popup class in ipyleaflet is a UILayer that exposes several critical traitlets that enable dynamic manipulation 11:
* location: A tuple (latitude, longitude). This is the anchor point of the popup. Crucially, this traitlet is dynamic. Changing the value on an existing instance immediately animates the popup to the new location on the client side without destroying the DOM element.
* child: The content of the popup. This expects a DOMWidget, typically an ipywidgets.HTML instance. By updating the value attribute of this child widget, the text inside the popup can be changed instantly.
* visible: While not always explicitly documented as a toggle for all layers, visibility can often be managed by adding/removing the layer from the map.
* auto_close and close_on_escape_key: These boolean attributes control user interaction. For a "tooltip-like" behavior requested by the user, setting close_button=False, auto_close=False, and close_on_escape_key=False is essential to prevent the popup from disappearing unexpectedly when the user interacts with other map elements.14
3.2 Comparison: Singleton Popup vs. Marker.popup
The user is using CircleMarker widgets. The Marker class has a popup attribute. One might be tempted to assign a popup to every marker:


Python




# Naive Approach - Do NOT Use
for marker in markers:
   marker.popup = HTML(value=marker.name)

Why this fails for 1,700 markers:
1. Memory Overhead: Creating 1,700 HTML widgets and 1,700 internal Popup associations consumes significant kernel memory and browser heap space.
2. State Management Complexity: If the selection changes via the sidebar (not a map click), the application must search through 1,700 markers to find the correct one and programmatically open its popup. This is an O(N) operation.
3. Visual Clutter: Leaflet's default behavior allows multiple popups if configured incorrectly, or requires strict management to close the previous one. A singleton guarantees only one label is shown.15
3.3 Comparison: Popup vs. WidgetControl
The user asked to investigate WidgetControl with an HTML widget positioned near the marker.
* WidgetControl: This class places a widget at a fixed position relative to the map container (e.g., 'topright', 'bottomleft').12 It does not naturally track a geographical coordinate (lat/lon).
* The Tracking Problem: To use WidgetControl as a label, one would need to calculate the screen coordinates (pixels) of the selected marker every time the map is panned or zoomed. This requires hooking into the pixel_bounds or bounds change events of the map, performing a projection (Geo -> Pixel) in Python, and updating the widget's margin/position. This introduces massive latency and "jitter" because the Python kernel cannot keep up with the 60fps render loop of the browser's pan interaction.
* Conclusion: WidgetControl is unsuitable for labeling a geographical point. Popup (or Marker with a bound popup) is the correct tool because it is anchored to (lat, lon) and the projection is handled natively by Leaflet.js in the browser.11
4. Architectural Solution: The Singleton Dynamic Popup Pattern
The optimal solution utilizes a single, reusable Popup instance. This instance is created once (via use_memo) and mutated imperatively inside a use_effect hook whenever the selected_school state changes. This pattern adheres to the Principle of Least Privilege regarding re-renders: only the specific attributes that need to change are touched, and the heavy map structure is left undisturbed.
4.1 The Mechanism of Action
The architecture consists of four distinct phases:
1. Initialization (Memoization): The Map, the list of 1,700 Markers, and the single Popup are instantiated. Their object references are cached by use_memo.
2. Event Capture (Imperative): A click on a marker triggers the .on_click handler. This handler does one thing only: it updates the reactive variable selected_school.
3. Reaction (Effect Hook): Solara detects the change in selected_school. It triggers the use_effect hook dependent on this variable.
4. Mutation (Side Effect): The code inside use_effect executes. It accesses the singleton Popup instance, updates its location and child.value, and ensures it is present in the Map.layers list.
4.2 Handling the "Layer Already Exists" Edge Case
When using map.add_layer(popup) imperatively, robustness is key.
* Idempotency: If add_layer is called on a layer already in the map, ipyleaflet (and Leaflet.js) generally handles this gracefully (no-op). However, repeatedly checking membership (if popup not in map.layers) prevents unnecessary Comm messages.18
* Removal: When selected_school is set to None, the popup must be removed via map.remove_layer(popup). This provides a clean UX where the label disappears if the selection is cleared.
4.3 Why this Prevents Infinite Loops
The "infinite loop" 3 is avoided because:
1. Stable Identity: We use use_memo for the Popup, so the Python object identity of the popup never changes. We are not creating a new Popup() every render.
2. Traitlet-Only Updates: We modify properties (location, child.value) of the existing object. These are traitlet changes that send messages to the frontend but do not trigger a Solara tree reconciliation because the object reference passed to Solara (if any) remains constant.
3. Side-Effect Isolation: The add_layer call happens inside use_effect, which runs after the render commit. It does not interrupt the rendering process. The dependency array [selected_school] ensures this code only runs when the business logic dictates, not when the map performs internal updates (like zooming), breaking the feedback cycle.
5. Detailed Implementation Strategy
The following section breaks down the implementation into discrete logical components.
5.1 Step 1: Defining the Singleton Popup Factory
We define a helper function to create the popup. Note that we separate the creation from the updating. This function is designed to be passed to use_memo.


Python




import ipywidgets
import ipyleaflet

def create_popup_widget():
   """
   Creates a singleton popup structure.
   Returns: (popup_widget, html_widget)
   """
   # The child widget that holds the text.
   # We use a Layout with a minimum width to ensure readability.
   html_widget = ipywidgets.HTML(
       value="Loading...",
       layout=ipywidgets.Layout(min_width="120px")
   )
   
   # Initialize off-screen or hidden. 
   # Key configurations for a 'tooltip' feel:
   # - close_button=False: Removes the 'x', cleaner look.
   # - auto_close=False: We manage closing via state.
   # - close_on_escape_key=False: Prevents accidental dismissal.
   # - auto_pan=True: Ensures the user sees the popup even at map edges.
   popup = ipyleaflet.Popup(
       location=(0, 0),
       child=html_widget,
       close_button=False,
       auto_close=False,
       close_on_escape_key=False,
       max_width=300,
       min_width=100,
       auto_pan=True
   )
   return popup, html_widget

Rationale: By returning both the popup (container) and html_widget (content), we gain direct access to update the text without traversing the widget tree later.13
5.2 Step 2: Memoizing the Map and Markers
The user currently employs use_memo for markers. We must extend this to the Map instance itself. While the user's snippet shows Map.element(layers=...), using Map.element implies that Solara manages the layer list. If we modify the layer list imperatively (adding the popup), Solara might try to revert it on the next render.
Optimization: We will memoize the Map widget instance itself. This effectively tells Solara "Here is a black box widget; render it, but don't try to manage its internal children dynamically."
5.3 Step 3: The Synchronization Effect
The core logic resides in the use_effect hook.


Python




def sync_popup():
   school = selected_school.value
   
   # Case 1: No selection. Ensure popup is removed.
   if school is None:
       if popup in map_instance.layers:
           map_instance.remove_layer(popup)
       return

   # Case 2: Selection active. Update and Show.
   
   # Update Content (HTML)
   # Using f-string for zero-latency formatting.
   popup_html.value = f"<b>{school.name}</b>"
   
   # Update Location (Traitlet)
   # Moves the popup instantly on the client side.
   popup.location = (school.lat, school.lon)
   
   # Ensure Visibility
   # Only verify membership if strictly necessary to avoid overhead, 
   # but checking `if popup not in layers` is safer for preventing duplicates.
   if popup not in map_instance.layers:
       map_instance.add_layer(popup)

Rationale: This logic handles all state transitions (Selected -> None, None -> Selected, Selected A -> Selected B) in O(1) time.2
6. Performance Optimization and Benchmarking
When dealing with 1,700 interactive elements, performance is the primary constraint.
6.1 Memory Footprint Analysis
* Naive Approach (1,700 Popups): A Popup widget is a Python object, wrapping a Backbone model, wrapping a Leaflet L.popup instance. 1,700 instances would consume MBs of memory and degrade browser performance due to the sheer number of attached event listeners.
* Singleton Approach (1 Popup): The overhead is negligible. The browser only manages one DOM node for the popup. Moving the popup (popup.setLatLng in JS) is an optimized DOM transformation that does not trigger layout thrashing.
6.2 Network Traffic (Comm Channel)
In the singleton pattern, selecting a school sends two messages over the websocket:
1. widget_update: Popup.location -> (lat, lon)
2. widget_update: HTML.value -> "New Name"
(If the popup was not already on the map, an add_layer message is also sent).
This payload is measured in bytes. In contrast, regenerating the layer list declaratively would involve sending a widget_update for the Map's layers trait, which contains the IDs of all 1,701 layers. While ipywidgets optimizes this by sending references, the serialization overhead on the Python side to prepare this list is O(N).8
6.3 Browser Rendering Cost
The auto_pan=True feature of the Popup widget 11 triggers a map pan animation if the marker is near the edge. This is handled by the GPU in modern browsers. By avoiding WidgetControl (which forces layout recalculations), we allow Leaflet to use hardware-accelerated transforms for the map pane, ensuring the animation remains smooth even with 1,700 SVG markers on the canvas.
7. Implementation Guide: The Code Deliverable
The following code snippet synthesizes the research into a production-ready component. It assumes the existence of a standard data structure (e.g., a dictionary or object) for the schools.
Table 1: Key Variable Definitions
Variable
	Type
	Description
	selected_school
	solara.Reactive[Optional[dict]]
	Global state holding the currently selected school object or None.
	map_instance
	ipyleaflet.Map
	The memoized map widget instance.
	popup_layer
	ipyleaflet.Popup
	The singleton popup layer.
	popup_content
	ipywidgets.HTML
	The HTML widget inside the popup.
	

Python




import solara
import ipyleaflet
import ipywidgets

# --- Mock Data & State Setup ---
# In your actual app, this is likely defined in a separate module.
# We assume a data structure like: {'id': 1, 'name': 'PS 123', 'lat': 40.7, 'lon': -74.0}
# selected_school = solara.reactive(None) 

def create_reusable_popup():
   """
   Factory function for the singleton popup.
   Returns: (Popup_Widget, Child_HTML_Widget)
   """
   # 1. Create the content widget
   # Using specific layout constraints to prevent zero-width rendering issues
   label_widget = ipywidgets.HTML(
       value="", 
       layout=ipywidgets.Layout(min_width="150px", overflow="hidden")
   )
   
   # 2. Create the Popup wrapper
   # Configured for "Tooltip-like" behavior:
   # - No close button (managed by state)
   # - auto_pan enabled for UX
   popup = ipyleaflet.Popup(
       location=(0, 0),
       child=label_widget,
       close_button=False,
       auto_close=False,
       close_on_escape_key=False,
       auto_pan=True,
       max_width=300
   )
   return popup, label_widget

@solara.component
def SchoolMap(markers_data, selected_school):
   """
   A reactive map component that handles 1700+ markers efficiently.
   
   Args:
       markers_data: List[dict] - The source data for schools.
       selected_school: solara.Reactive - The state variable for selection.
   """
   
   # ---------------------------------------------------------
   # 1. Resource Memoization
   # ---------------------------------------------------------
   
   # Initialize Map. 
   # dependent on to ensure it is created exactly once.
   map_widget = solara.use_memo(
       lambda: ipyleaflet.Map(
           center=(40.7, -74.0), 
           zoom=11, 
           scroll_wheel_zoom=True
       ),
       dependencies=
   )
   
   # Initialize the Singleton Popup.
   # We unpack the tuple to get references to both the container and content.
   popup_layer, popup_content = solara.use_memo(create_reusable_popup, dependencies=)

   # ---------------------------------------------------------
   # 2. Imperative Marker Generation (Optimized)
   # ---------------------------------------------------------
   
   # This function generates the markers and attaches click handlers.
   # It mimics the user's current working pattern.
   def setup_markers():
       # Ideally, we clear old layers if data changes, but for this report
       # we focus on the initial load.
       current_markers =
       
       for data in markers_data:
           # Create CircleMarker (Lightweight vector)
           marker = ipyleaflet.CircleMarker(
               location=(data['lat'], data['lon']),
               radius=5,
               color="#3388ff",
               fill_color="#3388ff",
               fill_opacity=0.7,
               weight=1
           )
           
           # Closure to capture the specific 'data' for this marker
           def on_click_handler(**kwargs):
               # Update the reactive state. 
               # This triggers the 'use_effect' below, NOT a full map re-render.
               selected_school.value = data
               
           marker.on_click(on_click_handler)
           current_markers.append(marker)
           
           # Add to map immediately (Imperative addition is often faster for large lists)
           map_widget.add_layer(marker)
           
       return current_markers

   # Only regenerate markers if the source data list changes.
   solara.use_memo(setup_markers, dependencies=[markers_data])

   # ---------------------------------------------------------
   # 3. Reactive State Synchronization (The Solution)
   # ---------------------------------------------------------
   
   # This effect acts as the bridge between the Reactive World (selected_school)
   # and the Imperative World (ipyleaflet Map).
   def update_popup_state():
       school = selected_school.value
       
       if school is None:
           # Logic: If selection is cleared, remove the visual indicator.
           if popup_layer in map_widget.layers:
               map_widget.remove_layer(popup_layer)
       else:
           # Logic: Selection exists.
           
           # 1. Update the Text
           # We assume 'name' is a key in the school dictionary.
           popup_content.value = f"<b>{school.get('name', 'Unknown School')}</b>"
           
           # 2. Update the Position
           # This triggers the move animation on the client.
           popup_layer.location = (school['lat'], school['lon'])
           
           # 3. Ensure Presence
           # If the popup was previously removed or never added, add it now.
           if popup_layer not in map_widget.layers:
               map_widget.add_layer(popup_layer)
               
   # CRITICAL: The dependency array must contain the reactive value.
   # This ensures the code runs whenever the selection updates.
   solara.use_effect(update_popup_state, dependencies=[selected_school.value])

   # ---------------------------------------------------------
   # 4. Rendering
   # ---------------------------------------------------------
   
   # We display the map widget directly. 
   # Since we are managing layers imperatively, we do not pass `layers=[...]` here.
   return solara.display(map_widget)

8. Limitations and Future Considerations
While the Singleton Dynamic Popup provides the most robust architecture for the stated constraints, certain limitations persist within the ipyleaflet/Solara ecosystem.
8.1 The "Z-Index" and Stacking Context
Leaflet places popups in a specific map pane (the popupPane) which sits above the markerPane and overlayPane. This generally ensures visibility. However, if the application introduces other high-z-index elements (like custom D3 overlays or WebGL layers), the popup might be obscured. Investigating the pane attribute of the Popup class allows for manual reassignment to the tooltipPane (z-index 650) or a custom pane if necessary.11
8.2 Mobile Responsiveness
The Popup widget has a max_width attribute. On mobile devices, a fixed max_width=300 might exceed the viewport width. A more advanced implementation might listen to the browser's window resize events (via solara.use_window_size) and dynamically adjust the max_width trait of the popup to min(300, window_width - 20).
8.3 Scaling Beyond 2,000 Markers
At 1,700 markers, CircleMarker (SVG) performance is acceptable. If the dataset grows to 5,000+, the DOM overhead of 5,000 SVG nodes will cause browser lag. At that scale, the architecture must shift to ipyleaflet.Circle (Canvas-backed) or ipyleaflet.Heatmap. The Singleton Popup solution described here remains perfectly valid and reusable in those scenarios, as it depends only on the selection coordinate, not on the marker implementation itself. This decoupling is a key architectural benefit of the proposed solution.
9. Conclusion
The integration of high-volume imperative markers with reactive Solara state requires a hybrid architecture that respects the strengths of both paradigms. Purely declarative approaches fail due to reconciliation overhead, while purely imperative approaches fail to maintain state consistency.
By treating the Map and Markers as stable, long-lived resources (memoized) and the Popup as a singular, mutable "cursor" that follows the reactive selection state, developers can achieve optimal performance. The Singleton Dynamic Popup pattern eliminates render loops by isolating updates to a side-effect hook, ensures scalability by maintaining O(1) complexity for updates regardless of dataset size, and unifies the user experience by responding identically to map clicks, sidebar selections, and programmatic data changes. This approach provides a solid foundation for building professional-grade geospatial dashboards in Python.
Works cited
   1. Ipyleaflet Advanced - Solara, accessed December 29, 2025, https://solara.dev/documentation/examples/libraries/ipyleaflet_advanced
   2. use_effect - Solara documentation, accessed December 29, 2025, https://solara.dev/documentation/api/hooks/use_effect
   3. Three Ways to Cause Infinite Loops When Using UseEffect in React and How to Prevent Them - DEV Community, accessed December 29, 2025, https://dev.to/oyedeletemitope/three-ways-to-cause-infinite-loops-when-using-useeffect-in-react-and-how-to-prevent-them-3ip3
   4. Prevent Infinite Re-renders in React | by Vikas Tiwari - Medium, accessed December 29, 2025, https://medium.com/@tiwarivikas/prevent-infinite-re-renders-in-react-f460e8f90974
   5. Infinite re-render - I'm doomed : r/react - Reddit, accessed December 29, 2025, https://www.reddit.com/r/react/comments/1inojpr/infinite_rerender_im_doomed/
   6. The anatomy of Solara's functionality, accessed December 29, 2025, https://solara.dev/documentation/advanced/understanding/anatomy
   7. React re-renders guide: preventing unnecessary re-renders | by Nadia Makarevich | Medium, accessed December 29, 2025, https://adevnadia.medium.com/react-re-renders-guide-preventing-unnecessary-re-renders-8a3d2acbdba3
   8. Introduction to ipyleaflet — ipyleaflet documentation, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/
   9. Opening a popup on clicking a GeoJSON object · Issue #912 · jupyter-widgets/ipyleaflet, accessed December 29, 2025, https://github.com/jupyter-widgets/ipyleaflet/issues/912
   10. What is ipyleaflet.Map.element() ? - Solara - Answer Overflow, accessed December 29, 2025, https://www.answeroverflow.com/m/1200464976368898119
   11. Documentation - Leaflet - a JavaScript library for interactive maps, accessed December 29, 2025, https://leafletjs.com/reference.html
   12. API Reference — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/api_reference/index.html
   13. Source code for ipyleaflet.leaflet, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/_modules/ipyleaflet/leaflet.html
   14. Popup — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/layers/popup.html
   15. How to make closed popups reappear? · Issue #723 · jupyter-widgets/ipyleaflet - GitHub, accessed December 29, 2025, https://github.com/jupyter-widgets/ipyleaflet/issues/723
   16. How can I prevent a popup to show when clicking on a marker in Leaflet? - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/26638432/how-can-i-prevent-a-popup-to-show-when-clicking-on-a-marker-in-leaflet
   17. Widget Control — ipyleaflet documentation - Read the Docs, accessed December 29, 2025, https://ipyleaflet.readthedocs.io/en/latest/controls/widget_control.html
   18. lazy pop up image loading for ipyleaflet - Stack Overflow, accessed December 29, 2025, https://stackoverflow.com/questions/75176609/lazy-pop-up-image-loading-for-ipyleaflet