/* eslint-disable */
// @ts-nocheck
import { useEffect, useRef } from "react";

const MAPBOX_TOKEN =
  "pk.eyJ1Ijoic3RhbXBlbWVkaWEiLCJhIjoiY210b293OGFoMDlxZzJ4cTgzdWxhcTZlOSJ9.woZXmBqNxSPkFE5g9bivAw";
const MAPBOX_CSS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.css";
const MAPBOX_JS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.js";
const COUNTIES_GEOJSON_URL =
  "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";

// California COHS counties (FIPS codes)
const COHS_COUNTY_FIPS = [
  "06001", // Alameda
  "06013", // Contra Costa
  "06019", // Fresno
  "06029", // Kern
  "06031", // Kings
  "06037", // Los Angeles
  "06039", // Madera
  "06041", // Marin
  "06045", // Mendocino
  "06047", // Merced
  "06053", // Monterey
  "06059", // Orange
  "06065", // Riverside
  "06067", // Sacramento
  "06071", // San Bernardino
  "06073", // San Diego
  "06075", // San Francisco
  "06081", // San Mateo
  "06083", // Santa Barbara
  "06085", // Santa Clara
  "06095", // Solano
  "06111", // Ventura
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

export function WorldMapBackground() {
  const containerRef = useRef(null);
  const markersRef = useRef([]);
  const pointerRef = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    if (!document.querySelector(`link[href="${MAPBOX_CSS_URL}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = MAPBOX_CSS_URL;
      document.head.appendChild(link);
    }

    let map = null;
    let cancelled = false;
    let animationFrame = null;

    function updateMarkerPositions() {
      if (!map) return;
      markersRef.current.forEach(({ element, coordinates }) => {
        const point = map.project(coordinates);
        element.style.transform = `translate3d(${point.x}px, ${point.y}px, 0) translate(-50%, -50%)`;
      });
      updateMarkerScale();
    }

    function updateMarkerScale() {
      const pointer = pointerRef.current;
      markersRef.current.forEach(({ element }) => {
        const rect = element.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const distance = Math.hypot(pointer.x - x, pointer.y - y);
        const proximity = Math.max(0, 1 - distance / 280);
        const scale = 0.52 + proximity * 0.82;
        const opacity = 0.42 + proximity * 0.58;
        element.style.setProperty("--marker-scale", scale.toFixed(3));
        element.style.opacity = opacity.toFixed(3);
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
        marker.style.width = "76px";
        marker.style.height = "76px";
        marker.style.borderRadius = "999px";
        marker.style.transformOrigin = "center";
        marker.style.transform = "translate(-50%, -50%) scale(0.52)";
        marker.style.transition = "transform 180ms ease-out, opacity 180ms ease-out";
        marker.style.opacity = "0.42";
        marker.style.setProperty("--marker-scale", "0.52");
        marker.style.background = "rgba(255,255,255,0.92)";
        marker.style.border = "1px solid rgba(255,255,255,0.95)";
        marker.style.boxShadow = "0 8px 28px rgba(0,0,0,0.28), 0 0 0 8px rgba(255,255,255,0.08)";
        marker.style.display = "grid";
        marker.style.placeItems = "center";
        marker.style.overflow = "hidden";

        const mark = document.createElement("div");
        mark.style.width = "30px";
        mark.style.height = "30px";
        mark.style.borderRadius = "10px 18px 10px 18px";
        mark.style.background = "linear-gradient(135deg, rgba(40,120,190,0.95), rgba(90,180,235,0.8))";
        mark.style.transform = "rotate(-12deg)";
        mark.style.boxShadow = "inset 0 0 0 5px rgba(255,255,255,0.28)";
        marker.appendChild(mark);

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

        map.addSource("ca-counties", {
          type: "geojson",
          data: california,
        });

        const cohsFilter = ["in", ["get", "fips"], ["literal", COHS_COUNTY_FIPS]];

        map.addLayer({
          id: "cohs-county-fill",
          type: "fill",
          source: "ca-counties",
          filter: cohsFilter,
          paint: {
            "fill-color": HIGHLIGHT_FILL,
          },
        });

        map.addLayer({
          id: "cohs-county-outline",
          type: "line",
          source: "ca-counties",
          filter: cohsFilter,
          paint: {
            "line-color": HIGHLIGHT_LINE,
            "line-width": 2,
          },
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
        center: [-119.5, 37.2],
        zoom: 6,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });

      map.on("load", () => {
        createPlanMarkers();
        addCountyLayers();
        map.on("move", updateMarkerPositions);
        map.on("resize", updateMarkerPositions);
      });
    }

    function handlePointerMove(event) {
      pointerRef.current = { x: event.clientX, y: event.clientY };
      if (animationFrame) return;
      animationFrame = requestAnimationFrame(() => {
        animationFrame = null;
        updateMarkerScale();
      });
    }

    window.addEventListener("pointermove", handlePointerMove, { passive: true });

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
      window.removeEventListener("pointermove", handlePointerMove);
      if (animationFrame) cancelAnimationFrame(animationFrame);
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
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 4,
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