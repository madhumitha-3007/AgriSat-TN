"""
Connection test for Google Earth Engine.
Loads a Sentinel-2 median composite over the study area and prints band names.
"""
import ee
from gee_auth import init_ee

# Study area: [min_lon, min_lat, max_lon, max_lat]
ROI_COORDS = [77.30, 8.60, 77.60, 8.80]

def test_connection():
    if not init_ee():
        print("[ERROR] Earth Engine initialization aborted.")
        return False

    try:
        roi = ee.Geometry.Rectangle(ROI_COORDS)
        s2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(roi)
            .filterDate("2025-01-01", "2025-12-31")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        )
        
        count = s2.size().getInfo()
        print(f"[INFO] Number of Sentinel-2 scenes found (2025, <20% cloud): {count}")

        composite = s2.median().clip(roi)
        band_names = composite.bandNames().getInfo()
        print(f"[SUCCESS] Connection confirmed! Retrieved composite bands: {band_names}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to query Sentinel-2 collection: {e}")
        return False

if __name__ == "__main__":
    test_connection()
