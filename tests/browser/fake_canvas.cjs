/* Shared by the browser tests: a fake canvas whose 2D context records every drawing call
   together with the fill/stroke style, alpha and font in effect, so tests can check what
   was drawn without a browser. Run directly, it checks itself. */
const assert = require('node:assert/strict');

const STYLE = ['fillStyle', 'strokeStyle', 'globalAlpha', 'font', 'textAlign', 'lineWidth', 'textBaseline'];

/** A 2D context stand-in: style properties are plain fields (save/restore keep a stack);
    every other method call is recorded as {name, args, fillStyle, strokeStyle, globalAlpha, font}. */
function recorder() {
  const calls = [], stack = [];
  const fields = { fillStyle: '', strokeStyle: '', globalAlpha: 1, font: '', textAlign: '', lineWidth: 1, textBaseline: '' };
  const record = (name, args) => calls.push({ name, args, fillStyle: fields.fillStyle, strokeStyle: fields.strokeStyle,
    globalAlpha: fields.globalAlpha, font: fields.font });
  const helpers = {
    calls,
    /** Strings drawn with fillText, in order. */
    texts: () => calls.filter(c => c.name === 'fillText').map(c => c.args[0]),
    /** The recorded calls of method `name`. */
    named: name => calls.filter(c => c.name === name),
    count: name => calls.filter(c => c.name === name).length,
    /** The fillText call that drew `text` (the last one), or undefined. */
    text: text => calls.filter(c => c.name === 'fillText' && c.args[0] === text).at(-1),
    reset: () => { calls.length = 0; },
    measureText: text => ({ width: String(text).length * 6 }),
    save: () => { record('save', []); stack.push(STYLE.map(key => fields[key])); },
    restore: () => { record('restore', []); const saved = stack.pop(); if (saved) STYLE.forEach((key, i) => { fields[key] = saved[i]; }); },
  };
  return new Proxy(fields, {
    get(target, key) {
      if (key in helpers) return helpers[key];
      if (key in target) return target[key];
      return (...args) => record(key, args);
    },
    set(target, key, value) { target[key] = value; return true; },
  });
}

/** A canvas element of CSS size width x height whose getContext('2d') is one recorder. */
function fakeCanvas(width = 600, height = 400) {
  const context = recorder();
  return { clientWidth: width, clientHeight: height, width: 0, height: 0, attributes: {}, context,
    getContext: () => context, setAttribute(key, value) { this.attributes[key] = value; }, addEventListener() {} };
}

module.exports = { recorder, fakeCanvas };

if (require.main === module) {
  const canvas = fakeCanvas(10, 20), c = canvas.getContext('2d');
  c.fillStyle = 'red'; c.save(); c.globalAlpha = .5; c.fillText('a', 1, 2); c.restore(); c.fill();
  assert.deepEqual(c.texts(), ['a']);
  assert.equal(c.text('a').globalAlpha, .5);
  assert.equal(c.named('fill')[0].globalAlpha, 1, 'restore brings back the saved alpha');
  assert.equal(c.named('fill')[0].fillStyle, 'red');
  assert.equal(c.measureText('abc').width, 18);
  c.reset(); assert.equal(c.count('fillText'), 0);
  console.log('PASS: recording canvas context');
}
