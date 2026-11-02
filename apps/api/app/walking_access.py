"""Bridge local OSM walking tiles with the GTFS stop database."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .walking import walking_minutes_to_points

_SOUTH, _NORTH, _WEST, _EAST = 52.05, 52.38, 20.76, 21.36
_GRID = 4


def walking_origin_stops(database: Path, origin: tuple[float, float]) -> list[dict[str, float | str]] | None:
    """Return GTFS boarding stops reachable on the prepared OSM walk network.

    ``None`` deliberately means that the matching tile has not been prepared
    yet, allowing callers to retain their safe geometric fallback during data
    rollout. An empty list means that OSM routing completed but found no stop.
    """
    graph_path = _tile_for_point(*origin)
    if graph_path is None or not database.is_file():
        return None
    lat, lon = origin
    # A 2 km candidate box is wider than the 15-minute walking cutoff and
    # avoids nearest-node work for distant GTFS stops.
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT stop_id, lat, lon FROM stops WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (lat - 0.025, lat + 0.025, lon - 0.04, lon + 0.04),
        ).fetchall()
    targets = {str(stop_id): (float(stop_lat), float(stop_lon)) for stop_id, stop_lat, stop_lon in rows}
    minutes = walking_minutes_to_points(graph_path, origin, targets, max_minutes=15)
    return [
        {"id": stop_id, "walk_minutes": duration}
        for stop_id, duration in sorted(minutes.items(), key=lambda item: item[1])[:8]
    ]


def _tile_for_point(lat: float, lon: float) -> Path | None:
    if not (_SOUTH <= lat <= _NORTH and _WEST <= lon <= _EAST):
        return None
    column = min(_GRID - 1, int((lon - _WEST) / ((_EAST - _WEST) / _GRID)))
    row = min(_GRID - 1, int((lat - _SOUTH) / ((_NORTH - _SOUTH) / _GRID)))
    project_root = Path(__file__).resolve().parents[3]
    tiles = Path(os.getenv("ZONIQ_WALKING_TILES_DIR", str(project_root / "data/processed/walking/tiles")))
    path = tiles / f"tile-{column}-{row}.graphml"
    return path if path.is_file() else None
