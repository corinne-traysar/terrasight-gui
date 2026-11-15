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
    // Illustrative rugged housing based on the supplied photo and VN-100-CR-ASM.
    // +X is away from the connector; the two mounting tabs extend along +/-Y.
    const faces = [];
    function extrude(outline, top, bottom, color, side, tag, openTop = false) {
      if (!openTop) faces.push({ points: outline.map(([x, y]) => [x, y, top]), color, normal: [0, 0, -1], tag });
      faces.push({ points: outline.map(([x, y]) => [x, y, bottom]), color: side, normal: [0, 0, 1] });
      outline.forEach(([x, y], i) => {
        const [nx, ny] = outline[(i + 1) % outline.length];
        faces.push({ points: [[x, y, top], [nx, ny, top], [nx, ny, bottom], [x, y, bottom]],
          color: side, normal: normalize([ny - y, x - nx, 0]) });
      });
    }
    const box = (x0, y0, x1, y1, top, bottom, color, side, tag) =>
      extrude([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], top, bottom, color, side, tag);
    const outline = [[-1, -.68], [-.76, -.94], [.98, -.94], [1, -.92], [1, .92], [.98, .94], [-.76, .94], [-1, .68]];
    extrude(outline, .20, .32, "#a4a8a9", "#737d83");
    for (const direction of [-1, 1]) {
      const y = direction * 1.13;
      const tab = Array.from({ length: 18 }, (_, i) => {
        const angle = i * Math.PI * 2 / 18;
        return [-.10 + .29 * Math.cos(angle), y + .22 * Math.sin(angle)];
      });
      extrude(tab, .20, .30, "#aeb3b4", "#69777e", direction === -1 ? "tab-left" : "tab-right");
    }
    extrude(outline, -.32, .20, "#bc2e48", "#842439", undefined, true);
    // A thin lid seam makes the casing recognizable in side views.
    extrude(outline.map(([x, y]) => [x * 1.008, y * 1.008]), -.32, -.27, "#c73750", "#a72d46", "case-top");
    box(-1.41, -.74, -1.00, .74, -.03, .28, "#3a424a", "#202b34", "connector-top");
    box(-1.425, -.47, -1.415, .47, .015, .24, "#151e24", "#0e151c");
    // Ten gold contacts on the connector's -X-facing surface.
    for (const y of [-.35, -.175, 0, .175, .35]) for (const z of [.065, .18]) {
      box(-1.46, y - .017, -1.426, y + .017, z - .015, z + .015, "#dcb95d", "#9a7b37");
    }
    for (const y of [-.60, .60]) box(-1.44, y - .075, -1.40, y + .075, .04, .22, "#88959c", "#657078");

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
      const visible = faces.filter(face => dot(transform(matrix, face.normal), view) > 0)
        .map(face => ({ ...face, world: face.points.map(point => transform(matrix, point)) }));
      visible.sort((a, b) => a.world.reduce((sum, p) => sum + dot(p, view), 0) / a.world.length -
        b.world.reduce((sum, p) => sum + dot(p, view), 0) / b.world.length);
      for (const face of visible) {
        const points = face.world.map(project);
        ctx.fillStyle = face.color; ctx.strokeStyle = "#ffffff20"; ctx.lineWidth = .65;
        ctx.beginPath(); ctx.moveTo(...points[0]); points.slice(1).forEach(point => ctx.lineTo(...point)); ctx.closePath(); ctx.fill(); ctx.stroke();
        if (face.tag === "case-top" || face.tag?.startsWith("tab-")) {
          const z = face.tag === "case-top" ? -.325 : .195;
          const origin = project(transform(matrix, [0, 0, z]));
          const x = project(transform(matrix, [1, 0, z]));
          const y = project(transform(matrix, [0, 1, z]));
          ctx.save(); ctx.transform(x[0] - origin[0], x[1] - origin[1], y[0] - origin[0], y[1] - origin[1], ...origin);
          if (face.tag === "case-top") {
            // Top artwork aligns toward +X, as on the reference housing.
            ctx.rotate(-Math.PI / 2); ctx.fillStyle = "#f0e8e4"; ctx.strokeStyle = "#f0e8e4"; ctx.lineWidth = .022;
            for (const triangle of [[[-.37, -.05], [-.10, -.05], [-.23, -.31]], [[.10, -.05], [.37, -.05], [.23, -.31]],
              [[-.13, -.28], [0, -.51], [.13, -.28], [0, -.12]]]) {
              ctx.beginPath(); ctx.moveTo(...triangle[0]); triangle.slice(1).forEach(p => ctx.lineTo(...p)); ctx.closePath(); ctx.stroke();
            }
            ctx.font = "600 .16px sans-serif"; ctx.textAlign = "center"; ctx.fillText("VECTORNAV", 0, .20);
            ctx.font = ".10px sans-serif"; ctx.fillText("VN-100", 0, .44);
          } else {
            const y = face.tag === "tab-left" ? -1.13 : 1.13;
            ctx.fillStyle = "#242e35"; ctx.beginPath(); ctx.arc(-.10, y, .10, 0, 2 * Math.PI); ctx.fill();
            ctx.strokeStyle = "#d1d5d6"; ctx.lineWidth = .025; ctx.stroke();
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
