# 🧭 SurakshaLander: Navigation Module (M4)

This module serves as the "brain" of the SurakshaLander. It provides an Explainable, Uncertainty-Aware A* pathfinding algorithm that dynamically alters the rover's routing behavior based on localization confidence.

## 🚀 Core Innovation
Standard A* algorithms rely on static costmaps (e.g., avoiding slopes > 15°). Our planner introduces a **Dynamic Uncertainty Penalty**. 

If the rover's localization uncertainty grows too high (e.g., odometry drift > 3m), the cost of traversing moderate slopes is artificially inflated. This forces the "lost" rover to enter **Caution Mode**, abandoning risky shortcuts in favor of longer, flatter, and safer routes until it can re-localize using crater geometry.

## 📁 Folder Structure
```text
navigation/
├── __init__.py            # Exposes the MissionPlanner class
├── mission_planner.py     # Contains A* logic, costmap generation, and XAI
└── README.md              # You are here