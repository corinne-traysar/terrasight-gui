// Tests web/live-calibration-panel.js: the saved calibration per sensor, the status
// text and the panel's Open/Remove behavior, with a minimal fake DOM and storage.
// Run: node tests/live_calibration_panel.cjs
const assert = require('node:assert/strict');
const { webFile } = require('../web_files.cjs');
const { FORMAT } = require(webFile('live-calibration.js'));
const { SENSORS } = require(webFile('live-calibration-sensors.js'));
const { LiveCalibrationPanel, CalibrationStore, statusText } = require(webFile('live-calibration-panel.js'));

const TEXT = JSON.stringify({ format: FORMAT, method: 'imu', offset_t: [0, 0, 0],
  correction: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], reference_magnitude_t: 4.52e-5, sample_count: 600 });

/** A Storage-like map; ``refuse`` makes setItem throw like a full or blocked store. */
function fakeStorage(refuse = false) {
  const items = new Map();
  return { items, getItem: key => items.get(key) ?? null, removeItem: key => items.delete(key),
    setItem(key, value) { if (refuse) throw new Error('QuotaExceededError'); items.set(key, String(value)); } };
}
/** An element stand-in with listeners, text and a disabled flag. */
function fakeElement() {
  const listeners = {};
  return { textContent: '', disabled: false, value: '', files: [],
    addEventListener(type, listener) { listeners[type] = listener; }, fire(type) { return listeners[type](); } };
}
/** A container whose querySelector returns one stable fake per selector. */
function fakeContainer() {
  const elements = {};
  return { elements, innerHTML: '', querySelector: selector => (elements[selector] ??= fakeElement()) };
}
const file = (name, text) => ({ name, text: async () => text });

// Store: save, load, discard unreadable entries, report refused writes.
const storage = fakeStorage(), store = new CalibrationStore('vn100', storage);
assert.equal(store.load(), null);
assert.equal(store.save('cal.json', TEXT), true);
assert.equal(store.load().name, 'cal.json');
assert.deepEqual([...storage.items.keys()], ['live-calibration-vn100']);
storage.items.set('live-calibration-vn100', '{"name":"cal.json","text":"{"}');
assert.equal(store.load(), null);
assert.equal(storage.items.size, 0, 'an unreadable calibration is discarded');
assert.equal(new CalibrationStore('ap230', fakeStorage(true)).save('cal.json', TEXT), false);
assert.equal(new CalibrationStore('ap230', null).load(), null);
console.log('PASS: calibration store per sensor');

// Status text names the frame each sensor uses, |B| and the reference.
assert.equal(statusText(SENSORS.vn100, null, null).badge, 'Off');
const calibration = store.save('cal.json', TEXT) && store.load();
const vnStatus = statusText(SENSORS.vn100, calibration, { enu: [0, 45000, 0], total: 45180.4 });
assert.equal(vnStatus.badge, 'Applied');
assert.match(vnStatus.detail, /rotated with the live yaw\/pitch\/roll/);
assert.match(vnStatus.detail, /\|B\| 45,180 nT \(reference 45,200 nT\)/);
assert.match(statusText(SENSORS.ap230, calibration, null).detail, /level, facing north.*waiting for data/);
calibration.method = 'ellipsoid';
assert.match(statusText(SENSORS.ap230, calibration, null).detail, /Ellipsoid fit: \|B\| is calibrated/);
console.log('PASS: status text');

(async () => {
  // A saved calibration is restored when the panel is built, without a change event.
  const changes = [], container = fakeContainer();
  const saved = fakeStorage();
  new CalibrationStore('vn100', saved).save('saved.json', TEXT);
  const panel = new LiveCalibrationPanel(container, 'vn100', value => changes.push(value), saved);
  assert.equal(panel.calibration.name, 'saved.json');
  assert.equal(container.elements['[role=status]'].textContent, 'Applied');
  assert.equal(container.elements.button.disabled, false);
  assert.deepEqual(changes, []);
  // apply() calibrates a VN-100 sample: 0.45 G forward at yaw 0 is 45,000 nT north.
  const enu = panel.apply({ magnetic: [0.45, 0, 0], attitude: [0, 0, 0] }).enu;
  [0, 45000, 0].forEach((expected, i) => assert.ok(Math.abs(enu[i] - expected) < 1e-6, `${enu} is not [0, 45000, 0]`));
  panel.showResult({ enu: [0, 45000, 0], total: 45000 });
  assert.match(container.elements['.pose-caption'].textContent, /\|B\| 45,000 nT/);

  // Remove clears the calibration, its storage and disables Remove.
  container.elements.button.fire('click');
  assert.deepEqual(changes, [null]);
  assert.equal(panel.apply({ magnetic: [0.45, 0, 0], attitude: [0, 0, 0] }), null);
  assert.equal(saved.items.size, 0);
  assert.equal(container.elements['[role=status]'].textContent, 'Off');
  assert.equal(container.elements.button.disabled, true);

  // Opening a file applies and saves it; a bad file leaves the panel unchanged with an error.
  await panel.open(file('new.json', TEXT));
  assert.equal(changes.at(-1).name, 'new.json');
  assert.equal(JSON.parse(saved.items.get('live-calibration-vn100')).name, 'new.json');
  await panel.open(file('broken.json', '{"format":"other"}'));
  assert.match(container.elements['[role=alert]'].textContent, /Cannot open broken.json: .*not an onyx/);
  assert.equal(panel.calibration.name, 'new.json');
  await panel.open(undefined);
  assert.equal(changes.length, 2);

  // The file input opens the chosen file and is reset so the same file can be chosen again.
  const input = container.elements.input;
  input.files = [file('picked.json', TEXT)]; input.value = 'C:\\fakepath\\picked.json';
  input.fire('change');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(panel.calibration.name, 'picked.json');
  assert.equal(input.value, '');

  // When the browser refuses to save, the calibration still applies to this page.
  const refusing = new LiveCalibrationPanel(fakeContainer(), 'ap230', () => {}, fakeStorage(true));
  await refusing.open(file('cal.json', TEXT));
  assert.equal(refusing.calibration.name, 'cal.json');
  console.log('PASS: panel open, apply, remove and restore');
})().catch(error => { console.error(error); process.exitCode = 1; });
