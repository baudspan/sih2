import numpy as np
import heapq
import math

# ---------------------------------------------------------
# M4 CORE LOGIC (NO I/O ALLOWED IN THIS CLASS)
# ---------------------------------------------------------
class MissionPlanner:
    def __init__(self, slope_map_matrix):
        """
        Expects a 2D NumPy array.
        """
        self.slope_map = slope_map_matrix
        self.max_safe_slope = 15.0
        self.height, self.width = self.slope_map.shape

    def get_step_cost(self, x, y, uncertainty):
        """Calculates the cost of stepping onto a specific pixel."""
        # Prevent out of bounds
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return float('inf')
            
        slope = self.slope_map[y, x]
        
        # 1. Constraint Check: Walls and No-Data zones
        if slope > self.max_safe_slope or np.isnan(slope):
            return float('inf')
            
        # 2. Base Cost + Hazard Cost
        cost = 1.0 + (slope * 0.5)
        
        # 3. Apply Uncertainty Penalty (The core innovation)
        if uncertainty > 3.0: 
            cost += (slope * 2.0) 
            
        return cost

    def heuristic(self, a, b):
        """Euclidean distance heuristic for A*"""
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def plan_route(self, start_pos, goal_pos, uncertainty):
        """
        A* Pathfinding Algorithm.
        start_pos and goal_pos must be (x, y) tuples.
        """
        # (f_score, (x, y))
        open_set = []
        heapq.heappush(open_set, (0, start_pos))
        
        came_from = {}
        
        g_score = {start_pos: 0}
        f_score = {start_pos: self.heuristic(start_pos, goal_pos)}
        
        # 8-way movement (up, down, left, right, diagonals)
        neighbors = [(0,1), (1,0), (0,-1), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == goal_pos:
                return self._reconstruct_path(came_from, current), self._generate_xai(uncertainty)

            for dx, dy in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                
                step_cost = self.get_step_cost(neighbor[0], neighbor[1], uncertainty)
                
                # Diagonal movement costs slightly more (math.sqrt(2))
                if dx != 0 and dy != 0 and step_cost != float('inf'):
                    step_cost *= 1.414

                tentative_g_score = g_score[current] + step_cost

                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, goal_pos)
                    
                    # Add to heap if not already there
                    if not any(neighbor == item[1] for item in open_set):
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # Return empty path if no valid route found
        return [], ["FAILED: No valid path found", f"Uncertainty: {uncertainty}m", f"Max slope: {self.max_safe_slope}°"]

    def _reconstruct_path(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _generate_xai(self, uncertainty):
        """Generates the 3-bullet explanation based on the state."""
        reasons = [
            f"Constraint: Slope limit enforced at {self.max_safe_slope}°",
            "Hazard: Avoided high-gradient terrain clusters"
        ]
        if uncertainty > 3.0:
            reasons.append(f"Uncertainty: Position error {uncertainty}m (>3m) -> Applied Caution Mode penalties")
        else:
            reasons.append(f"Uncertainty: Position error {uncertainty}m (<3m) -> Normal routing")
        return reasons


# ---------------------------------------------------------
# M4 LOCAL TESTING (Safe 3GB File Handling)
# ---------------------------------------------------------
# ---------------------------------------------------------
# M4 LOCAL TESTING (Safe 3GB File Handling)
# ---------------------------------------------------------
if __name__ == "__main__":
    import rasterio
    from rasterio.windows import Window
    import os
    
    # 1. Dynamically find the absolute path to the data file
    script_dir = os.path.dirname(os.path.abspath(__file__)) # Gets the /navigation folder
    TIF_PATH = os.path.join(script_dir, "..", "data", "processed", "slope.tif")
    
    # Clean up the path string for Windows (optional but looks nicer)
    TIF_PATH = os.path.normpath(TIF_PATH)
    
    print(f"Opening {TIF_PATH} safely...")
    
    try:
        with rasterio.open(TIF_PATH) as src:
            # Read a tiny 100x100 pixel window to test logic without crashing RAM
            window = Window(1000, 1000, 100, 100) 
            slope_chunk = src.read(1, window=window)
            
            planner = MissionPlanner(slope_chunk)
            
            start = (10, 10)
            goal = (80, 80)
            
            print("\n--- Test 1: High Uncertainty (Lost) ---")
            path_lost, reasons_lost = planner.plan_route(start, goal, uncertainty=4.5)
            print(f"Path length: {len(path_lost)} steps")
            for r in reasons_lost: print(f"- {r}")
            
            print("\n--- Test 2: Low Uncertainty (Confident) ---")
            path_confident, reasons_confident = planner.plan_route(start, goal, uncertainty=1.0)
            print(f"Path length: {len(path_confident)} steps")
            for r in reasons_confident: print(f"- {r}")
            
    except rasterio.errors.RasterioIOError:
        print(f"\nERROR: Could not find the file at:\n{TIF_PATH}")
        print("Did you run Sudhanwa's (M1's) script to generate the .tif files yet?")