"use client";

import { FormEvent, useCallback, useMemo, useState } from "react";
import { AccessibilityMap } from "./accessibility-map";

const modes = ["pieszo", "autobus", "tramwaj", "metro", "SKM", "KM", "WKD"];
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const defaultOrigin = { lat: 52.196, lon: 21.022 };
type Point = { lat: number; lon: number };
type Journey = { route: string; duration_minutes: number; access_walk_minutes: number; egress_walk_minutes: number; departure_seconds: number; arrival_seconds: number; transfers?: number };

function toTime(seconds: number) { return `${String(Math.floor(seconds / 3600) % 24).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}`; }

export function ScenarioWorkspace() {
  const [originLabel, setOriginLabel] = useState("ul. Puławska 100, Warszawa");
  const [limit, setLimit] = useState(60);
  const [selectedModes, setSelectedModes] = useState(modes);
  const [date, setDate] = useState("2026-11-02");
  const [time, setTime] = useState("08:00");
  const [destination, setDestination] = useState<Point | null>(null);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState("Kliknij mapę, aby wybrać punkt docelowy.");
  const weekday = useMemo(() => new Intl.DateTimeFormat("pl-PL", { weekday: "long" }).format(new Date(`${date}T12:00:00`)), [date]);
  const onDestinationChange = useCallback((point: Point) => { setDestination(point); setJourneys([]); setNotice(`Cel wybrany: ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}. Możesz wyszukać trasę.`); }, []);

  function toggleMode(mode: string) { setSelectedModes(current => current.includes(mode) ? current.filter(item => item !== mode) : [...current, mode]); }

  async function simulate(event: FormEvent) {
    event.preventDefault(); setIsLoading(true); setNotice("Przygotowuję scenariusz…");
    try {
      const response = await fetch(`${API_URL}/api/simulations`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ origin_label: originLabel, max_travel_time_minutes: limit, transport_modes: selectedModes.map(mode => mode.toLowerCase()) }) });
      if (!response.ok) throw new Error();
      const result = await response.json(); setNotice(`Scenariusz ${result.simulation_id} utworzony. Wybierz cel na mapie.`);
    } catch { setNotice("Nie mogę połączyć się z API. Uruchom FastAPI na porcie 8000."); }
    finally { setIsLoading(false); }
  }

  async function findJourney() {
    if (!destination) { setNotice("Najpierw kliknij punkt docelowy na mapie."); return; }
    setIsLoading(true); setNotice("Szukam planowych połączeń…");
    try {
      const response = await fetch(`${API_URL}/api/journeys`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ origin: defaultOrigin, destination, journey_date: date, departure_time: time }) });
      if (!response.ok) throw new Error();
      const result = await response.json(); setJourneys(result.journeys); setNotice(result.journeys.length ? "Pokazuję najbliższe warianty zgodne z rozkładem." : "Brak wariantu bezpośredniego ani z jedną przesiadką w wybranym czasie.");
    } catch { setNotice("Nie mogę połączyć się z przygotowanym indeksem GTFS."); }
    finally { setIsLoading(false); }
  }

  const journey = journeys[0];
  return <main>
    <header className="topbar"><div className="brand"><span className="mark">◌</span><span>zoniq</span></div><p>Dokąd dotrzesz w określonym czasie?</p><span className="badge">Warszawa · rozkłady planowe</span></header>
    <section className="workspace">
      <form className="controls panel" onSubmit={simulate}>
        <div><span className="eyebrow">SCENARIUSZ</span><h1>Sprawdź dostępność</h1><p className="muted">Wyszukiwanie obejmuje kursy bezpośrednie i jedną przesiadkę.</p></div>
        <label>Start<input value={originLabel} onChange={event => setOriginLabel(event.target.value)} aria-label="Punkt początkowy" /></label>
        <div className="split"><label>Data<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label><label>Godzina<input type="time" value={time} onChange={event => setTime(event.target.value)} /></label></div><span className="weekday">{weekday}</span>
        <fieldset><legend>Maksymalny czas podróży</legend><div className="pills">{[15, 30, 45, 60, 90, 120].map(value => <button type="button" className={value === limit ? "active" : ""} onClick={() => setLimit(value)} key={value}>{value} min</button>)}</div></fieldset>
        <fieldset><legend>Środki transportu</legend><div className="modes">{modes.map(mode => <label key={mode}><input type="checkbox" checked={selectedModes.includes(mode)} onChange={() => toggleMode(mode)} />{mode}</label>)}</div></fieldset>
        <button className="primary" disabled={isLoading}>{isLoading ? "Obliczam…" : "Utwórz scenariusz"}</button>
      </form>
      <section className="map panel" aria-label="Interaktywna mapa dostępności"><div className="map-header"><div><span className="eyebrow">MAPA WARSZAWY</span><h2>Kliknij punkt docelowy</h2></div><button type="button" className="route-button" onClick={findJourney} disabled={isLoading || !destination}>Szukaj połączenia</button></div><AccessibilityMap origin={defaultOrigin} destination={destination} onDestinationChange={onDestinationChange} /><p className="notice">{notice}</p></section>
      <aside className="details panel"><span className="eyebrow">NAJLEPSZY WARIANT</span><h2>{destination ? "Wybrany punkt" : "Wybierz cel"}</h2>{journey ? <><div className="metric"><strong>{Math.round(journey.duration_minutes)} min</strong><span>kurs planowy</span></div><div className="journey"><h3>Linia {journey.route}</h3><p><b>{toTime(journey.departure_seconds)}</b> odjazd z pobliskiego przystanku</p><p><b>{toTime(journey.arrival_seconds)}</b> przyjazd</p><p><b>{journey.access_walk_minutes.toFixed(0)} + {journey.egress_walk_minutes.toFixed(0)} min</b> dojścia piesze</p></div><dl><div><dt>Przesiadki</dt><dd>{journey.transfers ?? 0}</dd></div><div><dt>Alternatywy</dt><dd>{Math.max(0, journeys.length - 1)}</dd></div><div><dt>Dane</dt><dd>GTFS ZTM</dd></div></dl></> : <p className="muted">Wybierz cel na mapie i uruchom wyszukiwanie. Wynik obejmuje kursy zgodne z datą i godziną, z maksymalnie jedną przesiadką.</p>}<p className="attribution">Dane rozkładowe: ZTM Warszawa, Mikołaj Kuranowski. Mapa © OpenStreetMap contributors.</p></aside>
    </section>
  </main>;
}
