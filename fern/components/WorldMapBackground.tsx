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

const PLAN_POINTS = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { id: "partnership" }, geometry: { type: "Point", coordinates: [-121.7, 40.5] } },
    { type: "Feature", properties: { id: "alliance" }, geometry: { type: "Point", coordinates: [-121.0, 36.5] } },
    { type: "Feature", properties: { id: "cencal" }, geometry: { type: "Point", coordinates: [-120.0, 34.6] } },
    { type: "Feature", properties: { id: "gold-coast" }, geometry: { type: "Point", coordinates: [-119.1, 34.3] } },
    { type: "Feature", properties: { id: "caloptima" }, geometry: { type: "Point", coordinates: [-117.8, 33.7] } },
  ],
};

const INITIAL_CENTER = [-120.0, 34.6];
const INITIAL_ZOOM = 5.6;
const INITIAL_PITCH = 58;

export function WorldMapBackground() {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!document.querySelector(`link[href="${MAPBOX_CSS_URL}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = MAPBOX_CSS_URL;
      document.head.appendChild(link);
    }

    let map = null;
    let cancelled = false;

    async function addCountyLayers() {
      try {
        const response = await fetch(COUNTIES_GEOJSON_URL);
        const data = await response.json();
        if (cancelled || !map || map.getSource("ca-counties")) return;

        const california = {
          type: "FeatureCollection",
          features: data.features
            .filter((feature) => String(feature.id ?? "").startsWith("06"))
            .map((feature) => ({
              ...feature,
              properties: { ...(feature.properties || {}), fips: String(feature.id) },
            })),
        };

        map.addSource("ca-counties", { type: "geojson", data: california });
        const cohsFilter = ["in", ["get", "fips"], ["literal", COHS_COUNTY_FIPS]];

        map.addLayer({
          id: "cohs-county-fill",
          type: "fill",
          source: "ca-counties",
          filter: cohsFilter,
          paint: {
            "fill-color": "#4b9ed8",
            "fill-opacity": 0.22,
          },
        });

        map.addLayer({
          id: "cohs-county-outline",
          type: "line",
          source: "ca-counties",
          filter: cohsFilter,
          paint: {
            "line-color": "#8bc9f0",
            "line-width": 1.25,
            "line-opacity": 0.72,
          },
        });
      } catch (error) {
        console.error("Failed to load California county boundaries", error);
      }
    }

    function addPlanLayers() {
      if (!map || map.getSource("plan-points")) return;

      map.addSource("plan-points", { type: "geojson", data: PLAN_POINTS });

      // Native Mapbox layers: restrained beacon points instead of custom DOM badges.
      map.addLayer({
        id: "plan-glow",
        type: "circle",
        source: "plan-points",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 5, 7, 9],
          "circle-color": "#8bc9f0",
          "circle-opacity": 0.16,
          "circle-blur": 0.8,
        },
      });

      map.addLayer({
        id: "plan-beacon",
        type: "circle",
        source: "plan-points",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2.5, 7, 4.5],
          "circle-color": "#dff4ff",
          "circle-opacity": 0.96,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-opacity": 0.85,
        },
      });
    }

    function tuneMapboxMaterial() {
      if (!map) return;

      // Mapbox Standard provides the native basemap material, atmosphere, lighting,
      // labels, roads, landcover, and building treatment without a custom UI skin.
      try {
        map.setConfigProperty("basemap", "lightPreset", "night");
        map.setConfigProperty("basemap", "showPointOfInterestLabels", false);
        map.setConfigProperty("basemap", "showTransitLabels", false);
        map.setConfigProperty("basemap", "showPlaceLabels", true);
        map.setConfigProperty("basemap", "showRoadLabels", false);
      } catch (_) {}

      try {
        map.setFog({
          color: "rgb(12, 20, 30)",
          "high-color": "rgb(40, 75, 100)",
          "horizon-blend": 0.08,
          "space-color": "rgb(3, 7, 12)",
          "star-intensity": 0.12,
        });
      } catch (_) {}

      try {
        map.addSource("mapbox-dem", {
          type: "raster-dem",
          url: "mapbox://mapbox.mapbox-terrain-dem-v1",
          tileSize: 512,
          maxzoom: 14,
        });
        map.setTerrain({ source: "mapbox-dem", exaggeration: 1.15 });
      } catch (_) {}
    }

    function initMap() {
      if (cancelled || !containerRef.current) return;
      const mapboxgl = window.mapboxgl;
      if (!mapboxgl) return;

      mapboxgl.accessToken = MAPBOX_TOKEN;
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/standard",
        center: INITIAL_CENTER,
        zoom: INITIAL_ZOOM,
        pitch: INITIAL_PITCH,
        projection: "globe",
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        scrollZoom: false,
        doubleClickZoom: false,
        touchZoomRotate: true,
      });

      map.on("load", () => {
        tuneMapboxMaterial();
        addPlanLayers();
        addCountyLayers();
      });
    }

    if (window.mapboxgl) {
      initMap();
    } else {
      let script = document.querySelector(`script[src="${MAPBOX_JS_URL}"]`);
      if (!script) {
        script = document.createElement("script");
        script.src = MAPBOX_JS_URL;
        script.async = true;
        document.head.appendChild(script);
      }
      script.addEventListener("load", initMap);
    }

    return () => {
      cancelled = true;
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
        touchAction: "none",
        background: "#03070c",
      }}
    />
  );
}

export default WorldMapBackground;
