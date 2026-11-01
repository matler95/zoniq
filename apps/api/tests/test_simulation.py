from app.schemas import SimulationRequest
from app.simulation import create_simulation


def test_same_request_produces_stable_id() -> None:
    request = SimulationRequest(origin_label="Kabaty", max_travel_time_minutes=60)
    assert create_simulation(request).simulation_id == create_simulation(request).simulation_id
