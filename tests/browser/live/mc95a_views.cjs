/* Tests web/live/mc95a.js as the bench iframe sees it (fed by a fake BenchTelemetry):
   gain/sensitivity conversions, the readings, badge and notices for every acquisition state,
   spectrum peak picking, plot autoscaling and line gaps, paused plots, the acquisition command
   and shared settings; then the stand-alone page losing its connection. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { runWebScript } = require('../web_files.cjs');
const { fakeCanvas } = require('../fake_canvas.cjs');
const flush = () => new Promise(resolve => setImmediate(resolve));

function page({ telemetry, fetch = () => new Promise(() => {}) }) {
  const nodes = new Map(), clock = { now: 0 };
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, { ...fakeCanvas(400, 200), id, value: { 'frequency-range': '0:500' }[id] || '1', checked: true,
      textContent: '', className: '', disabled: false, style: {}, parentElement: { style: {} } });
    return nodes.get(id);
  };
  const window = { devicePixelRatio: 1, addEventListener() {}, BenchTelemetry: telemetry };
  window.parent = telemetry ? {} : window;
  const context = vm.createContext({ console, document: { getElementById: node }, window, performance: { now: () => clock.now },
    localStorage: { getItem: () => null }, setTimeout() {}, AbortSignal: { timeout() {} }, fetch });
  runWebScript('mc95a.js', context);
  return { node, clock, text: id => node(id).textContent };
}

let sequence = 0, listener, settingsChanged, gain = 2;
const sets = [], maxima = [], requests = [];
const telemetry = { subscribe(fn) { listener = fn; }, setSpectrumMaximum: value => maxima.push(value),
  settings: { gain: () => gain, sensitivity: () => 1, set: (...args) => sets.push(args), subscribe(fn) { settingsChanged = fn; } } };
const F = Array.from({ length: 11 }, (_, i) => i * 50);
const asd = microvolts => microvolts.map(v => v * 2e-6);   // at gain 2, µV/√Hz at the sensor
const frame = (extra = {}, latest = {}) => ({ mc: { stream_id: 1, sequence: ++sequence, status: 'live', sample_rate_Hz: 10240,
  samples_per_channel: 1024, timing: 'Simultaneous sampling', thermal_guard_active: false, error: null,
  channels: [{ channel: 0, label: 'Sensor A', latest: { t: 100, waveform_V: [.002, -.002, .006], ac_rms_V: .002, peak_to_peak_V: .004,
    mean_V: .0005, clipping: false, ...latest },
  history: [{ t: 30, ac_rms_V: .002, band_rms_V: .002 }, { t: 50, ac_rms_V: .002, band_rms_V: null }, { t: 100, ac_rms_V: .004, band_rms_V: .004 }],
  spectrum: { frequency_Hz: F, asd_V_sqrtHz: asd([1, 2, 1, 5, 3, 4, 1, 1, 6, 1, 1]), band_rms_V: .002, peak_Hz: 200 } }], ...extra },
  display_rate_hz: 12.5 });

(async () => {
  const { node, clock, text } = page({ telemetry, fetch: async (url, options) => { requests.push([url, options.method]); return reply; } });
  let reply;
  const values = () => ['ac-0', 'pp-0', 'mean-0', 'field-0', 'frequency-0'].map(text);
  assert.equal(node('gain-0').value, '2', 'the shared gain setting is shown');
  assert.equal(text('raw-output'), 'No fresh amplifier-output readings.');
  assert.deepEqual(values(), ['—', '—', '—', '—', '—']);

  listener(frame());
  assert.deepEqual([text('status'), node('status').className], ['Live', 'badge live']);
  assert.equal(text('config'), 'IEPE off · 10,240 samples/s/channel · 1,024 samples/channel · Display: 12.5 updates/s');
  assert.equal(text('label-0'), 'Sensor A'); assert.equal(node('label-1').parentElement.style.display, 'none', 'one channel shown');
  assert.equal(text('notice'), 'Simultaneous sampling. Compare sensors held still with parallel axes.');
  // Gain 2 halves the amplifier output; 1 mV/mG (100 nT per mV) turns 1 mV band RMS into 100 nT. Mean is not gain-corrected.
  assert.deepEqual(values(), ['1,000', '2,000', '500', '100', '200.00']);
  assert.equal(text('raw-output'), 'S1: 2 mV AC RMS · -2 to 6 mV · ADC clipping: no');
  assert.equal(text('spectrum-note'), 'Latest 0.8 s per channel · Hann window · 1.25 Hz bin spacing. All traces use the same axes.');
  // Local maxima above 10 Hz, largest first, at least 3 bins apart: 400 (6) and 150 (5); 250 (4) is too close to 150.
  assert.equal(text('spectrum-peaks'), 'S1 — #1: 400.00 Hz · 6 µV/√Hz | #2: 150.00 Hz · 5 µV/√Hz\n200 Hz Bin: 200.00 Hz · 3 µV/√Hz');
  // Waveform -1000..3000 µV, padded by 15% of its span (600 µV).
  const wave = node('wave').context;
  ['3600', '2300', '1000', '-300', '-1600', '0 ms', '50 ms', '100 ms', 'µV'].forEach(label => assert.ok(wave.texts().includes(label), label));
  // Trend keeps the last 60 s (t=50, t=100: 1000 then 2000 µV, +15%); the 50 s gap breaks the line.
  const trend = node('trend').context;
  assert.ok(trend.texts().includes('2300') && trend.texts().includes('-60.0 s') && trend.texts().includes('0.0 s'));
  assert.ok(node('field-trend').context.texts().includes('230'), 'field trend: only t=100 has a band value, 200 nT');
  trend.reset(); node('reset').onclick();
  assert.deepEqual([trend.count('moveTo'), trend.count('lineTo')], [5 + 2, 5], 'grid lines plus two unconnected points');

  node('frequency-range').value = '100:300'; node('frequency-range').onchange();
  assert.deepEqual(maxima, [300], 'the shared feed is asked for spectra up to 300 Hz');
  assert.equal(text('spectrum-peaks'), 'S1 — #1: 150.00 Hz · 5 µV/√Hz\n200 Hz Bin: 200.00 Hz · 3 µV/√Hz');
  assert.ok(node('spectrum').context.texts().includes('300.0 Hz'));

  node('sensitivity-0').value = '0'; node('sensitivity-0').oninput();
  assert.deepEqual(sets.at(-1), ['sensitivity', 0, 0]); assert.equal(text('field-0'), '—', 'no field without a sensitivity');
  node('sensitivity-0').value = '1'; node('gain-0').value = '1'; node('gain-0').onchange();
  assert.deepEqual(sets.at(-1), ['gain', 0, 1]); assert.equal(text('ac-0'), '2,000', 'gain 1 shows the amplifier output');
  gain = 51; settingsChanged();
  assert.equal(node('gain-0').value, '51', 'a gain changed in another view is shown here');
  gain = 2; settingsChanged();

  // Pausing the plots keeps drawing the frozen frame (10x larger waveform ignored) while the numbers keep updating.
  node('pause').onclick(); assert.equal(text('pause'), 'Resume Plots');
  wave.reset(); listener(frame({}, { ac_rms_V: .006, waveform_V: [.02, -.02, .06] }));
  assert.ok(wave.texts().includes('3600'), 'the paused wave plot keeps its scale');
  assert.equal(text('ac-0'), '3,000');
  assert.match(text('notice'), / Plots paused; numeric values continue updating\.$/);
  node('pause').onclick(); assert.equal(text('pause'), 'Pause Plots');
  assert.ok(wave.texts().includes('3.6e+4'), 'resumed, the plot rescales to the -10000..30000 µV waveform');

  node('show-0').checked = false; node('show-0').onchange(); listener(frame());
  assert.equal(text('raw-output'), '', 'hidden channels are left out of the raw line');
  assert.match(text('spectrum-peaks'), /^No visible live spectrum/);
  node('show-0').checked = true;

  listener(frame({}, { clipping: true }));
  assert.equal(text('notice'), 'CH0 near ±5 V limit—voltage may be clipped.');
  listener(frame({ status: 'error', error: 'ADC overflow' }));
  assert.deepEqual([text('status'), node('status').className, text('notice'), node('notice').className],
    ['Acquisition Error', 'badge disconnected', 'ADC overflow', 'notice error']);
  listener(frame({ status: 'pausing' }));
  assert.deepEqual([text('status'), text('acquisition'), node('acquisition').disabled], ['Pausing Acquisition', 'Pausing…', true]);
  assert.equal(text('notice'), 'Waiting for acquisition to stop. Wait for Acquisition Paused before changing connections.');
  listener(frame({ status: 'resuming' }));
  assert.deepEqual([text('status'), text('acquisition'), text('notice')], ['Resuming Acquisition', 'Resuming…', 'Waiting for acquisition to restart.']);
  listener(frame({ status: 'paused', thermal_guard_active: true }));
  assert.deepEqual([text('status'), text('acquisition'), node('acquisition').disabled], ['Acquisition Paused', 'Resume Acquisition', true]);
  assert.match(text('notice'), /^Thermal guard: acquisition paused/);
  listener(frame({ status: 'paused' }));
  assert.match(text('notice'), /^ADC acquisition is stopped on all configured channels/); assert.equal(node('acquisition').disabled, false);

  // The acquisition button resumes a paused acquisition and pauses a running one.
  reply = { ok: true, json: async () => frame({ status: 'resuming' }).mc };
  await node('acquisition').onclick();
  assert.deepEqual(requests.at(-1), ['/api/acquisition/resume', 'POST']);
  listener(frame());
  reply = { ok: false, status: 503 }; await node('acquisition').onclick();
  assert.deepEqual(requests.at(-1), ['/api/acquisition/pause', 'POST']);
  assert.match(text('notice'), /^Acquisition command could not be confirmed/);

  // Without a new sequence for 1.5 s the data is stale and the values are blanked.
  clock.now = 2000; const stale = frame(); stale.mc.sequence = sequence - 1; listener(stale);
  assert.deepEqual([text('status'), text('ac-0'), text('notice')], ['Stale', '—', 'No fresh samples. Historical waveforms are hidden.']);
  assert.match(text('config'), /Display: 0\.0 updates\/s$/);
  console.log('PASS: MC95A readings, states, peaks, autoscale, paused plots, commands and settings');

  const alone = page({ telemetry: undefined, fetch: async () => { throw new Error('offline'); } });
  await flush();
  assert.deepEqual([alone.text('status'), alone.text('notice'), alone.node('acquisition').disabled],
    ['Pi Unreachable', 'Connection lost. Retrying automatically.', true]);
  console.log('PASS: MC95A stand-alone page reports a lost connection');
})().catch(error => { console.error(error); process.exitCode = 1; });
