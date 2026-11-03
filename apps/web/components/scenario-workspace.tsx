"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AccessibilityMap, MapExporter, MapView, ReachabilityMap } from "./accessibility-map";

const modes = ["pieszo", "autobus", "tramwaj", "metro", "SKM", "KM", "WKD"];
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const defaultOrigin = { lat: 52.196, lon: 21.022 };
type Point = { lat: number; lon: number };
type Simulation = { simulation_id: string; status: "processing" | "completed" | "failed"; map_data_url: string; reachable_stops: number; disclaimer: string; data_version: string; data_imported_at?: string | null; time_bands: Record<string, number>; sample_count: number };
type GeocodeResult = { label: string; lat: number; lon: number };
type Journey = { route: string; duration_minutes: number; access_walk_minutes: number; egress_walk_minutes: number; departure_seconds: number; arrival_seconds: number; transfers?: number };

function toTime(seconds: number) { return `${String(Math.floor(seconds / 3600) % 24).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}`; }

export function ScenarioWorkspace() {
  const [originLabel, setOriginLabel] = useState("ul. Puławska 100, Warszawa");
  const [origin, setOrigin] = useState<Point>(defaultOrigin);
  const [limit, setLimit] = useState(60);
  const [customLimit, setCustomLimit] = useState("");
  const [selectedModes, setSelectedModes] = useState(modes);
  const [date, setDate] = useState("2026-11-02");
  const [time, setTime] = useState("08:00");
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [isChoosingOrigin, setIsChoosingOrigin] = useState(false);
  const [mapData, setMapData] = useState<ReachabilityMap | null>(null);
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [geocodeResults, setGeocodeResults] = useState<GeocodeResult[]>([]);
  const [destination, setDestination] = useState<Point | null>(null);
  const [destinationLabel, setDestinationLabel] = useState<string | null>(null);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState("Ustaw punkt startowy, parametry i wygeneruj mapę zasięgu.");
  const [mapView, setMapView] = useState<MapView>("reachability");
  const exporterRef = useRef<MapExporter | null>(null);
  const weekday = useMemo(() => new Intl.DateTimeFormat("pl-PL", { weekday: "long" }).format(new Date(`${date}T12:00:00`)), [date]);

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    const simulationId = parameters.get("sim");
    if (!simulationId) return;
    const latitude = Number(parameters.get("lat"));
    const longitude = Number(parameters.get("lon"));
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) setOrigin({ lat: latitude, lon: longitude });
    if (parameters.get("label")) setOriginLabel(parameters.get("label")!);
    if (parameters.get("date")) setDate(parameters.get("date")!);
    if (parameters.get("time")) setTime(parameters.get("time")!);
    const sharedLimit = Number(parameters.get("limit"));
    if (Number.isFinite(sharedLimit) && sharedLimit >= 5 && sharedLimit <= 180) setLimit(sharedLimit);
    const sharedWindow = Number(parameters.get("window"));
    if ([1, 15, 30, 60].includes(sharedWindow)) setWindowMinutes(sharedWindow);
    const sharedModes = parameters.get("modes")?.split(",").filter(mode => modes.includes(mode));
    if (sharedModes?.length) setSelectedModes(sharedModes);
    setNotice("Otwieram udostępnioną analizę…");
    void (async () => {
      try {
        const statusResponse = await fetch(`${API_URL}/api/simulations/${simulationId}`);
        if (!statusResponse.ok) throw new Error("Udostępniona analiza nie jest już dostępna.");
        const completed = await statusResponse.json() as Simulation;
        if (completed.status !== "completed") throw new Error("Udostępniona analiza nie została jeszcze ukończona.");
        const mapResponse = await fetch(`${API_URL}${completed.map_data_url}`);
        if (!mapResponse.ok) throw new Error("Nie udało się odczytać mapy udostępnionej analizy.");
        setSimulation(completed); setMapData(await mapResponse.json());
        setNotice("Otworzono udostępnioną analizę.");
      } catch (error) { setNotice(error instanceof Error ? error.message : "Nie udało się otworzyć analizy."); }
    })();
  }, []);

  const onOriginChange = useCallback((point: Point) => {
    setOrigin(point); setOriginLabel(`Punkt na mapie: ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`); setIsChoosingOrigin(false);
    setMapData(null); setSimulation(null); window.history.replaceState(null, "", window.location.pathname); setNotice("Punkt startowy wybrany. Wygeneruj mapę dostępności.");
  }, []);

  function toggleMode(mode: string) { setSelectedModes(current => current.includes(mode) ? current.filter(item => item !== mode) : [...current, mode]); }
  function setPreset(value: number) { setLimit(value); setCustomLimit(""); }
  function setCustom(value: string) { setCustomLimit(value); const minutes = Number(value); if (Number.isFinite(minutes) && minutes >= 5 && minutes <= 180) setLimit(minutes); }

  function shareScenario(simulationId: string) {
    const parameters = new URLSearchParams({ sim: simulationId, lat: String(origin.lat), lon: String(origin.lon), label: originLabel, date, time, window: String(windowMinutes), limit: String(limit), modes: selectedModes.join(",") });
    const url = `${window.location.origin}${window.location.pathname}?${parameters.toString()}`;
    window.history.replaceState(null, "", `${window.location.pathname}?${parameters.toString()}`);
    return url;
  }

  async function copyShareLink() {
    if (!simulation) return;
    const url = shareScenario(simulation.simulation_id);
    try { await navigator.clipboard.writeText(url); setNotice("Link do analizy skopiowany do schowka."); }
    catch { setNotice(`Skopiuj adres z paska przeglądarki, aby udostępnić analizę.`); }
  }

  function exportMap() {
    if (!simulation || !exporterRef.current) return;
    try { exporterRef.current(`${originLabel} · ${date}, ${time} · do ${limit} min`); setNotice("Pobrano obraz PNG mapy dostępności."); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Nie udało się wyeksportować mapy."); }
  }

  async function searchOrigin() {
    setNotice("Szukam adresu…"); setGeocodeResults([]);
    try {
      const response = await fetch(`${API_URL}/api/geocode?q=${encodeURIComponent(originLabel)}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Nie udało się wyszukać adresu.");
      setGeocodeResults(result.results); setNotice(result.results.length ? "Wybierz właściwy adres z listy." : "Nie znaleziono adresu. Spróbuj podać ulicę i numer.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Nie mogę połączyć się z usługą adresową."); }
  }

  const onDestinationChange = useCallback(async (point: Point) => {
    if (!simulation) return;
    setDestination(point); setDestinationLabel(null); setJourneys([]); setNotice("Sprawdzam dokładne połączenie do wybranego punktu…");
    void fetch(`${API_URL}/api/reverse-geocode?lat=${point.lat}&lon=${point.lon}`).then(response => response.ok ? response.json() : null).then(result => setDestinationLabel(result?.label ?? null)).catch(() => undefined);
    try {
      const response = await fetch(`${API_URL}/api/journeys`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ origin, destination: point, journey_date: date, departure_time: time, max_transfers: 2, transport_modes: selectedModes.map(mode => ({ "pieszo": "walk", "autobus": "bus", "tramwaj": "tram", "metro": "metro", SKM: "skm", KM: "km", WKD: "wkd" })[mode]) }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Nie udało się wyznaczyć trasy.");
      setJourneys(result.journeys); setNotice(result.journeys.length ? "Pokazuję najlepszy wariant do wybranego punktu." : "W tym zakresie nie znaleziono wariantu zgodnego z filtrami.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Nie udało się sprawdzić punktu."); }
  }, [date, origin, selectedModes, simulation, time]);

  async function simulate(event: FormEvent) {
    event.preventDefault();
    if (!selectedModes.some(mode => mode !== "pieszo")) { setNotice("Wybierz co najmniej jeden środek transportu."); return; }
    setIsLoading(true); setNotice("Liczymy planową dostępność przystanków…");
    try {
      const response = await fetch(`${API_URL}/api/simulations`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ origin, origin_label: originLabel, journey_date: date, departure_time: time, departure_window_minutes: windowMinutes, max_travel_time_minutes: limit, max_transfers: 2, transport_modes: selectedModes.map(mode => ({ "pieszo": "walk", "autobus": "bus", "tramwaj": "tram", "metro": "metro", SKM: "skm", KM: "km", WKD: "wkd" })[mode]) })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Nie udało się utworzyć symulacji.");
      let completed = result as Simulation;
      for (let attempt = 0; completed.status === "processing" && attempt < 180; attempt += 1) {
        setNotice(`Obliczam dostępność po OSM… ${Math.min(99, Math.round((attempt + 1) / 180 * 100))}%`);
        await new Promise(resolve => window.setTimeout(resolve, 1_000));
        const statusResponse = await fetch(`${API_URL}/api/simulations/${result.simulation_id}`);
        if (!statusResponse.ok) throw new Error("Nie udało się odczytać statusu symulacji.");
        completed = await statusResponse.json();
      }
      if (completed.status === "failed") throw new Error(completed.disclaimer);
      if (completed.status !== "completed") throw new Error("Obliczanie trwa zbyt długo — spróbuj krótszego okna analizy.");
      const mapResponse = await fetch(`${API_URL}${completed.map_data_url}`);
      if (!mapResponse.ok) throw new Error("Nie udało się pobrać warstwy mapy.");
      setMapData(await mapResponse.json()); setSimulation(completed); shareScenario(completed.simulation_id); setDestination(null); setDestinationLabel(null); setJourneys([]);
      setNotice(`Pokazuję ${completed.reachable_stops} osiągalnych przystanków w limicie ${limit} min.`);
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
        <label>Okno analizy<select value={windowMinutes} onChange={event => setWindowMinutes(Number(event.target.value))}><option value={15}>15 minut</option><option value={30}>30 minut</option><option value={60}>60 minut</option></select><span className="muted">Start co minutę; wynik jest uśredniony.</span></label>
        <fieldset><legend>Limit podróży</legend><div className="pills">{[15, 30, 45, 60].map(value => <button type="button" className={value === limit && !customLimit ? "active" : ""} onClick={() => setPreset(value)} key={value}>{value} min</button>)}</div><label className="custom-limit">Własny limit (5–180 min)<input inputMode="numeric" value={customLimit} placeholder="np. 75" onChange={event => setCustom(event.target.value)} /></label></fieldset>
        <fieldset><legend>Środki transportu</legend><div className="modes">{modes.map(mode => <label key={mode}><input type="checkbox" checked={selectedModes.includes(mode)} onChange={() => toggleMode(mode)} />{mode}</label>)}</div></fieldset>
        <button className="primary" disabled={isLoading}>{isLoading ? "Obliczam…" : "Generuj mapę zasięgu"}</button>
      </form>
      <section className="map panel" aria-label="Interaktywna mapa dostępności"><div className="map-header"><div><span className="eyebrow">MAPA WARSZAWY</span><h2>{isChoosingOrigin ? "Kliknij punkt startowy" : simulation ? "Kliknij cel, aby sprawdzić trasę" : "Zasięg komunikacyjny"}</h2><div className="map-tools"><div className="view-switch" aria-label="Tryb mapy"><button type="button" className={mapView === "reachability" ? "active" : ""} onClick={() => setMapView("reachability")}>Zasięg</button><button type="button" className={mapView === "time" ? "active" : ""} onClick={() => setMapView("time")}>Czas</button><button type="button" className={mapView === "modes" ? "active" : ""} onClick={() => setMapView("modes")}>Środki</button></div>{simulation && <><button type="button" className="route-button" onClick={copyShareLink}>Kopiuj link</button><button type="button" className="route-button" onClick={exportMap}>Eksport PNG</button></>}</div></div><div className="legend">{mapView === "modes" ? <><span><b className="mode-bus" /> autobus</span><span><b className="mode-tram" /> tramwaj</span><span><b className="mode-metro" /> metro</span><span><b className="mode-rail" /> kolej</span><em>Kolor punktu oznacza dominujący środek w najlepszym wariancie.</em></> : <><span><i className="band-15" />do 15 min</span><span><i className="band-30" />do 30 min</span><span><i className="band-45" />do 45 min</span><span><i className="band-60" />do {limit} min</span><em>{mapView === "time" ? "Krycie punktu oznacza prawdopodobieństwo dotarcia." : "Obwód punktu oznacza dominujący środek."}</em></>}</div></div><AccessibilityMap origin={origin} destination={destination} reachability={mapData} selectingOrigin={isChoosingOrigin} canSelectDestination={Boolean(simulation)} view={mapView} exporterRef={exporterRef} onOriginChange={onOriginChange} onDestinationChange={onDestinationChange} /><p className="notice">{notice}</p></section>
      <aside className="details panel"><span className="eyebrow">{destination ? "WYBRANY CEL" : "WYNIK SCENARIUSZA"}</span><h2>{destinationLabel ?? (destination ? "Szczegóły podróży" : simulation ? `${limit} minut od startu` : "Czeka na symulację")}</h2>{journeys[0] ? <><div className="metric"><strong>{Math.round(journeys[0].duration_minutes)} min</strong><span>planowo do wskazanego punktu</span></div><div className="journey"><h3>Linia {journeys[0].route}</h3><p><b>{toTime(journeys[0].departure_seconds)}</b> odjazd</p><p><b>{toTime(journeys[0].arrival_seconds)}</b> przyjazd</p><p><b>{journeys[0].access_walk_minutes.toFixed(0)} + {journeys[0].egress_walk_minutes.toFixed(0)} min</b> dojścia piesze</p></div><dl><div><dt>Przesiadki</dt><dd>{journeys[0].transfers ?? 0}</dd></div><div><dt>Alternatywy</dt><dd>{Math.max(0, journeys.length - 1)}</dd></div></dl></> : simulation ? <><div className="metric"><strong>{simulation.reachable_stops}</strong><span>osiągalnych przystanków</span></div><p className="muted">Średnia z {simulation.sample_count} startów minutowych. Krycie punktu oznacza prawdopodobieństwo dotarcia.</p><p className="muted">Liczba osiągalnych przystanków:</p><dl>{[15, 30, 45, 60].filter(minutes => minutes <= limit).map(minutes => <div key={minutes}><dt>do {minutes} min</dt><dd>{simulation.time_bands[String(minutes)] ?? 0}</dd></div>)}{limit !== 15 && limit !== 30 && limit !== 45 && limit !== 60 && <div><dt>do {limit} min</dt><dd>{simulation.time_bands[String(limit)] ?? 0}</dd></div>}</dl><p className="muted">Kliknij dowolny punkt mapy, aby sprawdzić najbliższą trasę.</p><dl><div><dt>Wersja danych</dt><dd>{simulation.data_version}</dd></div>{simulation.data_imported_at && <div><dt>Import danych</dt><dd>{new Intl.DateTimeFormat("pl-PL", { dateStyle: "medium" }).format(new Date(simulation.data_imported_at))}</dd></div>}<div><dt>Limit</dt><dd>{limit} min</dd></div></dl><p className="muted">{simulation.disclaimer}</p></> : <p className="muted">Ta mapa odpowie najpierw na pytanie „dokąd dojadę?”. Szczegóły konkretnego celu pojawią się po kliknięciu mapy.</p>}<p className="attribution">Dane rozkładowe: ZTM Warszawa, Mikołaj Kuranowski. Mapa © OpenStreetMap contributors.</p></aside>
    </section>
  </main>;
}
