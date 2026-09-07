# Changes made this pass

## 1. Label swap (trivial fix)
`dashboard/src/App.jsx` — header `<h1>`/`<h2>` text were swapped. Now:
- `<h1>` = "SURAKSHA LANDER" (big title)
- `<h2>` = "LUNAR TELEMETRY" (subtitle)

## 2. Live 2D map + trajectory trail (items #1 and #3)
`dashboard/src/App.jsx`:
- New `RoverMap` component — plain SVG, no Deck.gl, no new deps.
  - Draws the accumulated position trail as a polyline.
  - Draws a dashed circle around the rover sized to the current
    `uncertainty` value (meters), color-coded by mode (cyan = Driving,
    yellow = Caution, red = Relocalizing).
  - Draws the rover as a glowing marker.
  - Auto-fits its view to whatever the rover has actually covered so far
    (recomputed via `useMemo` off the trail + uncertainty), so it works
    whether the run covers 50m or 5km — nothing hardcoded to the
    `goal_pos = (500, 480)` in `simulation/main.py`.
- Trail is accumulated **client-side**: every WS telemetry packet that
  moves >5cm from the last recorded point gets pushed into a capped
  (400-point) array in React state. This is a no-op change to any
  backend/M2 code — `localization/state.py` and `simulation/main.py`
  are untouched.
- Wired into a new grid row between the existing 3-panel telemetry strip
  and the reasoning terminal panel: map takes 2/3 width, audit trail
  panel takes 1/3 width.

## 3. Audit trail endpoint + panel (item #2)
`backend/api.py`:
- Added a guarded import of `explain.audit_logger.read_log` (same
  fallback pattern as the other optional imports already in the file).
- Added `GET /audit-log?limit=20` — returns
  `{"decisions": [...]}`, most-recent-first, reading directly from
  `explain/decision_log.json` via the existing `read_log()` function
  (that function already existed in `audit_logger.py` — nothing there
  was changed).

`dashboard/src/App.jsx`:
- New `AuditLogPanel` component, polls `/audit-log` every 5s (separate
  from the 1Hz WS stream, since decisions only land on re-localization
  events) and lists each decision's timestamp + explanation text.
- `API_BASE` is derived from `VITE_WS_URL` (`ws://host:8000/ws` →
  `http://host:8000`) so no new env var/build arg is needed in
  `docker-compose.yml` or `dashboard/Dockerfile`.

## Nothing else touched
M2 localizer, M4 planner, M6 explain module, crater_loader, DEM loader,
docker-compose, Dockerfiles — all untouched. `npm run build` in
`dashboard/` passes cleanly with these changes (verified).

---

# Running without Docker (quick local dev loop)

Needs Python 3.11 + GDAL system libs (rasterio dependency) and Node 20.

## 1. System deps (GDAL) — skip if already installed
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y gdal-bin libgdal-dev libgl1 libglib2.0-0
```

## 2. Python env
```bash
cd sih
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Data files
Make sure these exist relative to the repo root (same paths the code
already expects):
- `data/Lunar_Map.tiff` — the DEM GeoTIFF used by `load_dem()`
- `crater_db/crater_db.sqlite` — already in the zip

If you don't have `data/Lunar_Map.tiff` yet, that's a separate M1 data
question — not something this pass touched.

## 4. Run backend + simulator (2 terminals, no shared-volume needed
   locally since both processes share the same filesystem)
```bash
# terminal 1 — API + WebSocket server
cd sih
source .venv/bin/activate
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

# terminal 2 — the orchestrator that actually drives the rover sim
cd sih
source .venv/bin/activate
python simulation/main.py
```
Note: locally you do **not** need to set `TELEMETRY_FILE` — it
defaults to `localization/telemetry.json`, and since both processes run
on the same machine (no containers), they share that file automatically.

## 5. Run the dashboard
```bash
cd sih/dashboard
npm install
npm run dev
```
Vite will print a local URL (usually `http://localhost:5173`). The
dashboard defaults to `ws://localhost:8000/ws` if `VITE_WS_URL` isn't
set, which matches the backend from step 4 — no `.env` needed for pure
local dev.

## 6. Sanity check
- Open the dashboard URL — you should see telemetry updating every ~1s,
  the live map building a trail, and (once the rover crosses the
  uncertainty threshold and re-localizes at least once) an entry
  appearing in the Audit Trail panel.
- `curl http://localhost:8000/audit-log` should return JSON once at
  least one re-localization + explanation has been logged.

---

## 7. 3D terrain and audit-log startup fix

The dashboard's 3D terrain and audit panel were reporting `Failed to fetch`
because port 8000 was serving the outer `sih/backend/api.py` copy. That copy
only defines `/` and `/ws`, so `/terrain-heightmap` and `/audit-log` returned
404 without the CORS headers from the inner application.

The inner `backend/api.py` now:

- Resolves `data/Lunar_Map.tiff` and `crater_db/crater_db.sqlite` from the
  inner `sih` project directory, independent of the terminal's current
  directory.
- Allows both `localhost:5173` and `127.0.0.1:5173` as dashboard origins.
- Uses the same absolute DEM path for the WebSocket evaluation loop.
- Resamples the GeoTIFF while reading it, so the 3D endpoint does not load
  all 924 million source cells into memory before creating a small heightmap.
- Imports the existing `load_craters` function instead of the nonexistent
  `load_craters_from_db`, restoring live crater evaluation in the WebSocket.
- Caches crater evaluation metrics from a 600x600 resampled DEM instead of
  reloading and processing the full 30,400x30,400 raster every WebSocket tick.
  This keeps `/terrain-heightmap` responsive while telemetry is connected.
- Adjusts crater Hough detection to the DEM's 2-20 pixel crater radius range.
- Converts local detector pixels into DEM world-meter coordinates before
  passing them to the localizer.
- Adds an explicit simulation-only catalog fallback when a local DEM patch has
  fewer than three visible craters, allowing uncertainty recovery instead of
  repeatedly failing correction.

Run the backend from the inner project directory so the dashboard reaches the
application that owns both routes:

```powershell
cd C:\Users\prava\OneDrive\Desktop\PROJECTS\SURAKSHALANDER\sih\sih
..\.venv\Scripts\Activate.ps1
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Then run the dashboard from `sih/sih/dashboard` and verify the backend:

```powershell
Invoke-RestMethod http://localhost:8000/
Invoke-RestMethod http://localhost:8000/audit-log
Invoke-RestMethod "http://localhost:8000/terrain-heightmap?grid_size=16"
```

# On the 3D / real DEM request

Given the "severe time pressure" framing and the explicit priority
order you gave (#4 → #1+#3 → #2), I held off on building a 3D terrain
view against the LOLA DEM tile — that's a materially bigger lift
(loading/reprojecting a real GeoTIFF client-side or via a tile
service, a Three.js/Deck.gl terrain mesh, camera controls) than the
SVG 2D map, and the PRD itself already downgraded this from
Deck.gl to "SVG/Canvas 2D is acceptable given time constraints."
The 2D map above satisfies the stated requirement.

If you still want a 3D pass after submission (or have spare time
before the deadline), the realistic path would be: pre-render the
`LDEM_80S_20MPP_ADJ.TIF` you linked into a heightmap-friendly format
(e.g. a downsampled PNG or a `.bin` of floats) offline via `terrain/dem_loader.py`
+ `rasterio`, ship that static asset to the frontend, and render it
with a Three.js `PlaneGeometry` + vertex displacement, with the rover
trail extruded slightly above the mesh. Happy to build that next if
there's time after the current three fixes are confirmed working.
