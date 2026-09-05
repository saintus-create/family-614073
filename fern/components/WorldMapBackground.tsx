"use client";

import { useEffect, useMemo, useState } from "react";
import DottedMap from "dotted-map";

type Point = { lat: number; lng: number };
type Dot = { start: Point; end: Point };

const dots: Dot[] = [
  { start: { lat: 37.7749, lng: -122.4194 }, end: { lat: 34.0522, lng: -118.2437 } },
  { start: { lat: 34.0522, lng: -118.2437 }, end: { lat: 40.7128, lng: -74.006 } },
  { start: { lat: 37.7749, lng: -122.4194 }, end: { lat: 47.6062, lng: -122.3321 } },
  { start: { lat: 34.0522, lng: -118.2437 }, end: { lat: 19.4326, lng: -99.1332 } },
];

export function WorldMapBackground() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const update = () => setDark(document.documentElement.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const svgMap = useMemo(() => {
    const map = new DottedMap({ height: 100, grid: "diagonal" });
    return map.getSVG({ radius: 0.22, color: dark ? "#FFFFFF35" : "#00000028", shape: "circle", backgroundColor: "transparent" });
  }, [dark]);

  const project = (point: Point) => ({ x: (point.lng + 180) * (800 / 360), y: (90 - point.lat) * (400 / 180) });

  return (
    <div aria-hidden="true" style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", opacity: 0.34, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: "8vh 0 0", width: "100%", height: "92vh" }}>
        <img src={`data:image/svg+xml;utf8,${encodeURIComponent(svgMap)}`} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center", opacity: 0.5, maskImage: "linear-gradient(to bottom, transparent, white 12%, white 88%, transparent)", WebkitMaskImage: "linear-gradient(to bottom, transparent, white 12%, white 88%, transparent)" }} />
        <svg viewBox="0 0 800 400" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          <defs>
            <linearGradient id="cei-world-map-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0" />
              <stop offset="8%" stopColor="#0ea5e9" stopOpacity="0.8" />
              <stop offset="92%" stopColor="#0ea5e9" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
            </linearGradient>
          </defs>
          {dots.map((dot, i) => {
            const start = project(dot.start);
            const end = project(dot.end);
            const midX = (start.x + end.x) / 2;
            const midY = Math.min(start.y, end.y) - 50;
            return (
              <g key={i}>
                <path d={`M ${start.x} ${start.y} Q ${midX} ${midY} ${end.x} ${end.y}`} fill="none" stroke="url(#cei-world-map-gradient)" strokeWidth="1" strokeDasharray="4 7">
                  <animate attributeName="stroke-dashoffset" from="22" to="0" dur="3s" begin={`${i * 0.45}s`} repeatCount="indefinite" />
                </path>
                {[start, end].map((point, pointIndex) => (
                  <circle key={pointIndex} cx={point.x} cy={point.y} r="2" fill="#0ea5e9" opacity="0.8">
                    <animate attributeName="r" from="2" to="7" dur="1.6s" begin={`${i * 0.45}s`} repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.65" to="0" dur="1.6s" begin={`${i * 0.45}s`} repeatCount="indefinite" />
                  </circle>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
