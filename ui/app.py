"""
ui/app.py
---------
SHOCKWAVE // Global Systemic Risk Matrix
Institutional risk-terminal dashboard built on Streamlit, with a
self-contained client-side canvas animation for the live cascade view.

Run with:  streamlit run ui/app.py
(run from the project root so the relative data path resolves)
"""

import os
import sys
import time
import streamlit as st
import streamlit.components.v1 as components

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.network_builder import build_network, graph_summary
from core.contagion_engine import ContagionEngine
from api.explainability import generate_postmortem
from simulation_data import compute_layout, build_topology_payload, build_frames
from simulation_component import build_component_html

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "institutions.json")

# ----------------------------------------------------------------------
# Page config + institutional theme
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="SHOCKWAVE — Systemic Risk Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

.stApp { background: #0b0e14; color: #c9d1d9; }

h1, h2, h3, h4 { font-family: 'Inter', sans-serif !important; color: #e6e9ef; font-weight: 600; }

.page-title {
    font-size: 1.5rem; font-weight: 700; color: #e6e9ef;
    letter-spacing: -0.3px; margin-bottom: 2px;
}
.page-subtitle {
    color: #6b7688; font-size: 0.82rem; letter-spacing: 0.3px;
    font-family: 'JetBrains Mono', monospace; margin-bottom: 1.2rem;
    display: flex; align-items: center; gap: 6px;
}
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #4ade80; display: inline-block; }

[data-testid="stMetric"] {
    background: #10131c; border: 1px solid #1c212c; border-radius: 4px; padding: 12px 14px;
}
[data-testid="stMetricLabel"] { color: #6b7688 !important; font-size: 0.7rem !important; letter-spacing: 0.8px; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: #e6e9ef !important; font-weight: 600; }

section[data-testid="stSidebar"] { background: #0d1017; border-right: 1px solid #1c212c; }
section[data-testid="stSidebar"] h3 { font-size: 0.8rem; letter-spacing: 0.8px; text-transform: uppercase; color: #7d8798; }

.stButton>button {
    background: #171b25; color: #c9d1d9; border: 1px solid #2a3140;
    border-radius: 4px; font-weight: 500; letter-spacing: 0.3px;
}
.stButton>button:hover { background: #1e2430; border-color: #3a4356; color: #e6e9ef; }

div[data-testid="stExpander"] { background: #10131c; border: 1px solid #1c212c; border-radius: 4px; }

.event-log { background: #10131c; border-left: 2px solid #2a3140; padding: 6px 12px; margin-bottom: 4px; font-size: 0.82rem; color: #9aa4b5; font-family: 'JetBrains Mono', monospace; }
.event-log.current { border-left-color: #f87171; color: #e6e9ef; }

.status-pill { font-size: 0.72rem; padding: 2px 8px; border-radius: 3px; font-weight: 500; }
.pill-healthy { background: rgba(74,222,128,0.12); color: #4ade80; }
.pill-distressed { background: rgba(234,179,8,0.12); color: #eab308; }
.pill-defaulted { background: rgba(248,113,113,0.12); color: #f87171; }

.ai-terminal {
    background: #0d1017; border: 1px solid #1c212c; border-radius: 4px;
    padding: 18px 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
    color: #c9d1d9; line-height: 1.6;
}
.ai-scan-line { color: #6b7688; font-size: 0.78rem; }
.blink-cursor::after { content: "▋"; animation: blink 0.9s steps(1) infinite; color: #4ade80; }
@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------
st.markdown(
    '<div class="page-title">SHOCKWAVE — Systemic Risk Intelligence</div>'
    '<div class="page-subtitle"><span class="live-dot"></span>CONTAGION PROPAGATION ENGINE · EXPOSURE NETWORK ANALYSIS</div>',
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Sidebar controls
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Simulation Setup")

    base_graph = build_network(DATA_PATH)
    node_options = {f"{d['name']} ({n})": n for n, d in base_graph.nodes(data=True)}
    target_label = st.selectbox("Patient Zero", list(node_options.keys()))
    target_node = node_options[target_label]

    shock_pct = st.slider("Initial shock (% capital loss)", 10, 100, 60, step=5) / 100.0
    sub_steps = st.select_slider("Animation smoothness", options=["Coarse", "Standard", "Ultra-smooth"], value="Standard")
    run_sim = st.button("Run Simulation", use_container_width=True, type="primary")

    st.markdown("---")
    st.markdown("### AI Explainability")
    api_key = st.text_input("Gemini API Key (optional)", type="password")
    st.caption("Without a key, a deterministic executive report is generated instead — the demo never breaks.")

SUB_STEP_MAP = {"Coarse": 16, "Standard": 30, "Ultra-smooth": 48}

# ----------------------------------------------------------------------
# Simulation state — engine runs once per "Run Simulation" click;
# all animation happens client-side afterward, no Python involved.
# ----------------------------------------------------------------------
if "engine" not in st.session_state or run_sim:
    graph = build_network(DATA_PATH)
    engine = ContagionEngine(graph)
    engine.apply_initial_shock(target_node, shock_pct)
    st.session_state.engine = engine

engine: ContagionEngine = st.session_state.engine
topo = engine.get_state_at(0)
node_ids = list(topo.nodes())

layout = compute_layout(topo)
topology_payload = build_topology_payload(topo, layout)
frames = build_frames(engine, node_ids, sub_steps=SUB_STEP_MAP[sub_steps])

st.markdown("### Live Cascade Simulation")
components.html(
    build_component_html(topology_payload, frames),
    height=780,
    scrolling=False,
)

# ----------------------------------------------------------------------
# Inspect panel — precise step-by-step read of the discrete cascade,
# driven by Streamlit (separate from the live client-side animation above)
# ----------------------------------------------------------------------
st.markdown("### Cascade Inspector")
timeline_len = engine.get_timeline_length()
step = st.slider(
    "Jump to cascade event", min_value=0, max_value=max(timeline_len - 1, 0),
    value=timeline_len - 1, label_visibility="collapsed",
)
inspect_graph = engine.get_state_at(step)
summary = graph_summary(inspect_graph)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Global System Assets", f"${summary['total_assets']:,.0f}")
c2.metric("Defaulted Nodes", summary["defaulted_count"])
c3.metric("Distressed Nodes", summary["distressed_count"])
c4.metric("Capital Wiped Out", f"${summary['capital_wiped_out']:,.0f}")

st.caption(f"**Event T+{step}:** {engine.get_event_log()[step]}")

PILL_CLASS = {"Healthy": "pill-healthy", "Distressed": "pill-distressed", "Defaulted": "pill-defaulted"}
rows = []
for n, d in inspect_graph.nodes(data=True):
    rows.append({
        "Institution": d["name"], "Type": d["type"], "Status": d["status"],
        "Capital Buffer": f"${d['capital_buffer']:,.0f}",
        "Initial Buffer": f"${d['initial_capital_buffer']:,.0f}",
    })
st.dataframe(rows, use_container_width=True, hide_index=True)

with st.expander("Full cascade event log"):
    for i, log in enumerate(engine.get_event_log()):
        cls = "event-log current" if i == step else "event-log"
        st.markdown(f'<div class="{cls}">T+{i} — {log}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# AI Explainability report
# ----------------------------------------------------------------------
st.markdown("### AI Chief Risk Officer — Post-Mortem")

SCAN_SEQUENCE = [
    "Initializing risk engine uplink...",
    "Ingesting initial network topology...",
    "Cross-referencing capital buffer deltas...",
    "Tracing exposure propagation paths...",
    "Compiling regulatory post-mortem...",
]

if st.button("Generate Executive Report"):
    terminal = st.empty()
    log_lines = []
    for line in SCAN_SEQUENCE:
        log_lines.append(line)
        terminal.markdown(
            '<div class="ai-terminal">' + "<br>".join(f'<span class="ai-scan-line">{l}</span>' for l in log_lines) +
            '<span class="blink-cursor"></span></div>', unsafe_allow_html=True,
        )
        time.sleep(0.4)

    report = generate_postmortem(engine.get_state_at(0), engine.get_state_at(timeline_len - 1), api_key=api_key or None)

    words = report.split(" ")
    chunk = ""
    for idx, word in enumerate(words):
        chunk += word + " "
        if idx % 3 == 0 or idx == len(words) - 1:
            terminal.markdown(f'<div class="ai-terminal">{chunk}<span class="blink-cursor"></span></div>', unsafe_allow_html=True)
            time.sleep(0.025)

    terminal.markdown(f'<div class="ai-terminal">{report}</div>', unsafe_allow_html=True)
