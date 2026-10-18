# 🌾 AgriGeo (AgriSat-TN): AI-Powered Crop Mapping Platform

[![1st Prize - VIT Mapathon 2026](https://img.shields.io/badge/Award-1st%20Prize%20%7C%20VIT%20Mapathon%202026-gold?style=for-the-badge)](https://github.com/abirami-302/AgriSat-TN)
[![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-API-green?style=for-the-badge&logo=googleearth)](https://earthengine.google.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Leaflet-blue?style=for-the-badge&logo=react)](https://reactjs.org/)

An end-to-end cloud and AI geospatial application designed to accurately identify, classify, and calculate the acreage of **Paddy** (rice) and **Banana** crops across 73,000+ hectares (730 km²) in Tamil Nadu, India.

> 🏆 **Winner of 1st Prize** at the **VIT MAPATHON – Geospatial Mapping Challenge** (SustainAI 2026, VIT Vellore).

---

## 📖 What is this Project About? (Explained in Simple Terms)

### 🌾 The Real-World Problem
Along the fertile Thamirabarani river basin in Tamil Nadu (specifically in **Ambasamudram** and **Cheranmahadevi** taluks), farmers grow vast fields of **Paddy** and **Banana** directly next to each other. 

Government agricultural departments and water authorities need to know:
- **Which crop is growing where?**
- **How many hectares of each crop exist?** (Paddy needs huge amounts of canal water; Banana requires different irrigation schedules).

### 🛰️ Why Traditional Satellite Mapping Fails
When an ordinary satellite takes a picture from space, it looks at how "green" the ground is. 
During peak growing season:
- A healthy paddy field is **bright green**.
- A banana plantation is **bright green**.

To an optical camera, both look identical! As a result, standard machine learning models hit a roadblock and get stuck around **~70% accuracy**, frequently confusing Paddy for Banana, and confusing Banana for Coconut trees.

---

## 💡 How AgriGeo Solved This (The Solution)

Instead of relying on single snapshots or guessing, AgriGeo combines **crop biology**, **satellite radar physics**, and **cloud computing**:

```
                       SATELLITE DATA INGESTION
                     ┌────────────┴────────────┐
                     ▼                         ▼
            Sentinel-2 (Optical)      Sentinel-1 (Radar SAR)
            • 10-meter resolution     • Penetrates clouds
            • Colors & Red-Edge       • Detects 3D plant structure
                     │                         │
                     └────────────┬────────────┘
                                  ▼
               19-FEATURE ADVANCED STACK (Google Earth Engine)
               ├── 1. Dual-Season Growth (Wet Season vs Dry Season)
               ├── 2. EVI (Dense canopy biomass index)
               ├── 3. RECI (Chlorophyll & leaf thickness index)
               └── 4. Radar Backscatter (Volume scattering)
                                  ▼
               RANDOM FOREST CLASSIFIER (120 Trees)
               ├── Trained on 69 verified ground-truth polygons
               └── 92.49% Real Validation Accuracy (0.8900 Kappa)
                                  ▼
               INTERACTIVE WEB GIS DASHBOARD
               ├── Fast Python FastAPI Backend
               └── React + Leaflet Frontend with Instant Hover
```

### 1. Tracking Crop Lifecycle Across Seasons (Phenology)
- **Banana** is a perennial plant: its large leaves stay green all 12 months of the year.
- **Paddy** is seasonal: once harvested, the field turns into bare brown soil or stubble.
- By comparing the **Monsoon Wet Season** against the **Dry Harvest Season**, our model immediately catches the difference.

### 2. Seeing Through Clouds with Radar (Sentinel-1 SAR)
Optical cameras cannot see through monsoon clouds. We added **radar microwaves**:
- Flooded, flat paddy beds act like mirrors, bouncing radar away (**specular reflection**).
- Banana trees have large, complex, 3D canopies that scatter radar waves in all directions (**volume scattering**).
- Coconut palms have open crowns with rough woody trunks, separating them from banana foliage.

### 3. Measuring Leaf Biology (Red-Edge Chlorophyll Index - RECI)
Sentinel-2 has narrow red-edge bands that can detect how thick a leaf is and how much chlorophyll it packs. Banana leaves are thick, rubbery, and packed with chlorophyll, whereas paddy leaves are thin and slender.

---

## 📊 Proven Results

Evaluated over **15,000+ independent holdout test pixels** from 69 real digitized agricultural fields with zero synthetic data:

| Metric | Score | Industry Interpretation |
| :--- | :---: | :--- |
| **Overall Accuracy** | **92.49%** | Significantly outperforms single-date baseline (~71%) |
| **Cohen's Kappa ($\kappa$)** | **0.8900** | Near-Perfect Agreement |
| **Study Area Analyzed** | **73,026 ha** | Full basin mapping across Ambasamudram & Cheranmahadevi |

### Confusion Matrix Breakdown (Number of Test Pixels)
```
                  Predicted   Predicted   Predicted   Predicted
                    Paddy       Banana      Other       Water
Actual Paddy        5,382          6         648          31
Actual Banana          41        480          20           3
Actual Other          284          2       4,329          55
Actual Water           39          0          57       4,409
```

---

## 🖥️ Interactive Web Dashboard Features

Rather than leaving the code in an offline notebook, AgriGeo is packaged as a full-stack web application:

- 🗺️ **Google Maps Hybrid Basemap**: High-resolution satellite backdrop with crisp, native road networks and village names (Ambasamudram, Cheranmahadevi, Kallidaikurichi, Veeravanallur).
- ⚡ **Instant Hover Inspector (<50ms)**: Point your cursor at any field to see a floating tooltip showing the exact crop classification and coordinates.
- 📐 **Real-Time Parcel Acreage**: Uses morphological connected components (`connectedPixelCount`) to calculate contiguous field size directly in **hectares** (`ha`).
- 📊 **Live Analytics**: Visual bar charts and metric cards detailing acreage distribution across the 730 km² study area.

---

## 🛠️ Tech Stack & Architecture

- **Cloud Geospatial Processing**: [Google Earth Engine (GEE)](https://earthengine.google.com/) via Python API.
- **Satellites Used**:
  - European Space Agency (ESA) **Sentinel-2 MSI** (10m Optical & Red-Edge).
  - ESA **Sentinel-1 C-band SAR** (All-weather microwave radar).
- **Machine Learning**: 120-Tree Random Forest (`smileRandomForest`) running distributed in GEE.
- **Backend**: Python 3.10, **FastAPI**, Uvicorn, in-memory caching (`MODEL_CACHE`).
- **Frontend**: **React**, Vite, **Leaflet** (`react-leaflet`), HTML5 Offscreen Canvas, Recharts, Lucide Icons.

---

## 🚀 Getting Started (How to Run Locally)

### Prerequisites
1. **Python 3.10+** installed.
2. **Node.js (v18+)** installed.
3. A **Google Earth Engine** authenticated cloud project.

### 1. Clone the Repository
```bash
git clone https://github.com/abirami-302/AgriSat-TN.git
cd AgriSat-TN
```

### 2. Set Up the Backend
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # On Windows
# source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt

# Authenticate Earth Engine (one-time setup)
earthengine authenticate

# Run the FastAPI server
cd backend
python -m uvicorn main:app --port 8000 --reload
```
The backend API documentation will be available at `http://localhost:8000/docs`.

### 3. Set Up the Frontend Dashboard
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open your browser and navigate to **`http://localhost:5173`**.

---

## 📁 Repository Directory Structure

```text
AgriSat-TN/
├── backend/
│   ├── main.py              # FastAPI application & GEE tile endpoints
│   └── requirements.txt     # Backend Python dependencies
├── data/
│   └── training_polygons.geojson  # 69 verified ground-truth field polygons
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React Leaflet dashboard UI
│   │   ├── map/
│   │   │   ├── mapConfig.js           # Palette & bounding box configurations
│   │   │   └── tileColorInspector.js  # Fast offscreen canvas pixel reader
│   │   └── index.css        # Dashboard styling & layout
│   └── package.json         # Node.js dependencies
├── classify.py              # 19-band feature stack & Random Forest trainer
├── gee_auth.py              # Earth Engine authentication helper
└── README.md                # Project documentation
```
