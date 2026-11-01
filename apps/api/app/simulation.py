from hashlib import sha256
from .schemas import SimulationRequest, SimulationResponse


DEMO_DISCLAIMER = "Wynik demonstracyjny: nie używa jeszcze zweryfikowanych danych GTFS ani grafu OSM."


def create_simulation(request: SimulationRequest) -> SimulationResponse:
    """Creates a stable placeholder until the GTFS/OSM-backed engine replaces it."""
    payload = request.model_dump_json()
    simulation_id = f"demo_{sha256(payload.encode()).hexdigest()[:10]}"
    return SimulationResponse(
        simulation_id=simulation_id,
        status="completed",
        data_version="demo",
        disclaimer=DEMO_DISCLAIMER,
        map_data_url=f"/api/simulations/{simulation_id}/map",
    )
