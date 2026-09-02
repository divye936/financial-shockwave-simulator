"""
ui/simulation_data.py
----------------------
Prepares everything the client-side animation needs:
  1. A STATIC node layout (computed once via networkx spring_layout) —
     positions never change during playback, so the animation only has
     to interpolate color/size/edge state, never re-run physics. This
     is what makes the motion smooth instead of jittery.
  2. A fine-grained frame trajectory: capital buffers eased/interpolated
     between every discrete cascade event, plus the exact edge each
     write-down should animate along (from the engine's structured_log).

All of this is computed once in Python and handed to the browser as
JSON, so the animation itself runs entirely client-side at 60fps —
completely decoupled from Streamlit's rerun cycle.
"""

import math
import networkx as nx


def compute_layout(topology: nx.DiGraph, width: int = 760, height: int = 440, seed: int = 7):
    """Fixed (x, y) position per node, computed once, scaled to canvas space."""
    pos = nx.spring_layout(topology, seed=seed, k=1.6 / max(len(topology.nodes()) ** 0.5, 1))
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    pad = 70

    def scale(v, lo, hi, out_lo, out_hi):
        if hi - lo < 1e-9:
            return (out_lo + out_hi) / 2
        return out_lo + (v - lo) / (hi - lo) * (out_hi - out_lo)

    scaled = {}
    for n, (x, y) in pos.items():
        scaled[n] = (
            float(scale(x, x_min, x_max, pad, width - pad)),
            float(scale(y, y_min, y_max, pad, height - pad)),
        )
    return scaled


def _ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def build_topology_payload(topology: nx.DiGraph, layout: dict) -> dict:
    nodes = []
    for n, d in topology.nodes(data=True):
        x, y = layout[n]
        nodes.append({
            "id": n, "name": d["name"], "type": d["type"],
            "totalAssets": d["total_assets"],
            "initialBuffer": d["initial_capital_buffer"],
            "x": x, "y": y,
        })
    edges = [
        {"source": u, "target": v, "exposure": d["exposure_amount"], "instrument": d["instrument"]}
        for u, v, d in topology.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def build_frames(engine, node_ids: list, sub_steps: int = 36) -> list:
    """
    Returns a list of frames: [{"buffers": {node_id: value}, "event": str|None,
    "impulse": {"from":..,"to":..,"amount":..}|None}, ...]

    Buffers are eased between each discrete engine.timeline snapshot so the
    browser can play (or further lerp between) a long, smooth sequence
    instead of jumping between the few discrete cascade events.
    """
    structured = engine.get_structured_log()
    timeline_len = engine.get_timeline_length()

    g0 = engine.get_state_at(0)
    frames = [{
        "buffers": {n: g0.nodes[n]["capital_buffer"] for n in node_ids},
        "event": engine.get_event_log()[0],
        "impulse": None,
    }]

    for seg in range(timeline_len - 1):
        g_a, g_b = engine.get_state_at(seg), engine.get_state_at(seg + 1)
        a_vals = {n: g_a.nodes[n]["capital_buffer"] for n in node_ids}
        b_vals = {n: g_b.nodes[n]["capital_buffer"] for n in node_ids}
        impulse = structured[seg] if seg < len(structured) else None

        for s in range(1, sub_steps + 1):
            t = _ease_in_out(s / sub_steps)
            buffers = {n: a_vals[n] + (b_vals[n] - a_vals[n]) * t for n in node_ids}
            is_boundary = s == sub_steps
            frames.append({
                "buffers": buffers,
                "event": engine.get_event_log()[seg + 1] if is_boundary else None,
                # fire the flow particle roughly a third of the way through
                # the segment so it visibly arrives as the buffer finishes draining
                "impulse": impulse if s == max(1, sub_steps // 3) else None,
            })

    return frames
