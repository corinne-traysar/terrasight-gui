/* Run every browser test under tests/browser/ in its own Node process; exit 1 if any fails.
   Usage: node tests/browser/run_all.cjs */
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

/* Test files below `folder` (this runner and the shared helper excluded). */
function tests(folder) {
  return fs.readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(folder, entry.name);
    if (entry.isDirectory()) return tests(full);
    return entry.name.endsWith('.cjs') && full !== __filename && entry.name !== 'web_files.cjs' ? [full] : [];
  }).sort();
}

const failed = tests(__dirname).filter(file => {
  console.log(`== ${path.relative(__dirname, file)}`);
  return spawnSync(process.execPath, [file], { stdio: 'inherit' }).status !== 0;
});
console.log(failed.length ? `FAILED: ${failed.map(f => path.relative(__dirname, f)).join(', ')}` : 'All browser tests passed.');
process.exit(failed.length ? 1 : 0);
