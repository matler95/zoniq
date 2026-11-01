"""Persistent OpenStreetMap walking graph and Dijkstra travel times."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

WALKING_SPEED_METERS_PER_MINUTE = 75.0


@dataclass(frozen=True)
class WalkingGraphReport:
    nodes: int
    edges: int
    crs: str


def prepare_walking_graph(destination: Path, *, north: float, south: float, east: float, west: float) -> WalkingGraphReport:
    """Download an OSM walk graph once and persist a projected GraphML cache."""
    import osmnx as ox

    destination.parent.mkdir(parents=True, exist_ok=True)
    graph = ox.graph_from_bbox((west, south, east, north), network_type="walk", simplify=True)
    graph = ox.project_graph(graph)
    for _, _, _, attributes in graph.edges(keys=True, data=True):
        length = float(attributes.get("length", 0))
        multiplier = 2 if str(attributes.get("highway", "")) == "steps" else 1
        attributes["walk_seconds"] = round(length / WALKING_SPEED_METERS_PER_MINUTE * 60 * multiplier, 1)
    ox.save_graphml(graph, destination)
    report = WalkingGraphReport(nodes=graph.number_of_nodes(), edges=graph.number_of_edges(), crs=str(graph.graph["crs"]))
    destination.with_suffix(".json").write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    return report


def walking_minutes_to_points(graph_path: Path, origin: tuple[float, float], targets: dict[str, tuple[float, float]], max_minutes: int) -> dict[str, float]:
    """Compute network walking time from one WGS84 point to named WGS84 targets."""
    import osmnx as ox
    from pyproj import Transformer

    graph = ox.load_graphml(graph_path)
    crs = graph.graph.get("crs", "EPSG:4326")
    transform = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    origin_x, origin_y = transform.transform(origin[1], origin[0])
    origin_node = ox.distance.nearest_nodes(graph, origin_x, origin_y)
    cutoff_seconds = max_minutes * 60
    lengths = nx.single_source_dijkstra_path_length(graph, origin_node, cutoff=cutoff_seconds, weight="walk_seconds")
    result: dict[str, float] = {}
    for identifier, (lat, lon) in targets.items():
        x, y = transform.transform(lon, lat)
        target_node = ox.distance.nearest_nodes(graph, x, y)
        seconds = lengths.get(target_node)
        if seconds is not None:
            result[identifier] = round(float(seconds) / 60, 2)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an OSM walking graph for zoniq.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--north", type=float, required=True)
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument("--west", type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_walking_graph(args.destination, north=args.north, south=args.south, east=args.east, west=args.west).__dict__))


if __name__ == "__main__":
    main()
