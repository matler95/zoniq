from hashlib import sha256
from pathlib import Path
from .gtfs import find_reachable_stops, latest_report
from .schemas import SimulationRequest, SimulationResponse


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
    stops = find_reachable_stops(
        database,
        (request.origin.lat, request.origin.lon),
        request.journey_date,
        departure_seconds,
        request.max_travel_time_minutes,
        route_types,
        request.max_transfers,
    )
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
        "properties": {key: value for key, value in stop.items() if key not in {"lat", "lon"}},
    } for stop in stops]
    _SIMULATIONS[simulation_id] = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"max_travel_minutes": request.max_travel_time_minutes, "data_version": report.sha256[:12]},
    }
    return SimulationResponse(
        simulation_id=simulation_id,
        status="completed",
        data_version=report.sha256[:12],
        disclaimer="Warstwa pokazuje planowo osiągalne przystanki. Obsługuje kursy bezpośrednie i jedną przesiadkę na tym samym przystanku; izochrony i dojścia po sieci OSM są kolejnym etapem.",
        map_data_url=f"/api/simulations/{simulation_id}/map",
        reachable_stops=len(features),
    )


def simulation_map(simulation_id: str) -> dict[str, object] | None:
    return _SIMULATIONS.get(simulation_id)
