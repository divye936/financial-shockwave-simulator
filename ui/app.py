"""
ui/app.py
---------
SHOCKWAVE // Global Systemic Risk Matrix
Cyberpunk command-center dashboard built on Streamlit.

Run with:  streamlit run ui/app.py
(run from the project root so the relative data path resolves)
"""

import os
import sys
import math
import time
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from pyvis.network import Network

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.network_builder import build_network, graph_summary
from core.contagion_engine import ContagionEngine, DISTRESS_THRESHOLD
from api.explainability import generate_postmortem

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "institutions.json")

# ----------------------------------------------------------------------
# Page config + cyberpunk CSS
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="SHOCKWAVE // Global Systemic Risk Matrix",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CYBERPUNK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&display=swap');

html, body, [class*="css"] { font-family: 'Share Tech Mono', monospace; }

.stApp {
    background:
        repeating-linear-gradient(0deg, rgba(0,255,204,0.015) 0px, rgba(0,255,204,0.015) 1px, transparent 1px, transparent 3px),
        radial-gradient(circle at 20% 20%, #0a1120 0%, #030712 60%);
    color: #d6f5ff;
}

h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }

.hud-title {
    font-family: 'Orbitron', sans-serif; font-size: 2.3rem; font-weight: 900;
    color: #00ffcc; text-shadow: 0 0 15px rgba(0,255,204,0.8), 0 0 35px rgba(0,255,204,0.35);
    border-bottom: 1px solid rgba(0,255,204,0.3); padding-bottom: 0.5rem; margin-bottom: 0.3rem;
    animation: flicker 6s infinite;
}
@keyframes flicker { 0%, 92%, 94%, 100% { opacity: 1; } 93% { opacity: 0.72; } }

.hud-subtitle { color: #7fdfff; font-size: 0.9rem; letter-spacing: 3px; opacity: 0.8; }

.live-dot {
    display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    background: #ff0055; box-shadow: 0 0 10px #ff0055; margin-right: 6px;
    animation: pulse-dot 1.4s infinite;
}
@keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(0.7); } }

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #0c1526, #060a14);
    border: 1px solid rgba(0,255,204,0.25); border-radius: 6px; padding: 14px 10px;
    box-shadow: 0 0 18px rgba(0,255,204,0.08); transition: box-shadow 0.4s ease;
}
[data-testid="stMetric"]:hover { box-shadow: 0 0 28px rgba(0,255,204,0.25); }
[data-testid="stMetricLabel"] { color: #7fdfff !important; font-family: 'Orbitron', sans-serif; font-size: 0.75rem !important; letter-spacing: 1.5px; }
[data-testid="stMetricValue"] { color: #00ffcc !important; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px rgba(0,255,204,0.5); }
.metric-alert [data-testid="stMetricValue"] { color: #ff0055 !important; text-shadow: 0 0 14px rgba(255,0,85,0.8); animation: alert-pulse 1s infinite; }
@keyframes alert-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

section[data-testid="stSidebar"] { background: #050912; border-right: 1px solid rgba(0,255,204,0.2); }

.stButton>button {
    background: linear-gradient(90deg, #ff0055, #ff2e6d); color: white;
    font-family: 'Orbitron', sans-serif; letter-spacing: 2px; border: none;
    box-shadow: 0 0 12px rgba(255,0,85,0.5); transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.stButton>button:hover { box-shadow: 0 0 22px rgba(255,0,85,0.95); transform: translateY(-1px); }

.status-healthy { color: #00ffcc; }
.status-distressed { color: #ffcc00; }
.status-defaulted { color: #ff0055; }

.event-banner {
    background: #060a14; border-left: 4px solid #ff0055; padding: 10px 16px;
    font-size: 0.95rem; color: #d6f5ff; border-radius: 3px;
    box-shadow: 0 0 14px rgba(255,0,85,0.15);
}

.event-log { background: #060a14; border-left: 3px solid #ff0055; padding: 8px 12px; margin-bottom: 6px; font-size: 0.85rem; color: #d6f5ff; }

.ai-terminal {
    background: #04060c; border: 1px solid rgba(0,255,204,0.3); border-radius: 6px;
    padding: 18px 20px; font-family: 'Share Tech Mono', monospace; color: #00ffcc;
    box-shadow: 0 0 22px rgba(0,255,204,0.12) inset; min-height: 40px;
}
.ai-scan-line { color: #7fdfff; opacity: 0.85; font-size: 0.85rem; letter-spacing: 1px; }
.blink-cursor::after { content: "▋"; animation: blink 0.9s steps(1) infinite; color: #00ffcc; }
@keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }

.impact-label { color: #7fdfff; font-family: 'Orbitron', sans-serif; font-size: 0.8rem; letter-spacing: 1.5px; margin-bottom: 4px; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #00ffcc, #ff0055) !important; }
</style>
"""
st.markdown(CYBERPUNK_CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Color helpers — continuous gradient instead of 3 hard-coded colors
# ----------------------------------------------------------------------
def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)

def _lerp_color(c1, c2, t):
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))

CYAN, YELLOW, RED = "#00ffcc", "#ffcc00", "#ff0055"

def ratio_color(ratio: float) -> str:
    """Continuous color gradient: cyan (healthy) -> yellow (distressed) -> red (defaulted)."""
    ratio = max(0.0, min(1.0, ratio))
    if ratio <= 0:
        return RED
    if ratio <= DISTRESS_THRESHOLD:
        t = 1 - (ratio / DISTRESS_THRESHOLD)
        return _lerp_color(YELLOW, RED, t)
    t = 1 - ((ratio - DISTRESS_THRESHOLD) / (1 - DISTRESS_THRESHOLD))
    return _lerp_color(CYAN, YELLOW, t)

def ratio_status(ratio: float) -> str:
    if ratio <= 0:
        return "Defaulted"
    if ratio <= DISTRESS_THRESHOLD:
        return "Distressed"
    return "Healthy"

def ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)

# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------
st.markdown(
    '<div class="hud-title">⚡ SHOCKWAVE // GLOBAL SYSTEMIC RISK MATRIX</div>'
    '<div class="hud-subtitle"><span class="live-dot"></span>CONTAGION SIMULATION '
    '&amp; EXPOSURE INTELLIGENCE — LIVE FEED</div>',
    unsafe_allow_html=True,
)
st.write("")

# ----------------------------------------------------------------------
# Sidebar controls
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ SIMULATION CONTROLS")

    base_graph = build_network(DATA_PATH)
    node_options = {f"{d['name']} ({n})": n for n, d in base_graph.nodes(data=True)}
    target_label = st.selectbox("PATIENT ZERO", list(node_options.keys()))
    target_node = node_options[target_label]

    shock_pct = st.slider("INITIAL SHOCK (% capital loss)", 10, 100, 60, step=5) / 100.0
    run_sim = st.button("🚨 DETONATE SHOCK", use_container_width=True)

    st.markdown("---")
    st.markdown("### 🌊 REAL-TIME SIMULATION")
    playback_speed = st.select_slider("Playback speed", options=["Slow", "Normal", "Fast"], value="Slow")
    auto_play = st.button("▶ RUN SMOOTH SIMULATION", use_container_width=True)

    st.markdown("---")
    st.markdown("### 🤖 AI EXPLAINABILITY")
    api_key = st.text_input("Gemini API Key (optional)", type="password")
    st.caption("No key? A deterministic executive report is generated instead — the demo never breaks.")

SUB_STEPS = {"Slow": 30, "Normal": 16, "Fast": 8}
FRAME_DELAY = {"Slow": 0.06, "Normal": 0.045, "Fast": 0.02}

# ----------------------------------------------------------------------
# Simulation state
# ----------------------------------------------------------------------
if "engine" not in st.session_state or run_sim:
    graph = build_network(DATA_PATH)
    engine = ContagionEngine(graph)
    engine.apply_initial_shock(target_node, shock_pct)
    st.session_state.engine = engine
    st.session_state.step = engine.get_timeline_length() - 1

engine: ContagionEngine = st.session_state.engine
timeline_len = engine.get_timeline_length()

# Static topology (edges + node metadata never change during the sim —
# only capital_buffer / status evolve over time)
topo = engine.get_state_at(0)
node_ids = list(topo.nodes())
node_meta = {n: topo.nodes[n] for n in node_ids}
edges = [(u, v, d) for u, v, d in topo.edges(data=True)]

st.markdown("### ⏱️ CASCADE TIMELINE VECTOR")
step = st.slider(
    "T+X", min_value=0, max_value=max(timeline_len - 1, 0),
    value=min(st.session_state.get("step", timeline_len - 1), timeline_len - 1),
    label_visibility="collapsed", key="timeline_slider",
)
st.session_state.step = step

hud_slot = st.empty()
impact_slot = st.empty()
event_slot = st.empty()
col_chart, col_graph = st.columns([1, 1.3])
chart_slot = col_chart.empty()
graph_slot = col_graph.empty()
table_slot = st.empty()

MAX_ASSETS = max(d["total_assets"] for d in node_meta.values()) or 1
MAX_EXPOSURE = max((d["exposure_amount"] for _, _, d in edges), default=1) or 1


def render_pyvis(buffers: dict):
    """Render the network graph for a given {node_id: capital_buffer} state."""
    net = Network(height="520px", width="100%", bgcolor="#030712", font_color="#d6f5ff", directed=True)
    net.barnes_hut(gravity=-9000, central_gravity=0.25, spring_length=160, spring_strength=0.015, damping=0.35)

    for n in node_ids:
        meta = node_meta[n]
        ratio = buffers[n] / max(meta["initial_capital_buffer"], 1e-9)
        color = ratio_color(ratio)
        pulsing = ratio <= 0
        size = 14 + 42 * (meta["total_assets"] / MAX_ASSETS)
        net.add_node(
            n, label=meta["name"],
            title=(f"{meta['name']} ({meta['type']})\n"
                   f"Buffer: ${buffers[n]:,.0f} / ${meta['initial_capital_buffer']:,.0f}\n"
                   f"Assets: ${meta['total_assets']:,.0f}"),
            color={"background": color, "border": "#ffffff" if pulsing else color,
                   "highlight": {"background": "#ffffff", "border": "#00ffcc"}},
            size=size, borderWidth=3 if pulsing else 2,
            shadow={"enabled": True, "color": color, "size": 22 if pulsing else 12},
        )

    for u, v, d in edges:
        u_ratio = buffers[u] / max(node_meta[u]["initial_capital_buffer"], 1e-9)
        width = 1 + 8 * (d["exposure_amount"] / MAX_EXPOSURE)
        color = RED if u_ratio <= 0 else "#3a4a6b"
        net.add_edge(u, v, value=width, title=f"{d['instrument']}: ${d['exposure_amount']:,.0f}", color=color, arrows="to")

    net.set_edge_smooth("dynamic")
    net.set_options('{"physics": {"stabilization": {"iterations": 60}}, "nodes": {"font": {"color": "#d6f5ff", "face": "Share Tech Mono"}}}')
    return net.generate_html(notebook=False)


def render_chart(history: dict, x_len: int):
    """Capital-buffer-as-%-of-initial line chart, cyberpunk-glow style."""
    fig = go.Figure()
    palette = [CYAN, "#7fdfff", YELLOW, "#ff7fb0", RED]
    for i, n in enumerate(node_ids):
        meta = node_meta[n]
        y = [100 * v / max(meta["initial_capital_buffer"], 1e-9) for v in history[n]]
        x = list(range(len(y)))
        c = palette[i % len(palette)]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(width=6, color=c), opacity=0.18, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(width=2, color=c, shape="spline"), name=meta["name"]))

    fig.update_layout(
        title=dict(text="CAPITAL BUFFER DEPLETION", font=dict(color="#00ffcc", family="Orbitron", size=14)),
        paper_bgcolor="#030712", plot_bgcolor="#030712",
        font=dict(color="#d6f5ff", family="Share Tech Mono", size=11),
        xaxis=dict(title="Propagation Step", gridcolor="rgba(0,255,204,0.08)", range=[0, max(x_len - 1, 1)]),
        yaxis=dict(title="Capital Buffer (%)", gridcolor="rgba(0,255,204,0.08)", range=[0, 105]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        margin=dict(l=10, r=10, t=40, b=10), height=430,
    )
    return fig


def render_frame(buffers: dict, event_text: str, history: dict, static_chart: bool = False):
    total_assets = sum(m["total_assets"] for m in node_meta.values())
    ratios = {n: buffers[n] / max(node_meta[n]["initial_capital_buffer"], 1e-9) for n in node_ids}
    statuses = {n: ratio_status(ratios[n]) for n in node_ids}
    defaulted = sum(1 for s in statuses.values() if s == "Defaulted")
    distressed = sum(1 for s in statuses.values() if s == "Distressed")
    wiped = sum(node_meta[n]["initial_capital_buffer"] - buffers[n] for n in node_ids)
    affected = defaulted + distressed

    with hud_slot.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("GLOBAL SYSTEM ASSETS", f"${total_assets:,.0f}")
        with c2:
            st.markdown('<div class="metric-alert">' if defaulted else "<div>", unsafe_allow_html=True)
            st.metric("DEFAULTED NODES", defaulted)
            st.markdown("</div>", unsafe_allow_html=True)
        c3.metric("DISTRESSED NODES", distressed)
        c4.metric("CAPITAL WIPED OUT", f"${wiped:,.0f}")

    with impact_slot.container():
        st.markdown(f'<div class="impact-label">NETWORK IMPACT — {affected} of {len(node_ids)} institutions affected</div>', unsafe_allow_html=True)
        st.progress(affected / len(node_ids) if node_ids else 0)

    event_slot.markdown(f'<div class="event-banner">📡 {event_text}</div>', unsafe_allow_html=True)

    with graph_slot.container():
        components.html(render_pyvis(buffers), height=530, scrolling=False)

    with chart_slot.container():
        st.plotly_chart(render_chart(history, len(next(iter(history.values())))), use_container_width=True, key=None if static_chart else f"chart_{time.time_ns()}")

    rows = [
        {"Institution": node_meta[n]["name"], "Type": node_meta[n]["type"], "Status": statuses[n],
         "Capital Buffer": f"${buffers[n]:,.0f}", "Initial Buffer": f"${node_meta[n]['initial_capital_buffer']:,.0f}"}
        for n in node_ids
    ]
    with table_slot.container():
        st.markdown("### 📊 INSTITUTION STATUS BOARD")
        st.dataframe(rows, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------
# Smooth real-time simulation: tween capital buffers between each
# discrete cascade event so money visibly drains rather than jumping
# ----------------------------------------------------------------------
if auto_play:
    sub_steps = SUB_STEPS[playback_speed]
    delay = FRAME_DELAY[playback_speed]
    history = {n: [] for n in node_ids}

    start_buffers = {n: engine.get_state_at(0).nodes[n]["capital_buffer"] for n in node_ids}
    for n in node_ids:
        history[n].append(start_buffers[n])
    render_frame(start_buffers, engine.get_event_log()[0], history)
    time.sleep(delay)

    for seg in range(timeline_len - 1):
        g_a, g_b = engine.get_state_at(seg), engine.get_state_at(seg + 1)
        a_vals = {n: g_a.nodes[n]["capital_buffer"] for n in node_ids}
        b_vals = {n: g_b.nodes[n]["capital_buffer"] for n in node_ids}
        for s in range(1, sub_steps + 1):
            t = ease_in_out(s / sub_steps)
            frame_buffers = {n: a_vals[n] + (b_vals[n] - a_vals[n]) * t for n in node_ids}
            for n in node_ids:
                history[n].append(frame_buffers[n])
            label = engine.get_event_log()[seg + 1] if s == sub_steps else f"T+{seg}→T+{seg+1}: propagating exposure..."
            render_frame(frame_buffers, label, history)
            time.sleep(delay)
    st.session_state.step = timeline_len - 1
else:
    static_buffers = {n: engine.get_state_at(step).nodes[n]["capital_buffer"] for n in node_ids}
    static_history = {n: [engine.get_state_at(i).nodes[n]["capital_buffer"] for i in range(step + 1)] for n in node_ids}
    render_frame(static_buffers, engine.get_event_log()[step], static_history, static_chart=True)

# ----------------------------------------------------------------------
# Event log
# ----------------------------------------------------------------------
with st.expander("📜 FULL CASCADE EVENT LOG"):
    for i, log in enumerate(engine.get_event_log()):
        marker = "▶" if i == st.session_state.step else " "
        st.markdown(f'<div class="event-log">{marker} T+{i}: {log}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# AI Explainability report — simulated live analysis + typewriter reveal
# ----------------------------------------------------------------------
st.markdown("### 🧠 AI CHIEF RISK OFFICER — POST-MORTEM")

SCAN_SEQUENCE = [
    "▸ INITIALIZING RISK ENGINE UPLINK...",
    "▸ INGESTING INITIAL NETWORK TOPOLOGY...",
    "▸ CROSS-REFERENCING CAPITAL BUFFER DELTAS...",
    "▸ TRACING EXPOSURE PROPAGATION PATHS...",
    "▸ COMPILING REGULATORY POST-MORTEM...",
]

if st.button("⚡ GENERATE EXECUTIVE REPORT", use_container_width=False):
    terminal = st.empty()
    log_lines = []
    for line in SCAN_SEQUENCE:
        log_lines.append(line)
        terminal.markdown(
            '<div class="ai-terminal">' + "<br>".join(f'<span class="ai-scan-line">{l}</span>' for l in log_lines) +
            '<span class="blink-cursor"></span></div>', unsafe_allow_html=True,
        )
        time.sleep(0.45)

    report = generate_postmortem(engine.get_state_at(0), engine.get_state_at(timeline_len - 1), api_key=api_key or None)

    words = report.split(" ")
    chunk = ""
    for idx, word in enumerate(words):
        chunk += word + " "
        if idx % 3 == 0 or idx == len(words) - 1:
            terminal.markdown(f'<div class="ai-terminal">{chunk}<span class="blink-cursor"></span></div>', unsafe_allow_html=True)
            time.sleep(0.03)

    terminal.markdown(f'<div class="ai-terminal">{report}</div>', unsafe_allow_html=True)
