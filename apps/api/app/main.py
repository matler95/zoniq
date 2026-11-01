import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .gtfs import find_direct_journeys, latest_report
from .schemas import JourneyRequest, JourneyResponse, SimulationRequest, SimulationResponse
from .simulation import create_simulation

app = FastAPI(title="zoniq API", version="0.1.0", description="API planowych analiz dostępności komunikacyjnej.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
GTFS_DATABASE = Path(os.getenv("ZONIQ_GTFS_DATABASE", "data/processed/ztm.sqlite"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_version": "demo"}


@app.get("/api/data/status")
def data_status() -> dict[str, object]:
    report = latest_report(GTFS_DATABASE)
    if report is None:
        return {"status": "pending_import", "data_version": "demo", "next_step": "Prepare a GTFS archive with python -m app.gtfs prepare"}
    return {"status": "ready", "data_version": report.sha256[:12], "feed": report.as_dict(), "next_step": "Direct scheduled journeys are ready; transfer rounds are next."}


@app.post("/api/simulations", response_model=SimulationResponse, status_code=201)
def post_simulation(request: SimulationRequest) -> SimulationResponse:
    return create_simulation(request)


@app.post("/api/journeys", response_model=JourneyResponse)
def post_journey(request: JourneyRequest) -> JourneyResponse:
    report = latest_report(GTFS_DATABASE)
    departure_seconds = request.departure_time.hour * 3600 + request.departure_time.minute * 60 + request.departure_time.second
    journeys = find_direct_journeys(
        GTFS_DATABASE,
        (request.origin.lat, request.origin.lon),
        (request.destination.lat, request.destination.lon),
        request.journey_date,
        departure_seconds,
    )
    return JourneyResponse(
        data_version=report.sha256[:12] if report else "unprepared",
        search_scope="direct scheduled trips with walking access; transfers are not included yet",
        journeys=journeys,
    )
