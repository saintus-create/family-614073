import DottedMap from "dotted-map";

type Point = { lat: number; lng: number };
type Dot = { start: Point; end: Point };

const dots: Dot[] = [
  { start: { lat: 37.7749, lng: -122.4194 }, end: { lat: 34.0522, lng: -118.2437 } },
  { start: { lat: 34.0522, lng: -118.2437 }, end: { lat: 40.7128, lng: -74.006 } },
  { start: { lat: 37.7749, lng: -122.4194 }, end: { lat: 47.6062, lng: -122.3321 } },
  { start: { lat: 34.0522, lng: -118.2437 }, end: { lat: 19.4326, lng: -99.1332 } },
];

const map = new DottedMap({ height: 60, grid: "diagonal" });
const svgMap = map.getSVG({
  radius: 0.22,
  color: "#00000030",
  shape: "circle",
  backgroundColor: "transparent",
});

function project(point: Point) {
  return {
    x: (point.lng + 180) * (800 / 360),
    y: (90 - point.lat) * (400 / 180),
  };
}

function path(start: Point, end: Point) {
  const a = project(start);
  const b = project(end);
  const midX = (a.x + b.x) / 2;
  const midY = Math.min(a.y, b.y) - 50;
  return { a, b, d: `M ${a.x} ${a.y} Q ${midX} ${midY} ${b.x} ${b.y}` };
}

export function WorldMapBackground() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
        overflow: "hidden",
        opacity: 0.32,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "4vh 0 0",
          width: "100%",
          height: "96vh",
        }}
      >
        <img
          src={`data:image/svg+xml;utf8,${encodeURIComponent(svgMap)}`}
          alt=""
          draggable={false}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center",
            opacity: 0.55,
            maskImage: "linear-gradient(to bottom, transparent, white 10%, white 90%, transparent)",
            WebkitMaskImage: "linear-gradient(to bottom, transparent, white 10%, white 90%, transparent)",
          }}
        />
        <svg
          viewBox="0 0 800 400"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
          <defs>
            <linearGradient id="world-map-line" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="white" stopOpacity="0" />
              <stop offset="5%" stopColor="#0ea5e9" stopOpacity="1" />
              <stop offset="95%" stopColor="#0ea5e9" stopOpacity="1" />
              <stop offset="100%" stopColor="white" stopOpacity="0" />
            </linearGradient>
          </defs>
          {dots.map((dot, i) => {
            const p = path(dot.start, dot.end);
            return (
              <g key={i}>
                <path
                  d={p.d}
                  fill="none"
                  stroke="url(#world-map-line)"
                  strokeWidth="1"
                  pathLength="1"
                  strokeDasharray="0.08 0.04"
                >
                  <animate
                    attributeName="stroke-dashoffset"
                    from="0.12"
                    to="0"
                    dur="2.4s"
                    begin={`${i * 0.45}s`}
                    repeatCount="indefinite"
                  />
                </path>
                <circle cx={p.a.x} cy={p.a.y} r="2" fill="#0ea5e9">
                  <animate attributeName="r" from="2" to="8" dur="1.5s" begin={`${i * 0.45}s`} repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.6" to="0" dur="1.5s" begin={`${i * 0.45}s`} repeatCount="indefinite" />
                </circle>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export default WorldMapBackground;
