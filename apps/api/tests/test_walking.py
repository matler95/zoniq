import networkx as nx

from app.walking import WALKING_SPEED_METERS_PER_MINUTE


def test_stairs_receive_double_walking_cost() -> None:
    graph = nx.MultiDiGraph()
    graph.add_edge("a", "b", length=75, highway="steps")
    for _, _, _, edge in graph.edges(keys=True, data=True):
        edge["walk_seconds"] = round(float(edge["length"]) / WALKING_SPEED_METERS_PER_MINUTE * 60 * (2 if edge["highway"] == "steps" else 1), 1)
    assert graph["a"]["b"][0]["walk_seconds"] == 120.0
