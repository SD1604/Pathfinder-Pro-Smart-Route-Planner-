# Pathfinder Pro — Delhi Urban Routing Engine

A production-grade geospatial routing engine purpose-built for Delhi-NCR's high-density road network. Pathfinder Pro computes optimal paths across a directed graph of 100,000+ real OSM nodes using a custom Bidirectional A\* implementation, returning results in near real-time through a Flask REST API and a Leaflet.js frontend.

---

## What Makes This Different from Google Maps

Commercial routing products optimize for the average city. Pathfinder Pro is built around **Delhi-specific ground truth** — the conditions that no general-purpose map captures or exposes.

| Capability                 | Google Maps                         | Pathfinder Pro                                                                    |
| -------------------------- | ----------------------------------- | --------------------------------------------------------------------------------- |
| Hafta bazaar penalty layer | ❌ Unaware of weekly street markets | 🔨 In progress — edge-level, time-bucketed penalty matrix with confidence scoring |
| Waterlogging rerouting     | ❌ Static road graph                | 🔨 Architected — WebSocket push infrastructure ready for live condition updates   |
| Algorithm transparency     | ❌ Proprietary black box            | ✅ Nodes explored, compute time (ms), and cache status surfaced to the user       |
| India-native geocoding     | Google Places                       | OLA Maps — better mohalla/colony/landmark coverage across Delhi-NCR               |
| Graph auditability         | ❌ Closed                           | ✅ OpenStreetMap — inspectable, correctable, extensible                           |
| Transport modes            | Drive / Walk / Transit              | Drive (time-optimized) · Walk · Cycle (distance-optimized)                        |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (HTML · CSS · Leaflet.js · OLA Maps)             │
│  • Map interaction  • Search  • Metrics panel  • Directions │
└────────────────────────┬────────────────────────────────────┘
                         │  POST /find_path  (REST)
                         │  Socket.IO        (WebSocket)
┌────────────────────────▼────────────────────────────────────┐
│  Flask Backend                                              │
│  • Coordinate snapping (KD-Tree)                            │
│  • Route cache (TTL=5 min, thread-safe)                     │
│  • Transport mode configuration                             │
│  • Road name extraction + turn-by-turn directions           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  Graph Layer  (OSMnx · NetworkX · GraphML)                  │
│  • delhi_full.graphml  — 100k+ nodes, pre-built             │
│  • Speed limits + travel times imputed by OSMnx             │
│  • Largest SCC extracted — guarantees full reachability     │
│  • Graph simplified — degree-2 nodes removed (~30% smaller) │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│  Algorithm Layer                                            │
│  • Bidirectional A*  (primary, production)                  │
│  • Haversine heuristic over spherical Earth surface         │
│  • Custom Dijkstra  (baseline for benchmarking)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Algorithm: Bidirectional A\*

Standard A\* searches from start to goal. Bidirectional A\* runs **two simultaneous searches** — one forward from the start, one backward from the goal using a reversed edge graph — and terminates when the frontiers meet and no shorter path can exist.

### How It Works

```
Forward search  : start_node → goal_node   (on original graph)
Backward search : goal_node  → start_node  (on graph.reverse())

Both searches maintain:
  dist[]     — best known cost from their respective source
  settled{}  — nodes whose optimal cost is confirmed
  pq         — priority queue ordered by f = g + h

Termination condition:
  min(f_forward) + min(f_backward) >= best_cost_found

  If the sum of the two frontier tops can't beat the best
  complete path seen so far, no better path exists.
```

### Heuristic: Haversine Distance

The heuristic $h(v)$ estimates the remaining cost from node $v$ to the goal using the great-circle distance over Earth's surface:

$$h(v) = \frac{2R \cdot \arcsin\!\left(\sqrt{\sin^2\!\frac{\Delta\phi}{2} + \cos\phi_v \cos\phi_g \sin^2\!\frac{\Delta\lambda}{2}}\right)}{v_{max}}$$

where $R = 6{,}371{,}000$ m, $\phi$ = latitude, $\lambda$ = longitude, and $v_{max} = 22.22$ m/s (80 km/h cap). This heuristic is **admissible** — it never overestimates — guaranteeing the algorithm returns the optimal path.

### Meeting Point Detection

When the forward search settles a node $v$ already settled by the backward search (or vice versa), a candidate path cost is recorded:

```
candidate = f_dist[u] + edge_weight(u,v) + b_dist[v]
if candidate < best_cost:
    best_cost    = candidate
    meeting_node = v
```

Path reconstruction walks `f_par[]` backward from the meeting node to the start, then `b_par[]` forward to the goal, and concatenates.

### Why Bidirectional vs. Vanilla A\*

Vanilla A\* explores a search frontier that grows as a circle of radius $r$ from the start. Bidirectional A\* grows two half-circles of radius $r/2$ each. Since area scales with $r^2$, the bidirectional approach explores roughly **half the nodes** for the same path length, with no loss of optimality.

---

## Engineering Highlights

**Spatial Indexing — 900× Lookup Speedup**

The original implementation used `ox.nearest_edges()`, which performs expensive geometric projections across every edge. Replacing this with a **SciPy KD-Tree** over node coordinates reduced coordinate-to-node lookup from ~45 s to <50 ms. At startup, all node coordinates are extracted into a NumPy array and indexed in O(n log n); each query is then O(log n).

**Graph Pre-processing Pipeline**

Raw OSM data for Delhi contains isolated subgraphs and dead-end components that make certain origin-destination pairs unreachable. The pipeline extracts the **Largest Strongly Connected Component**, guaranteeing 100% route reachability. OSMnx's graph simplification further removes non-intersectional degree-2 nodes, reducing the graph footprint by ~30% without altering topology.

**Pre-built GraphML**

Rather than re-fetching and re-parsing OSM data on every cold start (a 2–3 minute operation), the processed graph is serialized to `delhi_full.graphml` and stored on Google Drive. `graph_loader.py` downloads it once on first run and loads it in seconds on all subsequent starts.

**Route Cache**

A thread-safe, TTL-based in-memory cache (5-minute expiry) stores `(start_node, end_node, mode)` → result mappings. Repeated popular routes — AIIMS → Connaught Place, Lajpat Nagar → Airport — return instantly with a `cache_hit: true` flag surfaced in the UI.

**Transport Mode Configuration**

Each mode uses a different edge weight and speed cap, altering both the path chosen by A\* and the ETA calculation:

| Mode  | Edge Weight                              | Speed Cap | Optimization      |
| ----- | ---------------------------------------- | --------- | ----------------- |
| Drive | `travel_time` (OSMnx, real speed limits) | 80 km/h   | Fastest time      |
| Walk  | `length` (metres)                        | 5 km/h    | Shortest distance |
| Cycle | `length` (metres)                        | 20 km/h   | Shortest distance |

**WebSocket Foundation**

Flask-SocketIO is integrated and running. The `subscribe_conditions` event handler is the hook point for the upcoming waterlogging and street market alert push layer — clients can subscribe to their bounding box and receive server-pushed condition updates without polling.

---

## Performance Benchmarks (Delhi-NCR Dataset)

| Metric                   | Dijkstra v1.0             | Bidirectional A\* v3.0        | Improvement    |
| ------------------------ | ------------------------- | ----------------------------- | -------------- |
| Nodes explored (avg)     | High — uninformed         | ~50% fewer — heuristic-guided | ~50% reduction |
| Spatial lookup           | ~45 s (brute-force edges) | <50 ms (KD-Tree nodes)        | ~900× faster   |
| Cold-start total latency | ~50 s                     | ~2.1 s                        | ~24× faster    |
| Warm cache response      | ~2.1 s                    | <5 ms                         | —              |

---

## Tech Stack

| Component      | Technology                       | Role                                              |
| -------------- | -------------------------------- | ------------------------------------------------- |
| Graph data     | OSMnx + OpenStreetMap            | Real Delhi road network, speed limits, road names |
| Graph model    | NetworkX MultiDiGraph            | Directed edges (one-ways), multi-edge support     |
| Core algorithm | Custom Bidirectional A\*         | Optimal, heuristic-guided pathfinding             |
| Spatial index  | SciPy KD-Tree                    | Sub-millisecond coordinate snapping               |
| Backend        | Flask + Flask-SocketIO           | REST API + WebSocket foundation                   |
| Graph storage  | GraphML (pre-built)              | Fast cold-start, no re-parsing                    |
| Geocoding      | OLA Maps API                     | Autocomplete + text search, Delhi-native          |
| Frontend       | Leaflet.js + Stadia Maps         | Map rendering, route drawing, theming             |
| UI             | HTML5 · CSS3 · Vanilla JS (ES6+) | Single-page app, no framework dependencies        |

---

## Project Structure

```
Pathfinder_Pro/
├── algorithms/
│   ├── bidir_astar_path.py   # Bidirectional A* — production pathfinder
│   └── dijkstra.py           # Custom Dijkstra — benchmarking baseline
├── backend/
│   └── app.py                # Flask REST API + SocketIO server
├── graph/
│   └── graph_loader.py       # GraphML download + OSMnx load
├── utils/
│   └── geo_utils.py          # KD-Tree spatial index + nearest node
├── frontend/
│   ├── index.html            # Single-page UI shell
│   ├── app.js                # Map interaction, routing, OLA Maps
│   └── styles.css            # Design system, dark/light theme
├── requirements.txt
└── README.md
```

---

## Features

- Bidirectional A\* with Haversine heuristic — optimal paths, ~50% fewer nodes explored vs. vanilla A\*
- Three transport modes — drive (time-optimized), walk and cycle (distance-optimized)
- OLA Maps geocoding — autocomplete and text search, biased to Delhi-NCR, 50 km radius
- Geolocation — GPS-based "My location" with animated marker
- Turn-by-turn directions — extracted from OSM road name and ref attributes, merged by segment
- Metrics panel — distance (km), ETA (min), compute time (ms), nodes explored, cache hit badge
- Route cache — TTL-based, thread-safe, instant response on repeated queries
- Dark / light theme — CSS custom properties, persisted in localStorage
- Collapsible panel — map-first layout on smaller screens
- WebSocket client — connected and ready for live condition updates
- Congestion segment rendering — infrastructure for green/amber/red traffic coloring already implemented in `drawSegmentedRoute()`

---

## Roadmap

- **Street market penalty layer** — Hafta bazaars modeled as time-bucketed edge weight penalties on the OSM graph, with a confidence score per market entry. Covers Delhi's major weekly markets (INA Sunday, Lajpat Nagar Tuesday, etc.)
- **Waterlogging layer** — Integration with IMD/NDMC flood data; affected roads get elevated edge weights or are temporarily removed from the graph; updates pushed via WebSocket
- **Congestion layer** — Live traffic weights from a real-time source, rendered as colored route segments
- **Multi-waypoint routing** — Chain A\* across intermediate stops

---

## How to Run

```bash
# Clone the repository
git clone https://github.com/SD1604/Pathfinder-Pro-Smart-Route-Planner-.git
cd Pathfinder-Pro-Smart-Route-Planner-

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend (downloads delhi_full.graphml on first run)
python3 -m backend.app

# Open frontend/index.html in your browser
# or serve with: python3 -m http.server 8080 (from frontend/)
```

The server starts on `http://0.0.0.0:5000`. The health endpoint at `/health` returns node count, edge count, and cache size.

---

## Live Demo

[https://youtu.be/CenmCSQnDzc](https://youtu.be/CenmCSQnDzc)
