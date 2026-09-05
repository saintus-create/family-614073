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

const HIGHLIGHT_FILL = "rgba(100, 180, 255, 0.35)";
const HIGHLIGHT_LINE = "rgb(100, 180, 255)";

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
      });

      map.on("load", addCountyLayers);
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
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
      }}
    />
  );
}

export default WorldMapBackground;