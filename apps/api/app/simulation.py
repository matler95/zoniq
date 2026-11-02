from hashlib import sha256
from pathlib import Path
from .gtfs import find_reachable_stops, latest_report
from .schemas import SimulationRequest, SimulationResponse
from .walking_access import walking_origin_stops


_SIMULATIONS: dict[str, dict[str, object]] = {}
_MODE_ROUTE_TYPES = {
    "bus": 3,
    "tram": 0,
    "metro": 1,
    "skm": 2,
    "km": 2,
    "wkd": 2,
}


def create_simulation(request: SimulationRequest, database: Path) -> SimulationResponse:
    """Compute the first, GTFS-backed accessibility layer from one origin."""
    if request.origin is None:
        raise ValueError("Wskaż punkt startowy na mapie.")
    report = latest_report(database)
    if report is None:
        raise RuntimeError("Dane GTFS nie są jeszcze przygotowane.")
    payload = request.model_dump_json()
    simulation_id = f"sim_{sha256(payload.encode()).hexdigest()[:10]}"
    route_types = tuple(sorted({_MODE_ROUTE_TYPES[mode.value] for mode in request.transport_modes if mode.value in _MODE_ROUTE_TYPES}))
    departure_seconds = request.departure_time.hour * 3600 + request.departure_time.minute * 60 + request.departure_time.second
    origin_stops = walking_origin_stops(database, (request.origin.lat, request.origin.lon))
    stops = _aggregate_departure_window(request, database, route_types, departure_seconds, origin_stops)
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
        "properties": {key: value for key, value in stop.items() if key not in {"lat", "lon"}},
    } for stop in stops]
    time_bands = {str(minutes): sum(float(stop["travel_minutes"]) <= minutes for stop in stops) for minutes in (15, 30, 45, 60, request.max_travel_time_minutes)}
    _SIMULATIONS[simulation_id] = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"max_travel_minutes": request.max_travel_time_minutes, "data_version": report.sha256[:12]},
    }
    walking_note = "Dojście do przystanków liczy lokalny graf chodników OSM." if origin_stops is not None else "Dojście do przystanków jest obecnie przybliżone, ponieważ kafel OSM dla tego punktu nie jest jeszcze gotowy."
    return SimulationResponse(
        simulation_id=simulation_id,
        status="completed",
        data_version=report.sha256[:12],
        disclaimer=f"Wynik uśrednia starty co minutę w wybranym oknie. Obsługuje kursy bezpośrednie i jedną przesiadkę na tym samym przystanku. {walking_note}",
        map_data_url=f"/api/simulations/{simulation_id}/map",
        reachable_stops=len(features),
        time_bands=time_bands,
        sample_count=request.departure_window_minutes,
    )


def simulation_map(simulation_id: str) -> dict[str, object] | None:
    return _SIMULATIONS.get(simulation_id)


def _aggregate_departure_window(
    request: SimulationRequest, database: Path, route_types: tuple[int, ...], departure_seconds: int,
    origin_stops: list[dict[str, float | str]] | None = None,
) -> list[dict[str, object]]:
    """Aggregate independent one-minute travel starts into map statistics."""
    aggregate: dict[str, dict[str, object]] = {}
    for minute in range(request.departure_window_minutes):
        stops = find_reachable_stops(
            database, (request.origin.lat, request.origin.lon), request.journey_date,
            departure_seconds + minute * 60, request.max_travel_time_minutes, route_types, request.max_transfers, origin_stops,
        )
        for stop in stops:
            stop_id = str(stop["stop_id"])
            entry = aggregate.get(stop_id)
            if entry is None:
                entry = {**stop, "sample_count": 0, "time_total": 0.0, "route_type_counts": {}}
                aggregate[stop_id] = entry
            entry["sample_count"] = int(entry["sample_count"]) + 1
            entry["time_total"] = float(entry["time_total"]) + float(stop["travel_minutes"])
            mode_counts = entry["route_type_counts"]
            assert isinstance(mode_counts, dict)
            route_type = str(stop.get("route_type", "walk"))
            mode_counts[route_type] = int(mode_counts.get(route_type, 0)) + 1
            if float(stop["travel_minutes"]) < float(entry["travel_minutes"]):
                entry.update({key: value for key, value in stop.items() if key not in {"travel_minutes"}})
    results = []
    for entry in aggregate.values():
        count = int(entry.pop("sample_count"))
        total = float(entry.pop("time_total"))
        counts = entry.pop("route_type_counts")
        assert isinstance(counts, dict)
        entry["travel_minutes"] = round(total / count, 1)
        entry["reachable_probability"] = round(count / request.departure_window_minutes, 3)
        entry["dominant_route_type"] = int(max(counts, key=lambda item: int(counts[item])))
        results.append(entry)
    return sorted(results, key=lambda item: float(item["travel_minutes"]))
