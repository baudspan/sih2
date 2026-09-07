import rasterio
import numpy as np

def load_dem(path="../data/dem/south_pole_20m.tiff"):
    """
    Loads a DEM GeoTIFF and returns the elevation array + metadata.
    """
    with rasterio.open(path) as src:
        elevation = src.read(1).astype(np.float32)  # band 1 = elevation
        meta = src.meta.copy()
        bounds = src.bounds
        pixel_size = src.res  # (x_res, y_res) in meters

    # Handle common nodata sentinel values in LOLA products
    nodata_val = meta.get("nodata")
    if nodata_val is not None:
        elevation[elevation == nodata_val] = np.nan

    print(f"Loaded DEM: shape={elevation.shape}, pixel_size={pixel_size}, bounds={bounds}")
    return elevation, meta, pixel_size


if __name__ == "__main__":
    elevation, meta, pixel_size = load_dem()
    print("Min elevation:", np.nanmin(elevation))
    print("Max elevation:", np.nanmax(elevation))