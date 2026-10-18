import os
import sys
from typing import Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ee

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gee_auth import init_ee, PROJECT_ID
from classify import (
    get_s2_composite,
    load_training_polygons,
    train_and_classify,
    ROI_COORDS,
    EE_TRAINING_ASSET,
    FEATURE_BANDS
)

app = FastAPI(
    title="AgriSat-TN API",
    description="Earth Engine Real-Data Backend for Sentinel-2 Crop & Parcel Classification",
    version="2.0.0"
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for models by parameters
MODEL_CACHE: Dict[str, Any] = {}

def get_data_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

@app.on_event("startup")
def startup_event():
    success = init_ee(PROJECT_ID)
    if not success:
        print(f"[ERROR] Earth Engine initialization failed for project {PROJECT_ID}")
    else:
        print(f"[READY] Earth Engine initialized successfully on FastAPI startup.")

def get_trained_model(year: int = 2025, cloud_threshold: float = 20.0):
    cache_key = f"{year}_{cloud_threshold}"
    if cache_key in MODEL_CACHE:
        return MODEL_CACHE[cache_key]

    # Load real training polygons (local data/ or GEE asset)
    try:
        fc = load_training_polygons(get_data_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Training polygons not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing training polygons: {str(e)}")

    img, roi = get_s2_composite(year=year, cloud_threshold=cloud_threshold, roi_coords=ROI_COORDS)
    
    try:
        classified, conf_matrix, overall_acc, kappa = train_and_classify(img, roi, fc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to train classifier on real data: {str(e)}")

    result = {
        "img": img,
        "roi": roi,
        "classified": classified,
        "conf_matrix": conf_matrix,
        "overall_accuracy": overall_acc,
        "kappa": kappa
    }
    MODEL_CACHE[cache_key] = result
    return result

@app.get("/")
def read_root():
    return {
        "message": "AgriSat-TN Real Data API is online",
        "project": PROJECT_ID,
        "roi": ROI_COORDS,
        "asset": EE_TRAINING_ASSET
    }

@app.get("/api/debug")
def debug_training_polygons():
    """
    Returns the number of training features per class from the real dataset.
    """
    try:
        fc = load_training_polygons(get_data_dir())
        total = fc.size().getInfo()

        # Count features per class (0: paddy, 1: banana, 2: other, 3: water)
        class_counts = {}
        class_names = {0: "paddy", 1: "banana", 2: "other", 3: "water"}

        for cid, cname in class_names.items():
            count = fc.filter(ee.Filter.eq("class", cid)).size().getInfo()
            class_counts[cname] = count

        return {
            "status": "success",
            "total_features": total,
            "counts_per_class": class_counts,
            "source": "Local data/*.geojson or GEE asset"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Training polygons not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug inspection failed: {str(e)}")

@app.get("/api/tiles")
def get_tiles(
    year: int = Query(2025, description="Satellite image year"),
    cloud: float = Query(20.0, description="Max cloud cover percentage")
):
    """
    Returns Earth Engine tile URL templates (from getMapId) for RGB and classified layers.
    """
    model_data = get_trained_model(year, cloud)
    img = model_data["img"]
    classified = model_data["classified"]

    try:
        rgb_vis = {
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "gamma": 1.4
        }
        # Palette: 0 = Paddy (Green), 1 = Banana (Yellow), 2 = Other (Violet), 3 = Water (Blue)
        class_vis = {
            "min": 0,
            "max": 3,
            "palette": ["#008000", "#FFFF00", "#8A2BE2", "#0000FF"]
        }

        rgb_map_id = img.getMapId(rgb_vis)
        class_map_id = classified.getMapId(class_vis)

        return {
            "year": year,
            "cloud_threshold": cloud,
            "rgb_tile_url": rgb_map_id["tile_fetcher"].url_format,
            "classified_tile_url": class_map_id["tile_fetcher"].url_format
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate map tiles: {str(e)}")

@app.get("/api/stats")
def get_stats(
    year: int = Query(2025, description="Satellite image year"),
    cloud: float = Query(20.0, description="Max cloud cover percentage")
):
    """
    Returns area in hectares for each class computed via ee.Image.pixelArea().
    """
    model_data = get_trained_model(year, cloud)
    classified = model_data["classified"]
    roi = model_data["roi"]

    try:
        pixel_area = ee.Image.pixelArea()
        area_img = pixel_area.addBands(classified.rename("class"))

        area_stats = area_img.reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=roi,
            scale=10,
            maxPixels=1e9
        ).getInfo()

        area_dict = {"paddy": 0.0, "banana": 0.0, "other": 0.0, "water": 0.0}
        id_to_key = {0: "paddy", 1: "banana", 2: "other", 3: "water"}

        groups = area_stats.get("groups", [])
        for g in groups:
            c_idx = int(g.get("class", -1))
            sqm = g.get("sum", 0.0)
            ha = round(sqm / 10000.0, 2)
            if c_idx in id_to_key:
                area_dict[id_to_key[c_idx]] = ha

        total_ha = round(sum(area_dict.values()), 2)

        return {
            "year": year,
            "cloud_threshold": cloud,
            "classes": area_dict,
            "total_hectares": total_ha,
            "total_sq_km": round(total_ha / 100.0, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate statistics: {str(e)}")

@app.get("/api/inspect")
def inspect_pixel(
    lat: float = Query(..., description="Latitude of clicked/hovered point"),
    lon: float = Query(..., description="Longitude of clicked/hovered point"),
    year: int = Query(2025, description="Year"),
    cloud: float = Query(20.0, description="Cloud threshold")
):
    """
    Inspects a specific geographic point:
    Returns the predicted crop/landcover class and contiguous parcel area in hectares.
    """
    try:
        model_data = get_trained_model(year, cloud)
        classified = model_data["classified"]
        roi = model_data["roi"]

        point = ee.Geometry.Point([lon, lat])
        
        # Check if point is inside study area
        inside = roi.contains(point).getInfo()
        if not inside:
            return {"inside": False, "message": "Location outside Ambasamudram study area"}

        # Extract class at point
        val_dict = classified.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=10
        ).getInfo()

        raw_val = val_dict.get("classification")
        if raw_val is None:
            return {"inside": False, "message": "No data at this coordinate"}

        class_id = int(raw_val)
        class_names = {0: "Paddy", 1: "Banana", 2: "Other", 3: "Water"}
        class_colors = {0: "#008000", 1: "#FFFF00", 2: "#8A2BE2", 3: "#0000FF"}

        # Contiguous patch area calculation:
        # Connected pixels of the same crop class to determine the parcel size
        same_class_mask = classified.eq(class_id)
        connected = same_class_mask.connectedPixelCount(maxSize=256, eightConnected=True)
        # Each Sentinel-2 pixel is 10m x 10m = 100 m² = 0.01 hectare
        pixel_count_dict = connected.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=10
        ).getInfo()

        px_count = pixel_count_dict.get("classification", 1) or 1
        parcel_ha = round(px_count * 0.01, 2)

        return {
            "inside": True,
            "lat": lat,
            "lon": lon,
            "class_id": class_id,
            "class_name": class_names.get(class_id, "Unknown"),
            "color": class_colors.get(class_id, "#808080"),
            "parcel_hectares": parcel_ha
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inspection failed: {str(e)}")

@app.get("/api/accuracy")
def get_accuracy(
    year: int = Query(2025, description="Satellite image year"),
    cloud: float = Query(20.0, description="Max cloud cover percentage")
):
    """
    Returns real overall accuracy, kappa coefficient, and confusion matrix from the 30% test split.
    """
    model_data = get_trained_model(year, cloud)
    return {
        "overall_accuracy": round(model_data["overall_accuracy"], 4),
        "kappa": round(model_data["kappa"], 4),
        "confusion_matrix": model_data["conf_matrix"],
        "classes": ["paddy", "banana", "other", "water"]
    }
