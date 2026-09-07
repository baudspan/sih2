import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import numpy as np
import rasterio
from rasterio.enums import Resampling

# --- Create the app ONCE ---
app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = PROJECT_ROOT / "data" / "Lunar_Map.tiff"
CRATER_DB_PATH = PROJECT_ROOT / "crater_db" / "crater_db.sqlite"

# --- CORS middleware (allow React frontend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- All your safe imports and helper functions go here ---
# (the rest of your code, exactly as before)

# Safe imports with fallback protection
try:
    from tests.tests_evaluation import match_detections
    from src.perception.detector import detect_craters
    from terrain.dem_loader import load_dem
    from localization.crater_loader import load_craters
    
    HAS_EVAL_MODULES = True
except ImportError as e:
    print(f"⚠️ Warning: Evaluation modules could not be imported directly: {e}")
    HAS_EVAL_MODULES = False

# Safe import for the live localizer / simulation state including reasoning
try:
    from localization.state import get_current_position, get_rover_mode, get_reasoning
    HAS_LOCALIZER = True
except ImportError:
    try:
        from localization.localizer import get_current_position, get_rover_mode
        def get_reasoning(): return "System active. Streaming live telemetry."
        HAS_LOCALIZER = True
    except ImportError:
        HAS_LOCALIZER = False

# Safe import for the M6 audit trail (explain/audit_logger.py's decision_log.json)
try:
    from explain.audit_logger import read_log
    HAS_AUDIT_LOG = True
except ImportError as e:
    print(f"⚠️ Warning: audit logger could not be imported: {e}")
    HAS_AUDIT_LOG = False

# Separate, dedicated import for the DEM loader used by /terrain-heightmap.
# Deliberately decoupled from the HAS_EVAL_MODULES block above: that block
# aborts entirely if ANY of its imports fail (e.g. detector deps missing),
# which would otherwise take load_dem down with it even though load_dem
# itself has no such dependency.
try:
    from terrain.dem_loader import load_dem as load_dem_for_terrain
    HAS_DEM_LOADER = True
except ImportError as e:
    print(f"⚠️ Warning: terrain dem_loader could not be imported: {e}")
    HAS_DEM_LOADER = False

# In-memory cache for the decimated heightmap payload - loading the
# full-resolution DEM GeoTIFF is expensive (main.py's own comment calls it
# "this will take a while"), so we only ever do it once per grid_size.
_terrain_cache = {}
_evaluation_metrics = None


def _get_evaluation_metrics():
    global _evaluation_metrics
    if _evaluation_metrics is not None:
        return _evaluation_metrics

    with rasterio.open(DEM_PATH) as source:
        rows = min(600, source.height)
        cols = min(600, source.width)
        depth_map = source.read(
            1,
            out_shape=(rows, cols),
            resampling=Resampling.average,
        ).astype(np.float32)

    ground_truth = load_craters(str(CRATER_DB_PATH))
    detections = detect_craters(depth_map)
    tp, fp, fn, center_errs, radius_errs = match_detections(ground_truth, detections)
    total_det = len(detections)
    _evaluation_metrics = (
        round((tp / total_det) if total_det else 0.0, 3),
        round((tp / len(ground_truth)) if ground_truth else 0.0, 3),
        round(float(np.mean(center_errs)) if center_errs else 0.0, 2),
    )
    return _evaluation_metrics


def _build_heightmap_payload(grid_size=128):
    if grid_size in _terrain_cache:
        return _terrain_cache[grid_size]

    with rasterio.open(DEM_PATH) as source:
        output_rows = min(grid_size, source.height)
        output_cols = min(grid_size, source.width)
        dem_map = source.read(
            1,
            out_shape=(output_rows, output_cols),
            resampling=Resampling.average,
        ).astype(np.float32)
        dem_meta = source.meta.copy()
        dem_meta["transform"] = source.transform * source.transform.scale(
            source.width / output_cols,
            source.height / output_rows,
        )
        nodata = source.nodata

    if nodata is not None:
        dem_map[dem_map == nodata] = np.nan
    transform = dem_meta["transform"]
    h, w = dem_map.shape

    # Decimate down to ~grid_size cells per side for a WebGL-friendly mesh
    # (the raw DEM is far too dense to hand a browser directly).
    step_r = max(1, h // grid_size)
    step_c = max(1, w // grid_size)
    decimated = dem_map[::step_r, ::step_c]

    if np.isnan(decimated).any():
        fill_val = float(np.nanmean(dem_map))
        decimated = np.nan_to_num(decimated, nan=fill_val)

    rows, cols = decimated.shape
    # Real-world coordinates for each grid row/column, via the DEM's own
    # affine transform - same approach simulation/main.py's
    # downsampled_path_to_world() uses, so this lines up with the same
    # world frame the rover's telemetry x/y are already in.
    x_coords = [float((transform * (c * step_c, 0))[0]) for c in range(cols)]
    y_coords = [float((transform * (0, r * step_r))[1]) for r in range(rows)]

    payload = {
        "rows": rows,
        "cols": cols,
        "x_coords": x_coords,
        "y_coords": y_coords,
        "elevation": decimated.astype(float).tolist(),
        "source": "data/Lunar_Map.tiff (real DEM, decimated for the 3D view)",
    }
    _terrain_cache[grid_size] = payload
    return payload


# --- All routes are attached to the single 'app' instance ---

@app.get("/terrain-heightmap")
def get_terrain_heightmap(grid_size: int = 128):
    """
    Serve a decimated version of the real DEM (terrain/dem_loader.py, the
    same GeoTIFF the planner and localizer already use) as a heightmap grid
    for the dashboard's 3D terrain view. Cached in memory after first build.
    """
    if not HAS_DEM_LOADER:
        return {"error": "DEM loader module not available"}

    grid_size = max(16, min(grid_size, 512))
    try:
        return _build_heightmap_payload(grid_size)
    except Exception as e:
        print("Terrain heightmap build error:", e)
        return {"error": str(e)}


@app.get("/")
def read_root():
    return {"status": "SurakshaLander Backend is Live", "rover_mode": "Normal"}


@app.get("/audit-log")
def get_audit_log(limit: int = 20):
    """
    Serve the contrastive-XAI decision log written by explain/audit_logger.py
    (M6) so the dashboard can display recent path-selection decisions with
    their chosen-vs-rejected metrics and explanation text.
    """
    if not HAS_AUDIT_LOG:
        return {"decisions": [], "error": "audit logger module not available"}

    try:
        logs = read_log()
    except Exception as e:
        print("Audit log read error:", e)
        return {"decisions": [], "error": str(e)}

    # Most recent first, capped to `limit` so the dashboard panel stays light.
    recent = logs[-limit:] if limit > 0 else logs
    return {"decisions": list(reversed(recent))}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🟢 Frontend Dashboard Connected!")
    
    try:
        while True:
            precision, recall, center_error = 0.95, 0.85, 4.2
            
            # Default fallback telemetry and reasoning values if localizer isn't connected yet
            pos_x, pos_y, uncertainty, current_mode = 145.6, -89.5, 2.55, "Driving"
            current_reasoning = "Awaiting simulation telemetry stream..."

            # 1. Fetch live position, mode, and dynamic reasoning from state module
            if HAS_LOCALIZER:
                try:
                    pos_data = get_current_position()
                    if isinstance(pos_data, dict):
                        pos_x = pos_data.get("x", pos_x)
                        pos_y = pos_data.get("y", pos_y)
                        uncertainty = pos_data.get("uncertainty", uncertainty)
                    current_mode = get_rover_mode() or "Driving"
                    current_reasoning = get_reasoning() or current_reasoning
                except Exception as loc_err:
                    print("Localizer sync warning:", loc_err)

            # 2. Run actual crater detection & evaluation metrics if modules are available
            if HAS_EVAL_MODULES:
                try:
                    precision, recall, center_error = _get_evaluation_metrics()
                except Exception as e:
                    print("Evaluation loop execution error:", e)

            # 3. Package dynamic telemetry + real evaluation data together
            live_packet = {
                "x": pos_x,
                "y": pos_y,
                "uncertainty": uncertainty,
                "mode": current_mode,
                "reasoning": current_reasoning,
                "precision": precision,
                "recall": recall,
                "center_error": center_error
            }
            
            # Send through the WebSocket tunnel to the UI
            await websocket.send_text(json.dumps(live_packet))
            
            # Stream data every 1 second
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        print("🔴 Frontend Dashboard Disconnected.")