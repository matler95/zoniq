"use client";

import maplibregl, { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

type Coordinates = { lat: number; lon: number };
export type ReachabilityMap = {
  type: "FeatureCollection";
  features: Array<{ type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] }; properties: { travel_minutes: number; name: string; route: string; dominant_route_type?: number } }>;
};

type AccessibilityMapProps = {
  origin: Coordinates;
  destination: Coordinates | null;
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

export function AccessibilityMap({ origin, destination, reachability, selectingOrigin, canSelectDestination, onOriginChange, onDestinationChange }: AccessibilityMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const originMarker = useRef<Marker | null>(null);
  const destinationMarker = useRef<Marker | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({ container: container.current, style: osmStyle, center: [origin.lon, origin.lat], zoom: 11.5, attributionControl: { compact: true } });
    instance.addControl(new maplibregl.NavigationControl(), "bottom-right");
    instance.on("load", () => {
      instance.addSource("reachability", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      instance.addLayer({ id: "reachability-surface", type: "heatmap", source: "reachability", paint: {
        "heatmap-weight": ["*", ["interpolate", ["linear"], ["get", "travel_minutes"], 0, 1, 15, 0.95, 30, 0.72, 45, 0.45, 60, 0.25, 180, 0.05], ["coalesce", ["get", "reachable_probability"], 1]],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 9, 0.7, 12, 1.5, 14, 2],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 9, 20, 11, 35, 13, 50],
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(0,0,0,0)", 0.15, "rgba(47,204,227,0.14)", 0.35, "rgba(104,220,119,0.3)", 0.6, "rgba(242,208,79,0.46)", 0.82, "rgba(244,150,66,0.62)", 1, "rgba(243,94,90,0.76)"],
        "heatmap-opacity": 0.85
      } });
      instance.addLayer({ id: "reachability-stops", type: "circle", source: "reachability", paint: {
        "circle-radius": ["interpolate", ["linear"], ["get", "travel_minutes"], 0, 12, 15, 10, 30, 8, 45, 6, 60, 5, 180, 4],
        "circle-color": ["step", ["get", "travel_minutes"], "#f35e5a", 15, "#32cce3", 30, "#68dc77", 45, "#f2d04f", 60, "#f49642"],
        "circle-opacity": ["interpolate", ["linear"], ["coalesce", ["get", "reachable_probability"], 1], 0, 0.15, 1, 0.86],
        "circle-stroke-color": ["match", ["coalesce", ["get", "dominant_route_type"], -1], 0, "#ff554b", 1, "#3487ff", 2, "#f6f8ff", 3, "#ffe150", "#ffffff"], "circle-stroke-width": 2
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
    if (!map.current || !destination) return;
    destinationMarker.current?.remove();
    destinationMarker.current = new maplibregl.Marker({ color: "#f15246" }).setLngLat([destination.lon, destination.lat]).setPopup(new maplibregl.Popup().setText("Wybrany cel")).addTo(map.current);
  }, [destination]);

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
