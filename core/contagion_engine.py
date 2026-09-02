"""
contagion_engine.py
--------------------
Runs a systemic risk contagion simulation over a network built by
core.network_builder.

Logic:
  1. An initial shock hits one or more "patient zero" nodes, wiping out
     a percentage (or absolute amount) of their capital buffer.
  2. If a node's capital_buffer drops <= 0, it DEFAULTS.
  3. When a node defaults, every creditor exposed to it (via in_edges,
     i.e. creditor -> debtor where debtor = defaulted node) must write
     down their exposure_amount against their own capital_buffer.
  4. Write-downs can push creditors into Distressed (buffer < 25% of
     initial) or Defaulted (buffer <= 0) status, which in turn cascades
     further. This repeats until the system stabilizes (no new
     defaults in a pass).
  5. Each discrete step of the cascade is recorded as a deep-copied
     snapshot so the UI can scrub through a timeline (T+0, T+1, ...).
"""

import copy
import networkx as nx

DISTRESS_THRESHOLD = 0.25  # capital_buffer / initial_capital_buffer


class ContagionEngine:
    def __init__(self, graph: nx.DiGraph):
        self.G = graph
        self.timeline = []  # list of deep-copied graph snapshots
        self.event_log = []  # human-readable log of what happened at each step
        # Structured record of each shock/write-down, aligned so that
        # structured_log[i] corresponds to the transition INTO
        # event_log[i + 1] (event_log[0] is just the pre-shock baseline).
        # Lets the UI know exactly which edge to animate money flowing along.
        self.structured_log = []

    # ------------------------------------------------------------------
    # State recording
    # ------------------------------------------------------------------
    def _record_state(self, label: str):
        """Deep-copy the current graph state into the timeline."""
        snapshot = copy.deepcopy(self.G)
        self.timeline.append(snapshot)
        self.event_log.append(label)

    def _update_status(self, node_id: str):
        """Recompute a node's Healthy / Distressed / Defaulted status."""
        data = self.G.nodes[node_id]
        if data["status"] == "Defaulted":
            return  # already defaulted, terminal state

        buffer_ratio = data["capital_buffer"] / max(data["initial_capital_buffer"], 1e-9)

        if data["capital_buffer"] <= 0:
            data["capital_buffer"] = 0
            data["status"] = "Defaulted"
        elif buffer_ratio <= DISTRESS_THRESHOLD:
            data["status"] = "Distressed"
        else:
            data["status"] = "Healthy"

    # ------------------------------------------------------------------
    # Core simulation
    # ------------------------------------------------------------------
    def apply_initial_shock(self, node_id: str, shock_pct: float):
        """
        Apply the triggering shock to a single institution.
        shock_pct: fraction of capital_buffer wiped out (0.0 - 1.0+)
        """
        self._record_state(f"T+0: Initial state before shock")

        data = self.G.nodes[node_id]
        loss = data["capital_buffer"] * shock_pct
        data["capital_buffer"] -= loss
        self._update_status(node_id)

        self.structured_log.append({
            "type": "shock", "node": node_id, "amount": loss, "from": None, "to": node_id,
        })
        self._record_state(
            f"T+0: Shock applied to {data['name']} ({node_id}) — "
            f"{shock_pct*100:.0f}% capital loss (-{loss:,.0f})"
        )

        self.run_cascade()

    def run_cascade(self):
        """
        Recursively propagate defaults through the graph via in_edges
        (creditors exposed to a defaulted debtor) until no new defaults
        occur in a full pass.
        """
        step = 1
        while True:
            newly_defaulted = [
                n for n, d in self.G.nodes(data=True)
                if d["status"] == "Defaulted" and not d.get("_processed", False)
            ]

            if not newly_defaulted:
                break

            any_change = False
            for defaulted_node in newly_defaulted:
                self.G.nodes[defaulted_node]["_processed"] = True
                defaulted_name = self.G.nodes[defaulted_node]["name"]

                # Every creditor with an edge INTO this defaulted node
                # takes a write-down proportional to their exposure.
                for creditor_id in self.G.predecessors(defaulted_node):
                    edge_data = self.G.edges[creditor_id, defaulted_node]
                    exposure = edge_data["exposure_amount"]
                    creditor_data = self.G.nodes[creditor_id]

                    if creditor_data["status"] == "Defaulted":
                        continue  # already gone, no further write-down needed

                    write_down = min(exposure, creditor_data["capital_buffer"] + exposure)
                    write_down = exposure  # full exposure write-down on default
                    prev_status = creditor_data["status"]
                    creditor_data["capital_buffer"] -= write_down
                    self._update_status(creditor_id)

                    if creditor_data["status"] != prev_status:
                        any_change = True

                    self.event_log_note = (
                        f"T+{step}: {defaulted_name} defaulted -> "
                        f"{creditor_data['name']} writes down {write_down:,.0f} "
                        f"({prev_status} -> {creditor_data['status']})"
                    )
                    self.structured_log.append({
                        "type": "writedown", "node": creditor_id, "amount": write_down,
                        "from": defaulted_node, "to": creditor_id,
                    })
                    self._record_state(self.event_log_note)

                any_change = True

            step += 1
            if step > 50:  # safety valve against pathological cycles
                break

        # cleanup helper flag
        for _, d in self.G.nodes(data=True):
            d.pop("_processed", None)

    # ------------------------------------------------------------------
    # Accessors for the UI layer
    # ------------------------------------------------------------------
    def get_timeline_length(self) -> int:
        return len(self.timeline)

    def get_state_at(self, step: int) -> nx.DiGraph:
        step = max(0, min(step, len(self.timeline) - 1))
        return self.timeline[step]

    def get_event_log(self) -> list:
        return self.event_log

    def get_structured_log(self) -> list:
        return self.structured_log
