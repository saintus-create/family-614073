/* eslint-disable */
// @ts-nocheck
import { useEffect, useRef } from "react";

const MAPBOX_TOKEN =
  "pk.eyJ1Ijoic3RhbXBlbWVkaWEiLCJhIjoiY210b293OGFoMDlxZzJ4cTgzdWxhcTZlOSJ9.woZXmBqNxSPkFE5g9bivAw";
const MAPBOX_CSS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.css";
const MAPBOX_JS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.js";
const COUNTIES_GEOJSON_URL =
  "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";

const COHS_COUNTY_FIPS = [
  "06001", "06013", "06019", "06029", "06031", "06037", "06039", "06041",
  "06045", "06047", "06053", "06059", "06065", "06067", "06071", "06073",
  "06075", "06081", "06083", "06085", "06095", "06111",
];

const PLAN_MARKERS = [
  { id: "partnership", coordinates: [-121.7, 40.5] },
  { id: "alliance", coordinates: [-121.0, 36.5] },
  { id: "cencal", coordinates: [-120.0, 34.6] },
  { id: "gold-coast", coordinates: [-119.1, 34.3] },
  { id: "caloptima", coordinates: [-117.8, 33.7] },
];

const HIGHLIGHT_FILL = "rgba(100, 180, 255, 0.35)";
const HIGHLIGHT_LINE = "rgb(100, 180, 255)";
const INITIAL_CENTER = [-120.0, 34.6];
const INITIAL_ZOOM = 5.6;
const INITIAL_PITCH = 48;

function angularDistance(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const dLat = lat2 - lat1;
  const dLon = toRad(b[0] - a[0]);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const value = Math.min(1, sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon);
  return (2 * Math.asin(Math.sqrt(value)) * 180) / Math.PI;
}

export function WorldMapBackground() {
  const containerRef = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    if (!document.querySelector(`link[href="${MAPBOX_CSS_URL}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = MAPBOX_CSS_URL;
      document.head.appendChild(link);
    }

    let map = null;
    let cancelled = false;

    function updateMarkerPositions() {
      if (!map) return;
      const center = map.getCenter();

      markersRef.current.forEach(({ element, coordinates }) => {
        const distance = angularDistance([center.lng, center.lat], coordinates);
        const visible = distance < 104;
        const point = map.project(coordinates);
        const depth = Math.max(0, 1 - distance / 104);
        const scale = 0.48 + depth * 0.72;

        element.style.transform = `translate3d(${point.x}px, ${point.y}px, 0) translate(-50%, -50%) scale(${scale.toFixed(3)})`;
        element.style.opacity = visible ? (0.22 + depth * 0.78).toFixed(3) : "0";
        element.style.visibility = visible ? "visible" : "hidden";
      });
    }

    function createPlanMarkers() {
      if (!map || !containerRef.current) return;

      const layer = document.createElement("div");
      layer.style.position = "absolute";
      layer.style.inset = "0";
      layer.style.zIndex = "3";
      layer.style.pointerEvents = "none";
      containerRef.current.appendChild(layer);

      PLAN_MARKERS.forEach(({ id, coordinates }) => {
        const marker = document.createElement("div");
        marker.setAttribute("aria-label", `${id} health plan`);
        marker.style.position = "absolute";
        marker.style.left = "0";
        marker.style.top = "0";
        marker.style.width = "82px";
        marker.style.height = "82px";
        marker.style.borderRadius = "999px";
        marker.style.transformOrigin = "center";
        marker.style.background = "rgba(255,255,255,0.94)";
        marker.style.border = "1px solid rgba(255,255,255,0.98)";
        marker.style.boxShadow = "0 10px 34px rgba(0,0,0,0.32), 0 0 0 8px rgba(255,255,255,0.09)";
        marker.style.display = "grid";
        marker.style.placeItems = "center";
        marker.style.overflow = "visible";
        marker.style.transition = "opacity 160ms ease-out, transform 160ms ease-out";

        const mark = document.createElement("div");
        mark.style.width = "30px";
        mark.style.height = "30px";
        mark.style.borderRadius = "10px 18px 10px 18px";
        mark.style.background = "linear-gradient(135deg, rgba(40,120,190,0.98), rgba(90,180,235,0.86))";
        mark.style.transform = "rotate(-12deg)";
        mark.style.boxShadow = "inset 0 0 0 5px rgba(255,255,255,0.28)";
        marker.appendChild(mark);

        const stem = document.createElement("div");
        stem.style.position = "absolute";
        stem.style.left = "50%";
        stem.style.top = "calc(100% - 2px)";
        stem.style.width = "12px";
        stem.style.height = "18px";
        stem.style.transform = "translateX(-50%)";
        stem.style.background = "rgba(255,255,255,0.94)";
        stem.style.clipPath = "polygon(0 0, 100% 0, 50% 100%)";
        marker.appendChild(stem);

        layer.appendChild(marker);
        markersRef.current.push({ element: marker, coordinates });
      });

      updateMarkerPositions();
    }

    async function addCountyLayers() {
      try {
        const response = await fetch(COUNTIES_GEOJSON_URL);
        const data = await response.json();
        if (cancelled || !map) return;

        const california = {
          type: "FeatureCollection",
          features: data.features
            .filter((feature) => String(feature.id ?? "").startsWith("06"))
            .map((feature) => ({
              ...feature,
              properties: { ...(feature.properties || {}), fips: String(feature.id) },
            })),
        };

        if (map.getSource("ca-counties")) return;

        map.addSource("ca-counties", { type: "geojson", data: california });
        const cohsFilter = ["in", ["get", "fips"], ["literal", COHS_COUNTY_FIPS]];

        map.addLayer({
          id: "cohs-county-fill",
          type: "fill",
          source: "ca-counties",
          filter: cohsFilter,
          paint: { "fill-color": HIGHLIGHT_FILL },
        });

        map.addLayer({
          id: "cohs-county-outline",
          type: "line",
          source: "ca-counties",
          filter: cohsFilter,
          paint: { "line-color": HIGHLIGHT_LINE, "line-width": 2 },
        });
      } catch (error) {
        console.error("Failed to load California county boundaries", error);
      }
    }

    function initMap() {
      if (cancelled || !containerRef.current) return;
      const mapboxgl = window.mapboxgl;
      if (!mapboxgl) return;

      mapboxgl.accessToken = MAPBOX_TOKEN;
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/satellite-streets-v12",
        center: INITIAL_CENTER,
        zoom: INITIAL_ZOOM,
        pitch: INITIAL_PITCH,
        projection: "globe",
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        scrollZoom: false,
      });

      map.on("load", () => {
        createPlanMarkers();
        addCountyLayers();
        map.on("move", updateMarkerPositions);
        map.on("resize", updateMarkerPositions);
        updateMarkerPositions();
      });
    }

    if (window.mapboxgl) {
      initMap();
    } else {
      let script = document.querySelector(`script[src="${MAPBOX_JS_URL}"]`);
      if (!script) {
        script = document.createElement("script");
        script.src = MAPBOX_JS_URL;
        document.head.appendChild(script);
      }
      script.addEventListener("load", initMap);
    }

    return () => {
      cancelled = true;
      markersRef.current = [];
      if (map) {
        map.remove();
        map = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        overflow: "hidden",
        borderRadius: "28px",
        touchAction: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 2,
          pointerEvents: "none",
          background:
            "linear-gradient(90deg, rgba(0,0,0,0.48) 0%, rgba(0,0,0,0.22) 16%, rgba(0,0,0,0) 34%, rgba(0,0,0,0) 66%, rgba(0,0,0,0.22) 84%, rgba(0,0,0,0.48) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "12px",
          zIndex: 5,
          pointerEvents: "none",
          border: "1px solid rgba(255,255,255,0.24)",
          borderRadius: "28px",
          boxShadow: "inset 0 0 70px rgba(0,0,0,0.14)",
        }}
      />
    </div>
  );
}

export default WorldMapBackground;
