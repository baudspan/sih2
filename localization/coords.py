"""
coords.py — M2 Localization
Converts crater lat/lon (from M1's crater_db.sqlite, spherical degrees)
into local x/y meters, using a polar stereographic projection centered
on the lunar South Pole (matches M1's DEM/slope/roughness projection).
"""

import math

# Moon's mean radius in meters (IAU/lunar reference value)
MOON_RADIUS_M = 1_737_400.0

# Local origin, in (lat, lon) degrees — the point that maps to local (0, 0).
# NOTE: this is a placeholder assumption (rover start position / tile center).
# Confirm with M4/M5 before this is treated as final — must match across modules.
ORIGIN_LAT = -90.0
ORIGIN_LON = 0.0


def _stereographic_xy(lat_deg, lon_deg, origin_lat_deg, origin_lon_deg):
    """
    Forward polar stereographic projection (south-polar case).
    Returns (x, y) in meters relative to the given origin.
    """
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    lat0 = math.radians(origin_lat_deg)
    lon0 = math.radians(origin_lon_deg)

    # South polar stereographic: k is the scale factor at the given latitude
    k = (2 * MOON_RADIUS_M) / (1 + math.sin(lat0) * math.sin(lat)
                               + math.cos(lat0) * math.cos(lat) * math.cos(lon - lon0))

    x = k * math.cos(lat) * math.sin(lon - lon0)
    y = k * (math.cos(lat0) * math.sin(lat)
             - math.sin(lat0) * math.cos(lat) * math.cos(lon - lon0))

    return x, y


def latlon_to_local_xy(lat_deg, lon_deg):
    """
    Public function: crater (lat, lon) in degrees -> local (x, y) in meters,
    relative to ORIGIN_LAT/ORIGIN_LON.
    """
    return _stereographic_xy(lat_deg, lon_deg, ORIGIN_LAT, ORIGIN_LON)


if __name__ == "__main__":
    # Quick sanity check against a few known points
    test_points = [
        (-85.0, 0.0),    # should be ~ (0, 0) — it's the origin itself
        (-84.0, 0.0),    # ~1 degree of latitude away -> should be tens of km
        (-85.0, 90.0),   # same latitude, 90 degrees around -> nonzero x, ~0 y
    ]
    for lat, lon in test_points:
        x, y = latlon_to_local_xy(lat, lon)
        print(f"lat={lat}, lon={lon}  ->  x={x:.1f} m, y={y:.1f} m")