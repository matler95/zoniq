"""Persistent OpenStreetMap walking graph and Dijkstra travel times."""

from __future__ import annotations

import argparse
import heapq
import json
from dataclasses import dataclass
from functools import lru_cache
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
    ox.settings.cache_folder = destination.parent / "http-cache"
    ox.settings.use_cache = True
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


def prepare_walking_graph_from_pbf(
    source: Path,
    destination: Path,
    *,
    north: float,
    south: float,
    east: float,
    west: float,
    tiles: int = 1,
) -> WalkingGraphReport:
    """Extract and persist a walk graph from a downloaded OSM PBF extract.

    PBF parsing makes graph preparation deterministic and avoids a runtime
    dependency on an Overpass instance.  ``pyrosm`` creates a pedestrian graph
    with both directions available; OSMnx then projects and serializes it in
    the same GraphML format as the legacy online importer.
    """
    if not source.is_file():
        raise FileNotFoundError(f"Brak pliku PBF: {source}")
    if not south < north or not west < east:
        raise ValueError("Nieprawidłowe granice obszaru OSM.")
    if tiles < 1:
        raise ValueError("Liczba kafli musi być dodatnia.")

    import osmnx as ox
    from pyrosm import OSM

    destination.parent.mkdir(parents=True, exist_ok=True)
    # A complete urban extract can temporarily require too much RAM while the
    # PBF parser creates intermediate GeoDataFrames.  Small overlapping tiles
    # keep the peak bounded while shared OSM node ids stitch their graphs back
    # together into one routing network.
    tile_width = (east - west) / tiles
    tile_height = (north - south) / tiles
    overlap = 0.002  # roughly 140–220 m in Warsaw, enough to preserve joins
    graphs: list[nx.MultiDiGraph] = []
    for column in range(tiles):
        for row in range(tiles):
            tile_west = max(west, west + column * tile_width - overlap)
            tile_east = min(east, west + (column + 1) * tile_width + overlap)
            tile_south = max(south, south + row * tile_height - overlap)
            tile_north = min(north, south + (row + 1) * tile_height + overlap)
            osm = OSM(source, bounding_box=[tile_west, tile_south, tile_east, tile_north])
            graphs.append(
                osm.get_graph(
                    network_type="walking",
                    graph_type="networkx",
                    force_bidirectional=True,
                    retain_all=True,
                    simplify=True,
                )
            )
    graph = nx.compose_all(graphs)
    if graph.number_of_nodes() == 0:
        raise ValueError("Wybrany obszar nie zawiera sieci pieszej w pliku PBF.")
    # Keep the Pyrosm graph in WGS84.  Projecting a city-scale MultiDiGraph
    # duplicates its geometry and is needlessly memory-intensive; OSMnx's
    # nearest-node helper supports geographic graphs directly.
    graph.graph["crs"] = "EPSG:4326"
    for _, _, _, attributes in graph.edges(keys=True, data=True):
        length = float(attributes.get("length", 0))
        multiplier = 2 if str(attributes.get("highway", "")) == "steps" else 1
        attributes["walk_seconds"] = round(length / WALKING_SPEED_METERS_PER_MINUTE * 60 * multiplier, 1)
    ox.save_graphml(graph, destination)
    report = WalkingGraphReport(nodes=graph.number_of_nodes(), edges=graph.number_of_edges(), crs=str(graph.graph["crs"]))
    destination.with_suffix(".json").write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    return report


def merge_walking_graphs(sources: list[Path], destination: Path) -> WalkingGraphReport:
    """Merge independently prepared, overlapping GraphML tiles into one graph."""
    if not sources:
        raise ValueError("Wskaż co najmniej jeden kafel grafu.")

    import osmnx as ox

    missing = [str(source) for source in sources if not source.is_file()]
    if missing:
        raise FileNotFoundError(f"Brak kafli grafu: {', '.join(missing)}")
    graphs = [ox.load_graphml(source) for source in sources]
    graph = nx.compose_all(graphs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, destination)
    report = WalkingGraphReport(nodes=graph.number_of_nodes(), edges=graph.number_of_edges(), crs=str(graph.graph["crs"]))
    destination.with_suffix(".json").write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    return report


@lru_cache(maxsize=1)
def _load_walking_graph(graph_path: str) -> nx.MultiDiGraph:
    import osmnx as ox

    graph = ox.load_graphml(graph_path)
    for _, _, _, attributes in graph.edges(keys=True, data=True):
        attributes["walk_seconds"] = float(attributes["walk_seconds"])
    return graph


def walking_minutes_to_points(graph_path: Path, origin: tuple[float, float], targets: dict[str, tuple[float, float]], max_minutes: int) -> dict[str, float]:
    """Compute network walking time from one WGS84 point to named WGS84 targets."""
    import osmnx as ox
    from pyproj import Transformer

    if not targets:
        return {}
    graph = _load_walking_graph(str(graph_path.resolve()))
    crs = graph.graph.get("crs", "EPSG:4326")
    transform = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    origin_x, origin_y = transform.transform(origin[1], origin[0])
    origin_node = ox.distance.nearest_nodes(graph, origin_x, origin_y)
    cutoff_seconds = max_minutes * 60
    lengths = nx.single_source_dijkstra_path_length(graph, origin_node, cutoff=cutoff_seconds, weight="walk_seconds")
    identifiers = list(targets)
    coordinates = [transform.transform(targets[identifier][1], targets[identifier][0]) for identifier in identifiers]
    target_nodes = ox.distance.nearest_nodes(graph, X=[point[0] for point in coordinates], Y=[point[1] for point in coordinates])
    result: dict[str, float] = {}
    for identifier, target_node in zip(identifiers, target_nodes, strict=True):
        seconds = lengths.get(target_node)
        if seconds is not None:
            result[identifier] = round(float(seconds) / 60, 2)
    return result


def walking_surface_from_stops(
    graph_path: Path, stops: list[dict[str, object]], max_minutes: int, sample_limit: int = 1_200,
) -> list[dict[str, float]]:
    """Propagate each transit arrival through the local walking graph.

    Every seed carries its elapsed door-to-stop time. A multi-source Dijkstra
    therefore yields the earliest complete journey time for graph vertices,
    including the final walking leg.
    """
    if not stops:
        return []
    import osmnx as ox
    from pyproj import Transformer

    graph = _load_walking_graph(str(graph_path.resolve()))
    crs = graph.graph.get("crs", "EPSG:4326")
    transform = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    reverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    coordinates = [transform.transform(float(stop["lon"]), float(stop["lat"])) for stop in stops]
    nodes = ox.distance.nearest_nodes(graph, X=[point[0] for point in coordinates], Y=[point[1] for point in coordinates])
    distances: dict[object, float] = {}
    queue: list[tuple[float, int, object]] = []
    for index, (node, stop) in enumerate(zip(nodes, stops, strict=True)):
        elapsed = float(stop["travel_minutes"]) * 60
        if elapsed < distances.get(node, float("inf")):
            distances[node] = elapsed
            heapq.heappush(queue, (elapsed, index, node))
    cutoff = max_minutes * 60
    while queue:
        current, _, node = heapq.heappop(queue)
        if current != distances.get(node) or current > cutoff:
            continue
        for _, neighbor, attributes in graph.out_edges(node, data=True):
            candidate = current + float(attributes["walk_seconds"])
            if candidate <= cutoff and candidate < distances.get(neighbor, float("inf")):
                distances[neighbor] = candidate
                heapq.heappush(queue, (candidate, len(queue), neighbor))
    ordered = sorted(distances.items(), key=lambda item: item[1])
    stride = max(1, len(ordered) // sample_limit)
    samples = []
    for node, seconds in ordered[::stride]:
        attributes = graph.nodes[node]
        lon, lat = reverse.transform(float(attributes["x"]), float(attributes["y"]))
        samples.append({"lat": round(lat, 6), "lon": round(lon, 6), "travel_minutes": round(seconds / 60, 1)})
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an OSM walking graph for zoniq.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--north", type=float)
    parser.add_argument("--south", type=float)
    parser.add_argument("--east", type=float)
    parser.add_argument("--west", type=float)
    parser.add_argument("--pbf", type=Path, help="lokalny wyciąg OpenStreetMap .osm.pbf")
    parser.add_argument("--tiles", type=int, default=1, help="podział PBF na kafle dla ograniczenia pamięci")
    parser.add_argument("--merge", type=Path, nargs="+", help="scal przygotowane kafle GraphML")
    args = parser.parse_args()
    if args.merge:
        print(json.dumps(merge_walking_graphs(args.merge, args.destination).__dict__))
        return
    if None in (args.north, args.south, args.east, args.west):
        parser.error("--north, --south, --east i --west są wymagane przy przygotowaniu grafu")
    prepare = prepare_walking_graph_from_pbf if args.pbf else prepare_walking_graph
    kwargs = {"north": args.north, "south": args.south, "east": args.east, "west": args.west}
    if args.pbf:
        report = prepare(args.pbf, args.destination, tiles=args.tiles, **kwargs)
    else:
        report = prepare(args.destination, **kwargs)
    print(json.dumps(report.__dict__))


if __name__ == "__main__":
    main()
