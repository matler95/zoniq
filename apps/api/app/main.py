import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .geocoding import search_address
from .gtfs import find_direct_journeys, find_one_transfer_journeys, latest_report
from .schemas import JourneyRequest, JourneyResponse, SimulationRequest, SimulationResponse
from .simulation import create_simulation, simulation_map

app = FastAPI(title="zoniq API", version="0.1.0", description="API planowych analiz dostępności komunikacyjnej.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
GTFS_DATABASE = Path(os.getenv("ZONIQ_GTFS_DATABASE", str(PROJECT_ROOT / "data/processed/ztm.sqlite")))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_version": "demo"}


@app.get("/api/data/status")
def data_status() -> dict[str, object]:
    report = latest_report(GTFS_DATABASE)
    if report is None:
        return {"status": "pending_import", "data_version": "demo", "next_step": "Prepare a GTFS archive with python -m app.gtfs prepare"}
    return {"status": "ready", "data_version": report.sha256[:12], "feed": report.as_dict(), "next_step": "Direct scheduled journeys are ready; transfer rounds are next."}


@app.get("/api/geocode")
def get_geocode(q: str) -> dict[str, object]:
    try:
        return {"results": search_address(q)}
    except OSError as error:
        raise HTTPException(status_code=503, detail="Usługa wyszukiwania adresów jest chwilowo niedostępna.") from error


@app.post("/api/simulations", response_model=SimulationResponse, status_code=201)
def post_simulation(request: SimulationRequest) -> SimulationResponse:
    try:
        return create_simulation(request, GTFS_DATABASE)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/simulations/{simulation_id}/map")
def get_simulation_map(simulation_id: str) -> dict[str, object]:
    result = simulation_map(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono symulacji.")
    return result


@app.post("/api/journeys", response_model=JourneyResponse)
def post_journey(request: JourneyRequest) -> JourneyResponse:
    report = latest_report(GTFS_DATABASE)
    departure_seconds = request.departure_time.hour * 3600 + request.departure_time.minute * 60 + request.departure_time.second
    direct = find_direct_journeys(
        GTFS_DATABASE,
        (request.origin.lat, request.origin.lon),
        (request.destination.lat, request.destination.lon),
        request.journey_date,
        departure_seconds,
    )
    with_transfer = find_one_transfer_journeys(
        GTFS_DATABASE,
        (request.origin.lat, request.origin.lon),
        (request.destination.lat, request.destination.lon),
        request.journey_date,
        departure_seconds,
    )
    journeys = sorted([*direct, *with_transfer], key=lambda journey: float(journey["duration_minutes"]))[:3]
    return JourneyResponse(
        data_version=report.sha256[:12] if report else "unprepared",
        search_scope="scheduled trips with walking access and at most one same-stop transfer",
        journeys=journeys,
    )
