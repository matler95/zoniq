import time
from pathlib import Path
from zipfile import ZipFile

from app import main, simulation
from app.gtfs import prepare_store
from app.schemas import Coordinates, SimulationRequest, TransportMode


def test_background_simulation_completes_through_http_api(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "feed.zip"
    database = tmp_path / "gtfs.sqlite"
    rows = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nZTM,https://ztm.waw.pl,Europe/Warsaw\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Start,52.200,21.000\nB,End,52.210,21.010\n",
        "routes.txt": "route_id,route_short_name,route_type\nM1,M1,1\n",
        "trips.txt": "route_id,service_id,trip_id\nM1,weekday,trip-1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip-1,08:00:00,08:00:00,A,1\ntrip-1,08:10:00,08:10:00,B,2\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20261101,20261231\n",
    }
    with ZipFile(archive, "w") as zip_file:
        for filename, contents in rows.items():
            zip_file.writestr(filename, contents)
    prepare_store(archive, database, "ztm")
    monkeypatch.setattr(main, "GTFS_DATABASE", database)
    monkeypatch.setattr(simulation, "walking_origin_stops", lambda *_: None)
    monkeypatch.setattr(simulation, "walking_surface", lambda *_: [])
    simulation._SIMULATIONS.clear()
    simulation._RESPONSES.clear()
    simulation._FAILURES.clear()

    started = main.post_simulation(SimulationRequest(
        origin=Coordinates(lat=52.2, lon=21.0), journey_date="2026-11-02", departure_time="07:50:00",
        departure_window_minutes=1, max_travel_time_minutes=30, max_transfers=2, transport_modes=[TransportMode.METRO],
    ))
    for _ in range(250):
        status = main.get_simulation_status(started.simulation_id)
        if status.status != "processing":
            break
        time.sleep(0.02)
    assert status.status == "completed"
    assert main.get_simulation_map(started.simulation_id)["features"]
