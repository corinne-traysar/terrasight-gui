"use strict";

const groups = [
  { key: "attitude", title: "Attitude", unit: "deg", labels: ["Yaw", "Pitch", "Roll"], digits: 2 },
  { key: "magnetic", title: "Magnetic Field", unit: "gauss", labels: ["X", "Y", "Z"], digits: 4 },
  { key: "acceleration", title: "Acceleration", unit: "m/s²", labels: ["X", "Y", "Z"], digits: 3 },
  { key: "angular_rate", title: "Angular Rate", unit: "rad/s", labels: ["X", "Y", "Z"], digits: 5 },
];
const colors = ["#73d8c2", "#e8b775", "#97acff"];
const status = document.getElementById("status");
const notice = document.getElementById("notice");
const panels = groups.map(group => {
  const article = document.createElement("article");
  article.innerHTML = `<div class="panel-head"><h2>${group.title}</h2><span class="unit">${group.unit}</span></div>
    <div class="values">${group.labels.map((label, i) => `<div class="value" style="color:${colors[i]}"><small>${label}</small><strong>—</strong></div>`).join("")}</div>
    <canvas role="img" aria-label="${group.title} over the last 60 seconds"></canvas>`;
  document.getElementById("plots").append(article);
  return { group, canvas: article.querySelector("canvas"), values: article.querySelectorAll("strong") };
});
let history = [], after = 0, session = null;

function draw() {
  for (const panel of panels) {
    const { canvas, group } = panel;
    const width = Math.max(1, canvas.clientWidth), height = canvas.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
    const left = 56, right = width - 10, top = 12, bottom = height - 25;
    const values = history.flatMap(sample => sample[group.key]);
    let min = values.length ? Math.min(...values) : -1;
    let max = values.length ? Math.max(...values) : 1;
    const pad = Math.max((max - min) * .12, group.key === "angular_rate" ? .001 : .01);
    min -= pad; max += pad;
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

async function poll() {
  try {
    const response = await fetch(`/api/samples?after=${after}`, { signal: AbortSignal.timeout(2500) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (session !== data.session) {
      const restarting = session !== null;
      history = []; after = 0; session = data.session;
      // A restarted Pi application has reset sequence numbers. Refetch its history.
      if (restarting) { setTimeout(poll, 0); return; }
    }
    for (const sample of data.samples) {
      if (sample.sequence > after) { history.push(sample); after = sample.sequence; }
    }
    if (history.length) {
      const latestTime = history[history.length - 1].received_ms;
      history = history.filter(sample => sample.received_ms >= latestTime - 60000).slice(-2400);
    }
    status.textContent = ({ live: "Live", stale: "Data Stale", disconnected: "Sensor Disconnected", waiting: "Waiting for Sensor" })[data.status];
    status.className = `badge ${data.status}`;
    document.getElementById("counts").textContent = `${data.received.toLocaleString()} / ${data.rejected.toLocaleString()}`;
    document.getElementById("last").textContent = data.latest ? new Date(data.latest.received_ms).toLocaleTimeString() : "Waiting";
    notice.textContent = data.status === "live" ? "Receiving live measurements · display refreshes five times per second"
      : data.status === "stale" ? "No valid measurements for more than one second. Displayed values are historical."
      : data.status === "waiting" ? "Serial port is open; waiting for a valid VNYMR packet."
      : "Sensor connection unavailable. Retrying automatically; displayed values are historical.";
    if (data.history_truncated) notice.textContent += " Some display history was missed while the browser was away.";
    if (data.latest) for (const panel of panels) panel.values.forEach((element, axis) => {
      element.textContent = data.latest[panel.group.key][axis].toFixed(panel.group.digits);
    });
    draw();
  } catch (error) {
    status.textContent = "Pi Unreachable"; status.className = "badge disconnected";
    notice.textContent = "Cannot reach the Pi. Retrying automatically; displayed values are historical.";
  }
  setTimeout(poll, 200);
}
window.addEventListener("resize", draw);
draw(); poll();
