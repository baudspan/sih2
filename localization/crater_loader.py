"""
crater_loader.py — M2 Localization
Loads the real 100 crater landmarks from M1's SQLite database,
converts their lat/lon to local x/y meters (using coords.py),
and returns a clean list ready for RANSAC matching in correct().
"""

import sqlite3
import os
from pathlib import Path

# Import your coordinate conversion function from the same folder
from .coords import latlon_to_local_xy


def load_craters(db_path=None):
    if db_path is None:
        base_dir = Path(__file__).resolve().parent  # Code/localization/
        
        # 1. Look in your dedicated crater_db folder: Code/crater_db/crater_db.sqlite (PRIORITY)
        primary_path = base_dir.parent / "crater_db" / "crater_db.sqlite"
        
        # 2. Look in the root data folder: Code/data/crater_db.sqlite
        local_path = base_dir.parent / "data" / "crater_db.sqlite"
        
        # 3. Look in the terrain folder: Code/terrain/crater_db.sqlite
        upstream_path = base_dir.parent / "terrain" / "crater_db.sqlite"

        # 4. Fallback stub
        stub_path = base_dir / "stub_data" / "crater_db.sqlite"

        # Check paths in order of priority
        if os.path.exists(primary_path):
            db_path = str(primary_path)
            print(f"[crater_loader] Using primary DB: {db_path}")
        elif os.path.exists(upstream_path):
            db_path = str(upstream_path)
            print(f"[crater_loader] Using M1's live upstream DB: {db_path}")
        elif os.path.exists(local_path):
            db_path = str(local_path)
            print(f"[crater_loader] Using local DB copy: {db_path}")
        elif os.path.exists(stub_path):
            db_path = str(stub_path)
            print(f"[crater_loader] WARNING: falling back to stub_data copy "
                  f"(no upstream/local DB found): {db_path}")
        else:
            raise FileNotFoundError(
                f"Crater database not found.\n"
                f"Tried:\n"
                f"  - {primary_path}\n"
                f"  - {upstream_path}\n"
                f"  - {local_path}\n"
                f"  - {stub_path}\n"
                f"Please place crater_db.sqlite in one of these locations."
            )

    # Connect to SQLite and fetch top 100 craters
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Using the exact column names provided in your schema
    cursor.execute("""
    SELECT 
        CRATER_ID,
        LAT_CIRC_IMG,
        LON_CIRC_IMG,
        DIAM_CIRC_IMG
    FROM craters          -- ← Changed from 'crater_db' to 'craters'
    WHERE LAT_CIRC_IMG IS NOT NULL 
      AND LON_CIRC_IMG IS NOT NULL
    LIMIT 100
    """)

    rows = cursor.fetchall()
    conn.close()

    # Convert each crater to local x/y coordinates
    crater_list = []
    for row in rows:
        crater_id, lat, lon, diameter = row

        # Skip if essential data is missing
        if lat is None or lon is None:
            continue

        # Convert spherical lat/lon (degrees) to local meters
        x_m, y_m = latlon_to_local_xy(lat, lon)

        # Diameter is stored in the DB; if None, default to 0.0
        diam_m = float(diameter) if diameter is not None else 0.0

        crater_list.append({
            "id": str(crater_id),
            "x": x_m,
            "y": y_m,
            "diameter": diam_m
        })

    return crater_list


# ----------------------------------------------------------------------
# Quick test / sanity check
if __name__ == "__main__":
    try:
        craters = load_craters()
        print(f"✅ Successfully loaded {len(craters)} craters.")
        
        if craters:
            print("\n📍 First 5 craters in local meters:")
            print("-" * 50)
            for i, c in enumerate(craters[:5]):
                print(f"  [{i+1}] ID: {c['id']}, "
                      f"x: {c['x']:.2f}m, "
                      f"y: {c['y']:.2f}m, "
                      f"diameter: {c['diameter']:.2f}m")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("  1. Make sure M1 has generated crater_db.sqlite.")
        print("  2. If the database is elsewhere, call load_craters('/your/path/db.sqlite')")
        print("  3. Check that coords.py is in the same folder.")