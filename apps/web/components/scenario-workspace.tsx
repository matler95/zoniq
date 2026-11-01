"use client";

import { FormEvent, useCallback, useMemo, useState } from "react";
import { AccessibilityMap, ReachabilityMap } from "./accessibility-map";

const modes = ["pieszo", "autobus", "tramwaj", "metro", "SKM", "KM", "WKD"];
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const defaultOrigin = { lat: 52.196, lon: 21.022 };
type Point = { lat: number; lon: number };
type Simulation = { simulation_id: string; map_data_url: string; reachable_stops: number; disclaimer: string; data_version: string };
type GeocodeResult = { label: string; lat: number; lon: number };

export function ScenarioWorkspace() {
  const [originLabel, setOriginLabel] = useState("ul. Puławska 100, Warszawa");
  const [origin, setOrigin] = useState<Point>(defaultOrigin);
  const [limit, setLimit] = useState(60);
  const [customLimit, setCustomLimit] = useState("");
  const [selectedModes, setSelectedModes] = useState(modes);
  const [date, setDate] = useState("2026-11-02");
  const [time, setTime] = useState("08:00");
  const [isChoosingOrigin, setIsChoosingOrigin] = useState(false);
  const [mapData, setMapData] = useState<ReachabilityMap | null>(null);
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [geocodeResults, setGeocodeResults] = useState<GeocodeResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState("Ustaw punkt startowy, parametry i wygeneruj mapę zasięgu.");
  const weekday = useMemo(() => new Intl.DateTimeFormat("pl-PL", { weekday: "long" }).format(new Date(`${date}T12:00:00`)), [date]);

  const onOriginChange = useCallback((point: Point) => {
    setOrigin(point); setOriginLabel(`Punkt na mapie: ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`); setIsChoosingOrigin(false);
    setMapData(null); setSimulation(null); setNotice("Punkt startowy wybrany. Wygeneruj mapę dostępności.");
  }, []);

  function toggleMode(mode: string) { setSelectedModes(current => current.includes(mode) ? current.filter(item => item !== mode) : [...current, mode]); }
  function setPreset(value: number) { setLimit(value); setCustomLimit(""); }
  function setCustom(value: string) { setCustomLimit(value); const minutes = Number(value); if (Number.isFinite(minutes) && minutes >= 5 && minutes <= 180) setLimit(minutes); }

  async function searchOrigin() {
    setNotice("Szukam adresu…"); setGeocodeResults([]);
    try {
      const response = await fetch(`${API_URL}/api/geocode?q=${encodeURIComponent(originLabel)}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Nie udało się wyszukać adresu.");
      setGeocodeResults(result.results); setNotice(result.results.length ? "Wybierz właściwy adres z listy." : "Nie znaleziono adresu. Spróbuj podać ulicę i numer.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Nie mogę połączyć się z usługą adresową."); }
  }

  async function simulate(event: FormEvent) {
    event.preventDefault();
    if (!selectedModes.some(mode => mode !== "pieszo")) { setNotice("Wybierz co najmniej jeden środek transportu."); return; }
    setIsLoading(true); setNotice("Liczymy planową dostępność przystanków…");
    try {
      const response = await fetch(`${API_URL}/api/simulations`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ origin, origin_label: originLabel, journey_date: date, departure_time: time, max_travel_time_minutes: limit, transport_modes: selectedModes.map(mode => ({ "pieszo": "walk", "autobus": "bus", "tramwaj": "tram", "metro": "metro", SKM: "skm", KM: "km", WKD: "wkd" })[mode]) })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Nie udało się utworzyć symulacji.");
      const mapResponse = await fetch(`${API_URL}${result.map_data_url}`);
      if (!mapResponse.ok) throw new Error("Nie udało się pobrać warstwy mapy.");
      setMapData(await mapResponse.json()); setSimulation(result);
      setNotice(`Pokazuję ${result.reachable_stops} osiągalnych przystanków w limicie ${limit} min.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Nie mogę połączyć się z API."); }
    finally { setIsLoading(false); }
  }

  return <main>
    <header className="topbar"><div className="brand"><span className="mark">◌</span><span>zoniq</span></div><p>Dokąd dotrzesz w określonym czasie?</p><span className="badge">Warszawa · rozkłady planowe</span></header>
    <section className="workspace">
      <form className="controls panel" onSubmit={simulate}>
        <div><span className="eyebrow">SCENARIUSZ</span><h1>Mapa dostępności</h1><p className="muted">Wskaż start i zobacz obszary osiągalne w wybranym czasie.</p></div>
        <label>Start<input value={originLabel} onChange={event => { setOriginLabel(event.target.value); setGeocodeResults([]); }} aria-label="Punkt początkowy" /><div className="address-actions"><button className="route-button" type="button" onClick={searchOrigin}>Znajdź adres</button><button className="route-button" type="button" onClick={() => { setIsChoosingOrigin(true); setNotice("Kliknij mapę, aby ustawić punkt startowy."); }}>Wybierz na mapie</button></div></label>{geocodeResults.length > 0 && <ul className="address-results">{geocodeResults.map(result => <li key={`${result.lat}:${result.lon}`}><button type="button" onClick={() => onOriginChange(result)}>{result.label}</button></li>)}</ul>}
        <div className="split"><label>Data<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label><label>Godzina<input type="time" value={time} onChange={event => setTime(event.target.value)} /></label></div><span className="weekday">{weekday}</span>
        <fieldset><legend>Limit podróży</legend><div className="pills">{[15, 30, 45, 60].map(value => <button type="button" className={value === limit && !customLimit ? "active" : ""} onClick={() => setPreset(value)} key={value}>{value} min</button>)}</div><label className="custom-limit">Własny limit (5–180 min)<input inputMode="numeric" value={customLimit} placeholder="np. 75" onChange={event => setCustom(event.target.value)} /></label></fieldset>
        <fieldset><legend>Środki transportu</legend><div className="modes">{modes.map(mode => <label key={mode}><input type="checkbox" checked={selectedModes.includes(mode)} onChange={() => toggleMode(mode)} />{mode}</label>)}</div></fieldset>
        <button className="primary" disabled={isLoading}>{isLoading ? "Obliczam…" : "Generuj mapę zasięgu"}</button>
      </form>
      <section className="map panel" aria-label="Interaktywna mapa dostępności"><div className="map-header"><div><span className="eyebrow">MAPA WARSZAWY</span><h2>{isChoosingOrigin ? "Kliknij punkt startowy" : "Zasięg komunikacyjny"}</h2></div><div className="legend"><span><i className="band-15" />do 15 min</span><span><i className="band-30" />do 30 min</span><span><i className="band-45" />do 45 min</span><span><i className="band-60" />do {limit} min</span></div></div><AccessibilityMap origin={origin} reachability={mapData} selectingOrigin={isChoosingOrigin} onOriginChange={onOriginChange} /><p className="notice">{notice}</p></section>
      <aside className="details panel"><span className="eyebrow">WYNIK SCENARIUSZA</span><h2>{simulation ? `${limit} minut od startu` : "Czeka na symulację"}</h2>{simulation ? <><div className="metric"><strong>{simulation.reachable_stops}</strong><span>osiągalnych przystanków</span></div><p className="muted">Kolor punktu oznacza najszybszy planowy czas dotarcia, wraz z oczekiwaniem i dojściem do pierwszego przystanku.</p><dl><div><dt>Start</dt><dd>{origin.lat.toFixed(3)}, {origin.lon.toFixed(3)}</dd></div><div><dt>Wersja danych</dt><dd>{simulation.data_version}</dd></div><div><dt>Limit</dt><dd>{limit} min</dd></div></dl><p className="muted">{simulation.disclaimer}</p></> : <p className="muted">Ta mapa odpowie najpierw na pytanie „dokąd dojadę?”. Szczegóły konkretnego celu będą kolejną warstwą po kliknięciu wyniku.</p>}<p className="attribution">Dane rozkładowe: ZTM Warszawa, Mikołaj Kuranowski. Mapa © OpenStreetMap contributors.</p></aside>
    </section>
  </main>;
}
