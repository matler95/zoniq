"use client";

import { FormEvent, useMemo, useState } from "react";

const modes = ["pieszo", "autobus", "tramwaj", "metro", "SKM", "KM", "WKD"];
const bands = [
  { label: "≤ 15 min", color: "#27c7f4" }, { label: "15–30 min", color: "#48d987" },
  { label: "30–45 min", color: "#f6e452" }, { label: "45–60 min", color: "#ff9a31" },
  { label: "> 60 min", color: "#f15246" }
];

export function ScenarioWorkspace() {
  const [origin, setOrigin] = useState("ul. Puławska 100, Warszawa");
  const [limit, setLimit] = useState(60);
  const [selectedModes, setSelectedModes] = useState(modes);
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState("Wynik demonstracyjny — oczekuje na import danych GTFS.");
  const weekday = useMemo(() => new Intl.DateTimeFormat("pl-PL", { weekday: "long" }).format(new Date("2026-11-07")), []);

  function toggleMode(mode: string) {
    setSelectedModes(current => current.includes(mode) ? current.filter(item => item !== mode) : [...current, mode]);
  }

  async function simulate(event: FormEvent) {
    event.preventDefault();
    setIsLoading(true);
    setNotice("Przygotowuję scenariusz…");
    try {
      const response = await fetch("http://localhost:8000/api/simulations", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ origin_label: origin, max_travel_time_minutes: limit, transport_modes: selectedModes.map(mode => mode.toLowerCase()) })
      });
      if (!response.ok) throw new Error();
      const result = await response.json();
      setNotice(`Scenariusz ${result.simulation_id} utworzony. ${result.disclaimer}`);
    } catch {
      setNotice("Tryb podglądu: uruchom API FastAPI, aby zapisać scenariusz.");
    } finally { setIsLoading(false); }
  }

  return <main>
    <header className="topbar">
      <div className="brand"><span className="mark">◌</span><span>zoniq</span></div>
      <p>Dokąd dotrzesz w określonym czasie?</p>
      <span className="badge">Warszawa · planowe rozkłady</span>
    </header>
    <section className="workspace">
      <form className="controls panel" onSubmit={simulate}>
        <div><span className="eyebrow">SCENARIUSZ</span><h1>Sprawdź dostępność</h1><p className="muted">Ustaw punkt i warunki podróży.</p></div>
        <label>Start<input value={origin} onChange={event => setOrigin(event.target.value)} aria-label="Punkt początkowy" /></label>
        <div className="split"><label>Data<input type="date" defaultValue="2026-11-07" /></label><label>Godzina<input type="time" defaultValue="17:00" /></label></div>
        <span className="weekday">{weekday}</span>
        <fieldset><legend>Maksymalny czas podróży</legend><div className="pills">{[15, 30, 45, 60, 90, 120].map(value => <button type="button" className={value === limit ? "active" : ""} onClick={() => setLimit(value)} key={value}>{value} min</button>)}</div></fieldset>
        <fieldset><legend>Środki transportu</legend><div className="modes">{modes.map(mode => <label key={mode}><input type="checkbox" checked={selectedModes.includes(mode)} onChange={() => toggleMode(mode)} />{mode}</label>)}</div></fieldset>
        <button className="primary" disabled={isLoading}>{isLoading ? "Obliczam…" : "Generuj mapę"}</button>
      </form>
      <section className="map panel" aria-label="Podgląd mapy dostępności">
        <div className="map-header"><div><span className="eyebrow">MAPA DOSTĘPNOŚCI</span><h2>{origin}</h2></div><div className="legend">{bands.map(band => <span key={band.label}><i style={{ background: band.color }} />{band.label}</span>)}</div></div>
        <div className="map-stage"><div className="rings" /><div className="roads road-one" /><div className="roads road-two" /><div className="pin"><b>●</b><small>punkt startowy</small></div><div className="map-caption">Wizualizacja testowa · warstwy GeoJSON pojawią się po podłączeniu silnika</div></div>
        <p className="notice">{notice}</p>
      </section>
      <aside className="details panel"><span className="eyebrow">PUNKT DOCELOWY</span><h2>Śródmieście</h2><p className="muted">Wybierz miejsce na mapie, aby zobaczyć dokładną trasę.</p><div className="metric"><strong>38 min</strong><span>92% w limicie</span></div><div className="journey"><h3>Przykładowy wariant</h3><p><b>8 min</b> pieszo do metra</p><p><b>24 min</b> Metro M1 · Centrum</p><p><b>6 min</b> pieszo do celu</p></div><dl><div><dt>Przesiadki</dt><dd>0</dd></div><div><dt>Dystans pieszy</dt><dd>1,1 km</dd></div><div><dt>Wersja danych</dt><dd>demo</dd></div></dl></aside>
    </section>
  </main>;
}
