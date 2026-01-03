# Sidebar Redesign Plan

**Created**: December 29, 2025
**Status**: Planning Complete - Ready for Implementation
**Context**: User feedback identified redundancies and mode confusion in current sidebar

---

## Executive Summary

The sidebar will have **three distinct modes** that automatically switch based on user interaction:

| Mode | Trigger | Purpose |
|------|---------|---------|
| **Overview Mode** | No selection, no filters | Dashboard home - citywide summary |
| **Cluster Mode** | Filters active (borough/district/superintendent) | Aggregate stats for filtered group |
| **School Mode** | School marker clicked | Detailed info for single school |

---

## Design Decisions (Confirmed via User Dialogue)

### 1. Overview Mode (Default - Fresh Page Load)

**Content:**
- High-level citywide statistics (total schools, training coverage %)
- ONE summary visualization (training status donut chart)
- Brief guidance text for discoverability ("Use filters above to explore by district...")
- UX best practices: clean, inviting, encourages exploration

**Rationale**: Full dashboard summary serves as "home base" - user sees the big picture before drilling down.

---

### 2. School Mode (Single School Selected)

**Trigger**: User clicks a school marker on the map

**Header:**
- "← Back to [Previous View]" link (returns to Overview or Cluster Mode)
- School name prominently displayed
- Training status badge (Complete / Fundamentals Only / No Training)

**Main Content - Tabbed Interface:**

```
┌─────────────────┬──────────┬───────────────────┐
│  Fundamentals   │  LIGHTS  │  Student Sessions │
└─────────────────┴──────────┴───────────────────┘
```

**Tab Content Structure:**
- Participants grouped by role within each tab
- Per participant: Name + Training Date
- Priority roles appear first (SAPIS, Social Worker, SSM, School Counselor)
- "Student Sessions" tab placeholder for future development

**Vulnerability Section:**
- Numeric with context: "STH: 12.5% (high)" with color indicator
- "ENI: 78% (moderate)"
- Simple, informative, not overwhelming

**Navigation:**
- "← Back to [District 2]" or "← Back to Overview" clickable link at top
- Clicking elsewhere on map (empty area or different school) also navigates away

**What's NOT shown in School Mode:**
- Priority schools list (irrelevant for single school)
- Cluster statistics (irrelevant)
- Pie charts (removed entirely)
- Redundant count badges

---

### 3. Cluster Mode (Filters Active)

**Trigger**: User applies any filter (borough, district, superintendent, training status)

**Header:**
- "← Back to Overview" link
- Cluster identifier: "District 2" or "Bronx" or "Superintendent: John Smith"
- School count in cluster

**Statistics Section:**

```
Training Coverage          Vulnerability
─────────────────         ─────────────────
◉ Complete: 45%           Avg STH: 8.2%
◉ Fundamentals: 30%       Avg ENI: 72%
◉ No Training: 25%        High-Need: 12 schools

[Hover any stat for citywide comparison]
```

**Comparison Display**: Tooltip on hover (non-intrusive)
- e.g., Hover "Complete: 45%" → "Citywide average: 38%"

**Priority Schools Section:**

**Configurable Criteria** (user toggles):
- [ ] High STH (≥5%)
- [ ] High ENI (≥80%)
- [ ] No Training
- [ ] Fundamentals Only (missing LIGHTS)

**List Organization**: Grouped by Superintendent
```
📋 Superintendent: Jane Doe (4 priority schools)
   • PS 123 - STH: 15.2%, ENI: 85%
   • MS 456 - STH: 8.1%, ENI: 91%
   ...

📋 Superintendent: John Smith (2 priority schools)
   • HS 789 - STH: 12.0%, ENI: 78%
   ...
```

**Export:**
- CSV download button for priority schools list
- Simple, single format (no Excel for now)

---

### 4. Mode Switching Behavior

| From | To | Trigger | Behavior |
|------|----|---------|----------|
| Overview | Cluster | Apply filter | Sidebar transitions to Cluster Mode |
| Overview | School | Click marker | Sidebar transitions to School Mode |
| Cluster | School | Click marker | Sidebar transitions to School Mode (filters stay on map) |
| Cluster | Overview | Clear all filters | Sidebar returns to Overview |
| School | Cluster | Click "← Back to [Cluster]" | Sidebar returns to Cluster Mode |
| School | Overview | Click "← Back to Overview" | Sidebar returns to Overview, clears selection |
| School | School | Click different marker | Sidebar updates to new school |
| School | Cluster/Overview | Click empty map area | Sidebar returns to previous context |

---

## Elements to REMOVE (Clean Slate)

The following current sidebar elements will be **removed entirely**:

1. **Borough/District pie charts** - replaced by simpler progress bars in Cluster Mode
2. **Priority Schools section in School Mode** - only relevant in Cluster Mode
3. **Redundant count badges** - consolidated into single stats display
4. **Persistent summary section** - replaced by mode-aware header with back navigation
5. **All collapsible sections from current design** - replaced by cleaner tab/section structure

---

## Visual Hierarchy (Wireframe Concept)

### Overview Mode
```
┌────────────────────────────────────┐
│  HTYPE Training Dashboard          │
│  ════════════════════════════════  │
│                                    │
│  📊 1,679 Schools                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Complete: 523 (31%)   ████████░░  │
│  Fundamentals: 412 (25%)  █████░░  │
│  No Training: 744 (44%)   ██░░░░░  │
│                                    │
│  [Training Status Donut Chart]     │
│                                    │
│  ─────────────────────────────────│
│  💡 Use filters above to explore   │
│     by district or superintendent  │
└────────────────────────────────────┘
```

### Cluster Mode
```
┌────────────────────────────────────┐
│  ← Back to Overview                │
│  ════════════════════════════════  │
│  📍 District 2 (127 schools)       │
│                                    │
│  Training        │  Vulnerability  │
│  ──────────────  │  ────────────── │
│  Complete: 45%ⓘ  │  Avg STH: 8.2%ⓘ│
│  Fund Only: 30%  │  Avg ENI: 72%   │
│  Untrained: 25%  │  High-Need: 12  │
│                                    │
│  ─────────────────────────────────│
│  🎯 Priority Schools               │
│  ☑ High STH ☑ No Training ☐ ...   │
│                                    │
│  📋 Supt: Jane Doe (4 schools)     │
│     • PS 123 - STH: 15%, ENI: 85%  │
│     • MS 456 - STH: 8%, ENI: 91%   │
│                                    │
│  📋 Supt: John Smith (2 schools)   │
│     • HS 789 - STH: 12%, ENI: 78%  │
│                                    │
│  [📥 Export CSV]                   │
└────────────────────────────────────┘
```

### School Mode
```
┌────────────────────────────────────┐
│  ← Back to District 2              │
│  ════════════════════════════════  │
│  🏫 P.S. 123 The Example School    │
│  DBN: 02M123                       │
│  ┌──────────────────────────────┐  │
│  │  ✅ Complete                 │  │
│  └──────────────────────────────┘  │
│                                    │
│ ┌───────────┬────────┬──────────┐  │
│ │Fundamentals│ LIGHTS │ Students │  │
│ └───────────┴────────┴──────────┘  │
│                                    │
│  👥 Social Workers (2)             │
│     • Jane Smith - 10/15/24        │
│     • John Doe - 10/15/24          │
│                                    │
│  👥 SAPIS (1)                      │
│     • Maria Garcia - 10/15/24      │
│                                    │
│  👥 Teachers (8)                   │
│     • Alice Brown - 10/15/24       │
│     • Bob Wilson - 10/15/24        │
│     ...                            │
│                                    │
│  ─────────────────────────────────│
│  📊 Vulnerability                  │
│  STH: 12.5% (high)  🔴             │
│  ENI: 78% (moderate) 🟡            │
│                                    │
│  [🎯 Locate on Map]                │
└────────────────────────────────────┘
```

---

## Implementation Approach

### Phase 1: State Management Refactor
1. Add `sidebar_mode` reactive state: `"overview" | "cluster" | "school"`
2. Add `previous_mode` to track navigation history
3. Modify filter handlers to set mode to "cluster" when any filter applied
4. Modify school selection to set mode to "school"

### Phase 2: Component Architecture
1. Create `OverviewSidebar` component
2. Create `ClusterSidebar` component
3. Create `SchoolSidebar` component with tabs
4. Create `SidebarRouter` component that renders correct view based on mode

### Phase 3: Remove Legacy Code
1. Remove current `SummarySection` (replaced by mode-aware views)
2. Remove current pie chart code
3. Remove redundant collapsible sections
4. Clean up unused state variables

### Phase 4: New Features
1. Implement tabbed interface for School Mode (Solara tabs or custom)
2. Implement configurable priority criteria checkboxes
3. Implement citywide comparison tooltips
4. Implement CSV export for priority schools

---

## Data Requirements

### Already Available
- School data with training status ✅
- Vulnerability indicators (STH, ENI) ✅
- Participant detail data (4,955 records) ✅
- Filter state (borough, district, superintendent) ✅

### Needs Processing
- Citywide averages for comparison (calculate once on load)
- Priority school scoring (composite of STH + ENI + training status)
- Participant grouping by role per school

---

## Testing Checklist

### Overview Mode
- [ ] Shows on fresh page load
- [ ] Displays correct citywide stats
- [ ] Donut chart renders correctly
- [ ] Guidance text is helpful

### Cluster Mode
- [ ] Activates when any filter applied
- [ ] Shows correct aggregate stats for filtered schools
- [ ] Tooltips show citywide comparison on hover
- [ ] Priority criteria checkboxes work
- [ ] Priority list grouped by superintendent correctly
- [ ] CSV export downloads correct data
- [ ] "← Back to Overview" clears filters and returns

### School Mode
- [ ] Activates when marker clicked
- [ ] Tabs switch correctly (Fundamentals/LIGHTS/Students)
- [ ] Participants grouped by role within tabs
- [ ] Vulnerability shows numeric with context
- [ ] "← Back to [Cluster]" returns to Cluster Mode
- [ ] "← Back to Overview" clears selection
- [ ] Clicking different marker switches schools
- [ ] Clicking empty map returns to previous mode

### Mode Transitions
- [ ] Overview → Cluster (apply filter)
- [ ] Overview → School (click marker)
- [ ] Cluster → School (click marker, filters persist on map)
- [ ] School → Cluster (back link)
- [ ] School → Overview (back link when no filters)
- [ ] No jarring transitions or flicker

---

## Open Questions for Implementation

1. **Tab Implementation**: Use Solara's built-in tabs or custom HTML/CSS tabs?
2. **Tooltip Library**: Use ipywidgets tooltip or pure CSS hover?
3. **Animation**: Should mode transitions have smooth fade/slide, or instant?
4. **Mobile**: Any mobile considerations for sidebar width?

---

## Risk Mitigation

1. **Large participant lists**: Implement virtualization or "Show more" pagination
2. **Slow mode transitions**: Use memoization for computed values
3. **State complexity**: Clear separation between UI state and data state
4. **Regression**: Keep old components until new ones are verified working

---

*This plan is ready for implementation in the next working session.*
