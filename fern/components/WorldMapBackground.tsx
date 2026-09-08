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
    { type: "Feature", properties: { id: "partnership", label: "Partnership" }, geometry: { type: "Point", coordinates: [-121.7, 40.5] } },
    { type: "Feature", properties: { id: "alliance", label: "Alliance" }, geometry: { type: "Point", coordinates: [-121.0, 36.5] } },
    { type: "Feature", properties: { id: "cencal", label: "CenCal Health" }, geometry: { type: "Point", coordinates: [-120.0, 34.6] } },
    { type: "Feature", properties: { id: "gold-coast", label: "Gold Coast" }, geometry: { type: "Point", coordinates: [-119.1, 34.3] } },
    { type: "Feature", properties: { id: "caloptima", label: "CalOptima" }, geometry: { type: "Point", coordinates: [-117.8, 33.7] } },
  ],
};

const INITIAL_CENTER = [-120.0, 34.6];
const INITIAL_ZOOM = 5.6;
const INITIAL_PITCH = 58;

function distanceKm(a, b) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRadians(b[1] - a[1]);
  const dLon = toRadians(b[0] - a[0]);
  const lat1 = toRadians(a[1]);
  const lat2 = toRadians(b[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * earthRadiusKm * Math.asin(Math.sqrt(h));
}

function focusPlanPoints(center) {
  const ranked = PLAN_POINTS.features
    .map((feature) => ({
      feature,
      distance: distanceKm(center, feature.geometry.coordinates),
    }))
    .sort((a, b) => a.distance - b.distance);

  const nearest = ranked[0];

  return {
    ...PLAN_POINTS,
    features: ranked.map(({ feature, distance }, index) => ({
      ...feature,
      properties: {
        ...feature.properties,
        distanceKm: Math.round(distance),
        rank: index,
        // Keep the immediate area legible while suppressing distant competition.
        visibility: index === 0 ? 1 : index === 1 ? 0.42 : index === 2 ? 0.14 : 0,
        labelOpacity: feature === nearest.feature ? 0.96 : 0,
      },
    })),
  };
}

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
    let lastFocusUpdate = 0;

    function updatePlanFocus() {
      if (!map || !map.getSource("plan-points")) return;

      const now = performance.now();
      if (now - lastFocusUpdate < 80) return;
      lastFocusUpdate = now;

      const center = map.getCenter();
      map.getSource("plan-points").setData(focusPlanPoints([center.lng, center.lat]));
    }

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
            "fill-opacity": 0.12,
          },
          slot: "bottom",
        });

        map.addLayer({
          id: "cohs-county-outline",
          type: "line",
          source: "ca-counties",
          filter: cohsFilter,
          paint: {
            "line-color": "#8bc9f0",
            "line-width": 1.1,
            "line-opacity": 0.48,
          },
          slot: "middle",
        });
      } catch (error) {
        console.error("Failed to load California county boundaries", error);
      }
    }

    function addPlanLayers() {
      if (!map || map.getSource("plan-points")) return;

      map.addSource("plan-points", {
        type: "geojson",
        data: focusPlanPoints(INITIAL_CENTER),
      });

      // The nearest clinical-plan location becomes the visual anchor.
      // Nearby locations remain discoverable; distant ones disappear from view.
      map.addLayer({
        id: "plan-glow",
        type: "circle",
        source: "plan-points",
        slot: "top",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            4, ["match", ["get", "rank"], 0, 9, 1, 6, 2, 4, 0],
            7, ["match", ["get", "rank"], 0, 16, 1, 10, 2, 6, 0],
          ],
          "circle-color": "#8bc9f0",
          "circle-opacity": ["get", "visibility"],
          "circle-blur": 0.82,
        },
      });

      map.addLayer({
        id: "plan-beacon",
        type: "circle",
        source: "plan-points",
        slot: "top",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            4, ["match", ["get", "rank"], 0, 3.5, 1, 2.5, 2, 2, 0],
            7, ["match", ["get", "rank"], 0, 6, 1, 4, 2, 3, 0],
          ],
          "circle-color": "#dff4ff",
          "circle-opacity": ["get", "visibility"],
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-opacity": ["get", "visibility"],
        },
      });

      map.addLayer({
        id: "plan-label",
        type: "symbol",
        source: "plan-points",
        slot: "top",
        layout: {
          "text-field": ["get", "label"],
          "text-size": 12,
          "text-font": ["Open Sans Regular"],
          "text-offset": [0, 1.45],
          "text-anchor": "top",
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#e8f7ff",
          "text-halo-color": "rgba(3, 7, 12, 0.9)",
          "text-halo-width": 1.5,
          "text-opacity": ["get", "labelOpacity"],
        },
      });
    }

    function tuneMapboxMaterial() {
      if (!map) return;

      try {
        map.setConfigProperty("basemap", "lightPreset", "night");
        map.setConfigProperty("basemap", "showPointOfInterestLabels", false);
        map.setConfigProperty("basemap", "showTransitLabels", false);
        map.setConfigProperty("basemap", "showPlaceLabels", false);
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

      // Native Mapbox drag remains the exploration gesture. As the user drags,
      // the nearest plan becomes the isolated focal point without adding controls.
      map.on("move", updatePlanFocus);
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
