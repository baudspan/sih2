import sys
import os
import time
import numpy as np

# Connect to root Code folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.localizer import Localizer
from navigation.mission_planner import MissionPlanner
from src.perception.detector import detect_craters
from terrain.dem_loader import load_dem
from localization.state import update_telemetry
from explain.generate_explanation import generate_contrastive_explanation
from explain.audit_logger import log_decision


def crop_local_patch(dem_map, center_x_m, center_y_m, patch_size_px=600, resolution_m=20.0):
    """
    Extracts a local sub-window around the rover's meter coordinates
    to prevent OpenCV OutOfMemory crashes on giant 30k x 30k maps.
    """
    h, w = dem_map.shape[:2]
    center_row = int(h / 2 - (center_y_m / resolution_m))
    center_col = int(w / 2 + (center_x_m / resolution_m))

    half_size = patch_size_px // 2
    r_start = max(0, center_row - half_size)
    r_end = min(h, center_row + half_size)
    c_start = max(0, center_col - half_size)
    c_end = min(w, center_col + half_size)

    patch = dem_map[r_start:r_end, c_start:c_end]

    if patch.shape[0] < patch_size_px or patch.shape[1] < patch_size_px:
        padded = np.zeros((patch_size_px, patch_size_px), dtype=dem_map.dtype)
        padded[:patch.shape[0], :patch.shape[1]] = patch
        return padded
    return patch


def patch_pixels_to_world(detections, dem_map_shape, center_x_m, center_y_m,
                          patch_size_px=600, resolution_m=20.0):
    """Convert detector pixels in the centered patch into DEM world meters."""
    height, width = dem_map_shape[:2]
    center_row = int(height / 2 - (center_y_m / resolution_m))
    center_col = int(width / 2 + (center_x_m / resolution_m))
    half_size = patch_size_px // 2
    row_start = max(0, center_row - half_size)
    col_start = max(0, center_col - half_size)

    converted = []
    for crater in detections:
        full_row = row_start + crater["y"]
        full_col = col_start + crater["x"]
        converted.append({
            **crater,
            "x": (full_col - width / 2) * resolution_m,
            "y": (height / 2 - full_row) * resolution_m,
            "radius": crater["radius"] * resolution_m,
        })
    return converted


def catalog_fallback_craters(landmarks, center_x_m, center_y_m, minimum=3):
    """Return nearest catalog landmarks when the DEM patch has no visible craters."""
    nearby = sorted(
        landmarks,
        key=lambda crater: (crater["x"] - center_x_m) ** 2
        + (crater["y"] - center_y_m) ** 2,
    )
    return [
        {"x": crater["x"], "y": crater["y"], "radius": crater["diameter"] / 2}
        for crater in nearby[:minimum]
    ]


def downsampled_path_to_world(path, transform, downsample_factor=10):
    """
    The planner runs on a downsampled DEM array (dem_map[::10, ::10]), so
    every (col, row) it returns is a downsampled-pixel index, NOT a
    real-world coordinate. compute_path_metrics() needs real-world (x, y)
    to sample slope.tif/roughness.tif correctly via rasterio.

    This converts each path point back to world coordinates using the
    DEM's own affine transform, undoing the downsampling stride.
    """
    world_path = []
    for col, row in path:
        full_col = col * downsample_factor
        full_row = row * downsample_factor
        world_x, world_y = transform * (full_col, full_row)
        world_path.append((world_x, world_y))
    return world_path


def start_orchestrator():
    print("SurakshaLander Orchestrator Started")

    print("Loading M1 DEM map (full-resolution real tile, this will take a while)...")
    dem_map, dem_meta, dem_pixel_size = load_dem("data/Lunar_Map.tiff")
    dem_transform = dem_meta["transform"]

    print(f"Initializing modules with DEM shape: {dem_map.shape}...")
    localizer = Localizer()

    downsample_factor = 10
    downsampled_map = dem_map[::downsample_factor, ::downsample_factor] if dem_map.shape[0] > 1000 else dem_map
    planner = MissionPlanner(downsampled_map)

    rover_running = True
    goal_pos = (500.0, 480.0)
    velocity_m_s = 2.0
    dt = 1.0

    while rover_running:
        odometry = {"velocity": velocity_m_s, "angular_velocity": 0.0}
        localizer.predict(dt, odometry)

        telemetry = localizer.get_telemetry()
        current_pos = [telemetry["x"], telemetry["y"]]
        uncertainty = telemetry["uncertainty"]
        level = localizer.get_uncertainty_level()

        mode = "Driving"
        reasoning = f"Rover cruising at coordinates ({current_pos[0]:.1f}, {current_pos[1]:.1f}). Terrain nominal."

        if level == "caution":
            mode = "Caution"
            reasoning = f"CAUTION MODE: uncertainty ({uncertainty:.1f}m) crossed the 3m safety margin."

        elif level == "re_localizing":
            mode = "Relocalizing"
            print(f"RE-LOCALIZING TRIGGERED ({uncertainty:.1f}m > 5m). Cropping local terrain patch...")

            local_patch = crop_local_patch(dem_map, current_pos[0], current_pos[1], patch_size_px=600)
            detected_craters = detect_craters(local_patch)
            detected_craters = patch_pixels_to_world(
                detected_craters,
                dem_map.shape,
                current_pos[0],
                current_pos[1],
            )
            if len(detected_craters) < 3:
                detected_craters = catalog_fallback_craters(
                    localizer.landmark_db,
                    current_pos[0],
                    current_pos[1],
                )
                print("   -> DEM patch has fewer than 3 visible craters; using catalog landmarks for simulation recovery.")
            print(f"   -> Detected {len(detected_craters)} local craters.")

            try:
                corrected = localizer.correct(detected_craters)
                telemetry = localizer.get_telemetry()
                current_pos = [telemetry["x"], telemetry["y"]]
                uncertainty = telemetry["uncertainty"]
                print(f"   -> Correction {'succeeded' if corrected else 'failed'}. "
                      f"Position: {current_pos} | Uncertainty: {uncertainty:.2f}m")
            except Exception as e:
                print(f"   -> Localizer error during correct(): {e}")

            try:
                start_px = (
                    int(current_pos[0] / dem_pixel_size[0] / downsample_factor),
                    int(current_pos[1] / dem_pixel_size[1] / downsample_factor),
                )
                goal_px = (
                    int(goal_pos[0] / downsample_factor),
                    int(goal_pos[1] / downsample_factor),
                )

                path_a_px, xai_a = planner.plan_route(start_px, goal_px, uncertainty)
                path_b_px, xai_b = planner.plan_route(start_px, goal_px, 0.0)

                path_a_world = downsampled_path_to_world(path_a_px, dem_transform, downsample_factor)
                path_b_world = downsampled_path_to_world(path_b_px, dem_transform, downsample_factor)

                result = generate_contrastive_explanation(
                    path_a_world, path_b_world, telemetry, telemetry
                )
                reasoning = result["explanation"]

                log_decision(
                    chosen_path=path_a_world,
                    rejected_path=path_b_world,
                    metrics_a=result["metrics_a"],
                    metrics_b=result["metrics_b"],
                    explanation=result["explanation"],
                )
            except Exception as e:
                reasoning = f"Route sustained. Explanation engine notice: {e}"

        update_telemetry(current_pos[0], current_pos[1], uncertainty, mode, reasoning)
        print(f"Rover at [{current_pos[0]:.1f}, {current_pos[1]:.1f}] | Uncertainty: {uncertainty:.1f}m | Mode: {mode}")

        time.sleep(1.0)


if __name__ == "__main__":
    start_orchestrator()
