// Tests web/live-calibration.js and web/live-calibration-sensors.js: the browser-side
// calibration of live samples. Run: node tests/live_calibration.cjs
// Expected values come from hand-derived rotations and from the onyx calibration
// package itself (EllipsoidCalibration.restore + calibrated_enu on the mock calibration).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { webFile, webSource, ROOT } = require('../web_files.cjs');
const { LiveCalibration, FORMAT } = require(webFile('live-calibration.js'));
const { LiveSensor, SENSORS } = require(webFile('live-calibration-sensors.js'));

const NT = 1e-9;
function close(actual, expected, tolerance, label) {
  actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) <= tolerance,
    `${label}: ${actual} does not match ${expected}`));
}
function document(overrides = {}) {
  return { format: FORMAT, method: 'imu', offset_t: [0, 0, 0], correction: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    reference_magnitude_t: 45000 * NT, sample_count: 600, ...overrides };
}
const identity = new LiveCalibration('identity.json', document());

// Onyx reference: examples/mock_calibration.json applied by onyx to two raw readings (tesla).
const mockText = fs.readFileSync(path.join(ROOT, 'examples', 'mock_calibration.json'), 'utf8');
const mock = LiveCalibration.parse('mock_calibration.json', mockText);
const raw = [[20e-6, -5e-6, 40e-6], [1.5e-5, 2.5e-5, -3.0e-5]];
const attitude = [[30, -10, 45], [-120, 25, 170]];
const onyxWithAttitude = [[-20331.940915107833, 29053.442710312884, -26376.111637991267],
  [-11288.465054282598, -32391.609286113777, -26831.24939351175]];
const onyxLevel = [[-6196.491552605762, 19347.404228893498, -39248.83516588647],
  [28195.964490543633, 12199.16118349915, 30866.321327781287]];
// 1e-6 nT is far below the ~1e-11 relative rounding of double arithmetic on 4e4 nT values.
raw.forEach((field, i) => close(mock.enuNT(field, attitude[i]), onyxWithAttitude[i], 1e-6, 'onyx with attitude'));
raw.forEach((field, i) => close(mock.enuNT(field), onyxLevel[i], 1e-6, 'onyx level'));
assert.equal(mock.method, 'imu');
close([mock.referenceNT], [45201.51932181041], 1e-6, 'reference |B|');
console.log('PASS: matches onyx calibrated_enu with and without attitude');

// Level and facing north: body forward/right/down = north/east/down, so ENU = [right, forward, -down].
close(identity.enuNT([1000 * NT, 2000 * NT, 3000 * NT]), [2000, 1000, -3000], 1e-9, 'level');
// Yaw +90 turns forward from north to east.
close(identity.enuNT([1000 * NT, 0, 0], [90, 0, 0]), [1000, 0, 0], 1e-9, 'yaw');
// Pitch +90 raises the nose: forward points up.
close(identity.enuNT([1000 * NT, 0, 0], [0, 90, 0]), [0, 0, 1000], 1e-9, 'pitch');
// Roll +90 lowers the right side: right points down.
close(identity.enuNT([0, 1000 * NT, 0], [0, 0, 90]), [0, 0, -1000], 1e-9, 'roll');
// A rotation keeps |B|.
assert.ok(Math.abs(Math.hypot(...identity.enuNT([1e-6, 2e-6, 3e-6], [32, -24, 71])) - Math.sqrt(14) * 1000) < 1e-9);
console.log('PASS: yaw/pitch/roll signs and level north-facing frame');

// C (B - b): a reading equal to the offset is zero; C scales after subtracting b.
const shifted = new LiveCalibration('b.json', document({ offset_t: [1e-6, -2e-6, 3e-6],
  correction: [[2, 0, 0], [0, 2, 0], [0, 0, 2]] }));
close(shifted.enuNT([1e-6, -2e-6, 3e-6]), [0, 0, 0], 1e-9, 'offset');
close(shifted.correct([2e-6, -2e-6, 3e-6]), [2e-6, 0, 0], 1e-18, 'correct');
assert.equal(shifted.describe(), 'b.json (imu, fitted on 600 rows)');
assert.equal(new LiveCalibration('x.json', document({ sample_count: undefined, method: undefined })).describe(), 'x.json (unknown)');
assert.equal(new LiveCalibration('x.json', document({ reference_magnitude_t: -1 })).referenceNT, null);
console.log('PASS: offset, correction matrix and description');

for (const [label, text, message] of [
  ['not JSON', '{', /not valid JSON/],
  ['wrong format', JSON.stringify(document({ format: 'other' })), /is not an onyx-vector-calibration\/1/],
  ['short offset', JSON.stringify(document({ offset_t: [0, 0] })), /offset_t must be 3 finite numbers/],
  ['NaN offset', JSON.stringify(document({ offset_t: [0, 'x', 0] })), /offset_t/],
  ['2x3 correction', JSON.stringify(document({ correction: [[1, 0, 0], [0, 1, 0]] })), /3x3 matrix/],
  ['bad correction row', JSON.stringify(document({ correction: [[1, 0], [0, 1, 0], [0, 0, 1]] })), /correction/],
  ['null', 'null', /is not an onyx/]]) {
  assert.throws(() => LiveCalibration.parse('bad.json', text), message, label);
}
console.log('PASS: invalid calibration files are refused with a reason');

// VN-100: gauss -> tesla (1 G = 1e-4 T), attitude from the sample. 0.45 G forward = 45,000 nT north.
const vn = SENSORS.vn100;
const level = vn.calibrate(identity, { magnetic: [0.45, 0, 0], attitude: [0, 0, 0] });
close(level.enu, [0, 45000, 0], 1e-6, 'vn100 level');
close([level.total], [45000], 1e-6, 'vn100 total');
close(vn.calibrate(identity, { magnetic: [0.45, 0, 0], attitude: [90, 0, 0] }).enu, [45000, 0, 0], 1e-6, 'vn100 yaw');
assert.equal(vn.calibrate(identity, { magnetic: [0.45, NaN, 0], attitude: [0, 0, 0] }), null);
assert.equal(vn.calibrate(identity, { magnetic: [0.45, 0, 0], attitude: [0, null, 0] }), null);
assert.equal(vn.hasAttitude, true);
// AP230 rows [time, x, y, z, total] in µT, no attitude: level, facing north.
const ap = SENSORS.ap230;
close(ap.calibrate(identity, [1700000000, 10, 20, 30, 37.4]).enu, [20000, 10000, -30000], 1e-6, 'ap230');
assert.equal(ap.calibrate(identity, [1700000000, 10, null, 30, 0]), null);
assert.equal(ap.calibrate(identity, null), null);
assert.equal(ap.hasAttitude, false);
assert.throws(() => new LiveSensor('x', 'X', 1).field({}), /must implement field/);
assert.deepEqual(Object.keys(SENSORS), ['vn100', 'ap230']);
console.log('PASS: VN-100 and AP230 sample adapters');
