import { useEffect, useRef } from "react";

const MAPBOX_TOKEN =
  "pk.eyJ1Ijoic3RhbXBlbWVkaWEiLCJhIjoiY210b293OGFoMDlxZzJ4cTgzdWxhcTZlOSJ9.woZXmBqNxSPkFE5g9bivAw";
const MAPBOX_CSS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.css";
const MAPBOX_JS_URL = "https://api.mapbox.com/mapbox-gl-js/v3.4.0/mapbox-gl.js";

export function WorldMapBackground() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Inject Mapbox CSS if not already present
    if (!document.querySelector(`link[href="${MAPBOX_CSS_URL}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = MAPBOX_CSS_URL;
      document.head.appendChild(link);
    }

    // Inject Mapbox JS if not already present, then initialise the map
    let map: any = null;
    let script: HTMLScriptElement | null = null;

    function initMap() {
      if (!containerRef.current) return;
      const mapboxgl = (window as any).mapboxgl;
      if (!mapboxgl) return;

      mapboxgl.accessToken = MAPBOX_TOKEN;
      map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/satellite-streets-v12",
        center: [-119.7, 34.5],
        zoom: 8,
      });
    }

    if ((window as any).mapboxgl) {
      // Already loaded from a previous render
      initMap();
    } else if (!document.querySelector(`script[src="${MAPBOX_JS_URL}"]`)) {
      script = document.createElement("script");
      script.src = MAPBOX_JS_URL;
      script.onload = initMap;
      document.head.appendChild(script);
    } else {
      // Script tag exists but may still be loading
      const existing = document.querySelector(
        `script[src="${MAPBOX_JS_URL}"]`
      ) as HTMLScriptElement;
      existing.addEventListener("load", initMap);
    }

    return () => {
      if (map) {
        map.remove();
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: "500px",
      }}
    />
  );
}

export default WorldMapBackground;
