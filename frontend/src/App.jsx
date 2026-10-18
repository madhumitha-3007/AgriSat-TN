import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { MapContainer, TileLayer, Marker, Tooltip as LeafletTooltip, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell
} from "recharts";
import { Layers, Activity, PieChart as ChartIcon, CheckCircle2, MapPin } from "lucide-react";
import { CLASS_COLORS, STUDY_BBOX } from "./map/mapConfig";
import { getPixelClassAtLatLng } from "./map/tileColorInspector";

const API_BASE = "http://localhost:8000";

const CLASS_CONFIG = CLASS_COLORS.reduce((acc, curr) => {
  acc[curr.name.toLowerCase()] = { name: curr.name, color: curr.color };
  return acc;
}, {});

// Prominent towns in Ambasamudram & Cheranmahadevi taluks
const STUDY_LOCATIONS = [
  { name: "Ambasamudram", lat: 8.7042, lon: 77.4539, type: "Taluk HQ" },
  { name: "Cheranmahadevi", lat: 8.6833, lon: 77.5667, type: "Taluk HQ" },
  { name: "Kallidaikurichi", lat: 8.6875, lon: 77.4625, type: "Town" },
  { name: "Veeravanallur", lat: 8.6847, lon: 77.5181, type: "Town" },
  { name: "Singampatti", lat: 8.6550, lon: 77.4350, type: "Village" },
  { name: "Pappankulam", lat: 8.6720, lon: 77.4480, type: "Village" },
  { name: "Vellanguli", lat: 8.6910, lon: 77.4930, type: "Village" },
  { name: "Mukkudal", lat: 8.7360, lon: 77.5250, type: "Town" },
  { name: "Harikesavanallur", lat: 8.7180, lon: 77.5180, type: "Village" },
  { name: "Nadukkallur", lat: 8.7250, lon: 77.5950, type: "Village" }
];

function HoverInspector({ onHover, onMouseMove, onMouseOut }) {
  const map = useMapEvents({
    mousemove(e) {
      onHover(e.latlng.lat, e.latlng.lng, map.getZoom());
      if (onMouseMove) {
        onMouseMove(e.containerPoint.x, e.containerPoint.y);
      }
    },
    mouseout() {
      if (onMouseOut) {
        onMouseOut();
      }
    },
    click(e) {
      // Tap support for mobile/touch devices
      onHover(e.latlng.lat, e.latlng.lng, map.getZoom());
      if (onMouseMove) {
        onMouseMove(e.containerPoint.x, e.containerPoint.y);
      }
    }
  });
  return null;
}

export default function App() {
  const [year, setYear] = useState(2025);
  const [cloud, setCloud] = useState(20);

  const [showRgb, setShowRgb] = useState(true);
  const [showClassified, setShowClassified] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  const [tiles, setTiles] = useState(null);
  const [stats, setStats] = useState(null);
  const [accuracy, setAccuracy] = useState(null);

  const [loadingTiles, setLoadingTiles] = useState(false);
  const [loadingStats, setLoadingStats] = useState(false);
  const [loadingAcc, setLoadingAcc] = useState(false);
  const [error, setError] = useState(null);

  // Hover Inspector State
  const [hoverInfo, setHoverInfo] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const lastHoverTime = useRef(0);
  const parcelFetchTimer = useRef(null);

  useEffect(() => {
    fetchTiles();
    fetchStats();
    fetchAccuracy();
  }, [year, cloud]);

  const handleMapHover = (lat, lon, zoom) => {
    // If classified overlay is turned off, do not show tooltip
    if (!showClassified || !tiles?.classified_tile_url) {
      setHoverInfo(null);
      return;
    }

    // Check geographic bounding box
    if (
      lon < STUDY_BBOX.west ||
      lon > STUDY_BBOX.east ||
      lat < STUDY_BBOX.south ||
      lat > STUDY_BBOX.north
    ) {
      setHoverInfo(null);
      return;
    }

    // Throttle pixel reading to ~50ms
    const now = performance.now();
    if (now - lastHoverTime.current < 50) {
      return;
    }
    lastHoverTime.current = now;

    // Fast Offscreen Canvas Tile Pixel Read
    getPixelClassAtLatLng(lat, lon, zoom, tiles.classified_tile_url).then((matched) => {
      if (!matched || matched.name === "Unclassified") {
        setHoverInfo(null);
        return;
      }

      setHoverInfo({
        class_name: matched.name,
        color: matched.color,
        lat,
        lon,
        parcel_hectares: null
      });

      // Background parcel area fetch (debounced to 180ms so mouse sliding remains instant)
      if (parcelFetchTimer.current) clearTimeout(parcelFetchTimer.current);
      parcelFetchTimer.current = setTimeout(async () => {
        try {
          const res = await axios.get(
            `${API_BASE}/api/inspect?lat=${lat.toFixed(5)}&lon=${lon.toFixed(5)}&year=${year}&cloud=${cloud}`
          );
          if (res.data?.inside && res.data.parcel_hectares) {
            setHoverInfo((prev) =>
              prev ? { ...prev, parcel_hectares: res.data.parcel_hectares } : null
            );
          }
        } catch {
          // ignore
        }
      }, 180);
    });
  };

  const handleMouseOut = () => {
    setHoverInfo(null);
  };

  const fetchTiles = async () => {
    setLoadingTiles(true);
    try {
      const res = await axios.get(`${API_BASE}/api/tiles?year=${year}&cloud=${cloud}`);
      setTiles(res.data);
    } catch (err) {
      console.error(err);
      setError("Failed to load map tiles from Earth Engine.");
    } finally {
      setLoadingTiles(false);
    }
  };

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await axios.get(`${API_BASE}/api/stats?year=${year}&cloud=${cloud}`);
      setStats(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchAccuracy = async () => {
    setLoadingAcc(true);
    try {
      const res = await axios.get(`${API_BASE}/api/accuracy?year=${year}&cloud=${cloud}`);
      setAccuracy(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAcc(false);
    }
  };

  const chartData = stats
    ? Object.entries(stats.classes).map(([key, val]) => ({
        name: CLASS_CONFIG[key]?.name || key,
        key,
        hectares: val,
        fill: CLASS_CONFIG[key]?.color || "#8884d8"
      }))
    : [];

  return (
    <div className="app-container" style={{ flexDirection: "column" }}>
      {/* Sleek Top Navigation Bar */}
      <header style={{
        height: "56px",
        backgroundColor: "#1e293b",
        borderBottom: "1px solid #334155",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        zIndex: 50,
        flexShrink: 0
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "1.4rem" }}>🌾</span>
          <div>
            <h1 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#38bdf8", margin: 0, lineHeight: 1.2 }}>
              AgriSat-TN
            </h1>
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", margin: 0 }}>
              Ambasamudram &amp; Cheranmahadevi Crop Mapping
            </p>
          </div>
        </div>

        {/* Minimal Floating Quick Toggles */}
        <div style={{ display: "flex", alignItems: "center", gap: "18px", fontSize: "0.85rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "#cbd5e1" }}>
            <input
              type="checkbox"
              checked={showRgb}
              onChange={(e) => setShowRgb(e.target.checked)}
            />
            <span>Satellite RGB</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "#cbd5e1" }}>
            <input
              type="checkbox"
              checked={showClassified}
              onChange={(e) => setShowClassified(e.target.checked)}
            />
            <span>Crop Classification</span>
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "#cbd5e1" }}>
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            <span>Town &amp; Road Names</span>
          </label>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content" style={{ width: "100%", height: "calc(100vh - 56px)" }}>
        {(loadingTiles || loadingStats || loadingAcc) && (
          <div className="loading-banner">
            Processing Earth Engine composite & Random Forest...
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}

        {/* Map Section */}
        <section className="map-section" style={{ height: "60vh" }}>
          <MapContainer
            center={[8.7, 77.45]}
            zoom={11}
            attributionControl={false}
            style={{ width: "100%", height: "100%" }}
            scrollWheelZoom={true}
          >
            {/* 1. Official Google Maps Hybrid Satellite Basemap */}
            <TileLayer
              url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
              maxZoom={20}
            />

            {/* 2. Earth Engine Sentinel-2 RGB Layer */}
            {showRgb && tiles?.rgb_tile_url && (
              <TileLayer
                key={`rgb-${tiles.rgb_tile_url}`}
                url={tiles.rgb_tile_url}
                opacity={0.80}
                maxZoom={20}
              />
            )}

            {/* 3. Earth Engine Classified Layer */}
            {showClassified && tiles?.classified_tile_url && (
              <TileLayer
                key={`class-${tiles.classified_tile_url}`}
                url={tiles.classified_tile_url}
                opacity={0.65}
                maxZoom={20}
              />
            )}

            {/* 4. Google Maps Road & Town Labels Top-Overlay */}
            {showLabels && (
              <TileLayer
                url="https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}"
                maxZoom={20}
                zIndex={600}
              />
            )}

            {/* Mouse Hover Event Listener */}
            <HoverInspector
              onHover={handleMapHover}
              onMouseMove={(x, y) => setMousePos({ x, y })}
              onMouseOut={handleMouseOut}
            />
          </MapContainer>

          {/* Real-time Dynamic Cursor Follow Tooltip */}
          {hoverInfo && (
            <div style={{
              position: "absolute",
              top: mousePos.y + 14,
              left: mousePos.x + 14,
              zIndex: 1000,
              backgroundColor: "rgba(15, 23, 42, 0.95)",
              backdropFilter: "blur(8px)",
              border: `2px solid ${hoverInfo.color}`,
              padding: "8px 14px",
              borderRadius: "8px",
              boxShadow: "0 6px 20px rgba(0,0,0,0.7)",
              color: "#f8fafc",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              fontSize: "0.85rem",
              pointerEvents: "none",
              userSelect: "none",
              transition: "top 0.04s ease, left 0.04s ease"
            }}>
              {/* Color swatch */}
              <div style={{
                width: 14,
                height: 14,
                borderRadius: "3px",
                backgroundColor: hoverInfo.color,
                boxShadow: `0 0 8px ${hoverInfo.color}`,
                flexShrink: 0
              }} />
              <div>
                <div style={{ fontWeight: 800, fontSize: "1.02rem", color: hoverInfo.color, lineHeight: 1.15 }}>
                  {hoverInfo.class_name}
                </div>
                <div style={{ color: "#94a3b8", fontSize: "0.74rem", marginTop: "2px" }}>
                  {hoverInfo.lat.toFixed(4)}°N, {hoverInfo.lon.toFixed(4)}°E
                </div>
              </div>
              {hoverInfo.parcel_hectares && (
                <div style={{ borderLeft: "1px solid #334155", paddingLeft: "10px", marginLeft: "2px" }}>
                  <div style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "#94a3b8", fontWeight: 700 }}>
                    Parcel
                  </div>
                  <div style={{ fontWeight: 800, color: "#38bdf8", fontSize: "0.90rem" }}>
                    {hoverInfo.parcel_hectares} ha
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Analytics Section */}
        <section className="analytics-section">
          {/* Area Bar Chart */}
          <div className="card">
            <div className="card-title">
              <ChartIcon size={18} />
              <span>Area Distribution (Hectares)</span>
            </div>
            <div style={{ width: "100%", height: 190 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155" }}
                  />
                  <Bar dataKey="hectares" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Area Data Table */}
          <div className="card">
            <div className="card-title">
              <Layers size={18} />
              <span>Parcel Statistics</span>
            </div>
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Area (ha)</th>
                </tr>
              </thead>
              <tbody>
                {stats &&
                  Object.entries(stats.classes).map(([key, val]) => (
                    <tr key={key}>
                      <td style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          className="color-badge"
                          style={{ backgroundColor: CLASS_CONFIG[key]?.color }}
                        />
                        {CLASS_CONFIG[key]?.name}
                      </td>
                      <td>{val.toLocaleString()} ha</td>
                    </tr>
                  ))}
                {stats && (
                  <tr>
                    <td><strong>Total</strong></td>
                    <td><strong>{stats.total_hectares.toLocaleString()} ha</strong></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Model Accuracy Card */}
          <div className="card">
            <div className="card-title">
              <Activity size={18} />
              <span>Model Evaluation</span>
            </div>
            {accuracy && (
              <>
                <div className="metric-row">
                  <span>Overall Accuracy</span>
                  <span className="metric-val">
                    {(accuracy.overall_accuracy * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="metric-row">
                  <span>Kappa Coefficient</span>
                  <span className="metric-val">{accuracy.kappa.toFixed(4)}</span>
                </div>
                <div>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                    Confusion Matrix (Paddy, Banana, Other, Water)
                  </span>
                  <div className="confusion-grid">
                    {accuracy.confusion_matrix.flat().map((val, idx) => (
                      <div key={idx} className="matrix-cell">
                        {val}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
