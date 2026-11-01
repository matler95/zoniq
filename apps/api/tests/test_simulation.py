import pytest

from app.schemas import SimulationRequest


def test_custom_travel_limit_is_constrained() -> None:
    assert SimulationRequest(max_travel_time_minutes=75).max_travel_time_minutes == 75
    with pytest.raises(ValueError):
        SimulationRequest(max_travel_time_minutes=181)
