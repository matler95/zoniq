from datetime import date, time
from enum import StrEnum
from pydantic import BaseModel, Field


class TransportMode(StrEnum):
    WALK = "walk"
    BUS = "bus"
    TRAM = "tram"
    METRO = "metro"
    SKM = "skm"
    KM = "km"
    WKD = "wkd"


class Coordinates(BaseModel):
    lat: float = Field(ge=51, le=54)
    lon: float = Field(ge=19, le=23)


class SimulationRequest(BaseModel):
    origin: Coordinates | None = None
    origin_label: str | None = Field(default=None, max_length=180)
    journey_date: date = date(2026, 11, 7)
    departure_time: time = time(17, 0)
    departure_window_minutes: int = Field(default=60, ge=1, le=120)
    max_travel_time_minutes: int = Field(default=60, ge=15, le=120)
    max_transfers: int = Field(default=2, ge=0, le=3)
    transport_modes: list[TransportMode] = list(TransportMode)


class SimulationResponse(BaseModel):
    simulation_id: str
    status: str
    data_version: str
    disclaimer: str
    map_data_url: str


class JourneyRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates
    journey_date: date
    departure_time: time


class JourneyResponse(BaseModel):
    data_version: str
    search_scope: str
    journeys: list[dict[str, object]]
