/* Tests web/offline/offline-calibration.js, Apply Calibration in Offline Data: opening a
   calibration JSON, the button states and calibration line, applying it to the magnetic file
   (request, calibrated series, angle window opened in the click and sent the payload),
   pop-up blocking, failures, Show Angles, Remove Calibration and a new file dropping it. */
const assert = require('node:assert/strict');
const { offlinePage, flush, file, reply } = require('./fake_page.cjs');
const same = (actual, expected, message) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, message);
const ORIGIN = 'http://pi.local:8080';
const CAL = JSON.stringify({ format: 'onyx-vector-calibration/1', method: 'imu', sample_count: 600 });
const LOADED = { source: 'scan.csv', count: 2, labels: ['E', 'N', 'U'], field_nt: [[3, 4, 0], [0, 0, 2]], attitude: { columns: ['yaw', 'pitch', 'roll'] } };
const APPLIED = { count: 2, labels: ['E', 'N', 'U'], field_nt: [[1, 2, 2], [0, 0, 3]], b_columns: ['Bx', 'By', 'Bz'],
  calibration: { method: 'imu', mounting_deg: { yaw: 1, pitch: 2, roll: 3 } }, summary: { attitude_used: false } };

/** A pop-up window stand-in that records focus and messages. */
const popup = () => ({ closed: false, focused: 0, messages: [], focus() { this.focused++; }, postMessage(message, origin) { this.messages.push([message, origin]); } });

/** Offline Data with offline-calibration.js; `status` answers /api/calibration/status, `answers` the other URLs. */
async function view(status, answers) {
  const opened = [], windows = [];
  const fetch = (url, options) => { if (url === '/api/calibration/status') return status(); opened.push([url, JSON.parse(options.body)]); return answers[url](); };
  const page = offlinePage(fetch, { location: { origin: ORIGIN }, open: (...args) => { opened.push(['open', ...args]); return windows.shift() ?? null; } });
  page.load('offline-calibration.js'); await flush();
  const choose = async (id, chosen) => { page.node(id).onchange({ target: { files: [chosen], value: 'x' } }); await flush(); };
  return { ...page, opened, windows, choose, text: id => page.node(id).textContent };
}

(async () => {
  let release, loaded = LOADED;
  const answers = { '/api/offline/load': () => reply(loaded),
    '/api/offline/calibrate': () => new Promise(resolve => { release = (data, code = 200) => resolve({ ok: code < 400, status: code, json: async () => data }); }) };
  const { node, run, context, opened, windows, choose, text } = await view(() => reply({ available: true, reason: null }), answers);
  const apply = node('apply-calibration');
  assert.equal(text('calibration-line'), 'Calibration: none. Open an onyx calibration JSON (from the Calibration tab) to calibrate the magnetic data.');
  assert.deepEqual([apply.disabled, apply.title, node('show-angles').disabled, node('remove-calibration').disabled], [true, 'Open a calibration JSON first.', true, true]);

  await choose('calibration-file', file('bad.json', '{'));
  assert.equal(text('error'), 'bad.json is not valid JSON.');
  await choose('calibration-file', file('other.json', '{"format":"x"}'));
  assert.equal(text('error'), 'other.json is not an onyx-vector-calibration/1 calibration file.');
  await choose('calibration-file', file('cal.json', CAL));
  assert.equal(text('error'), '');
  assert.equal(text('calibration-line'), 'Calibration: cal.json (imu, fitted on 600 rows) is open. Select Apply Calibration.');
  assert.deepEqual([apply.disabled, apply.title], [true, 'Open a magnetic file first.']);
  await choose('magnetic-file', file('scan.csv', 'raw text'));
  assert.deepEqual([apply.disabled, apply.title], [false, 'Calibrate the magnetic data with the open calibration and open the angle window']);

  // Apply: the window opens in the click with a pending payload, before the server answers.
  const angleWindow = popup(); windows.push(angleWindow);
  const applying = apply.onclick();
  assert.deepEqual(opened.at(-2), ['open', '/angles', 'terrasight-angles', 'popup,width=1200,height=900']);
  assert.equal(context.terrasightAngles.pending, 'Applying cal.json to scan.csv…');
  assert.deepEqual([apply.disabled, text('status')], [true, 'Calibrating scan.csv with cal.json…']);
  assert.deepEqual(opened.at(-1), ['/api/offline/calibrate', { name: 'scan.csv', text: 'raw text', calibration: CAL }]);
  release(APPLIED); await applying;
  assert.equal(text('status'), 'Magnetic (calibrated): scan.csv calibrated with cal.json, 2 samples');
  assert.equal(run('magnitudeGraph(series.magnetic).traces["|B|"][0]'), 3, 'the main graph shows the calibrated |B|');
  assert.equal(text('calibration-line'), 'Calibration: cal.json applied to scan.csv (level, facing north; 2 rows).');
  assert.deepEqual([node('show-angles').disabled, node('remove-calibration').disabled, text('error')], [false, false, '']);
  const [message, origin] = angleWindow.messages.at(-1);
  assert.equal(origin, ORIGIN);
  same(message, { type: 'terrasight-angles', data: { calibration: { name: 'cal.json', method: 'imu', mounting_deg: { yaw: 1, pitch: 2, roll: 3 } },
    summary: { attitude_used: false }, appliedTo: 'scan.csv', bColumns: ['Bx', 'By', 'Bz'], calibratedRows: 2,
    scans: [{ sensor: 'magnetic', label: 'Magnetic', source: 'scan.csv', count: 2, attitude: { columns: ['yaw', 'pitch', 'roll'] } }] } },
  'the payload names the raw scan, not the calibrated copy');

  // Applying again calibrates the raw data, not the calibrated copy; the open window is reused.
  const again = apply.onclick(); release({ ...APPLIED, summary: { attitude_used: true } }); await again;
  assert.equal(angleWindow.focused, 1);
  assert.equal(opened.filter(r => r[0] === '/api/offline/calibrate').at(-1)[1].text, 'raw text');
  assert.match(text('calibration-line'), /with the scan's yaw\/pitch\/roll; 2 rows/);

  node('show-angles').onclick();
  assert.equal(angleWindow.focused, 2); assert.equal(angleWindow.messages.at(-1)[0].data.calibratedRows, 2);
  angleWindow.closed = true; node('show-angles').onclick();
  assert.equal(text('error'), 'The browser blocked the angle window. Allow pop-ups for this dashboard and try again.');

  node('remove-calibration').onclick();
  assert.equal(text('status'), 'Magnetic: scan.csv, 2 samples', 'the raw data is shown again');
  assert.equal(context.terrasightAngles.calibration, null);
  assert.deepEqual([node('show-angles').disabled, node('remove-calibration').disabled], [true, true]);
  node('remove-calibration').onclick();
  assert.equal(text('status'), 'Magnetic: scan.csv, 2 samples', 'removing twice changes nothing');

  // A blocked window still calibrates; a server failure is reported in the page and to the window.
  const blocked = apply.onclick(); release(APPLIED); await blocked;
  assert.equal(text('error'), 'The browser blocked the angle window. Select Show Angles to open it.');
  const failing = popup(); windows.push(failing);
  node('remove-calibration').onclick();
  const refused = apply.onclick(); release({ error: 'bad matrix' }, 422); await refused;
  assert.equal(text('error'), 'Cannot apply cal.json: bad matrix');
  assert.equal(failing.messages.at(-1)[0].data.error, 'Cannot apply cal.json to scan.csv: bad matrix');
  assert.equal(text('status'), 'Magnetic: scan.csv, 2 samples', 'nothing is calibrated');
  assert.deepEqual([apply.disabled, node('show-angles').disabled], [false, true]);

  // A new magnetic file replaces the raw data, so the applied calibration is dropped (the window is told).
  const success = apply.onclick(); release(APPLIED); await success;
  loaded = { ...LOADED, source: 'next.csv' };
  await choose('magnetic-file', file('next.csv', 'next'));
  assert.equal(text('calibration-line'), 'Calibration: cal.json (imu, fitted on 600 rows) is open. Select Apply Calibration.');
  assert.equal(failing.messages.at(-1)[0].data.calibration, null);
  assert.equal(failing.messages.at(-1)[0].data.scans[0].source, 'next.csv');
  failing.postMessage = () => { throw new Error('window gone'); };
  await choose('magnetic-file', file('next.csv', 'next'));
  const reopened = popup(), opens = () => opened.filter(r => r[0] === 'open').length, before = opens();
  windows.push(reopened);
  const last = apply.onclick(); release(APPLIED); await last;
  assert.equal(opens(), before + 1, 'a window that cannot be reached is forgotten and opened anew');
  assert.equal(reopened.messages.at(-1)[0].data.appliedTo, 'next.csv');
  console.log('PASS: open, apply, re-apply, show, remove, failures and pop-up blocking');

  // Without calibration support the button explains why.
  const off = await view(() => Promise.reject(new Error('offline')), { '/api/offline/load': () => reply(LOADED) });
  await off.choose('calibration-file', file('cal.json', CAL)); await off.choose('magnetic-file', file('scan.csv', 'x'));
  assert.equal(off.node('apply-calibration').disabled, true);
  assert.equal(off.node('apply-calibration').title, 'The dashboard server did not report calibration support.');
  assert.match(off.text('calibration-line'), /is open\. The dashboard server did not report calibration support\.$/);
  const unavailable = await view(() => reply({ available: false, reason: 'onyx is not installed' }), {});
  assert.equal(unavailable.node('apply-calibration').title, 'onyx is not installed');
  console.log('PASS: Apply Calibration without server support');
})().catch(error => { console.error(error); process.exitCode = 1; });
