/* Tests web/live/ap230.js: status badges and readings, the Start/Stop commands, freezing the
   plots, the charts (axis labels, the time window and gaps), the live calibration panel's
   east/north/up readout, and the stand-alone polling fallback. Fake DOM, fetch and canvas. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { runWebScript } = require('../web_files.cjs');
const { fakeCanvas } = require('../fake_canvas.cjs');

const CALIBRATION = JSON.stringify({ format: 'onyx-vector-calibration/1', method: 'imu', offset_t: [0, 0, 0],
  correction: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], reference_magnitude_t: 4.52e-5, sample_count: 600 });
const flush = () => new Promise(resolve => setImmediate(resolve));

/** A page with ap230.js loaded; `telemetry` subscribes it to a fake BenchTelemetry, otherwise it polls `fetch`. */
function page({ fetch, telemetry = true }) {
  const nodes = new Map(), feed = {}, timers = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, { ...fakeCanvas(600, 300), id, value: id === 'window' ? '60' : '', checked: false,
      hidden: false, disabled: false, textContent: '', className: '', innerHTML: '', children: {},
      querySelector(selector) { return this.children[selector] ??= { textContent: '', addEventListener() {} }; } });
    return nodes.get(id);
  };
  const context = vm.createContext({ console, Math, Number, String, JSON, Date, Promise, Array, Error,
    document: { getElementById: node, body: {} }, ResizeObserver: class { observe() {} }, AbortSignal: { timeout() {} },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} }, setTimeout: fn => timers.push(fn), fetch });
  context.window = context;
  if (telemetry) context.BenchTelemetry = { subscribe(listener) { feed.send = ap => listener(ap && { ap }); } };
  for (const name of ['live-calibration.js', 'live-calibration-sensors.js', 'live-calibration-panel.js', 'ap230.js']) runWebScript(name, context);
  return { node, feed, timers, run: code => vm.runInContext(code, context) };
}
const reading = (extra = {}) => ({ status: 'live', running: true, count: 1234, rate_hz: 9.96, nonmeasurement_lines: 2, age_s: 1.5,
  error: null, latest: [100, 10, 20, 30, 37.42], samples: [[10, 1, 1, 1, 2], [98, 10, 20, 30, 37], [98.1, 10, 20, 30, 37], [100, 10, 20, 30, 37.42]], ...extra });

(async () => {
  const requests = [];
  let reply = { ok: true, json: async () => reading({ running: false, status: 'stopped' }) };
  const { node, feed, run } = page({ fetch: async (url, options) => { requests.push([url, options.method]); return reply; } });
  const text = id => node(id).textContent;
  assert.equal(text('status'), 'Pi Unreachable', 'nothing received yet');
  assert.equal(node('calibrated').hidden, true, 'no calibration saved in this browser');
  assert.equal(node('start').disabled, true);
  assert.ok(node('axes-plot').context.texts().includes('Start AP230 to see live readings'));

  node('axes-plot').context.reset(); feed.send(reading());
  assert.equal(text('status'), 'Live'); assert.equal(node('status').className, 'badge live');
  assert.deepEqual(['x', 'y', 'z', 'total'].map(text), ['10.00', '20.00', '30.00', '37.42']);
  assert.equal(text('details'), '1,234 complete XYZ readings · 10.0 readings/s · 2 nonmeasurement lines · last reading 1.5 s ago');
  assert.deepEqual([node('start').disabled, node('stop').disabled], [true, false], 'running: only Stop');
  assert.equal(text('cal-east'), '—', 'no calibrated values without a calibration');
  const axes = node('axes-plot').context;
  ['-65', '0', '65', 'µT', '-60 s', '-40 s', '-20 s', '0 s'].forEach(label => assert.ok(axes.texts().includes(label), label));
  // 5 grid lines; per axis the 10 s row is outside the 60 s window and the 1.9 s gap before t=100 breaks the line.
  assert.deepEqual([axes.count('moveTo'), axes.count('lineTo')], [5 + 3 * 2, 5 + 3 * 1]);
  assert.ok(node('total-plot').context.texts().includes('115'), 'total |B| axis runs to 115 µT');

  // Freezing keeps the plot while the readings keep updating; unfreezing redraws.
  node('freeze').checked = true; node('freeze').onchange();
  assert.equal(node('frozen').hidden, false);
  axes.reset(); feed.send(reading({ latest: [101, 11, 20, 30, 38] }));
  assert.equal(axes.count('stroke'), 0, 'frozen plots are not redrawn');
  assert.equal(text('x'), '11.00', 'numbers still update while frozen');
  node('freeze').checked = false; node('freeze').onchange();
  assert.equal(node('frozen').hidden, true); assert.ok(axes.count('stroke') > 0);

  // Status words for every state; readings blank unless live.
  for (const [status, word, kind] of [['stopped', 'Stopped', 'waiting'], ['error', 'Connection Error', 'disconnected'],
    ['stale', 'Data Stale', 'waiting'], ['starting', 'Waiting for Data', 'waiting'], ['unreachable', 'Pi Unreachable', 'disconnected']]) {
    feed.send(reading({ status, running: false, error: status === 'error' ? 'serial port closed' : null }));
    assert.deepEqual([text('status'), node('status').className, text('x')], [word, 'badge ' + kind, '—'], status);
  }
  assert.equal(text('error'), 'serial port closed');
  feed.send(reading({ status: 'stopped', running: false, rate_hz: null, age_s: null }));
  assert.equal(text('details'), '1,234 complete XYZ readings · rate pending · 2 nonmeasurement lines');
  assert.deepEqual([node('start').disabled, node('stop').disabled], [false, true], 'stopped: only Start');
  feed.send(null); assert.equal(text('status'), 'Stopped', 'an empty telemetry snapshot is ignored');

  // Start posts the command, clears the frozen plot and takes the answer as the current state.
  node('freeze').checked = true; node('frozen').hidden = false;
  reply = { ok: true, json: async () => reading({ samples: [] }) };
  await node('start').onclick();
  assert.deepEqual(requests.at(-1), ['/api/ap230/start', 'POST']);
  assert.deepEqual([node('freeze').checked, node('frozen').hidden, text('status')], [false, true, 'Live']);
  reply = { ok: false, json: async () => ({ error: 'AP230 is not connected' }) };
  await node('stop').onclick();
  assert.deepEqual(requests.at(-1), ['/api/ap230/stop', 'POST']);
  assert.equal(text('error'), 'AP230 is not connected');
  reply = { ok: false, json: async () => ({}) }; await node('stop').onclick();
  assert.equal(text('error'), 'Command failed', 'a refusal without a message');

  // Live calibration: identity C, no offset; µT x/y/z = forward/right/down, so E = y, N = x, U = -z (nT).
  await run('calibration').open({ name: 'cal.json', text: async () => CALIBRATION });
  assert.equal(node('calibrated').hidden, false);
  node('calibrated-axes-plot').context.reset(); feed.send(reading());
  assert.deepEqual(['cal-east', 'cal-north', 'cal-up', 'cal-total'].map(text), ['20,000', '10,000', '-30,000', '37,417']);
  const calibrated = node('calibrated-axes-plot').context;
  ['-65000', '65000', 'nT'].forEach(label => assert.ok(calibrated.texts().includes(label), label));
  assert.equal(calibrated.count('lineTo'), 5 + 3, 'the calibrated rows are plotted like the raw ones');
  assert.ok(node('calibrated-total-plot').context.texts().includes('115000'));
  run('calibration').set(null);
  assert.equal(node('calibrated').hidden, true, 'removing the calibration hides the calibrated plots');
  console.log('PASS: AP230 status, readings, commands, freeze, charts and live calibration');

  // Without the shared feed the page polls /api/ap230 itself.
  let answer = { ok: true, json: async () => reading() };
  const polled = page({ telemetry: false, fetch: async url => { assert.equal(url, '/api/ap230'); if (answer instanceof Error) throw answer; return answer; } });
  await flush();
  assert.equal(polled.node('status').textContent, 'Live'); assert.equal(polled.timers.length, 1, 'next poll scheduled');
  answer = { ok: false, json: async () => ({}) }; polled.timers.shift()(); await flush();
  assert.equal(polled.node('status').textContent, 'Pi Unreachable');
  answer = new Error('network down'); polled.timers.shift()(); await flush();
  assert.equal(polled.node('status').textContent, 'Pi Unreachable'); assert.equal(polled.timers.length, 1);
  console.log('PASS: AP230 polling fallback');
})().catch(error => { console.error(error); process.exitCode = 1; });
