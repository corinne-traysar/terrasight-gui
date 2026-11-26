/* Drawing checks for web/live/pose.js (the VN-100 housing model) and web/live/capsule.js
   (the capsule wireframe): canvas sizing, the waiting text, back-face culling of the housing,
   on-screen axis directions, and the dimmed look of non-live data. Uses a recording 2D context. */
const assert = require('node:assert/strict');
const { webFile } = require('../web_files.cjs');
const { fakeCanvas } = require('../fake_canvas.cjs');
const pose = require(webFile('pose.js'));
const { createCapsule } = require(webFile('capsule.js'));
const close = (a, b, tol = 1e-9, message = '') => assert.ok(Math.abs(a - b) <= tol, `${message} ${a} != ${b}`);
globalThis.devicePixelRatio = 2;

/* ---- pose.js: the housing. 670 x 450 CSS px gives a scale of exactly 100 px per unit. */
const canvas = fakeCanvas(670, 450), c = canvas.context, model = pose.create(canvas);
model.update(null, 'waiting'); model.draw();
assert.deepEqual([canvas.width, canvas.height], [1340, 900], 'backing store follows the device pixel ratio');
assert.equal(canvas.attributes['aria-label'], 'Waiting for attitude measurements');
assert.deepEqual(c.texts(), ['N', 'E', 'D', 'Waiting for attitude measurements'], 'only the compass and the waiting text');
assert.equal(c.count('fill'), 3, 'no housing faces without attitude, only the three compass arrow heads');

/* The unit vector from `from` toward where the arrow labelled `label` points (labels sit 14 px past the tip, 4 px low). */
function direction(context, label, from) {
  const [, x, y] = context.text(label).args, dx = x - from[0], dy = y - 4 - from[1], length = Math.hypot(dx, dy);
  return [dx / length, dy / length];
}
const compass = [44, 450 - 43], center = [335, 450 * .46];
const sameDirection = (a, b, message) => a.forEach((v, i) => close(v, b[i], 1e-9, message));

c.reset(); model.update([0, 0, 0], 'live'); model.draw();
assert.equal(canvas.attributes['aria-label'], 'Live orientation: yaw 0.00, pitch 0.00, roll 0.00 degrees');
assert.ok(c.texts().includes('VECTORNAV') && c.texts().includes('VN-100'), 'the lid artwork faces the camera when level');
assert.equal(c.count('arc'), 2, 'both mounting-tab holes are seen from above');
assert.ok(c.named('fill').some(call => call.fillStyle === '#c73750'), 'the red lid is filled');
assert.ok(c.named('fill').every(call => call.globalAlpha === 1), 'live data is drawn opaque');
sameDirection(direction(c, '+X', center), direction(c, 'N', compass), 'level, +X points north');
sameDirection(direction(c, '+Y', center), direction(c, 'E', compass), 'level, +Y points east');

c.reset(); model.update([90, 0, 0], 'live'); model.draw();
sameDirection(direction(c, '+X', center), direction(c, 'E', compass), 'yaw 90 turns +X east');
c.reset(); model.update([0, 90, 0], 'live'); model.draw();
sameDirection(direction(c, '+X', center), direction(c, 'D', compass).map(v => -v), 'pitch 90 raises +X up');

c.reset(); model.update([0, 0, 180], 'live'); model.draw();
assert.ok(!c.texts().includes('VECTORNAV'), 'upside down, the lid artwork is culled');
assert.ok(!c.named('fill').some(call => call.fillStyle === '#c73750'), 'upside down, the lid face is culled');
assert.ok(c.named('fill').some(call => call.fillStyle === '#a72d46'), 'upside down, the lid underside is seen');

c.reset(); model.update([10, 20, 30], 'stale'); model.draw();
assert.match(canvas.attributes['aria-label'], /^Last received orientation: yaw 10.00, pitch 20.00, roll 30.00/);
const faceFills = c.named('fill').filter(call => call.fillStyle === '#737d83' || call.fillStyle === '#a4a8a9');
assert.ok(faceFills.length && faceFills.every(call => call.globalAlpha === .45), 'old data is dimmed');
c.reset(); model.update([1, 2, NaN], 'live'); model.draw();
assert.ok(c.texts().includes('Waiting for attitude measurements'), 'a missing angle is no attitude');
console.log('PASS: housing sizing, waiting text, culling, axis directions and dimming');

/* ---- capsule.js: the capsule wireframe. */
const capsuleCanvas = fakeCanvas(800, 500), k = capsuleCanvas.context, capsule = createCapsule(capsuleCanvas);
const FOOTER = 'Ø101.6 × 950 mm · Planned Mounting';
capsule.update(undefined, 'waiting'); capsule.draw();
assert.deepEqual([capsuleCanvas.width, capsuleCanvas.height], [1600, 1000]);
assert.equal(capsuleCanvas.attributes['aria-label'], 'Capsule wireframe waiting for VN-100 attitude');
assert.ok(k.texts().includes('Waiting for IMU Attitude') && k.texts().includes(FOOTER));
assert.ok(k.count('fill') > 0, 'the capsule is still drawn, at the zero pose');
['N', 'E', 'D', '+X', '+Y', '+Z'].forEach(label => assert.ok(k.texts().includes(label), `${label} is labelled`));

k.reset(); capsule.update([30, 10, -5], 'live'); capsule.draw();
assert.ok(!k.texts().includes('Waiting for IMU Attitude') && !k.texts().includes('Historical Orientation · Not Live'));
assert.deepEqual(k.texts().at(-1), FOOTER);
const liveAlpha = Math.max(...k.named('fill').map(call => call.globalAlpha));
close(liveAlpha, .1, 1e-12, 'live surfaces keep their own translucency (VN-100 faces .1)');
const vnStrokes = () => k.named('stroke').filter(call => call.strokeStyle === '#e8b775' && call.args.length === 0);
assert.ok(vnStrokes().length && vnStrokes().every(call => call.globalAlpha === 1), 'live VN-100 outlines are opaque');
for (const label of ['N', 'E', 'D', '+X', '+Y', '+Z']) {
  const [, x, y] = k.text(label).args;
  assert.ok(x >= 8 && x <= 800 && y >= 16 && y <= 500 - 28, `${label} label is kept inside the canvas`);
}

k.reset(); capsule.update([30, 10, -5], 'stale'); capsule.draw();
assert.ok(k.texts().includes('Historical Orientation · Not Live'));
close(Math.max(...k.named('fill').map(call => call.globalAlpha)), .03, 1e-12, 'historical surfaces are dimmed to 30%');
assert.ok(vnStrokes().filter(call => call.globalAlpha !== .45).every(call => Math.abs(call.globalAlpha - .3) < 1e-12), 'historical outlines are dimmed to 30%');
console.log('PASS: capsule sizing, status text, labels kept on canvas and live/historical alpha');
