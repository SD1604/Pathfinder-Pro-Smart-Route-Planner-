# Smart Route Planner (Pathfinder Pro)

A city-scale routing engine for Delhi, India, utilizing Python (OSMnx/NetworkX) to model a graph of 100,000+ nodes and edges. Implemented A* Search with a Haversine Heuristic*, achieving a 40% reduction in pathfinding latency compared to Dijkstra’s algorithm. Guaranteed 100% route reliability by pre-processing the graph into its Largest Strongly Connected Component (SCC).

---

## Features

- Fast route computation using **A\*** algorithm
- Real-world map data via **OpenStreetMap (OSMnx)**
- Optimized spatial queries using **nearest node lookup (KD-tree)**
- Caching for repeated coordinate queries
- Backend API built using **Flask**
- Handles large graphs via largest connected component extraction

---

## System Architecture

1. User provides source & destination coordinates
2. Coordinates mapped to nearest locations using spatial indexing
3. A\* algorithm computes shortest route
4. Route returned via Flask API

---

## Version History

### v3.0 - Major Performance Optimization

- Reduced API response time from ~50s → ~2-3s (~10x improvement)
- Optimized nearest node lookup from ~45s → ~1s
- Leveraged spatial indexing (KD-tree) for fast lookup
- Added caching for repeated coordinate queries
- Optimized overall A\* pipeline

---

### v2.0 - A\* Pathfinding

- Implemented A\* algorithm
- Added Haversine heuristic
- Improved efficiency over Dijkstra

---

### v1.0 - Initial Release (Dijkstra Implementation)

- Implemented Dijkstra’s algorithm from scratch
- Integrated OpenStreetMap data using OSMnx
- Built Flask backend

---

## Performance Benchmark

| Stage                               | Before (v2) | After (v3) |
| ----------------------------------- | ----------- | ---------- |
| Spatial Query & Nearest Node lookup | ~43s        | ~0.05s     |
| A\* Search with Haversine heuristic | ~1s         | ~1s        |
| Total Response Time                 | ~50s        | ~2–3s      |

### Result

Achieved ~10x speed improvement by optimizing spatial queries.
The system is now capable of near real-time route computation and is significantly more scalable.

---

## Technical Insight

The primary bottleneck was the use of `nearest edges lookup`, which performs expensive geometric computations on graph edges and takes longer.

Switching to `nearest nodes lookup` enabled the use of spatial indexing (KD-tree), reducing lookup time from seconds to milliseconds.

---

## Tech Stack

- Python
- Flask
- OSMnx
- NetworkX

---

## Project Structure

Pathfinder_Pro/
├── algorithms/
├── backend/
├── graph/
├── utils/
├── frontend/
├── requirements.txt
└── README.md

---

## How to Run

```bash
git clone https://github.com/SD1604/Pathfinder-Pro-Smart-Route-Planner-.git
cd Pathfinder-Pro-Smart-Route-Planner-

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python3 -m backend.app
```
