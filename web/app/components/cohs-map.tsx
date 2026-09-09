"use client";

import { useEffect, useRef, useState } from "react";
import "mapbox-gl/dist/mapbox-gl.css";

type Plan = {
  id: string;
  name: string;
  coverage: string;
  headquarters: string;
  coordinates: [number, number];
  logo: string;
  source: string;
  accent: string;
};

const plans: Plan[] = [
  {
    id: "partnership",
    name: "Partnership HealthPlan of California",
    coverage: "North Coast and North State counties",
    headquarters: "Fairfield / regional service area",
    coordinates: [-122.13, 38.25],
    logo: "/logos/partnership-healthplan.png",
    source: "https://www.partnershiphp.org/",
    accent: "#7f1d1d",
  },
  {
    id: "alliance",
    name: "Central California Alliance for Health",
    coverage: "Monterey, Santa Cruz, and Merced counties",
    headquarters: "Scotts Valley",
    coordinates: [-121.02, 37.22],
    logo: "/logos/central-california-alliance.png",
    source: "https://thealliance.health/",
    accent: "#075985",
  },
  {
    id: "hpsm",
    name: "Health Plan of San Mateo",
    coverage: "San Mateo County",
    headquarters: "South San Francisco",
    coordinates: [-122.41, 37.56],
    logo: "/logos/health-plan-san-mateo.png",
    source: "https://www.hpsm.org/",
    accent: "#0891b2",
  },
  {
    id: "caloptima",
    name: "CalOptima Health",
    coverage: "Orange County",
    headquarters: "Orange",
    coordinates: [-117.85, 33.79],
    logo: "/logos/caloptima-health.jpg",
    source: "https://www.caloptima.org/",
    accent: "#7c3aed",
  },
  {
    id: "cencal",
    name: "CenCal Health",
    coverage: "Santa Barbara and San Luis Obispo counties",
    headquarters: "Santa Barbara",
    coordinates: [-119.70, 34.42],
    logo: "/logos/cencal-health.png",
    source: "https://www.cencalhealth.org/",
    accent: "#0f766e",
  },
  {
    id: "gold-coast",
    name: "Gold Coast Health Plan",
    coverage: "Ventura County",
    headquarters: "Camarillo",
    coordinates: [-119.04, 34.22],
    logo: "/logos/gold-coast-health-plan.jpg",
    source: "https://www.goldcoasthealthplan.org/",
    accent: "#1d4ed8",
  },
];

function PlanLogo({ plan, small = false }: { plan: Plan; small?: boolean }) {
  return (
    <div className={`cohs-logo ${small ? "cohs-logo-small" : ""}`} style={{ borderColor: plan.accent }}>
      <img src={plan.logo} alt={`${plan.name} logo`} />
    </div>
  );
}

export default function CohsMap() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<{ remove: () => void } | null>(null);
  const [selected, setSelected] = useState<Plan>(plans[4]);
  const [mapboxActive, setMapboxActive] = useState(false);

  useEffect(() => {
    const token = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;
    if (!token || !mapContainer.current) return;

    let cancelled = false;
    import("mapbox-gl").then((mapboxgl) => {
      if (cancelled || !mapContainer.current) return;
      mapboxgl.default.accessToken = token;
      const map = new mapboxgl.default.Map({
        container: mapContainer.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [-119.5, 36.7],
        zoom: 5.65,
        attributionControl: true,
      });
      mapRef.current = map;
      setMapboxActive(true);
      map.on("load", () => {
        plans.forEach((plan) => {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "cohs-map-marker";
          el.ariaLabel = `Open ${plan.name}`;
          el.innerHTML = `<img src="${plan.logo}" alt="" />`;
          el.addEventListener("click", () => setSelected(plan));
          new mapboxgl.default.Marker({ element: el, anchor: "bottom" })
            .setLngLat(plan.coordinates)
            .addTo(map);
        });
      });
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="cohs-map-shell">
      <div className="cohs-map-canvas" ref={mapContainer}>
        {!mapboxActive && (
          <div className="cohs-fallback-map" aria-label="California COHS plan map fallback">
            <div className="cohs-state-shape" aria-hidden="true" />
            {plans.map((plan, index) => (
              <button
                className={`cohs-fallback-marker marker-${index}`}
                key={plan.id}
                type="button"
                onClick={() => setSelected(plan)}
                aria-label={`Open ${plan.name}`}
              >
                <img src={plan.logo} alt="" />
              </button>
            ))}
            <div className="cohs-fallback-note">Mapbox-ready · configure NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN for live tiles</div>
          </div>
        )}
      </div>
      <aside className="cohs-map-card" aria-live="polite">
        <div className="cohs-card-kicker">Selected COHS plan</div>
        <PlanLogo plan={selected} />
        <h3>{selected.name}</h3>
        <p className="cohs-card-coverage">{selected.coverage}</p>
        <dl>
          <div><dt>Operational hub</dt><dd>{selected.headquarters}</dd></div>
          <div><dt>Map role</dt><dd>Plan identity and service-area orientation</dd></div>
        </dl>
        <a href={selected.source} target="_blank" rel="noreferrer">Open official plan site ↗</a>
        <p className="cohs-card-disclaimer">Plan logos are used for identification. County service areas and operational responsibility should be verified against current DHCS and plan sources.</p>
      </aside>
      <div className="cohs-map-legend">
        {plans.map((plan) => (
          <button type="button" key={plan.id} onClick={() => setSelected(plan)} className="cohs-legend-item">
            <PlanLogo plan={plan} small />
            <span>{plan.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
