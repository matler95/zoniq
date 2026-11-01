"use client";

import maplibregl, { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

type Coordinates = { lat: number; lon: number };
export type ReachabilityMap = {
  type: "FeatureCollection";
  features: Array<{ type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] }; properties: { travel_minutes: number; name: string; route: string } }>;
};

type AccessibilityMapProps = {
  origin: Coordinates;
  reachability: ReachabilityMap | null;
  selectingOrigin: boolean;
  canSelectDestination: boolean;
  onOriginChange: (point: Coordinates) => void;
  onDestinationChange: (point: Coordinates) => void;
};

const osmStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" } },
  layers: [{ id: "osm", type: "raster", source: "osm" }]
};

export function AccessibilityMap({ origin, reachability, selectingOrigin, canSelectDestination, onOriginChange, onDestinationChange }: AccessibilityMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const originMarker = useRef<Marker | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({ container: container.current, style: osmStyle, center: [origin.lon, origin.lat], zoom: 11.5, attributionControl: { compact: true } });
    instance.addControl(new maplibregl.NavigationControl(), "bottom-right");
    instance.on("load", () => {
      instance.addSource("reachability", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      instance.addLayer({ id: "reachability-stops", type: "circle", source: "reachability", paint: {
        "circle-radius": ["interpolate", ["linear"], ["get", "travel_minutes"], 0, 12, 15, 10, 30, 8, 45, 6, 60, 5, 180, 4],
        "circle-color": ["step", ["get", "travel_minutes"], "#f35e5a", 15, "#32cce3", 30, "#68dc77", 45, "#f2d04f", 60, "#f49642"],
        "circle-opacity": 0.82, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1
      } });
      instance.on("click", "reachability-stops", event => {
        const feature = event.features?.[0];
        if (!feature || !("travel_minutes" in feature.properties!)) return;
        new maplibregl.Popup().setLngLat(event.lngLat).setHTML(`<strong>${feature.properties?.name ?? "Przystanek"}</strong><br>${feature.properties?.travel_minutes} min · linia ${feature.properties?.route ?? "—"}`).addTo(instance);
      });
      instance.on("mouseenter", "reachability-stops", () => { instance.getCanvas().style.cursor = "pointer"; });
      instance.on("mouseleave", "reachability-stops", () => { instance.getCanvas().style.cursor = ""; });
    });
    originMarker.current = new maplibregl.Marker({ color: "#087afe" }).setLngLat([origin.lon, origin.lat]).setPopup(new maplibregl.Popup().setText("Punkt startowy")).addTo(instance);
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, []);

  useEffect(() => { originMarker.current?.setLngLat([origin.lon, origin.lat]); }, [origin]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || (!selectingOrigin && !canSelectDestination)) return;
    const selectPoint = (event: maplibregl.MapMouseEvent) => {
      const point = { lat: event.lngLat.lat, lon: event.lngLat.lng };
      if (selectingOrigin) onOriginChange(point); else onDestinationChange(point);
    };
    instance.on("click", selectPoint);
    return () => { instance.off("click", selectPoint); };
  }, [canSelectDestination, onDestinationChange, onOriginChange, selectingOrigin]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !reachability) return;
    const update = () => (instance.getSource("reachability") as GeoJSONSource | undefined)?.setData(reachability);
    if (instance.isStyleLoaded()) update(); else instance.once("load", update);
  }, [reachability]);

  return <div ref={container} className="map-stage" aria-label="Mapa dostępności komunikacyjnej Warszawy." />;
}
