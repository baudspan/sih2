

```markdown
# SurakshaLander: Autonomous Lunar Navigation & HUD

SurakshaLander is an integrated simulation and telemetry system designed for autonomous lunar rover navigation, perception, and re-localization using real Digital Elevation Model (DEM) data and crater databases.

---

## System Architecture

* **Backend (`/backend`)**: FastAPI server streaming real-time telemetry and crater evaluation metrics via WebSockets.
* **Frontend (`/dashboard`)**: React and Vite-powered command-center HUD for live mission tracking and spatial visualization.
* **Terrain & Data (`/terrain`)**: Terrain preprocessing pipeline, slope/roughness matrix generation, and crater catalog mapping for M2 (Localization) and M4 (Planning).
* **Simulation & Core (`/simulation`, `/src`, `/localization`, `/navigation`)**: Orchestrates rover movement, local terrain patching, OpenCV-based crater matching, and path planning.

---

## Prerequisites

* **Python 3.10 or higher** installed on your system.
* **Node.js and npm** (v16+) installed for the React dashboard.

---

## Installation & Setup

### 1. Clone or Download the Repository
Open your terminal inside the root project directory.

### 2. Install Python Dependencies
Install the required packages for spatial processing, computer vision, and backend APIs:
```bash
pip install fastapi uvicorn numpy scipy pandas opencv-python rasterio

```

### 3. Install Frontend Dependencies

Navigate into the dashboard directory and install node modules:

```bash
cd dashboard
npm install
cd ..

```

### 4. Setup Data Assets & M1 Pipeline Outputs

The large `.tif`/`.tiff` elevation files and raw `.csv` datasets are excluded from git via `.gitignore` due to file size limits. You must either place pre-generated outputs into your data folders or build them using the pipeline steps below.

**Required Directory Structure & Outputs:**

* `data/dem/` — Raw DEM elevation tile (e.g., `Lunar_MapE.tif` or `south_p_20m.tiff`)
* `data/processed/slope.tif` — Terrain slope in degrees (consumed by M4)
* `data/processed/roughness.tif` — Elevation standard deviation in meters (consumed by M4)
* `crater_db/crater_db.sqlite` — Top South Pole craters catalog (consumed by M2)

*(Optional pipeline execution to build data locally from raw NASA/Robbins sources)*:

```bash
python terrain/dem_loader.py        # sanity check — prints DEM shape/bounds
python terrain/slope.py            # generates data/processed/slope.tif
python terrain/roughness.py        # generates data/processed/roughness.tif
python terrain/build_crater_db.py  # generates crater_db/crater_db.sqlite

```

---

## Running the Application

To run the complete end-to-end system, open **three separate terminal windows** from the root project directory.

### Terminal 1: Start the FastAPI Backend

```bash
uvicorn backend.api:app --reload --port 8000

```

### Terminal 2: Start the React Frontend Dashboard

*(Note: If PowerShell blocks script execution, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first)*

```bash
cd dashboard
npm run dev

```

*(Open the local Vite link, usually `http://localhost:5173`, in your browser to view the HUD).*

### Terminal 3: Start the Rover Simulation Orchestrator

```bash
python -m simulation.main

```

---

## Technical Notes on Coordinates & Projection

* **Region Covered:** Lunar South Pole, approximately 80°S–90°S, polar stereographic projection, ~608km × 608km tile, 20m/pixel resolution.
* **Coordinate Mapping:** The crater database stores plain lat/lon (spherical coordinates), while the DEM, slope, and roughness rasters use polar stereographic **meters**. A spatial conversion script (`localization/coords.py`) bridges matching between raster pixels and catalog coordinates.

```

```