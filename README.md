# Smart Route Planner (Pathfinder)

A route optimization system that computes shortest paths using graph algorithms on real-world map data.

## Features

- Custom implementation of Dijkstra’s Algorithm (from scratch)
- Shortest path computation on real-world road networks (OpenStreetMap via OSMnx)
- Backend API built using Flask
- Efficient graph traversal using priority queue (heap)
- Handles large graphs by extracting largest connected component

## Tech Stack

- Python
- Flask
- OSMnx
- NetworkX

## Project Structure

smart-route-planner/
├── algorithms/  
├── backend/  
├── graph/  
├── utils/  
├── frontend/  
├── requirements.txt
└── README.md

## How to Run

```bash
git clone https://github.com/YOUR-USERNAME/smart-route-planner.git
cd smart-route-planner

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python3 -m backend.app
```
