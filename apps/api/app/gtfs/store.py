"""SQLite-backed prepared GTFS store and first transit journey query."""

from __future__ import annotations

import csv
import io
import json
import math
import sqlite3
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from .ingestion import FeedReport, inspect_feed, scope_id

WALKING_SPEED_METERS_PER_MINUTE = 75.0
EARTH_RADIUS_METERS = 6_371_000


def prepare_store(archive: Path, database: Path, feed_id: str) -> FeedReport:
    """Build a queryable local store from a validated GTFS archive.

    The raw archive remains immutable. Import stages are committed so a long
    production import is observable and a stopped import can safely restart.
    """
    report = inspect_feed(archive, feed_id)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.executescript(_SCHEMA)
        connection.executescript(_DROP_INDEXES)
        connection.executescript("DELETE FROM metadata; DELETE FROM stops; DELETE FROM routes; DELETE FROM trips; DELETE FROM stop_times; DELETE FROM calendar; DELETE FROM service_dates;")
        connection.commit()
        with ZipFile(archive) as zip_file:
            _load_stops(connection, zip_file, feed_id)
            _load_routes(connection, zip_file, feed_id)
            _load_trips(connection, zip_file, feed_id)
            _load_calendar(connection, zip_file, feed_id)
            _load_calendar_dates(connection, zip_file, feed_id)
            connection.commit()
            _load_stop_times(connection, zip_file, feed_id)
            connection.commit()
        connection.executescript(_INDEXES)
        connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", ("feed_report", json.dumps(report.as_dict())))
        connection.commit()
    finally:
        connection.close()
    return report


def latest_report(database: Path) -> FeedReport | None:
    if not database.is_file():
        return None
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'feed_report'").fetchone()
    return FeedReport(**json.loads(row[0])) if row else None


def find_direct_journeys(
    database: Path,
    origin: tuple[float, float],
    destination: tuple[float, float],
    journey_date: date,
    departure_seconds: int,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Find scheduled journeys without transfers plus walking approaches.

    This is the first routing slice. The same store/indexes later support
    RAPTOR rounds for transfers; the API labels this result accurately rather
    than pretending the direct route is a complete search.
    """
    if not database.is_file():
        return []
    with sqlite3.connect(database) as connection:
        origin_stops = _nearby_stops(connection, *origin)
        destination_stops = _nearby_stops(connection, *destination)
        if not origin_stops or not destination_stops:
            return []
        origin_ids = tuple(stop["id"] for stop in origin_stops)
        destination_ids = tuple(stop["id"] for stop in destination_stops)
        active_services = _active_services(connection, journey_date)
        if not active_services:
            return []
        query = f"""
            SELECT r.short_name, r.route_type, a.departure_seconds, b.arrival_seconds,
                   a.stop_id, b.stop_id
            FROM stop_times a
            JOIN stop_times b ON b.trip_id = a.trip_id AND b.stop_sequence > a.stop_sequence
            JOIN trips t ON t.trip_id = a.trip_id
            JOIN routes r ON r.route_id = t.route_id
            WHERE a.stop_id IN ({','.join('?' for _ in origin_ids)})
              AND b.stop_id IN ({','.join('?' for _ in destination_ids)})
              AND a.departure_seconds >= ?
              AND t.service_id IN ({','.join('?' for _ in active_services)})
            ORDER BY a.departure_seconds, b.arrival_seconds
            LIMIT ?
        """
        values = (*origin_ids, *destination_ids, departure_seconds, *active_services, limit)
        results = []
        for route, route_type, depart, arrive, from_stop, to_stop in connection.execute(query, values):
            access = _stop_by_id(origin_stops, from_stop)["walk_minutes"]
            egress = _stop_by_id(destination_stops, to_stop)["walk_minutes"]
            results.append({
                "route": route or "bez numeru",
                "route_type": route_type,
                "departure_seconds": depart,
                "arrival_seconds": arrive,
                "duration_minutes": round((arrive - departure_seconds) / 60 + access + egress, 1),
                "access_walk_minutes": round(access, 1),
                "egress_walk_minutes": round(egress, 1),
                "from_stop_id": from_stop,
                "to_stop_id": to_stop,
            })
        return results


def find_one_transfer_journeys(
    database: Path,
    origin: tuple[float, float],
    destination: tuple[float, float],
    journey_date: date,
    departure_seconds: int,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Find a scheduled journey with at most one same-stop transfer.

    The query deliberately bounds candidate trips and transfer stops. It is a
    practical first RAPTOR-like round over the prepared stop-time indexes; the
    next step will add walking transfers between distinct platforms/stops.
    """
    if not database.is_file():
        return []
    with sqlite3.connect(database) as connection:
        origin_stops = _nearby_stops(connection, *origin)
        destination_stops = _nearby_stops(connection, *destination)
        active_services = _active_services(connection, journey_date)
        if not origin_stops or not destination_stops or not active_services:
            return []
        active_slots = ",".join("?" for _ in active_services)
        first_boards: list[tuple[str, int, int, float]] = []
        for stop in origin_stops:
            rows = connection.execute(
                f"""SELECT a.trip_id, a.stop_sequence, a.departure_seconds
                    FROM stop_times a JOIN trips t ON t.trip_id = a.trip_id
                    WHERE a.stop_id = ? AND a.departure_seconds >= ?
                      AND a.departure_seconds <= ? AND t.service_id IN ({active_slots})
                    ORDER BY a.departure_seconds LIMIT 12""",
                (stop["id"], departure_seconds, departure_seconds + 5_400, *active_services),
            )
            first_boards.extend((trip, sequence, depart, float(stop["walk_minutes"])) for trip, sequence, depart in rows)

        transfer_arrivals: dict[str, tuple[int, int, float, str]] = {}
        for trip_id, board_sequence, first_departure, access in first_boards:
            for stop_id, arrival in connection.execute("SELECT stop_id, arrival_seconds FROM stop_times WHERE trip_id = ? AND stop_sequence > ? AND arrival_seconds <= ?", (trip_id, board_sequence, first_departure + 5_400)):
                previous = transfer_arrivals.get(stop_id)
                candidate = (arrival, first_departure, access, trip_id)
                if previous is None or candidate[0] < previous[0]:
                    transfer_arrivals[stop_id] = candidate

        destinations = {str(stop["id"]): float(stop["walk_minutes"]) for stop in destination_stops}
        found: list[dict[str, object]] = []
        for transfer_stop, (arrival, first_departure, access, first_trip) in sorted(transfer_arrivals.items(), key=lambda item: item[1][0])[:250]:
            second_boards = connection.execute(
                f"""SELECT a.trip_id, a.stop_sequence, a.departure_seconds
                    FROM stop_times a JOIN trips t ON t.trip_id = a.trip_id
                    WHERE a.stop_id = ? AND a.departure_seconds >= ? AND t.service_id IN ({active_slots})
                    ORDER BY a.departure_seconds LIMIT 4""",
                (transfer_stop, arrival + 120, *active_services),
            )
            for second_trip, second_sequence, second_departure in second_boards:
                arrival_rows = connection.execute(
                    f"SELECT stop_id, arrival_seconds FROM stop_times WHERE trip_id = ? AND stop_sequence > ? AND stop_id IN ({','.join('?' for _ in destinations)}) ORDER BY arrival_seconds LIMIT 1",
                    (second_trip, second_sequence, *destinations),
                ).fetchone()
                if arrival_rows is None:
                    continue
                destination_stop, final_arrival = arrival_rows
                egress = destinations[destination_stop]
                found.append({
                    "route": f"{_route_for_trip(connection, first_trip)} → {_route_for_trip(connection, second_trip)}",
                    "route_type": None,
                    "departure_seconds": first_departure,
                    "arrival_seconds": final_arrival,
                    "duration_minutes": round((final_arrival - departure_seconds) / 60 + access + egress, 1),
                    "access_walk_minutes": round(access, 1),
                    "egress_walk_minutes": round(egress, 1),
                    "from_stop_id": None,
                    "to_stop_id": destination_stop,
                    "transfers": 1,
                })
        return sorted(found, key=lambda journey: float(journey["duration_minutes"]))[:limit]


def parse_gtfs_time(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _reader(zip_file: ZipFile, filename: str) -> csv.DictReader:
    return csv.DictReader(io.TextIOWrapper(zip_file.open(filename), encoding="utf-8-sig", newline=""))


def _load_stops(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    rows = ((scope_id(feed_id, row["stop_id"]), row["stop_name"], float(row["stop_lat"]), float(row["stop_lon"])) for row in _reader(zip_file, "stops.txt"))
    connection.executemany("INSERT INTO stops VALUES (?, ?, ?, ?)", rows)


def _load_routes(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    rows = ((scope_id(feed_id, row["route_id"]), row.get("route_short_name", ""), int(row["route_type"])) for row in _reader(zip_file, "routes.txt"))
    connection.executemany("INSERT INTO routes VALUES (?, ?, ?)", rows)


def _load_trips(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    rows = ((scope_id(feed_id, row["trip_id"]), scope_id(feed_id, row["route_id"]), scope_id(feed_id, row["service_id"])) for row in _reader(zip_file, "trips.txt"))
    connection.executemany("INSERT INTO trips VALUES (?, ?, ?)", rows)


def _load_stop_times(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    cursor = connection.cursor()
    batch: list[tuple[str, str, int, int, int]] = []
    for row in _reader(zip_file, "stop_times.txt"):
        batch.append((scope_id(feed_id, row["trip_id"]), scope_id(feed_id, row["stop_id"]), parse_gtfs_time(row["arrival_time"]), parse_gtfs_time(row["departure_time"]), int(row["stop_sequence"])))
        if len(batch) == 20_000:
            cursor.executemany("INSERT INTO stop_times VALUES (?, ?, ?, ?, ?)", batch)
            batch.clear()
    if batch:
        cursor.executemany("INSERT INTO stop_times VALUES (?, ?, ?, ?, ?)", batch)


def _load_calendar(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    names = {Path(name).name for name in zip_file.namelist()}
    if "calendar.txt" not in names:
        return
    rows = []
    for row in _reader(zip_file, "calendar.txt"):
        rows.append((scope_id(feed_id, row["service_id"]), *(int(row[day]) for day in _DAYS), row["start_date"], row["end_date"]))
    connection.executemany("INSERT INTO calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def _load_calendar_dates(connection: sqlite3.Connection, zip_file: ZipFile, feed_id: str) -> None:
    names = {Path(name).name for name in zip_file.namelist()}
    if "calendar_dates.txt" not in names:
        return
    rows = ((scope_id(feed_id, row["service_id"]), row["date"], int(row["exception_type"])) for row in _reader(zip_file, "calendar_dates.txt"))
    connection.executemany("INSERT INTO service_dates VALUES (?, ?, ?)", rows)


def _active_services(connection: sqlite3.Connection, journey_date: date) -> tuple[str, ...]:
    day = journey_date.strftime("%A").lower()
    date_key = journey_date.strftime("%Y%m%d")
    query = f"""
        SELECT service_id FROM calendar WHERE start_date <= ? AND end_date >= ? AND {day} = 1
        UNION
        SELECT service_id FROM service_dates WHERE date = ? AND exception_type = 1
        EXCEPT
        SELECT service_id FROM service_dates WHERE date = ? AND exception_type = 2
    """
    return tuple(row[0] for row in connection.execute(query, (date_key, date_key, date_key, date_key)))


def _route_for_trip(connection: sqlite3.Connection, trip_id: str) -> str:
    row = connection.execute("SELECT COALESCE(r.short_name, 'bez numeru') FROM trips t JOIN routes r ON r.route_id = t.route_id WHERE t.trip_id = ?", (trip_id,)).fetchone()
    return str(row[0]) if row else "bez numeru"


def _nearby_stops(connection: sqlite3.Connection, lat: float, lon: float, radius_meters: float = 1_100) -> list[dict[str, float | str]]:
    candidates = []
    for stop_id, stop_lat, stop_lon in connection.execute("SELECT stop_id, lat, lon FROM stops"):
        distance = _distance(lat, lon, stop_lat, stop_lon)
        if distance <= radius_meters:
            candidates.append({"id": stop_id, "walk_minutes": distance / WALKING_SPEED_METERS_PER_MINUTE})
    return sorted(candidates, key=lambda stop: float(stop["walk_minutes"]))[:8]


def _stop_by_id(stops: list[dict[str, float | str]], stop_id: str) -> dict[str, float | str]:
    return next(stop for stop in stops if stop["id"] == stop_id)


def _distance(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat_delta = math.radians(lat_b - lat_a)
    lon_delta = math.radians(lon_b - lon_a)
    a = math.sin(lat_delta / 2) ** 2 + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * math.sin(lon_delta / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stops (stop_id TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL);
CREATE TABLE IF NOT EXISTS routes (route_id TEXT PRIMARY KEY, short_name TEXT, route_type INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS trips (trip_id TEXT PRIMARY KEY, route_id TEXT NOT NULL, service_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stop_times (trip_id TEXT NOT NULL, stop_id TEXT NOT NULL, arrival_seconds INTEGER NOT NULL, departure_seconds INTEGER NOT NULL, stop_sequence INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS calendar (service_id TEXT PRIMARY KEY, monday INTEGER, tuesday INTEGER, wednesday INTEGER, thursday INTEGER, friday INTEGER, saturday INTEGER, sunday INTEGER, start_date TEXT, end_date TEXT);
CREATE TABLE IF NOT EXISTS service_dates (service_id TEXT NOT NULL, date TEXT NOT NULL, exception_type INTEGER NOT NULL, PRIMARY KEY(service_id, date));
"""
_DROP_INDEXES = """
DROP INDEX IF EXISTS stop_times_departure;
DROP INDEX IF EXISTS stop_times_trip;
DROP INDEX IF EXISTS trips_service;
DROP INDEX IF EXISTS service_dates_date;
"""
_INDEXES = """
CREATE INDEX IF NOT EXISTS stop_times_departure ON stop_times(stop_id, departure_seconds, trip_id, stop_sequence);
CREATE INDEX IF NOT EXISTS stop_times_trip ON stop_times(trip_id, stop_sequence);
CREATE INDEX IF NOT EXISTS trips_service ON trips(service_id);
CREATE INDEX IF NOT EXISTS service_dates_date ON service_dates(date, exception_type, service_id);
"""
