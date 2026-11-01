"use client";

import maplibregl, { Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

type Coordinates = { lat: number; lon: number };

type AccessibilityMapProps = {
  origin: Coordinates;
  destination: Coordinates | null;
  onDestinationChange: (point: Coordinates) => void;
};

const osmStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors"
    }
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }]
};

export function AccessibilityMap({ origin, destination, onDestinationChange }: AccessibilityMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const destinationMarker = useRef<Marker | null>(null);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({
      container: container.current,
      style: osmStyle,
      center: [origin.lon, origin.lat],
      zoom: 11.5,
      attributionControl: { compact: true }
    });
    instance.addControl(new maplibregl.NavigationControl(), "bottom-right");
    new maplibregl.Marker({ color: "#087afe" }).setLngLat([origin.lon, origin.lat]).setPopup(new maplibregl.Popup().setText("Punkt startowy")).addTo(instance);
    instance.on("click", event => onDestinationChange({ lat: event.lngLat.lat, lon: event.lngLat.lng }));
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, [onDestinationChange, origin.lat, origin.lon]);

  useEffect(() => {
    if (!map.current || !destination) return;
    destinationMarker.current?.remove();
    destinationMarker.current = new maplibregl.Marker({ color: "#f15246" })
      .setLngLat([destination.lon, destination.lat])
      .setPopup(new maplibregl.Popup().setText("Punkt docelowy"))
      .addTo(map.current);
  }, [destination]);

  return <div ref={container} className="map-stage" aria-label="Interaktywna mapa Warszawy. Kliknij punkt docelowy." />;
}
