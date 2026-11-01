from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import SimulationRequest, SimulationResponse
from .simulation import create_simulation

app = FastAPI(title="zoniq API", version="0.1.0", description="API planowych analiz dostępności komunikacyjnej.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_version": "demo"}


@app.get("/api/data/status")
def data_status() -> dict[str, str]:
    return {"status": "pending_import", "data_version": "demo", "next_step": "Import GTFS ZTM and build walking graph"}


@app.post("/api/simulations", response_model=SimulationResponse, status_code=201)
def post_simulation(request: SimulationRequest) -> SimulationResponse:
    return create_simulation(request)
