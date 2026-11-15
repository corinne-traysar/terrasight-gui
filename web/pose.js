/* Schematic VN-100 body pose. UM001: right-handed 3-2-1 Euler angles in NED. */
(function (root) {
  "use strict";
  const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const normalize = a => a.map(value => value / Math.hypot(...a));

  function rotation(yaw, pitch, roll) {
    // Body -> NED: Rz(yaw) Ry(pitch) Rx(roll), angles received in degrees.
    const [y, p, r] = [yaw, pitch, roll].map(value => value * Math.PI / 180);
    const cy = Math.cos(y), sy = Math.sin(y), cp = Math.cos(p), sp = Math.sin(p), cr = Math.cos(r), sr = Math.sin(r);
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
      [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr], [-sp, cp * sr, cp * cr]];
  }

  const transform = (matrix, point) => matrix.map(row => dot(row, point));

  function create(canvas) {
    let attitude = null, state = "waiting";
    const view = normalize([4, -6, -4]);
    const right = normalize(cross(view, [0, 0, -1]));
    const up = cross(right, view);
    const vertices = [[-1.2, -.75, -.22], [1.2, -.75, -.22], [1.2, .75, -.22], [-1.2, .75, -.22],
      [-1.2, -.75, .22], [1.2, -.75, .22], [1.2, .75, .22], [-1.2, .75, .22]];
    const faces = [
      { ids: [0, 1, 2, 3], color: "#c64246", normal: [0, 0, -1], top: true },
      { ids: [4, 5, 6, 7], color: "#632b35", normal: [0, 0, 1] },
      { ids: [0, 1, 5, 4], color: "#8c303a", normal: [0, -1, 0] },
      { ids: [3, 2, 6, 7], color: "#9f3640", normal: [0, 1, 0] },
      { ids: [0, 3, 7, 4], color: "#732d38", normal: [-1, 0, 0] },
      { ids: [1, 2, 6, 5], color: "#a33740", normal: [1, 0, 0] },
    ];

    function draw() {
      const width = Math.max(1, canvas.clientWidth), height = canvas.clientHeight;
      const ratio = root.devicePixelRatio || 1;
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
      }
      const ctx = canvas.getContext("2d");
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, width, height);
      const scale = Math.min(width / 6.7, height / 4.5);
      const project = point => [width / 2 + dot(point, right) * scale, height * .46 - dot(point, up) * scale];
      const line = (a, b, color, thickness = 1) => {
        ctx.strokeStyle = color; ctx.lineWidth = thickness; ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke();
      };
      const arrow = (a, b, label, color) => {
        line(a, b, color, 2);
        const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
        ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(...b);
        ctx.lineTo(b[0] - 8 * Math.cos(angle - .4), b[1] - 8 * Math.sin(angle - .4));
        ctx.lineTo(b[0] - 8 * Math.cos(angle + .4), b[1] - 8 * Math.sin(angle + .4)); ctx.closePath(); ctx.fill();
        ctx.font = "600 12px sans-serif"; ctx.textAlign = "center";
        ctx.fillText(label, b[0] + 14 * Math.cos(angle), b[1] + 14 * Math.sin(angle) + 4);
      };

      // Fixed horizontal reference grid in the NED frame, below the sensor.
      for (let step = -3; step <= 3; step++) {
        line(project([step * .5, -1.5, .8]), project([step * .5, 1.5, .8]), "#253441");
        line(project([-1.5, step * .5, .8]), project([1.5, step * .5, .8]), "#253441");
      }
      const reference = [44, height - 43];
      for (const [axis, label] of [[[1, 0, 0], "N"], [[0, 1, 0], "E"], [[0, 0, 1], "D"]]) {
        arrow(reference, [reference[0] + dot(axis, right) * 30, reference[1] - dot(axis, up) * 30], label, "#8196aa");
      }
      if (!attitude) {
        ctx.fillStyle = "#93a5b7"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
        ctx.fillText("Waiting for attitude measurements", width / 2, height / 2);
        return;
      }
      ctx.save(); ctx.globalAlpha = state === "live" ? 1 : .45;
      const matrix = rotation(...attitude);
      const world = vertices.map(point => transform(matrix, point));
      const visible = faces.filter(face => dot(transform(matrix, face.normal), view) > 0)
        .sort((a, b) => a.ids.reduce((sum, i) => sum + dot(world[i], view), 0) - b.ids.reduce((sum, i) => sum + dot(world[i], view), 0));
      for (const face of visible) {
        const points = face.ids.map(index => project(world[index]));
        ctx.fillStyle = face.color; ctx.strokeStyle = "#e47b7d"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(...points[0]); points.slice(1).forEach(point => ctx.lineTo(...point)); ctx.closePath(); ctx.fill(); ctx.stroke();
        if (face.top) {
          const origin = project(transform(matrix, [0, 0, -.225]));
          const x = project(transform(matrix, [1, 0, -.225]));
          const y = project(transform(matrix, [0, 1, -.225]));
          ctx.save(); ctx.transform(x[0] - origin[0], x[1] - origin[1], y[0] - origin[0], y[1] - origin[1], ...origin);
          ctx.fillStyle = "#fff1eb"; ctx.font = "bold .26px sans-serif"; ctx.textAlign = "center";
          ctx.fillText("VN-100", 0, .04);
          ctx.font = ".12px sans-serif"; ctx.fillText("+X →", .66, -.39);
          for (const x of [-1.02, 1.02]) for (const y of [-.57, .57]) {
            ctx.fillStyle = "#241d25"; ctx.beginPath(); ctx.arc(x, y, .055, 0, 2 * Math.PI); ctx.fill();
          }
          ctx.restore();
        }
      }
      const origin = project([0, 0, 0]);
      for (const [axis, label, color] of [[[1.95, 0, 0], "+X", "#73d8c2"], [[0, 1.6, 0], "+Y", "#e8b775"], [[0, 0, 1.4], "+Z", "#97acff"]]) {
        arrow(origin, project(transform(matrix, axis)), label, color);
      }
      ctx.restore();
    }

    return { draw, update(values, status) {
      attitude = values && values.length === 3 && values.every(Number.isFinite) ? values.slice() : null;
      state = status;
      const label = !attitude ? "Waiting for attitude measurements" :
        (state === "live" ? "Live orientation" : "Last received orientation") +
        `: yaw ${attitude[0].toFixed(2)}, pitch ${attitude[1].toFixed(2)}, roll ${attitude[2].toFixed(2)} degrees`;
      canvas.setAttribute("aria-label", label);
    } };
  }

  const api = { rotation, transform, create };
  root.VN100Pose = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
