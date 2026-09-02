"""
ui/simulation_component.py
---------------------------
Builds a single self-contained HTML/CSS/Canvas component that animates
the full cascade client-side. Rendered ONCE via st.components.v1.html —
Streamlit is never involved in the animation loop, which is what makes
the motion smooth (60fps requestAnimationFrame) instead of the previous
approach of re-rendering PyVis on every Python-driven tick.

Node positions are fixed (computed once in Python, see simulation_data.py)
so nothing re-layouts mid-animation — only fill color, radius, edge
state, and small flow particles change per frame.
"""

import json

DISTRESS_THRESHOLD = 0.25


def build_component_html(topology_payload: dict, frames: list, height: int = 760) -> str:
    data = {
        "nodes": topology_payload["nodes"],
        "edges": topology_payload["edges"],
        "frames": frames,
        "distressThreshold": DISTRESS_THRESHOLD,
    }
    payload_json = json.dumps(data)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    background: #0b0e14;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Helvetica, Arial, sans-serif;
    color: #c9d1d9;
  }}
  .panel {{
    border: 1px solid #232a36;
    background: #10131c;
    border-radius: 4px;
  }}
  .header-row {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 16px; border-bottom: 1px solid #1c212c;
  }}
  .header-title {{
    font-size: 11px; letter-spacing: 1.5px; color: #7d8798;
    text-transform: uppercase; font-weight: 600;
  }}
  .status-chip {{
    font-size: 10px; letter-spacing: 1px; color: #4ade80;
    display: flex; align-items: center; gap: 6px;
  }}
  .status-dot {{
    width: 6px; height: 6px; border-radius: 50%; background: #4ade80;
  }}
  .layout {{ display: flex; gap: 14px; padding: 14px; }}
  .col-graph {{ flex: 1.35; }}
  .col-side {{ flex: 1; display: flex; flex-direction: column; gap: 14px; }}

  .metrics-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 14px;
  }}
  .metric {{
    background: #0d1017; border: 1px solid #1c212c; border-radius: 3px;
    padding: 10px 12px;
  }}
  .metric-label {{
    font-size: 9.5px; letter-spacing: 1px; color: #6b7688; text-transform: uppercase;
  }}
  .metric-value {{
    font-size: 20px; font-weight: 600; color: #e6e9ef; margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }}
  .metric-value.alert {{ color: #f87171; }}
  .metric-value.warn {{ color: #eab308; }}

  .impact-wrap {{ padding: 0 14px 14px 14px; }}
  .impact-label {{
    font-size: 9.5px; letter-spacing: 1px; color: #6b7688; text-transform: uppercase;
    margin-bottom: 6px; display: flex; justify-content: space-between;
  }}
  .impact-bar-track {{
    height: 5px; background: #1c212c; border-radius: 3px; overflow: hidden;
  }}
  .impact-bar-fill {{
    height: 100%; background: linear-gradient(90deg, #4ade80, #eab308, #f87171);
    width: 0%; transition: width 0.25s ease;
  }}

  .event-row {{
    padding: 10px 14px; font-size: 11.5px; color: #9aa4b5;
    border-top: 1px solid #1c212c; min-height: 34px; display: flex; align-items: center;
  }}
  .event-row .dot {{ width: 5px; height: 5px; border-radius: 50%; background: #f87171; margin-right: 8px; flex-shrink: 0; }}

  .controls {{
    display: flex; align-items: center; gap: 10px; padding: 10px 14px;
    border-top: 1px solid #1c212c;
  }}
  button.ctrl {{
    background: #171b25; border: 1px solid #2a3140; color: #c9d1d9;
    border-radius: 3px; padding: 5px 12px; font-size: 11px; cursor: pointer;
    letter-spacing: 0.5px;
  }}
  button.ctrl:hover {{ background: #1e2430; border-color: #3a4356; }}
  input[type=range] {{ flex: 1; accent-color: #4ade80; }}
  select.speed {{
    background: #171b25; border: 1px solid #2a3140; color: #c9d1d9;
    border-radius: 3px; padding: 4px 8px; font-size: 11px;
  }}

  .legend {{ display: flex; gap: 16px; padding: 8px 14px; font-size: 10px; color: #6b7688; }}
  .legend span {{ display: flex; align-items: center; gap: 5px; }}
  .legend .sw {{ width: 8px; height: 8px; border-radius: 50%; }}
</style>
</head>
<body>

<div class="panel">
  <div class="header-row">
    <div class="header-title">Contagion Propagation — Live Simulation</div>
    <div class="status-chip"><span class="status-dot"></span><span id="playState">PLAYING</span></div>
  </div>

  <div class="layout">
    <div class="col-graph panel" style="padding:10px;">
      <canvas id="netCanvas" width="760" height="440" style="width:100%; display:block;"></canvas>
      <div class="legend">
        <span><span class="sw" style="background:#4ade80;"></span>Healthy</span>
        <span><span class="sw" style="background:#eab308;"></span>Distressed</span>
        <span><span class="sw" style="background:#f87171;"></span>Defaulted</span>
        <span><span class="sw" style="background:#5b6478;"></span>Exposure</span>
      </div>
    </div>

    <div class="col-side">
      <div class="panel">
        <div class="header-row" style="border-bottom:none; padding-bottom:0;">
          <div class="header-title">System Telemetry</div>
        </div>
        <div class="metrics-grid">
          <div class="metric"><div class="metric-label">Global Assets</div><div class="metric-value" id="mAssets">—</div></div>
          <div class="metric"><div class="metric-label">Capital Wiped</div><div class="metric-value alert" id="mWiped">—</div></div>
          <div class="metric"><div class="metric-label">Defaulted</div><div class="metric-value alert" id="mDefaulted">—</div></div>
          <div class="metric"><div class="metric-label">Distressed</div><div class="metric-value warn" id="mDistressed">—</div></div>
        </div>
        <div class="impact-wrap">
          <div class="impact-label"><span>Network Impact</span><span id="mImpactText">0 / 0</span></div>
          <div class="impact-bar-track"><div class="impact-bar-fill" id="mImpactBar"></div></div>
        </div>
      </div>

      <div class="panel" style="flex:1; display:flex; flex-direction:column;">
        <div class="header-row" style="border-bottom:none;">
          <div class="header-title">Capital Buffer Trajectory</div>
        </div>
        <canvas id="chartCanvas" width="360" height="220" style="width:100%; flex:1;"></canvas>
      </div>
    </div>
  </div>

  <div class="event-row"><span class="dot"></span><span id="eventText">Awaiting simulation start…</span></div>

  <div class="controls">
    <button class="ctrl" id="btnPlay">Pause</button>
    <button class="ctrl" id="btnRestart">Restart</button>
    <input type="range" id="scrub" min="0" max="100" value="0">
    <select class="speed" id="speedSel">
      <option value="55">Slow</option>
      <option value="30" selected>Normal</option>
      <option value="14">Fast</option>
    </select>
  </div>
</div>

<script>
const DATA = {payload_json};
const nodes = DATA.nodes;
const edges = DATA.edges;
const frames = DATA.frames;
const DIST_T = DATA.distressThreshold;
const nodeById = {{}};
nodes.forEach(n => nodeById[n.id] = n);

const maxAssets = Math.max(...nodes.map(n => n.totalAssets));
const maxExposure = Math.max(...edges.map(e => e.exposure));
const totalAssets = nodes.reduce((s, n) => s + n.totalAssets, 0);

function ratioColor(ratio) {{
  ratio = Math.max(0, Math.min(1, ratio));
  const healthy = [74, 222, 128];
  const warn    = [234, 179, 8];
  const danger  = [248, 113, 113];
  let c;
  if (ratio <= 0) return `rgb(${{danger.join(',')}})`;
  if (ratio <= DIST_T) {{
    const t = 1 - (ratio / DIST_T);
    c = warn.map((v, i) => v + (danger[i] - v) * t);
  }} else {{
    const t = 1 - ((ratio - DIST_T) / (1 - DIST_T));
    c = healthy.map((v, i) => v + (warn[i] - v) * t);
  }}
  return `rgb(${{c.map(Math.round).join(',')}})`;
}}

function statusOf(ratio) {{
  if (ratio <= 0) return "Defaulted";
  if (ratio <= DIST_T) return "Distressed";
  return "Healthy";
}}

let particles = [];
function spawnParticle(fromId, toId) {{
  if (!fromId || !toId) return;
  const a = nodeById[fromId], b = nodeById[toId];
  if (!a || !b) return;
  particles.push({{ x0: a.x, y0: a.y, x1: b.x, y1: b.y, t: 0 }});
}}

const netCanvas = document.getElementById('netCanvas');
const netCtx = netCanvas.getContext('2d');
const chartCanvas = document.getElementById('chartCanvas');
const chartCtx = chartCanvas.getContext('2d');

function drawNetwork(buffers) {{
  const w = netCanvas.width, h = netCanvas.height;
  netCtx.clearRect(0, 0, w, h);

  edges.forEach(e => {{
    const a = nodeById[e.source], b = nodeById[e.target];
    const srcRatio = buffers[e.source] / Math.max(nodeById[e.source].initialBuffer, 1e-9);
    const width = 1 + 5 * (e.exposure / maxExposure);
    netCtx.strokeStyle = srcRatio <= 0 ? 'rgba(248,113,113,0.55)' : 'rgba(91,100,120,0.45)';
    netCtx.lineWidth = width;
    netCtx.beginPath();
    netCtx.moveTo(a.x, a.y);
    netCtx.lineTo(b.x, b.y);
    netCtx.stroke();

    const angle = Math.atan2(b.y - a.y, b.x - a.x);
    const nodeRadius = 12 + 26 * (nodeById[e.target].totalAssets / maxAssets);
    const ax = b.x - Math.cos(angle) * (nodeRadius + 4);
    const ay = b.y - Math.sin(angle) * (nodeRadius + 4);
    netCtx.beginPath();
    netCtx.moveTo(ax, ay);
    netCtx.lineTo(ax - 7 * Math.cos(angle - 0.4), ay - 7 * Math.sin(angle - 0.4));
    netCtx.lineTo(ax - 7 * Math.cos(angle + 0.4), ay - 7 * Math.sin(angle + 0.4));
    netCtx.closePath();
    netCtx.fillStyle = srcRatio <= 0 ? 'rgba(248,113,113,0.55)' : 'rgba(91,100,120,0.45)';
    netCtx.fill();
  }});

  particles.forEach(p => {{
    const x = p.x0 + (p.x1 - p.x0) * p.t;
    const y = p.y0 + (p.y1 - p.y0) * p.t;
    netCtx.beginPath();
    netCtx.arc(x, y, 3.2, 0, Math.PI * 2);
    netCtx.fillStyle = '#f87171';
    netCtx.shadowColor = '#f87171';
    netCtx.shadowBlur = 8;
    netCtx.fill();
    netCtx.shadowBlur = 0;
  }});

  nodes.forEach(n => {{
    const ratio = buffers[n.id] / Math.max(n.initialBuffer, 1e-9);
    const color = ratioColor(ratio);
    const radius = 12 + 26 * (n.totalAssets / maxAssets);

    netCtx.beginPath();
    netCtx.arc(n.x, n.y, radius, 0, Math.PI * 2);
    netCtx.fillStyle = color;
    netCtx.globalAlpha = 0.92;
    netCtx.fill();
    netCtx.globalAlpha = 1;
    netCtx.lineWidth = ratio <= 0 ? 2 : 1;
    netCtx.strokeStyle = ratio <= 0 ? '#ffffff' : 'rgba(255,255,255,0.25)';
    netCtx.stroke();

    netCtx.fillStyle = '#c9d1d9';
    netCtx.font = '11px -apple-system, sans-serif';
    netCtx.textAlign = 'center';
    netCtx.fillText(n.name, n.x, n.y + radius + 15);
  }});
}}

function drawChart(historyByNode, frameCount) {{
  const w = chartCanvas.width, h = chartCanvas.height;
  chartCtx.clearRect(0, 0, w, h);
  const padL = 34, padR = 8, padT = 8, padB = 20;
  const plotW = w - padL - padR, plotH = h - padT - padB;

  chartCtx.strokeStyle = 'rgba(255,255,255,0.06)';
  chartCtx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {{
    const y = padT + plotH * (i / 4);
    chartCtx.beginPath(); chartCtx.moveTo(padL, y); chartCtx.lineTo(w - padR, y); chartCtx.stroke();
    chartCtx.fillStyle = '#5b6478'; chartCtx.font = '9px sans-serif'; chartCtx.textAlign = 'right';
    chartCtx.fillText(`${{100 - i * 25}}%`, padL - 5, y + 3);
  }}

  const palette = ['#7dd3fc', '#c9d1d9', '#eab308', '#a78bfa', '#f87171'];
  nodes.forEach((n, i) => {{
    const hist = historyByNode[n.id];
    if (!hist || hist.length < 2) return;
    chartCtx.strokeStyle = palette[i % palette.length];
    chartCtx.lineWidth = 1.6;
    chartCtx.beginPath();
    hist.forEach((v, idx) => {{
      const pct = Math.max(0, Math.min(100, 100 * v / Math.max(n.initialBuffer, 1e-9)));
      const x = padL + plotW * (idx / Math.max(frameCount - 1, 1));
      const y = padT + plotH * (1 - pct / 100);
      if (idx === 0) chartCtx.moveTo(x, y); else chartCtx.lineTo(x, y);
    }});
    chartCtx.stroke();
  }});
}}

const fmt = v => '$' + Math.round(v).toLocaleString();

function updateHud(buffers) {{
  const ratios = {{}}; nodes.forEach(n => ratios[n.id] = buffers[n.id] / Math.max(n.initialBuffer, 1e-9));
  const statuses = {{}}; nodes.forEach(n => statuses[n.id] = statusOf(ratios[n.id]));
  const defaulted = Object.values(statuses).filter(s => s === 'Defaulted').length;
  const distressed = Object.values(statuses).filter(s => s === 'Distressed').length;
  const wiped = nodes.reduce((s, n) => s + (n.initialBuffer - buffers[n.id]), 0);
  const affected = defaulted + distressed;

  document.getElementById('mAssets').textContent = fmt(totalAssets);
  document.getElementById('mWiped').textContent = fmt(wiped);
  document.getElementById('mDefaulted').textContent = defaulted;
  document.getElementById('mDistressed').textContent = distressed;
  document.getElementById('mImpactText').textContent = `${{affected}} / ${{nodes.length}}`;
  document.getElementById('mImpactBar').style.width = `${{100 * affected / nodes.length}}%`;
}}

let frameIdx = 0;
let playing = true;
let msPerFrame = 30;
let lastTick = 0;
const historyByNode = {{}};
nodes.forEach(n => historyByNode[n.id] = []);

const scrub = document.getElementById('scrub');
scrub.max = frames.length - 1;

function resetHistory(upTo) {{
  nodes.forEach(n => historyByNode[n.id] = []);
  for (let i = 0; i <= upTo; i++) {{
    nodes.forEach(n => historyByNode[n.id].push(frames[i].buffers[n.id]));
  }}
}}

function renderFrame(idx) {{
  const f = frames[idx];
  drawNetwork(f.buffers);
  updateHud(f.buffers);
  drawChart(historyByNode, idx + 1);
  if (f.event) document.getElementById('eventText').textContent = f.event;
  scrub.value = idx;
}}

function step(ts) {{
  if (playing) {{
    if (ts - lastTick >= msPerFrame) {{
      lastTick = ts;
      if (frameIdx < frames.length - 1) {{
        frameIdx += 1;
        const f = frames[frameIdx];
        nodes.forEach(n => historyByNode[n.id].push(f.buffers[n.id]));
        if (f.impulse) spawnParticle(f.impulse.from, f.impulse.to);
        renderFrame(frameIdx);
      }} else {{
        playing = false;
        document.getElementById('playState').textContent = 'COMPLETE';
        document.getElementById('btnPlay').textContent = 'Replay';
      }}
    }}
    particles.forEach(p => p.t += 0.045);
    particles = particles.filter(p => p.t < 1);
    if (particles.length) drawNetwork(frames[frameIdx].buffers);
  }}
  requestAnimationFrame(step);
}}

document.getElementById('btnPlay').addEventListener('click', () => {{
  if (frameIdx >= frames.length - 1 && !playing) {{
    frameIdx = 0; resetHistory(0); particles = [];
    document.getElementById('playState').textContent = 'PLAYING';
    document.getElementById('btnPlay').textContent = 'Pause';
    playing = true;
    return;
  }}
  playing = !playing;
  document.getElementById('playState').textContent = playing ? 'PLAYING' : 'PAUSED';
  document.getElementById('btnPlay').textContent = playing ? 'Pause' : 'Resume';
}});

document.getElementById('btnRestart').addEventListener('click', () => {{
  frameIdx = 0; resetHistory(0); particles = [];
  playing = true;
  document.getElementById('playState').textContent = 'PLAYING';
  document.getElementById('btnPlay').textContent = 'Pause';
  renderFrame(0);
}});

scrub.addEventListener('input', () => {{
  playing = false;
  document.getElementById('playState').textContent = 'PAUSED';
  document.getElementById('btnPlay').textContent = 'Resume';
  frameIdx = parseInt(scrub.value);
  resetHistory(frameIdx);
  particles = [];
  renderFrame(frameIdx);
}});

document.getElementById('speedSel').addEventListener('change', (e) => {{
  msPerFrame = parseInt(e.target.value);
}});

resetHistory(0);
renderFrame(0);
requestAnimationFrame(step);
</script>
</body>
</html>
"""
