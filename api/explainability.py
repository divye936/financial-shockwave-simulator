"""
explainability.py
------------------
Turns the initial and final network states into a 3-paragraph
executive "Chief Risk Officer" post-mortem using Gemini
(gemini-2.5-flash). Falls back to a deterministic, template-based
report if no API key is provided or the call fails — so live judging
demos never crash on a network hiccup.
"""

import json
import networkx as nx

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


SYSTEM_PROMPT = """You are the Chief Risk Officer of a global financial
regulator, writing a post-mortem after a systemic contagion event.
You are given the initial and final states of the financial exposure
network (JSON). Write a structured 3-paragraph executive report:

1. TRIGGER — what initiated the crisis and why that institution was vulnerable.
2. CONTAGION WAVE — how the shock propagated through the network via exposures.
3. SYSTEMIC IMPACT — the final state of the system, capital destroyed, and forward-looking risk implications.

Be precise, use the institution names and figures provided, and write
in a formal regulatory tone. Do not use markdown headers, just three
clear paragraphs."""


def _graph_to_summary_dict(G: nx.DiGraph) -> dict:
    """Condense a graph snapshot into a compact JSON-serializable summary."""
    return {
        "nodes": [
            {
                "id": n,
                "name": d["name"],
                "type": d["type"],
                "status": d["status"],
                "capital_buffer": round(d["capital_buffer"], 2),
                "initial_capital_buffer": round(d["initial_capital_buffer"], 2),
            }
            for n, d in G.nodes(data=True)
        ],
        "edges": [
            {
                "creditor": u,
                "debtor": v,
                "exposure_amount": d["exposure_amount"],
                "instrument": d["instrument"],
            }
            for u, v, d in G.edges(data=True)
        ],
    }


def _fallback_report(initial_state: nx.DiGraph, final_state: nx.DiGraph) -> str:
    """Deterministic, always-available report — no external API needed."""
    initial = _graph_to_summary_dict(initial_state)
    final = _graph_to_summary_dict(final_state)

    defaulted = [n for n in final["nodes"] if n["status"] == "Defaulted"]
    distressed = [n for n in final["nodes"] if n["status"] == "Distressed"]
    total_wiped = sum(
        n["initial_capital_buffer"] - n["capital_buffer"] for n in final["nodes"]
    )

    defaulted_names = ", ".join(n["name"] for n in defaulted) if defaulted else "none"
    distressed_names = ", ".join(n["name"] for n in distressed) if distressed else "none"

    trigger_node = None
    for i_node, f_node in zip(initial["nodes"], final["nodes"]):
        if i_node["capital_buffer"] > f_node["capital_buffer"]:
            trigger_node = f_node["name"]
            break

    paragraph_1 = (
        f"TRIGGER: The event was precipitated by a sudden capital shock at "
        f"{trigger_node or 'a key institution'}, whose leverage profile left "
        f"insufficient buffer to absorb the initial loss. This vulnerability "
        f"reflects a broader pattern seen across highly-leveraged, "
        f"interconnected balance sheets in the network."
    )

    paragraph_2 = (
        f"CONTAGION WAVE: As the initiating institution's capital buffer was "
        f"depleted, counterparties with direct exposure absorbed write-downs "
        f"proportional to their outstanding claims. This triggered a cascading "
        f"sequence of downgrades and defaults, ultimately affecting "
        f"{len(defaulted) + len(distressed)} institution(s) across the "
        f"network, with {defaulted_names} defaulting outright and "
        f"{distressed_names} left in a distressed state."
    )

    paragraph_3 = (
        f"SYSTEMIC IMPACT: In total, approximately {total_wiped:,.0f} in "
        f"capital buffer was destroyed across the system. Regulators should "
        f"treat this as a signal to reassess concentration risk and minimum "
        f"buffer requirements for institutions with high interbank "
        f"interconnectedness, as the failure of a single node was sufficient "
        f"to materially impair system-wide stability."
    )

    return f"{paragraph_1}\n\n{paragraph_2}\n\n{paragraph_3}"


def generate_postmortem(
    initial_state: nx.DiGraph,
    final_state: nx.DiGraph,
    api_key: str | None = None,
) -> str:
    """
    Generate the executive post-mortem. Tries Gemini first if an API key
    is supplied; falls back to a deterministic report on any failure so
    the demo never crashes.
    """
    if not api_key or not _GENAI_AVAILABLE:
        return _fallback_report(initial_state, final_state)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        payload = {
            "initial_state": _graph_to_summary_dict(initial_state),
            "final_state": _graph_to_summary_dict(final_state),
        }

        response = model.generate_content(
            f"Here is the simulation data:\n{json.dumps(payload, indent=2)}"
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Empty response from Gemini")
        return text

    except Exception:
        # Guarantee zero crashes during live judging demos.
        return _fallback_report(initial_state, final_state)
