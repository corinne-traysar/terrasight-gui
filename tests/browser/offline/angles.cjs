/* Tests web/offline/angles.js, the Calibration and Scan Angles window: the banner and badge for
   each state, the calibration card (facts, mounting, Earth field, notes), attitude range tiles
   and plots for the calibration scan and open scans, updates by postMessage (same origin only),
   and the messages shown without an opener. */
const assert = require('node:assert/strict');
const { page, findAll } = require('./fake_page.cjs');

const ORIGIN = 'http://pi.local:8080';
const IMU = { name: 'cal.json', method: 'imu', sample_count: 1200, output_frame: 'ENU', reflected: true,
  mounting_deg: { yaw: 1.234, pitch: -2, roll: .5 },
  earth: { declination_deg: 4.5, inclination_deg: 62.25, total_nt: 45201.53, enu_nt: [1650.2, 20966.4, -39999.6] },
  attitude: { columns: ['yaw', 'pitch', 'roll'], axis: 'time [s]', axis_values: [0, 1, 2], degrees: [[10, 0, 0], [20, null, 5], [30, 2, -5]] } };
const PAYLOAD = { calibration: IMU, summary: { attitude_used: true, b_total_mean_nt: 45201.26, b_total_std_nt: 3.04 },
  appliedTo: 'scan.csv', bColumns: ['Bx', 'By', 'Bz'], calibratedRows: 1500,
  scans: [{ sensor: 'magnetic', label: 'Magnetic', source: 'scan.csv', count: 1500,
    attitude: { columns: ['yaw_deg', 'pitch_deg', 'roll_deg'], axis: 't', axis_values: [0, NaN], degrees: [[0, 0, 0], [90, 0, 0]] } },
  { sensor: 'electromagnetic', label: 'Electromagnetic', source: 'em.csv', count: 20, attitude: null }] };

/** The angle window opened by an Offline Data view holding `payload`; returns its page and message listener. */
function open(opener) {
  const listeners = {};
  const view = page({ location: { origin: ORIGIN }, opener, addEventListener: (type, fn) => { listeners[type] = fn; } }, { size: [600, 260] });
  view.load('angles.js');
  return { ...view, message: data => listeners.message(data) };
}
const byClass = (root, name) => findAll(root, n => n.className === name);
const texts = (root, tag) => findAll(root, n => n.tagName === tag).map(n => n.textContent);
const facts = root => { const list = byClass(root, 'facts')[0].children; return Object.fromEntries(list.filter((_, i) => i % 2 === 0).map((dt, i) => [dt.textContent, list[2 * i + 1].textContent])); };
const tiles = root => byClass(root, 'tile').map(tile => [...tile.children.map(c => c.textContent), tile.children[1].style.color]);

const { node, context, message } = open({ terrasightAngles: PAYLOAD });
const COLORS = [...context.ScanPlot.COLORS];
assert.equal(node('banner').textContent, 'cal.json applied to scan.csv · 1,500 calibrated rows.');
assert.equal(node('banner').className, 'banner');
assert.deepEqual([node('badge').textContent, node('badge').className], ['Calibrated', 'badge live']);
assert.equal(context.document.title, 'Angles · cal.json');

const card = node('calibration').children[0];
assert.deepEqual(texts(card, 'h3'), ['cal.json']);
assert.deepEqual(facts(card), { Method: 'imu', 'Fitted on': '1,200 rows', 'Output frame': 'ENU', 'B columns read': 'Bx, By, Bz',
  'Attitude used when applying': 'yes (the scan\'s yaw/pitch/roll)', 'Calibrated |B|': '45,201.3 nT ± 3 nT (mean ± std)' });
const cardTiles = tiles(card);
assert.deepEqual(cardTiles.slice(0, 3), [['Yaw', '1.23°', 'fitted', COLORS[0]], ['Pitch', '-2.00°', 'fitted', COLORS[1]], ['Roll', '0.50°', 'fitted', COLORS[2]]]);
assert.deepEqual(cardTiles.slice(3, 6).map(t => t.slice(0, 3)), [['Declination', '4.50°', 'east of north'], ['Inclination', '62.25°', 'below horizontal'],
  ['|B|', '45,201.5 nT', 'E/N/U 1,650 / 20,966 / -40,000 nT']]);
// The calibration scan: ranges skip the missing pitch; the plot runs over the scan's time axis.
assert.deepEqual(cardTiles.slice(6).map(t => t.slice(0, 3)), [['Yaw · yaw', '20.0° span', '10.0° to 30.0°'],
  ['Pitch · pitch', '2.0° span', '0.0° to 2.0°'], ['Roll · roll', '10.0° span', '-5.0° to 5.0°']]);
const notes = texts(card, 'p');
assert.deepEqual(notes, ['The correction matrix mirrors the axes (negative determinant); the angles are of its mirror image.'], 'only the mirror note for an IMU fit');

const canvases = findAll(node('calibration'), n => n.tagName === 'canvas').concat(findAll(node('scans'), n => n.tagName === 'canvas'));
assert.deepEqual(canvases.map(c => c.attributes['aria-label']), ['Yaw, pitch and roll in degrees over the time [s]',
  'Yaw, pitch and roll in degrees over the sample index'], 'a scan whose axis has a gap is plotted over the sample index');
const plot = canvases[0].context;
['time [s]', '-180°', '-90°', '0°', '90°', '180°'].forEach(label => assert.ok(plot.texts().includes(label), label));
assert.deepEqual(plot.named('stroke').filter(c => COLORS.slice(0, 3).includes(c.strokeStyle)).map(c => c.strokeStyle), COLORS.slice(0, 3),
  'one trace each for yaw, pitch and roll');

const [scan, em] = node('scans').children;
assert.deepEqual(texts(scan, 'h3'), ['Magnetic: scan.csv']);
assert.deepEqual(facts(scan), { Rows: '1,500', 'Attitude columns': 'yaw_deg, pitch_deg, roll_deg' });
assert.deepEqual(tiles(scan)[0].slice(0, 3), ['Yaw · yaw_deg', '90.0° span', '0.0° to 90.0°']);
assert.deepEqual(texts(em, 'p'), ['No yaw/pitch/roll columns in this scan.']);
console.log('PASS: angle window with an IMU calibration and two scans');

/* Updates arrive by postMessage, from this dashboard only. */
message({ origin: 'http://elsewhere', data: { type: 'terrasight-angles', data: { error: 'spoofed', scans: [] } } });
assert.equal(node('badge').textContent, 'Calibrated', 'messages from other origins are ignored');
message({ origin: ORIGIN, data: { type: 'other', data: { error: 'x', scans: [] } } });
assert.equal(node('badge').textContent, 'Calibrated', 'other message types are ignored');
message({ origin: ORIGIN, data: { type: 'terrasight-angles', data: null } });
assert.equal(node('badge').textContent, 'Calibrated', 'an empty update is ignored');
message({ origin: ORIGIN, data: { type: 'terrasight-angles', data: { ...PAYLOAD, pending: 'Applying cal.json to scan.csv…' } } });
assert.deepEqual([node('banner').textContent, node('badge').textContent, node('badge').className], ['Applying cal.json to scan.csv…', 'Applying', 'badge waiting']);
message({ origin: ORIGIN, data: { type: 'terrasight-angles', data: { calibration: null, scans: [], error: 'Cannot apply cal.json: bad matrix' } } });
assert.deepEqual([node('banner').textContent, node('banner').className, node('badge').textContent, node('badge').className],
  ['Cannot apply cal.json: bad matrix', 'banner error', 'Error', 'badge disconnected']);
assert.deepEqual(texts(node('calibration'), 'p'), ['No calibration applied yet.']);
assert.deepEqual(texts(node('scans'), 'p'), ['No scan is open in Offline Data.']);
assert.equal(context.document.title, 'Calibration Angles');

message({ origin: ORIGIN, data: { type: 'terrasight-angles', data: { calibration: null, scans: [] } } });
assert.deepEqual([node('badge').textContent, node('banner').textContent], ['No Calibration',
  'No calibration is applied in Offline Data. Open a calibration JSON there and select Apply Calibration.']);

/* An ellipsoid fit: declared mounting, no Earth field, no stored attitude; a magnetic scan without attitude. */
const ellipsoid = { name: 'ell.json', method: 'ellipsoid', mounting_deg: { yaw: 0, pitch: 0, roll: 180 }, earth: null, attitude: null };
message({ origin: ORIGIN, data: { type: 'terrasight-angles', data: { calibration: ellipsoid, summary: { attitude_used: false, b_total_mean_nt: NaN, b_total_std_nt: 1 },
  appliedTo: 'm.csv', bColumns: [], calibratedRows: 3, scans: [{ sensor: 'magnetic', label: 'Magnetic', source: 'm.csv', count: 3, attitude: null },
    { sensor: 'electromagnetic', label: 'Electromagnetic', source: 'e.csv', count: 0, attitude: { columns: ['y', 'p', 'r'], axis: 'i', axis_values: [], degrees: [] } }] } } });
const ellCard = node('calibration').children[0];
const ellFacts = facts(ellCard);
assert.deepEqual([ellFacts['Fitted on'], ellFacts['Output frame'], ellFacts['B columns read'], ellFacts['Attitude used when applying'], ellFacts['Calibrated |B|']],
  ['—', '—', '—', 'no (level, facing north)', '— ± 1 nT (mean ± std)']);
assert.deepEqual(tiles(ellCard).map(t => t[2]), ['declared', 'declared', 'declared']);
assert.equal(texts(ellCard, 'p').length, 3, 'ellipsoid, Earth-field and stored-attitude notes');
assert.match(texts(ellCard, 'p')[0], /^The ellipsoid method cannot measure the mounting/);
assert.match(texts(ellCard, 'p')[1], /^Not estimated: only the IMU method fits the Earth field/);
assert.deepEqual(texts(node('scans').children[0], 'p'), ['No yaw/pitch/roll columns: the calibration took the sensor as level and facing north.']);
const emptyScan = node('scans').children[1];
assert.deepEqual(tiles(emptyScan).map(t => t.slice(1)), COLORS.slice(0, 3).map(color => ['no values', color]), 'no range and no detail line');
assert.deepEqual(findAll(emptyScan, n => n.tagName === 'canvas')[0].context.texts(), ['No rows']);
console.log('PASS: postMessage updates, error/pending/empty states and an ellipsoid calibration');

/* Without an opener, or one this window cannot read. */
assert.equal(open(undefined).node('banner').textContent, 'Open this window from Offline Data: open a calibration JSON and select Apply Calibration.');
const blocked = { get terrasightAngles() { throw new Error('cross-origin'); } };
assert.equal(open(blocked).node('banner').textContent, 'Cannot read the Offline Data view that opened this window.');
console.log('PASS: angle window opened without a readable Offline Data view');
