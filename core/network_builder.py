"""
network_builder.py
-------------------
Parses data/institutions.json and constructs a directed exposure graph
(nx.DiGraph) representing the financial system topology.

Edge direction convention: creditor -> debtor
  (the creditor is OWED money by the debtor; if the debtor defaults,
   the creditor takes the loss / write-down)
"""

import json
import networkx as nx


def load_institution_data(json_path: str) -> dict:
    """Load the raw institutions JSON spec from disk."""
    with open(json_path, "r") as f:
        return json.load(f)


def build_network(json_path: str = "data/institutions.json") -> nx.DiGraph:
    """
    Build a directed graph of the financial system.

    Node attributes:
        name, type, total_assets, capital_buffer, leverage_ratio, status

    Edge attributes:
        exposure_amount, instrument
    """
    data = load_institution_data(json_path)
    G = nx.DiGraph()

    for node in data["nodes"]:
        G.add_node(
            node["id"],
            name=node["name"],
            type=node["type"],
            total_assets=node["total_assets"],
            capital_buffer=node["capital_buffer"],
            leverage_ratio=node["leverage_ratio"],
            status=node["status"],
            # keep an immutable record of the starting buffer for reporting
            initial_capital_buffer=node["capital_buffer"],
        )

    for edge in data["edges"]:
        G.add_edge(
            edge["creditor"],
            edge["debtor"],
            exposure_amount=edge["exposure_amount"],
            instrument=edge["instrument"],
        )

    return G


def graph_summary(G: nx.DiGraph) -> dict:
    """Quick aggregate stats used by the top telemetry HUD."""
    total_assets = sum(d["total_assets"] for _, d in G.nodes(data=True))
    defaulted = [n for n, d in G.nodes(data=True) if d["status"] == "Defaulted"]
    distressed = [n for n, d in G.nodes(data=True) if d["status"] == "Distressed"]
    capital_wiped = sum(
        d["initial_capital_buffer"] - d["capital_buffer"] for _, d in G.nodes(data=True)
    )
    return {
        "total_assets": total_assets,
        "defaulted_count": len(defaulted),
        "distressed_count": len(distressed),
        "defaulted_nodes": defaulted,
        "distressed_nodes": distressed,
        "capital_wiped_out": capital_wiped,
    }


if __name__ == "__main__":
    g = build_network("data/institutions.json")
    print(f"Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}")
    print(graph_summary(g))
