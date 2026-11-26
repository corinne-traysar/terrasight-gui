const assert = require('node:assert/strict');
const { webFile } = require('../web_files.cjs');
const { rotation, displayRotation, cameraAxes, transform } = require(webFile('pose.js'));
function close(actual, expected) {
  actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-10,
    `${actual} does not match ${expected}`));
}
// Screen right, screen up, and the direction toward the camera must be
// right-handed. A mirrored camera reverses observed yaw and roll.
const { right, up, view } = cameraAxes();
const rightCrossUp = [right[1] * up[2] - right[2] * up[1],
  right[2] * up[0] - right[0] * up[2], right[0] * up[1] - right[1] * up[0]];
close(rightCrossUp, view);
// Above the table, positive NED yaw must project clockwise in screen pixels.
const projectedN = [right[0], -up[0]], projectedE = [right[1], -up[1]];
assert.ok(projectedN[0] * projectedE[1] - projectedN[1] * projectedE[0] > 0,
  'positive yaw must appear clockwise when the camera is above the table');
close(transform(rotation(0, 0, 0), [1, 2, 3]), [1, 2, 3]);
// NED: positive yaw turns north (+X) toward east (+Y).
close(transform(rotation(90, 0, 0), [1, 0, 0]), [0, 1, 0]);
// Positive pitch raises the nose: +X turns toward up (-Z).
close(transform(rotation(0, 90, 0), [1, 0, 0]), [0, 0, -1]);
// Positive roll lowers the right side: +Y turns toward down (+Z).
close(transform(rotation(0, 0, 90), [0, 1, 0]), [0, 0, 1]);
close(transform(rotation(180, 0, 0), [1, 2, 3]), transform(rotation(-180, 0, 0), [1, 2, 3]));
// Mixed angles must apply roll, then pitch, then yaw to body vectors.
const mixed = transform(rotation(32, -24, 71), [1, 2, 3]);
close(mixed, transform(rotation(32, 0, 0), transform(rotation(0, -24, 0), transform(rotation(0, 0, 71), [1, 2, 3]))));
assert.ok(Math.abs(Math.hypot(...mixed) - Math.sqrt(14)) < 1e-10);
// A proper camera preserves all sensor signs, without per-axis corrections.
const received = [0, 0, 90];
close(transform(displayRotation(received), [0, 1, 0]), [0, 0, 1]);
assert.deepEqual(received, [0, 0, 90]);
close(transform(displayRotation([90, 0, 0]), [1, 0, 0]), [0, 1, 0]);
close(transform(displayRotation([0, 90, 0]), [1, 0, 0]), [0, 0, -1]);
console.log('PASS: zero pose, yaw/pitch/roll signs, wraparound, and mixed rotation');

// Alignment changes the camera heading, so -X faces the viewer at any yaw.
for (const yaw of [-179, -90, 0, 65, 179, 359]) {
  const camera = cameraAxes(yaw + 180);
  const connector = transform(rotation(yaw, 0, 0), [-1, 0, 0]);
  close([connector.reduce((sum, v, i) => sum + v * camera.right[i], 0)], [0]);
  assert.ok(connector.reduce((sum, v, i) => sum + v * camera.view[i], 0) > .8);
  assert.ok(connector.reduce((sum, v, i) => sum + v * camera.up[i], 0) < 0);
}
// No alignment from missing or historical data; live alignment never edits input.
const pose = require(webFile('pose.js')).create({ setAttribute() {} });
assert.equal(pose.alignView(), false);
const sample = [62, 12, -18];
pose.update(sample, 'stale');
assert.equal(pose.alignView(), false);
pose.update(sample, 'live');
assert.equal(pose.alignView(), true);
assert.deepEqual(sample, [62, 12, -18]);
pose.resetView();
console.log('PASS: connector-facing alignment across yaw wrap and live-data gating');
