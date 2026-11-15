const assert = require('node:assert/strict');
const { rotation, displayRotation, transform } = require('../web/pose.js');
function close(actual, expected) {
  actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-10,
    `${actual} does not match ${expected}`));
}
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
// The bench display correction reverses only roll, preserving received angles.
const received = [0, 0, 90];
close(transform(displayRotation(received), [0, 1, 0]), [0, 0, -1]);
assert.deepEqual(received, [0, 0, 90]);
close(transform(displayRotation([90, 0, 0]), [1, 0, 0]), [0, 1, 0]);
close(transform(displayRotation([0, 90, 0]), [1, 0, 0]), [0, 0, -1]);
console.log('PASS: zero pose, yaw/pitch/roll signs, wraparound, and mixed rotation');
