import streamlit as st
import ee
import geemap.foliumap as geemap
from streamlit_folium import folium_static

from gee_auth import init_ee
from classify import get_s2_composite, load_training_polygons, train_and_classify, DEFAULT_ROI

st.set_page_config(
    page_title="AgriSat-TN | Crop & Land Cover Classification",
    layout="wide"
)

st.title("🌾 AgriSat-TN: Crop & Parcel Classification")
st.markdown(
    "Satellite-based classification of **Paddy vs. Banana** and land parcels in "
    "**Ambasamudram and Cheranmahadevi taluks, Tirunelveli, Tamil Nadu** using Sentinel-2 and Earth Engine."
)

# Sidebar controls
st.sidebar.header("Parameters & Filters")
year = st.sidebar.selectbox("Observation Year", options=[2025, 2024, 2023], index=0)
cloud_cover = st.sidebar.slider("Max Cloud Cover (%)", min_value=1.0, max_value=50.0, value=20.0, step=1.0)
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Class Schema & Colors:**
    - 🟩 **Paddy**: `#008000` (Green)
    - 🟨 **Banana**: `#FFFF00` (Yellow)
    - ⬜ **Other**: `#808080` (Gray)
    - 🟦 **Water**: `#0000FF` (Blue)
    """
)

# Initialize Earth Engine
with st.spinner("Connecting to Google Earth Engine..."):
    connected = init_ee()

if not connected:
    st.error("Could not authenticate or connect to Google Earth Engine. Please run `python gee_auth.py` in your terminal to authenticate.")
    st.stop()

# Generate composite and classification
with st.spinner(f"Fetching Sentinel-2 ({year}) imagery and running classification..."):
    try:
        composite, roi = get_s2_composite(year=year, cloud_threshold=cloud_cover)
        training_fc = load_training_polygons()
        classified = train_and_classify(composite, roi, training_fc)
    except Exception as e:
        st.error(f"Error during classification: {e}")
        st.stop()

# Layout: 2 Columns (Map & Metrics)
col_map, col_stats = st.columns([3, 1])

with col_map:
    st.subheader("Satellite & Classification Map")
    # Center map on Ambasamudram / Cheranmahadevi area
    center_lat = (DEFAULT_ROI[1] + DEFAULT_ROI[3]) / 2.0
    center_lon = (DEFAULT_ROI[0] + DEFAULT_ROI[2]) / 2.0
    
    m = geemap.Map(center=[center_lat, center_lon], zoom=12)

    # Sentinel-2 Natural Color RGB
    rgb_vis = {
        "bands": ["B4", "B3", "B2"],
        "min": 0,
        "max": 3000,
        "gamma": 1.4
    }
    m.addLayer(composite, rgb_vis, f"Sentinel-2 RGB ({year})")

    # Classification layer palette: paddy green, banana yellow, other gray, water blue
    class_vis = {
        "min": 0,
        "max": 3,
        "palette": ["#008000", "#FFFF00", "#808080", "#0000FF"]
    }
    m.addLayer(classified, class_vis, "AgriSat Classification")

    # Layer control
    m.add_layer_control()
    folium_static(m, width=900, height=580)

with col_stats:
    st.subheader("Area Statistics")
    st.caption("Calculated in Hectares (ha)")
    
    with st.spinner("Calculating pixel areas..."):
        try:
            # Area calculation using ee.Image.pixelArea() in square meters
            pixel_area = ee.Image.pixelArea()
            area_img = pixel_area.addBands(classified.rename("class"))
            
            # Reduce region by class
            area_stats = area_img.reduceRegion(
                reducer=ee.Reducer.sum().group(
                    groupField=1,
                    groupName="class"
                ),
                geometry=roi,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            class_map = {
                0: ("Paddy", "🟩", "#008000"),
                1: ("Banana", "🟨", "#FFFF00"),
                2: ("Other", "⬜", "#808080"),
                3: ("Water", "🟦", "#0000FF")
            }
            
            area_dict = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
            groups = area_stats.get("groups", [])
            for g in groups:
                c_idx = int(g.get("class", -1))
                sqm = g.get("sum", 0.0)
                hectares = sqm / 10000.0
                if c_idx in area_dict:
                    area_dict[c_idx] = hectares

            for c_id, (label, emoji, _) in class_map.items():
                ha = area_dict[c_id]
                st.metric(label=f"{emoji} {label}", value=f"{ha:,.2f} ha")

            total_ha = sum(area_dict.values())
            st.markdown(f"**Total Area:** `{total_ha:,.2f} ha` (~`{total_ha/100:,.2f} km²`)")
        except Exception as e:
            st.warning(f"Could not compute real-time area statistics: {e}")
