/* Tests the pages of web/offline/offline.js (the Offline Data view): opening magnetic and
   electromagnetic files, the status line, the |B| graphs (ticks, trace, heading), clicking a
   graph to open its per-axis page with a marker, rotating and resetting the axis frame, going
   back, and redrawing on resize. Frame and phasor math is checked in scan_views.cjs. */
const assert = require('node:assert/strict');
const { offlinePage, flush, file, reply } = require('./fake_page.cjs');
const close = (a, b, message) => assert.ok(Math.abs(a - b) < 1e-9, `${message} ${a} != ${b}`);
const MAIN_HINT = 'x = sample index from start · click for the per-axis graphs';

(async () => {
  const requests = [], resized = [];
  let answer;
  const { node, run, events, context } = offlinePage((url, options) => { requests.push([url, JSON.parse(options.body)]); return answer; },
    { ResizeObserver: class { constructor(fn) { resized.push(fn); } observe() {} } });
  const COLORS = [...context.ScanPlot.COLORS], MARKER = context.ScanPlot.THEME.marker;
  const text = id => node(id).textContent;
  const choose = async (sensor, chosen) => { const input = { files: [chosen], value: 'C:\\fakepath\\x' };
    node(sensor + '-file').onchange({ target: input }); assert.equal(input.value, '', 'the input is reset'); await flush(); };

  run('showMain();showStatus()');
  assert.deepEqual([node('main-graphs').children[0].className, node('main-graphs').children[0].textContent], ['empty', 'Open a magnetic and/or electromagnetic file.']);
  assert.deepEqual([text('status'), text('badge'), node('badge').className], ['Open a magnetic and/or electromagnetic file.', 'No Data', 'badge waiting']);

  // Magnetic file: |B| = 5, missing, 2 over samples 0..2.
  answer = reply({ source: 'mag.csv', count: 3, labels: ['E', 'N', 'U'], field_nt: [[3, 4, 0], [null, 1, 1], [0, 0, 2]], attitude: null });
  await choose('magnetic', file('mag.csv', 't,Bx'));
  assert.deepEqual(requests[0], ['/api/offline/load', { sensor: 'magnetic', name: 'mag.csv', text: 't,Bx' }]);
  assert.deepEqual([text('status'), text('badge'), node('badge').className], ['Magnetic: mag.csv, 3 samples', 'Data Loaded', 'badge live']);
  assert.deepEqual(events.map(e => [e.type, e.detail.sensor]), [['offline-loaded', 'magnetic']]);
  const [magArticle] = node('main-graphs').children, magCanvas = magArticle.children[0], main = magCanvas.context;
  assert.equal(magArticle.className, 'graph clickable');
  assert.equal(magCanvas.attributes['aria-label'], 'Magnetic |B| over the sample index');
  ['Magnetic |B| [nT]', MAIN_HINT, '2.0', '3.0', '4.0', '5.0', '0', '1', '2'].forEach(label => assert.ok(main.texts().includes(label), label));
  // Plot box: x 80..586 px for samples 0..2, y 178..32 px for |B| 2..5; the missing sample is skipped.
  const trace = main.calls.filter(c => ['moveTo', 'lineTo'].includes(c.name) && c.strokeStyle === COLORS[0]).map(c => [c.name, ...c.args]);
  assert.deepEqual(trace, [['moveTo', 80, 32], ['lineTo', 586, 178]]);

  answer = reply({ error: 'no B columns' }, 400);
  await choose('magnetic', file('bad.csv', ''));
  assert.equal(text('error'), 'Cannot open magnetic data: no B columns');
  assert.equal(text('status'), 'Magnetic: mag.csv, 3 samples', 'a failed file keeps the loaded one');
  assert.equal(events.length, 1);
  node('magnetic-file').onchange({ target: { files: [], value: '' } }); await flush();
  assert.equal(requests.length, 2, 'cancelling the file dialog sends nothing');

  answer = reply({ source: 'em.csv', count: 2, labels: ['x', 'y', 'z'], real_nt: [[1, 0, 0], [0, 1, 0]], imag_nt: [[0, 0, 0], [0, 0, null]] });
  await choose('electromagnetic', file('em.csv', 'em'));
  assert.equal(text('error'), '', 'a new file clears the error');
  assert.equal(text('status'), 'Magnetic: mag.csv, 3 samples  ·  Electromagnetic: em.csv, 2 samples');
  assert.equal(node('main-graphs').children.length, 2);
  assert.ok(node('main-graphs').children[1].children[0].context.texts().includes('Electromagnetic |B| (peak) [nT]'));

  // Clicking x = 333 px on the magnetic graph is sample 1.
  node('main-graphs').children[0].children[0].listeners.click({ offsetX: 333 });
  assert.deepEqual([node('main-page').hidden, node('axis-page').hidden], [true, false]);
  assert.equal(text('axis-title'), 'Magnetic per axis — mag.csv · marker at sample 1');
  assert.deepEqual([text('theta-value'), text('phi-value'), node('axis-grid').className], ['0°', '0°', 'axis-grid']);
  const grid = () => node('axis-grid').children;
  assert.deepEqual(grid().map(a => [a.style.gridRow, a.style.gridColumn]), [['1', '1'], ['2', '1'], ['3', '1']]);
  const east = grid()[0].children[0].context;
  assert.ok(east.texts().includes('Magnetic B along E [nT]'));
  const marker = east.calls.filter(c => ['moveTo', 'lineTo'].includes(c.name) && c.strokeStyle === MARKER).map(c => c.args);
  assert.deepEqual(marker, [[333, 32], [333, 178]], 'the marker spans the plot at sample 1');

  // phi = 90° turns the first axis from E toward N: B = (3, 4, 0) reads (4, -3, 0) in the primed frame.
  node('phi').value = '90'; node('phi').oninput();
  assert.equal(text('phi-value'), '90°');
  assert.deepEqual(run('axisEntries.map(e=>e.graph.title)'), ['Magnetic B along E′', 'Magnetic B along N′', 'Magnetic B along U′']);
  run("axisEntries.map(e=>Object.values(e.graph.traces)[0][0])").forEach((v, k) => close(v, [4, -3, 0][k], 'rotated first sample'));
  assert.ok(grid()[0].children[0].context.texts().includes('Magnetic B along E′ [nT]'), 'the graphs are redrawn');
  node('reset-axes').onclick();
  assert.deepEqual([node('theta').value, node('phi').value, text('phi-value')], ['0', '0', '0°']);
  assert.equal(run('axisEntries[0].graph.title'), 'Magnetic B along E');

  east.reset(); resized.forEach(fn => fn());
  assert.ok(east.count('stroke') > 0, 'a resize redraws the open per-axis page');
  node('back').onclick();
  assert.deepEqual([node('main-page').hidden, node('axis-page').hidden, run('axisEntries.length')], [false, true, 0]);
  node('theta').value = '30'; node('theta').oninput();
  assert.equal(text('theta-value'), '30°', 'the slider label follows even without a per-axis page');
  const shown = node('main-graphs').children[0].children[0].context; shown.reset(); resized.forEach(fn => fn());
  assert.ok(shown.count('stroke') > 0, 'a resize redraws the main page');

  // Electromagnetic per-axis page: amplitude and phase columns side by side.
  node('main-graphs').children[1].children[0].listeners.click({ offsetX: 586 });
  assert.equal(text('axis-title'), 'Electromagnetic per axis — em.csv · marker at sample 1');
  assert.equal(node('axis-grid').className, 'axis-grid two');
  assert.deepEqual(grid().map(a => a.style.gridColumn), ['1', '1', '1', '2', '2', '2']);
  assert.equal(node('theta').value, '0', 'a new per-axis page starts unrotated');

  // Several traces get a coloured legend; clicks before the first draw are ignored.
  const legend = run(`(()=>{const e=graphEntry(document.createElement('div'),{title:'T',unit:'u',traces:{a:[1,2],b:[2,3]}},{hint:'h'});drawGraph(e);return e.canvas.context;})()`);
  assert.deepEqual([legend.text('a').fillStyle, legend.text('b').fillStyle, legend.text('h').fillStyle], [COLORS[0], COLORS[1], context.ScanPlot.THEME.dim]);
  assert.equal(run(`(()=>{let n=0;const e=graphEntry(document.createElement('div'),{title:'T',unit:'u',traces:{a:[1]}},{onClick:()=>n++});e.canvas.listeners.click({offsetX:90});return n;})()`), 0);
  console.log('PASS: Offline Data files, status, graphs, per-axis pages, rotation, back and resize');
})().catch(error => { console.error(error); process.exitCode = 1; });
