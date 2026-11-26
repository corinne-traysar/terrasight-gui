/* Shared by the offline view tests: a fake page (getElementById nodes, created elements and
   canvases whose 2D context records calls) in a vm context with scan-plot.js loaded.
   `size` is the CSS size of every canvas; [0, 0] (the default) means nothing is drawn.
   Run directly, it checks itself. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { runWebScript } = require('../web_files.cjs');
const { recorder } = require('../fake_canvas.cjs');

const DEFAULT_VALUES = { sensor: 'magnetic', theta: '0', phi: '0', method: 'auto', mounting: 'enu' };

/** A page; `extra` adds or replaces globals, `values` sets input values by id. */
function page(extra = {}, { values = {}, size = [0, 0] } = {}) {
  const nodes = new Map(), defaults = { ...DEFAULT_VALUES, ...values };
  const drawable = () => { const context = recorder(); return { clientWidth: size[0], clientHeight: size[1], context, getContext: () => context }; };
  const base = () => ({ ...drawable(), style: {}, children: [], attributes: {}, listeners: {}, textContent: '', className: '',
    append(...children) { this.children.push(...children); }, replaceChildren(...children) { this.children = children; },
    setAttribute(key, value) { this.attributes[key] = value; }, addEventListener(type, listener) { this.listeners[type] = listener; } });
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, { ...base(), id, value: defaults[id] || '', hidden: false, disabled: false, title: '',
      querySelectorAll() { return this.children.filter(c => c.type === 'checkbox'); },
      classList: { toggle(name, on) { this[name] = on; } }, setPointerCapture() {} });
    return nodes.get(id);
  };
  const element = tag => ({ ...base(), tagName: tag, click() {}, remove() {} });
  const context = vm.createContext({ console, Math, Number, String, JSON, Promise, Array, Object, Set, Map, Infinity, NaN, isFinite,
    parseFloat, Error, SyntaxError, setTimeout, requestAnimationFrame: fn => fn(), ResizeObserver: class { observe() {} },
    document: { getElementById: node, createElement: element, createTextNode: text => ({ textContent: text }), body: element('body') },
    URL: { createObjectURL() { return 'blob:'; }, revokeObjectURL() {} }, Blob: class {}, ...extra });
  context.window = context;
  runWebScript('scan-plot.js', context);
  return { context, node, run: code => vm.runInContext(code, context), load: name => runWebScript(name, context) };
}

/** The Offline Data view (offline.js) with a window event bus; `fetch` answers its requests. */
function offlinePage(fetch, extra = {}) {
  const listeners = {}, events = [];
  const view = page({ fetch, CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail; } },
    addEventListener: (type, fn) => (listeners[type] ??= []).push(fn),
    dispatchEvent: event => { events.push(event); (listeners[event.type] || []).forEach(fn => fn(event)); }, ...extra }, { size: [600, 200] });
  view.load('offline.js');
  return { ...view, events };
}

/** Every element below `root` (depth first, root included) that `test` accepts. */
function findAll(root, test) {
  const found = test(root) ? [root] : [];
  for (const child of root.children || []) found.push(...findAll(child, test));
  return found;
}

/** Resolves once pending promise callbacks have run. */
const flush = () => new Promise(resolve => setImmediate(resolve));

/** A File stand-in. */
const file = (name, text) => ({ name, text: async () => text });

/** A fetch reply with status `status` and JSON `data`. */
const reply = (data, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => data });

module.exports = { page, offlinePage, findAll, flush, file, reply };

if (require.main === module) {
  const { context, node } = page({}, { values: { theta: '45' }, size: [300, 100] });
  assert.equal(node('theta').value, '45'); assert.equal(node('sensor').value, 'magnetic');
  assert.equal(typeof context.ScanPlot.linearMap, 'function', 'scan-plot.js is loaded');
  const holder = context.document.createElement('div'), inner = context.document.createElement('span');
  holder.append(inner); inner.append(context.document.createElement('canvas'));
  assert.equal(findAll(holder, n => n.tagName === 'canvas').length, 1);
  assert.equal(context.ScanPlot.setupCanvas(node('plot')).w, 300, 'canvases have the requested size');
  console.log('PASS: fake offline page');
}
