import pytest
from datetime import date, time
from pathlib import Path
from zipfile import ZipFile

from app.gtfs import prepare_store
from app.schemas import Coordinates, SimulationRequest
from app.simulation import create_simulation


def test_custom_travel_limit_is_constrained() -> None:
    assert SimulationRequest(max_travel_time_minutes=75).max_travel_time_minutes == 75
    with pytest.raises(ValueError):
        SimulationRequest(max_travel_time_minutes=181)


def test_simulation_aggregates_each_minute_in_window(tmp_path: Path) -> None:
    archive = tmp_path / "feed.zip"
    database = tmp_path / "gtfs.sqlite"
    rows = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Start,52.200,21.000\nB,End,52.210,21.010\n",
        "routes.txt": "route_id,route_short_name,route_type\nB,bus,3\n",
        "trips.txt": "route_id,service_id,trip_id\nB,weekday,trip\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip,08:01:00,08:01:00,A,1\ntrip,08:11:00,08:11:00,B,2\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20261101,20261231\n",
    }
    with ZipFile(archive, "w") as zip_file:
        for filename, contents in rows.items():
            zip_file.writestr(filename, contents)
    prepare_store(archive, database, "ztm")

    result = create_simulation(SimulationRequest(origin=Coordinates(lat=52.200, lon=21.000), journey_date=date(2026, 11, 2), departure_time=time(8, 0), departure_window_minutes=2, max_travel_time_minutes=30, transport_modes=["bus"]), database)

    assert result.sample_count == 2
    assert result.reachable_stops == 1
    assert result.time_bands["15"] == 1
