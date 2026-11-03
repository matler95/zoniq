from hashlib import sha256
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .gtfs import find_reachable_stops, latest_report
from .schemas import SimulationRequest, SimulationResponse
from .walking_access import walking_origin_stops, walking_surface


_SIMULATIONS: dict[str, dict[str, object]] = {}
_RESPONSES: dict[str, SimulationResponse] = {}
_FAILURES: dict[str, str] = {}
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zoniq-simulation")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SIMULATION_DIRECTORY = Path(os.getenv("ZONIQ_SIMULATION_DIRECTORY", str(PROJECT_ROOT / "data" / "simulations")))
_MODE_ROUTE_TYPES = {
    "bus": 3,
    "tram": 0,
    "metro": 1,
    "skm": 2,
    "km": 2,
    "wkd": 2,
}


def create_simulation(
    request: SimulationRequest,
    database: Path,
    storage_directory: Path | None = None,
) -> SimulationResponse:
    """Compute the first, GTFS-backed accessibility layer from one origin."""
    if request.origin is None:
        raise ValueError("Wskaż punkt startowy na mapie.")
    report = latest_report(database)
    if report is None:
        raise RuntimeError("Dane GTFS nie są jeszcze przygotowane.")
    payload = request.model_dump_json()
    simulation_id = f"sim_{sha256(payload.encode()).hexdigest()[:10]}"
    storage = storage_directory or _storage_directory(database)
    route_types = tuple(sorted({_MODE_ROUTE_TYPES[mode.value] for mode in request.transport_modes if mode.value in _MODE_ROUTE_TYPES}))
    departure_seconds = request.departure_time.hour * 3600 + request.departure_time.minute * 60 + request.departure_time.second
    cached = _RESPONSES.get(simulation_id)
    if cached is not None and cached.status != "failed":
        return cached
    stored = _load_stored_simulation(simulation_id, storage, report.sha256[:12])
    if stored is not None:
        _RESPONSES[simulation_id], _SIMULATIONS[simulation_id] = stored
        return _RESPONSES[simulation_id]
    if cached is not None:
        _RESPONSES.pop(simulation_id, None)
        _FAILURES.pop(simulation_id, None)
        _SIMULATIONS.pop(simulation_id, None)
    report_version = report.sha256[:12]
    response = SimulationResponse(simulation_id=simulation_id, status="processing", data_version=report_version, data_imported_at=report.imported_at, disclaimer="Trwa liczenie dostępności po rozkładach i sieci pieszej OSM.", map_data_url=f"/api/simulations/{simulation_id}/map", reachable_stops=0, time_bands={}, sample_count=request.departure_window_minutes)
    _RESPONSES[simulation_id] = response
    _EXECUTOR.submit(_compute_simulation, simulation_id, request, database, route_types, departure_seconds, report_version, report.imported_at, storage)
    return response


def simulation_status(simulation_id: str, storage_directory: Path = DEFAULT_SIMULATION_DIRECTORY) -> SimulationResponse | None:
    response = _RESPONSES.get(simulation_id)
    if response is not None:
        return response
    stored = _load_stored_simulation(simulation_id, storage_directory)
    if stored is None:
        return None
    response, map_data = stored
    _RESPONSES[simulation_id] = response
    _SIMULATIONS[simulation_id] = map_data
    return response


def _compute_simulation(
    simulation_id: str,
    request: SimulationRequest,
    database: Path,
    route_types: tuple[int, ...],
    departure_seconds: int,
    report_version: str,
    imported_at: str,
    storage_directory: Path,
) -> None:
    try:
        origin_stops = walking_origin_stops(database, (request.origin.lat, request.origin.lon))
        stops = _aggregate_departure_window(request, database, route_types, departure_seconds, origin_stops)
        features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
        "properties": {**{key: value for key, value in stop.items() if key not in {"lat", "lon"}}, "point_kind": "stop"},
        } for stop in stops]
        surface = walking_surface(stops, request.max_travel_time_minutes)
        features.extend({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point["lon"], point["lat"]]},
        "properties": {"travel_minutes": point["travel_minutes"], "point_kind": "surface", "reachable_probability": 1},
        } for point in surface)
        time_bands = {str(minutes): sum(float(stop["travel_minutes"]) <= minutes for stop in stops) for minutes in (15, 30, 45, 60, request.max_travel_time_minutes)}
        _SIMULATIONS[simulation_id] = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"max_travel_minutes": request.max_travel_time_minutes, "data_version": report_version},
        }
        walking_note = "Dojście do przystanków liczy lokalny graf chodników OSM." if origin_stops is not None else "Dojście do przystanków jest obecnie przybliżone, ponieważ kafel OSM dla tego punktu nie jest jeszcze gotowy."
        response = SimulationResponse(
        simulation_id=simulation_id,
        status="completed",
        data_version=report_version,
        data_imported_at=imported_at,
        disclaimer=f"Wynik uśrednia starty co minutę w wybranym oknie. Obsługuje do dwóch przesiadek. {walking_note}",
        map_data_url=f"/api/simulations/{simulation_id}/map",
        reachable_stops=len(stops),
        time_bands=time_bands,
        sample_count=request.departure_window_minutes,
        )
        _RESPONSES[simulation_id] = response
        _store_simulation(simulation_id, request, response, _SIMULATIONS[simulation_id], storage_directory)
    except Exception as error:
        _FAILURES[simulation_id] = str(error)
        _RESPONSES[simulation_id] = SimulationResponse(simulation_id=simulation_id, status="failed", data_version=report_version, data_imported_at=imported_at, disclaimer="Nie udało się obliczyć symulacji.", map_data_url=f"/api/simulations/{simulation_id}/map", reachable_stops=0, time_bands={}, sample_count=request.departure_window_minutes)


def simulation_map(simulation_id: str, storage_directory: Path = DEFAULT_SIMULATION_DIRECTORY) -> dict[str, object] | None:
    result = _SIMULATIONS.get(simulation_id)
    if result is not None:
        return result
    stored = _load_stored_simulation(simulation_id, storage_directory)
    if stored is None:
        return None
    response, map_data = stored
    _RESPONSES[simulation_id] = response
    _SIMULATIONS[simulation_id] = map_data
    return map_data


def _storage_directory(database: Path) -> Path:
    """Keep production artefacts outside processed inputs, while tests stay isolated."""
    if database.parent.name == "processed" and database.parent.parent.name == "data":
        return DEFAULT_SIMULATION_DIRECTORY
    return database.parent / "simulations"


def simulation_storage_directory(database: Path) -> Path:
    """Expose the storage selection to HTTP handlers and integration tests."""
    return _storage_directory(database)


def _simulation_path(simulation_id: str, storage_directory: Path) -> Path:
    return storage_directory / f"{simulation_id}.json"


def _store_simulation(
    simulation_id: str,
    request: SimulationRequest,
    response: SimulationResponse,
    map_data: dict[str, object],
    storage_directory: Path,
) -> None:
    storage_directory.mkdir(parents=True, exist_ok=True)
    destination = _simulation_path(simulation_id, storage_directory)
    payload = {
        "request": request.model_dump(mode="json"),
        "response": response.model_dump(mode="json"),
        "map_data": map_data,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    temporary = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    try:
        temporary.replace(destination)
    except PermissionError:
        # Some Windows file scanners keep an older result open briefly. The
        # complete temporary file still lets us fall back without losing the
        # freshly computed result; normal deployments retain the atomic path.
        destination.write_text(serialized, encoding="utf-8")
        temporary.unlink(missing_ok=True)


def _load_stored_simulation(
    simulation_id: str,
    storage_directory: Path,
    data_version: str | None = None,
) -> tuple[SimulationResponse, dict[str, object]] | None:
    source = _simulation_path(simulation_id, storage_directory)
    if not source.is_file():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        response = SimulationResponse.model_validate(payload["response"])
        map_data = payload["map_data"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if response.status != "completed" or (data_version is not None and response.data_version != data_version):
        return None
    return response, map_data


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
