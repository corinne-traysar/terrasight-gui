/* Tests the Calibration view's drawing and file handling: web/offline/calibration-plot.js
   (strips, legend clipping, sample-axis ticks, the shaded window, the attitude plot),
   web/offline/calibration-fit.js (opening and applying a calibration file) and the window
   dragging and missing server support of web/offline/calibration.js. Values are checked in
   scan_views.cjs; this file checks what is drawn and sent. */
const assert = require('node:assert/strict');
const { page, flush, file, reply } = require('./fake_page.cjs');
const CAL = JSON.stringify({ format: 'onyx-vector-calibration/1', method: 'imu', sample_count: 600 });
const SCAN = { name: 'scan.csv', axis: 'time [s]', rows: 4, channels: ['Bx', 'By', 'Bz', 'yaw', 'pitch', 'roll'], axis_values: [0, 1, 2, 3],
  columns: { Bx: [0, 1, 2, 3], By: [1, 1, 1, 1], Bz: [3, 2, 1, 0], yaw: [0, 10, 20, 30], pitch: [0, 0, 0, 0], roll: [0, 0, 0, 0] },
  profiles: { magnetic: { b_axes: ['Bx', 'By', 'Bz'], imu: ['yaw', 'pitch', 'roll'] }, electromagnetic: { b_axes: [], imu: ['yaw', 'pitch', 'roll'] } },
  attitude: { columns: ['yaw', 'pitch', 'roll'], to_degrees: [1, 1, 1] } };

/** The Calibration view at 800 x 300 px; `answers` maps URLs to reply functions. */
async function view(answers) {
  const requests = [], downloads = [];
  const fetch = (url, options) => { requests.push([url, options?.body && JSON.parse(options.body)]); return answers[url](); };
  const v = page({ fetch, Blob: class { constructor(parts) { downloads.push(parts.join('')); } } }, { size: [800, 300] });
  v.node('attitude-panel').hidden = true;
  for (const name of ['calibration-plot.js', 'calibration-fit.js', 'calibration.js']) v.load(name);
  await flush();
  return { ...v, requests, downloads, text: id => v.node(id).textContent };
}

(async () => {
  let applyAnswer = () => reply({ csv: 'E,N,U', summary: { rows: 4, attitude_used: true, b_total_mean_nt: 45201.26, b_total_std_nt: 2.54 } });
  const { node, run, context, requests, downloads, text } = await view({ '/api/calibration/status': () => reply({ available: true, default_reference_nt: 45201.5 }),
    '/api/scan/load': () => reply(SCAN), '/api/calibration/apply': () => applyAnswer(), '/api/calibration/fit': () => reply({ error: 'singular' }, 422) });
  const { COLORS, THEME } = context.ScanPlot, plot = node('plot'), shown = plot.context;
  assert.deepEqual(shown.texts(), ['Open a scan and select channels']);

  await run("openScan({name:'scan.csv',text:async()=>'csv'})");
  const layer = run('layer.canvas.context');
  // Two strips of (300 - 34) / 2 = 133 px; titles 10 px below each strip top, legends in palette order.
  assert.deepEqual([...layer.text('B axes:').args], ['B axes:', 12, 10]);
  assert.deepEqual([...layer.text('IMU:').args], ['IMU:', 12, 143]);
  assert.deepEqual(['Bx', 'By', 'Bz', 'yaw', 'pitch', 'roll'].map(name => layer.text(name).fillStyle), [...COLORS.slice(0, 3), ...COLORS.slice(0, 3)]);
  ['0', '0.75', '1.5', '2.25', '3', 'time [s]'].forEach(label => assert.ok(layer.texts().includes(label), label));
  assert.equal(layer.count('stroke'), 6, 'one trace per selected channel');
  // The window (whole scan, 0..3 s on 12..788 px) is shaded behind the traces and edged on top.
  const lastShade = () => shown.named('fillRect').at(-1);
  assert.deepEqual([lastShade().args, lastShade().fillStyle], [[12, 0, 776, 266], THEME.window]);
  assert.equal(shown.named('drawImage').at(-1).args[0], run('layer.canvas'));
  const edges = () => shown.calls.filter(c => c.strokeStyle === THEME.edge && ['moveTo', 'lineTo'].includes(c.name)).slice(-4).map(c => c.args);
  assert.deepEqual(edges(), [[12, 0], [12, 266], [788, 0], [788, 266]]);

  // Dragging from 12 px to 400 px selects 0 to 1.5 s; moves after release, or with other buttons, do nothing.
  plot.listeners.pointerdown({ button: 0, offsetX: 12, pointerId: 1 });
  plot.listeners.pointermove({ offsetX: 400 });
  assert.deepEqual([node('start').value, node('end').value, [...run('state.window')]], ['0', '1.5', [0, 1.5]]);
  assert.equal(text('status'), 'scan.csv: 4 rows; window time [s] 0 to 1.5 keeps 2 rows × 6 channels');
  assert.deepEqual(lastShade().args, [12, 0, 388, 266]);
  plot.listeners.pointerup(); plot.listeners.pointermove({ offsetX: 700 });
  assert.equal(node('end').value, '1.5', 'released: no more dragging');
  plot.listeners.pointerdown({ button: 2, offsetX: 600, pointerId: 1 });
  plot.listeners.pointermove({ offsetX: 700 });
  assert.equal(node('end').value, '1.5', 'only the main button drags');
  plot.listeners.pointerdown({ button: 0, offsetX: 788, pointerId: 1 }); plot.listeners.pointermove({ offsetX: 400 }); plot.listeners.pointercancel();
  assert.deepEqual([...run('state.window')], [1.5, 3], 'dragging leftward still orders the window');

  plot.clientWidth = 60; run('drawPlot()');
  assert.ok(run('layer.canvas.context').texts().includes('…'), 'channel names that do not fit are cut with an ellipsis');
  plot.clientWidth = 800;
  run("state.selected.clear();syncChecks();channelsChanged()");
  assert.equal(shown.texts().at(-1), 'Select channels to plot'); assert.equal(run('layer'), null);
  run('sensorChanged()');

  // The attitude plot of a window without rows, then of the whole scan.
  node('start').value = '5'; node('end').value = '6'; run('applyWindow()');
  run('toggleAttitude()');
  assert.equal(text('attitude-rows'), '0 rows in the window');
  assert.deepEqual(node('attitude-plot').context.texts(), ['The calibration window contains no rows']);
  node('attitude-plot').context.reset(); node('whole-scan').onclick();
  assert.ok(node('attitude-plot').context.texts().includes('time [s]'), 'the attitude plot follows the window');
  console.log('PASS: strips, legend, ticks, shaded window, dragging and attitude plot');

  // Opening a calibration file, then applying it to the open scan.
  const open = async chosen => { node('calibration-file').onchange({ target: { files: [chosen], value: 'x' } }); await flush(); };
  await open(file('x.json', 'nope'));
  assert.equal(text('error'), 'x.json is not valid JSON.');
  await open(file('y.json', '{"format":"other"}'));
  assert.equal(text('error'), 'y.json is not an onyx-vector-calibration/1 calibration file.');
  assert.equal(node('apply').disabled, true, 'nothing to apply yet');
  await open(file('cal.json', CAL));
  assert.deepEqual([text('error'), text('cal-source'), node('apply').disabled], ['', 'cal.json (imu, fitted on 600 rows).', false]);
  await node('apply').onclick();
  assert.deepEqual(requests.at(-1), ['/api/calibration/apply', { name: 'scan.csv', text: 'csv', calibration: CAL }]);
  assert.deepEqual(downloads.at(-1), 'E,N,U');
  assert.equal(context.document.body.children.at(-1).download, 'scan-calibrated.csv');
  const summary = node('apply-summary').children.map(c => c.textContent);
  assert.deepEqual(summary, ['Saved', 'scan-calibrated.csv', 'Rows', '4', 'Attitude used', 'yes (scan yaw/pitch/roll)', 'Calibrated |B|', '45,201.3 ± 2.5 nT (mean ± std)']);
  assert.equal(text('status'), 'Calibrated 4 rows and saved scan-calibrated.csv');
  applyAnswer = () => reply({ error: 'calibration does not match the scan' }, 400);
  await node('apply').onclick();
  assert.equal(text('error'), 'calibration does not match the scan');
  const saved = downloads.length;
  await run('extractCalibration()');
  assert.deepEqual([text('error'), downloads.length], ['singular', saved], 'a failed fit saves nothing');
  console.log('PASS: open and apply a calibration file');

  const unsupported = await view({ '/api/calibration/status': () => Promise.reject(new Error('down')) });
  assert.deepEqual([unsupported.text('fit-badge'), unsupported.node('fit-badge').className], ['Fit Unavailable', 'badge disconnected']);
  assert.deepEqual([unsupported.text('fit-unavailable'), unsupported.node('fit-unavailable').hidden], ['The dashboard server did not report calibration support.', false]);
  assert.equal(unsupported.node('fit-file').disabled, true);
  console.log('PASS: calibration view without server support');
})().catch(error => { console.error(error); process.exitCode = 1; });
