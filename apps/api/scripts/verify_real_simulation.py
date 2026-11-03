"""Run one end-to-end accessibility simulation against locally prepared data.

This is intentionally a manual smoke check: it uses the real Warsaw GTFS
database and OSM walking tiles, so it is too expensive for the unit-test suite.
"""

from __future__ import annotations

import json
import time
from argparse import ArgumentParser
from datetime import date, time as clock_time
from pathlib import Path

from app.schemas import Coordinates, SimulationRequest
from app.simulation import create_simulation, simulation_map, simulation_status


def main() -> None:
    parser = ArgumentParser(description="Uruchom rzeczywistą próbę symulacji z Kabatów.")
    parser.add_argument("--limit", type=int, default=15, choices=(15, 30, 45, 60))
    parser.add_argument("--window", type=int, default=1, choices=(1, 2, 5, 15, 30, 60))
    args = parser.parse_args()
    print(json.dumps({"status": "started"}), flush=True)
    database = Path(__file__).resolve().parents[3] / "data" / "processed" / "ztm.sqlite"
    request = SimulationRequest(
        origin=Coordinates(lat=52.196, lon=21.022),  # Kabaty
        journey_date=date(2026, 11, 7),  # Saturday
        departure_time=clock_time(17, 0),
        departure_window_minutes=args.window,
        max_travel_time_minutes=args.limit,
        max_transfers=2,
    )
    started = create_simulation(request, database)
    deadline = time.monotonic() + 180
    result = started
    while result.status == "processing" and time.monotonic() < deadline:
        time.sleep(1)
        result = simulation_status(started.simulation_id) or started

    map_data = simulation_map(started.simulation_id) or {"features": []}
    summary = {
        "initial_status": started.status,
        "final_status": result.status,
        "time_bands": result.time_bands,
        "reachable_stops": result.reachable_stops,
        "features": len(map_data["features"]),
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if result.status != "completed" or not map_data["features"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
