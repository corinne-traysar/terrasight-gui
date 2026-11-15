// Run the actual browser application with a deterministic 40 Hz source and clock.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

module.exports = (async () => {
  let now = 0;
  const tasks = [], valueUpdates = [], articles = [];
  const noop = () => {};
  const context = new Proxy({}, { get: () => noop, set: () => true });
  const ids = new Map();
  const element = () => ({ textContent: '', className: '', addEventListener: noop });
  const document = {
    getElementById(id) {
      if (!ids.has(id)) ids.set(id, { ...element(), append: noop });
      return ids.get(id);
    },
    createElement() {
      const index = articles.length;
      const values = Array.from({ length: 3 }, (_, axis) => {
        let text = '';
        return { set textContent(value) {
          if (index === 0 && axis === 0 && value !== text) valueUpdates.push(now);
          text = value;
        }, get textContent() { return text; } };
      });
      const canvas = { clientWidth: 500, clientHeight: 180, getContext: () => context };
      const article = { innerHTML: '', querySelector: () => canvas, querySelectorAll: () => values };
      articles.push(article);
      return article;
    },
  };
  const schedule = (fn, delay = 0) => {
    const task = { fn, at: now + delay };
    tasks.push(task);
    return task;
  };
  const sandbox = {
    document, window: { devicePixelRatio: 1, addEventListener: noop,
      VN100Pose: { create: () => ({ draw: noop, update: noop }) } }, console,
    setTimeout: schedule, clearTimeout: task => { task.cancelled = true; },
    requestAnimationFrame: fn => schedule(() => fn(now), 16),
    performance: { now: () => now },
    Date: class extends Date { static now() { return now; } },
    AbortSignal: { timeout: noop },
    fetch: async url => {
      const after = Number(new URL(url, 'http://test').searchParams.get('after')) || 0;
      const count = Math.floor(now / 25) + 1;
      const sample = sequence => ({ sequence, received_ms: (sequence - 1) * 25,
        attitude: [sequence, 2, 3], magnetic: [.1, .2, .3],
        acceleration: [1, 2, -9], angular_rate: [.01, .02, .03] });
      return { ok: true, json: async () => ({ session: 'test', status: 'live', received: count,
        rejected: 0, age_seconds: 0, latest: sample(count), history_truncated: false,
        samples: Array.from({ length: Math.max(0, count - after) }, (_, i) => sample(after + i + 1)) }) };
    },
  };
  sandbox.EventSource = class {
    constructor() {
      const deliver = async () => {
        const response = await sandbox.fetch('/api/samples?after=' + this.after);
        const data = await response.json();
        this.after = data.received;
        if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
        schedule(deliver, 50);
      };
      this.after = 0;
      schedule(deliver, 0);
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), sandbox);
  for (let i = 0; i < 10; i++) await Promise.resolve();
  while (tasks.some(task => !task.cancelled && task.at <= 1000)) {
    tasks.sort((a, b) => a.at - b.at);
    const task = tasks.shift();
    if (task.cancelled) continue;
    now = task.at;
    await task.fn();
    for (let i = 0; i < 10; i++) await Promise.resolve();
  }
  const gaps = valueUpdates.slice(1).map((time, i) => time - valueUpdates[i]);
  const worstGap = Math.max(...gaps);
  assert.ok(valueUpdates.length >= 15 && worstGap <= 100,
    `40 Hz sensor: ${valueUpdates.length} value updates/s; largest visible gap ${worstGap} ms (limit 100 ms)`);
  return { updates: valueUpdates.length, worstGapMs: worstGap };
})();

if (require.main === module) module.exports.then(result => console.log('PASS', result))
  .catch(error => { console.error(error.message); process.exitCode = 1; });
