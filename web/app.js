"use strict";

const groups = [
  { key: "attitude", title: "Attitude", unit: "deg", labels: ["Yaw", "Pitch", "Roll"], digits: 2, minSpan: 20 },
  { key: "magnetic", title: "Magnetic Field", unit: "gauss", labels: ["X", "Y", "Z"], digits: 4, minSpan: .2 },
  { key: "acceleration", title: "Acceleration", unit: "m/s²", labels: ["X", "Y", "Z"], digits: 3, minSpan: 4 },
  { key: "angular_rate", title: "Angular Rate", unit: "rad/s", labels: ["X", "Y", "Z"], digits: 5, minSpan: .1 },
];
const colors = ["#73d8c2", "#e8b775", "#97acff"];
const status = document.getElementById("status");
const notice = document.getElementById("notice");
const pose = window.VN100Pose.createCapsule(document.getElementById("pose"));
let latestAttitude = null;
const startRecording = document.getElementById("start-recording");
const stopRecording = document.getElementById("stop-recording");
let recordingBusy = false, recordingState = null, sensorLive = false, piReachable = false, recordingCommandError = "";
function showRecording() {
  const rec = recordingState;
  startRecording.disabled = recordingBusy || !piReachable || !sensorLive || !rec?.available || rec.active;
  stopRecording.disabled = recordingBusy || !piReachable || !rec?.active;
  document.getElementById("recording-status").textContent = !piReachable ? "Status Unknown" :
    rec?.error ? "Recording Error" : rec?.active ? "Recording" : rec?.path ? "Saved" : "Ready";
  document.getElementById("recording-detail").textContent = !piReachable ?
    "Pi unreachable. Recording may still be running on the Pi; reconnect to check its status." : rec?.active ?
    `${rec.rows.toLocaleString()} rows · recording continues if this page closes. Sensor gaps add no rows.` :
    rec?.path ? `${rec.rows.toLocaleString()} rows · ${rec.error ? "file may be incomplete" : "CSV saved on the Pi"}.` :
    "CSV files are saved on the Pi. Live display continues while recording.";
  document.getElementById("recording-path").textContent = rec?.path || "";
  document.getElementById("recording-error").textContent = rec?.error || recordingCommandError;
}
async function controlRecording(action) {
  recordingCommandError = ""; recordingBusy = true; showRecording();
  try {
    const response = await fetch(`/api/recording/${action}`, { method: "POST", signal: AbortSignal.timeout(5000) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Recording command failed");
    recordingState = result;
  } catch (error) {
    recordingCommandError = `${error.message}. Check recording status before retrying.`;
  } finally {
    recordingBusy = false;
    showRecording();
  }
}
startRecording.addEventListener("click", () => controlRecording("start"));
stopRecording.addEventListener("click", () => controlRecording("stop"));
const alignView = document.getElementById("align-view");
const resetView = document.getElementById("reset-view");
const viewReference = document.getElementById("view-reference");
alignView.addEventListener("click", () => {
  if (!pose.alignView()) return;
  resetView.disabled = false;
  viewReference.textContent = "View aligned with the connector toward you. Tilt stays live; sensor readings are unchanged. Alignment resets on page reload.";
  queueDraw();
});
resetView.addEventListener("click", () => {
  pose.resetView();
  resetView.disabled = true;
  viewReference.textContent = "Default view. Place the sensor flat with its connector toward you, then select Align View. Alignment resets on page reload.";
  queueDraw();
});
const panels = groups.map(group => {
  const article = document.createElement("article");
  article.innerHTML = `<div class="panel-head"><h2>${group.title}</h2><span class="unit">${group.unit}</span></div>
    <div class="values">${group.labels.map((label, i) => `<div class="value" style="color:${colors[i]}"><small>${label}</small><strong>—</strong></div>`).join("")}</div>
    <canvas role="img" aria-label="${group.title} over the last 60 seconds"></canvas>`;
  document.getElementById("plots").append(article);
  return { group, canvas: article.querySelector("canvas"), values: article.querySelectorAll("strong") };
});
let history = [], after = 0, session = null, drawPending = false;

function queueDraw() {
  if (drawPending) return;
  drawPending = true;
  requestAnimationFrame(() => { drawPending = false; draw(); });
}

function draw() {
  pose.draw();
  for (const panel of panels) {
    const { canvas, group } = panel;
    const width = Math.max(1, canvas.clientWidth), height = canvas.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    }
    const ctx = canvas.getContext("2d"); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, width, height);
    const left = 56, right = width - 10, top = 12, bottom = height - 25;
    const values = history.flatMap(sample => sample[group.key]);
    const low = values.length ? Math.min(...values) : -group.minSpan / 2;
    const high = values.length ? Math.max(...values) : group.minSpan / 2;
    // Expand to include new extremes; keep axes stable during this session.
    if (!panel.range || low < panel.range[0] || high > panel.range[1]) {
      const span = Math.max(high - low, group.minSpan), middle = (low + high) / 2;
      panel.range = [Math.min(panel.range?.[0] ?? Infinity, middle - span * .62),
        Math.max(panel.range?.[1] ?? -Infinity, middle + span * .62)];
    }
    const [min, max] = panel.range;
    ctx.font = "10px sans-serif";
    for (let row = 0; row < 4; row++) {
      const y = top + (bottom - top) * row / 3;
      ctx.strokeStyle = "#293744"; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      ctx.fillStyle = "#879caf"; ctx.fillText((max - (max - min) * row / 3).toPrecision(4), 0, y + 3);
    }
    ctx.fillStyle = "#879caf"; ctx.fillText("−60 s", left, height - 4); ctx.fillText("Latest", right - 30, height - 4);
    if (!history.length) { ctx.fillText("Waiting for measurements", left + 12, height / 2); continue; }
    const end = history[history.length - 1].received_ms;
    for (let axis = 0; axis < 3; axis++) {
      ctx.strokeStyle = colors[axis]; ctx.lineWidth = 1.3; ctx.beginPath();
      let previous = null;
      for (const sample of history) {
        const x = left + (sample.received_ms - end + 60000) / 60000 * (right - left);
        const y = bottom - (sample[group.key][axis] - min) / (max - min) * (bottom - top);
        if (!previous || sample.sequence !== previous.sequence + 1 || sample.received_ms - previous.received_ms > 1000) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        previous = sample;
      }
      ctx.stroke();
    }
  }
}

function receive(data) {
  try {
    if (session !== data.session) {
      history = []; after = 0; session = data.session;
      panels.forEach(panel => { panel.range = null; });
    }
    for (const sample of data.samples) {
      if (sample.sequence > after) { history.push(sample); after = sample.sequence; }
    }
    if (history.length) {
      const latestTime = history[history.length - 1].received_ms;
      history = history.filter(sample => sample.received_ms >= latestTime - 60000).slice(-2400);
    }
    recordingState = data.recording || null;
    piReachable = true; sensorLive = data.status === "live";
    showRecording();
    status.textContent = ({ stopped: "Acquisition Stopped", live: "Live", stale: "Data Stale", disconnected: "Sensor Disconnected", waiting: "Waiting for Sensor" })[data.status];
    status.className = `badge ${data.status}`;
    document.getElementById("counts").textContent = `${data.received.toLocaleString()} / ${data.rejected.toLocaleString()}`;
    document.getElementById("last").textContent = data.latest ? new Date(data.latest.received_ms).toLocaleTimeString() : "Waiting";
    notice.textContent = data.status === "stopped" ? "Acquisition is stopped. Start VN-100 from the dashboard Overview when the sensor is connected." : data.status === "live" ? "Receiving live measurements · continuous stream · up to 20 display updates per second"
      : data.status === "stale" ? "No valid measurements for more than one second. Displayed values are historical."
      : data.status === "waiting" ? "Serial port is open; waiting for a valid VNYMR packet."
      : "Sensor connection unavailable. Retrying automatically; displayed values are historical.";
    if (data.history_truncated) notice.textContent += " Some display history was missed while the browser was away.";
    if (data.latest) for (const panel of panels) panel.values.forEach((element, axis) => {
      element.textContent = data.latest[panel.group.key][axis].toFixed(panel.group.digits);
    });
    latestAttitude = data.latest?.attitude || null;
    pose.update(latestAttitude, data.status);
    alignView.disabled = !latestAttitude || data.status !== "live";
    document.getElementById("pose-status").textContent = !latestAttitude ? "Waiting" :
      (data.status === "live" ? "Live Pose" : "Last Received Pose");
    queueDraw();
  } catch (error) {
    status.textContent = "Invalid Data"; status.className = "badge disconnected";
    notice.textContent = "Received an invalid display update. Waiting for the next valid update.";
  }
}

const sharedVN=window.parent!==window && window.BenchTelemetry;
const source = sharedVN ? {} : new EventSource("/api/events");
let lastMessageAt = performance.now();
source.onmessage = event => { lastMessageAt = performance.now(); receive(JSON.parse(event.data)); };
source.onerror = () => {
  piReachable = false; showRecording();
  status.textContent = "Pi Unreachable"; status.className = "badge disconnected";
  notice.textContent = "Cannot reach the Pi. Retrying automatically; displayed values are historical.";
  pose.update(latestAttitude, "disconnected");
  alignView.disabled = true;
  document.getElementById("pose-status").textContent = latestAttitude ? "Last Received Pose" : "Waiting";
  queueDraw();
};
if(sharedVN)sharedVN.subscribeVN(data=>{
  if(data){lastMessageAt=performance.now();receive(data);}else source.onerror();
});
function watchConnection() {
  if (performance.now() - lastMessageAt > 1500) source.onerror();
  setTimeout(watchConnection, 250);
}
window.addEventListener("resize", queueDraw);
queueDraw(); watchConnection();
