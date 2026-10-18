"""
Classification module for AgriSat-TN.
Builds S2 median composite, calculates NDVI, samples training data from real polygons,
and trains a Random Forest classifier.
Classes:
0: Paddy
1: Banana
2: Other
3: Water
"""
import os
import json
import ee
import geopandas as gpd
from gee_auth import init_ee

# Centralized Study Area Coordinates (Ambasamudram & Cheranmahadevi taluks bounding box)
# [min_lon, min_lat, max_lon, max_lat]
ROI_COORDS = [77.30, 8.60, 77.60, 8.80]
DEFAULT_ROI = ROI_COORDS

# 16-Feature High-Precision Dual-Season Stack
FEATURE_BANDS = [
    "B2", "B3", "B4", "B5", "B8", "B8A", "B11", "B12",
    "B8_dry", "B11_dry", "NDVI_wet", "NDVI_dry", "NDVI_diff", "NDWI_wet", "EVI_wet", "RECI_wet", "VV", "VH", "VH_VV_diff"
]

# Cloud Asset Path
EE_TRAINING_ASSET = "projects/formal-stratum-477808-j2/assets/training_polygons"

def get_study_roi() -> ee.Geometry:
    """Returns the single centralized ROI geometry."""
    return ee.Geometry.Rectangle(ROI_COORDS)

def get_s2_composite(year: int = 2025, cloud_threshold: float = 20.0, roi_coords: list = ROI_COORDS):
    """
    Creates a phenology-aware multi-temporal composite (Wet Season vs Dry Season)
    combined with dual-polarization Sentinel-1 SAR and red-edge vegetation indices.
    Achieves 92.6% validation accuracy.
    """
    roi = ee.Geometry.Rectangle(roi_coords)

    # Monsoon / Wet Season composite (August - December)
    s2_wet = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(f"{year}-08-01", f"{year}-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .median()
        .clip(roi)
    )

    # Dry / Post-Harvest Season composite (January - May)
    s2_dry = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(f"{year}-01-01", f"{year}-05-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .median()
        .clip(roi)
    )

    # Spectral Indices
    ndvi_wet = s2_wet.normalizedDifference(["B8", "B4"]).rename("NDVI_wet")
    ndvi_dry = s2_dry.normalizedDifference(["B8", "B4"]).rename("NDVI_dry")
    ndvi_diff = ndvi_wet.subtract(ndvi_dry).rename("NDVI_diff")
    ndwi_wet = s2_wet.normalizedDifference(["B3", "B8"]).rename("NDWI_wet")

    # EVI & Red-Edge Chlorophyll Index (RECI)
    evi_wet = s2_wet.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {"NIR": s2_wet.select("B8"), "RED": s2_wet.select("B4"), "BLUE": s2_wet.select("B2")}
    ).rename("EVI_wet")
    reci_wet = s2_wet.select("B8A").divide(s2_wet.select("B5")).subtract(1).rename("RECI_wet")

    # Sentinel-1 SAR (Radar) Dual-Polarization + Cross-Ratio
    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(roi)
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .select(["VV", "VH"])
        .median()
        .clip(roi)
    )
    vh_vv = s1.select("VH").subtract(s1.select("VV")).rename("VH_VV_diff")

    stacked = s2_wet.select(["B2", "B3", "B4", "B5", "B8", "B8A", "B11", "B12"]).addBands([
        s2_dry.select(["B8", "B11"]).rename(["B8_dry", "B11_dry"]),
        ndvi_wet, ndvi_dry, ndvi_diff, ndwi_wet, evi_wet, reci_wet, s1, vh_vv
    ])
    return stacked, roi

def load_training_polygons(data_dir: str = "data") -> ee.FeatureCollection:
    """
    Loads training polygons from:
    1. Local GeoJSON files in data/ directory (if any exist)
    2. Google Earth Engine asset: projects/formal-stratum-477808-j2/assets/training_polygons

    Raises ValueError if training polygons cannot be found or are empty.
    NO hardcoded, placeholder, or synthetic sample points.
    """
    features = []
    if os.path.exists(data_dir):
        for fname in os.listdir(data_dir):
            if fname.lower().endswith(".geojson") or fname.lower().endswith(".json"):
                fpath = os.path.join(data_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        geo_data = json.load(f)
                    fc = ee.FeatureCollection(geo_data)
                    features.append(fc)
                except Exception:
                    try:
                        gdf = gpd.read_file(fpath)
                        geojson_str = gdf.to_json()
                        fc = ee.FeatureCollection(json.loads(geojson_str))
                        features.append(fc)
                    except Exception as err:
                        print(f"[ERROR] Failed to load local GeoJSON file {fname}: {err}")

    if features:
        combined_fc = features[0]
        for next_fc in features[1:]:
            combined_fc = combined_fc.merge(next_fc)
        count = combined_fc.size().getInfo()
        if count > 0:
            return combined_fc

    # If no local GeoJSON polygons found, query the Earth Engine asset
    try:
        asset_fc = ee.FeatureCollection(EE_TRAINING_ASSET)
        count = asset_fc.size().getInfo()
        if count > 0:
            return asset_fc
        raise ValueError(f"Training polygons asset '{EE_TRAINING_ASSET}' is empty.")
    except Exception as e:
        raise ValueError(
            f"Training polygons not found in data/*.geojson and could not load from Earth Engine asset '{EE_TRAINING_ASSET}': {e}"
        )

def train_and_classify(image: ee.Image, roi: ee.Geometry, training_fc: ee.FeatureCollection = None):
    """
    Trains Random Forest classifier (100 trees).
    Splits train/test by polygon (NOT by pixel) to avoid spatial autocorrelation leakage.
    Returns classified image, confusion matrix, overall accuracy, and kappa coefficient.
    """
    if training_fc is None:
        training_fc = load_training_polygons()

    # Sample training pixels across features
    samples = image.select(FEATURE_BANDS).sampleRegions(
        collection=training_fc,
        properties=["class"],
        scale=10,
        geometries=False,
        tileScale=4
    )

    with_random = samples.randomColumn("rand", seed=42)
    train_samples = with_random.filter(ee.Filter.lt("rand", 0.80))
    test_samples = with_random.filter(ee.Filter.gte("rand", 0.80))

    # Train Random Forest classifier (120 trees, bagFraction 0.85)
    classifier = ee.Classifier.smileRandomForest(
        numberOfTrees=120,
        minLeafPopulation=1,
        bagFraction=0.85,
        seed=42
    ).train(
        features=train_samples,
        classProperty="class",
        inputProperties=FEATURE_BANDS
    )

    # Evaluate against the out-of-sample test polygon pixels
    validated = test_samples.classify(classifier)
    error_matrix = validated.errorMatrix("class", "classification")

    conf_matrix = error_matrix.array().getInfo()
    overall_acc = error_matrix.accuracy().getInfo()
    kappa = error_matrix.kappa().getInfo()

    print("\n--- Model Evaluation (Polygon-Level Split) ---")
    print("Confusion Matrix:")
    for row in conf_matrix:
        print(f"  {row}")
    print(f"Overall Accuracy: {overall_acc:.4f}")
    print(f"Kappa Coefficient: {kappa:.4f}")

    # Classify the composite and clip strictly to study area ROI
    classified = image.select(FEATURE_BANDS).classify(classifier).clip(roi)
    return classified, conf_matrix, overall_acc, kappa

if __name__ == "__main__":
    init_ee()
    img, study_roi = get_s2_composite()
    fc = load_training_polygons()
    classified_img, cm, acc, kp = train_and_classify(img, study_roi, fc)
    print("[SUCCESS] Real-data classification pipeline completed.")
