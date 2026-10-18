// src/map/tileColorInspector.js
// Offscreen canvas tile reader with LRU caching for instant pixel color matching

import { CLASS_COLORS } from "./mapConfig";

const tileCanvasCache = new Map();
const MAX_CACHE_TILES = 64;

/**
 * Converts geographic latitude and longitude to XYZ tile indices and within-tile pixel coordinates.
 */
export function latLngToTileCoordinates(lat, lng, zoom) {
  const n = Math.pow(2, zoom);
  const latRad = (lat * Math.PI) / 180;
  
  const xExact = ((lng + 180) / 360) * n;
  const yExact =
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n;

  const tileX = Math.floor(xExact);
  const tileY = Math.floor(yExact);

  const pixelX = Math.floor((xExact - tileX) * 256);
  const pixelY = Math.floor((yExact - tileY) * 256);

  return {
    tileX,
    tileY,
    pixelX: Math.max(0, Math.min(255, pixelX)),
    pixelY: Math.max(0, Math.min(255, pixelY))
  };
}

/**
 * Loads an XYZ tile image into an offscreen canvas and returns its 2D context.
 */
function getTileContext(tileUrl) {
  if (tileCanvasCache.has(tileUrl)) {
    return Promise.resolve(tileCanvasCache.get(tileUrl));
  }

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous"; // Earth Engine tiles support CORS
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 256;
      canvas.height = 256;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);

      if (tileCanvasCache.size >= MAX_CACHE_TILES) {
        const firstKey = tileCanvasCache.keys().next().value;
        tileCanvasCache.delete(firstKey);
      }
      tileCanvasCache.set(tileUrl, ctx);
      resolve(ctx);
    };
    img.onerror = () => {
      resolve(null);
    };
    img.src = tileUrl;
  });
}

/**
 * Finds the nearest class name by calculating Euclidean distance in RGB color space.
 * Max threshold = 40 (avoids anti-aliasing edge artifacts or background blending).
 */
export function matchClassColor(r, g, b, alpha) {
  if (alpha === 0) return null; // Outside classified study area

  let minDistance = Infinity;
  let matchedClass = null;

  for (const item of CLASS_COLORS) {
    const [cr, cg, cb] = item.rgb;
    const dist = Math.sqrt(
      Math.pow(r - cr, 2) + Math.pow(g - cg, 2) + Math.pow(b - cb, 2)
    );
    if (dist < minDistance) {
      minDistance = dist;
      matchedClass = item;
    }
  }

  if (minDistance <= 40) {
    return matchedClass;
  }
  return { name: "Unclassified", color: "#64748b" };
}

/**
 * Inspects the pixel at the hovered lat/lng from the active tile URL.
 */
export async function getPixelClassAtLatLng(lat, lng, zoom, tileUrlTemplate) {
  if (!tileUrlTemplate) return null;

  const { tileX, tileY, pixelX, pixelY } = latLngToTileCoordinates(lat, lng, zoom);

  const tileUrl = tileUrlTemplate
    .replace("{z}", zoom)
    .replace("{x}", tileX)
    .replace("{y}", tileY);

  const ctx = await getTileContext(tileUrl);
  if (!ctx) return null;

  try {
    const pixel = ctx.getImageData(pixelX, pixelY, 1, 1).data;
    const r = pixel[0];
    const g = pixel[1];
    const b = pixel[2];
    const a = pixel[3];

    return matchClassColor(r, g, b, a);
  } catch (err) {
    return null;
  }
}
