/* Shared by the browser tests: find a web file by name wherever it sits under web/
   (the same rule as dashboard/web_assets.py), and the repository root. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..', '..');
const WEB = path.join(ROOT, 'web');

/* Absolute path of every file under `folder`, keyed by file name. */
function index(folder, found = new Map()) {
  for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
    const full = path.join(folder, entry.name);
    if (entry.isDirectory()) index(full, found);
    else found.set(entry.name, full);
  }
  return found;
}
const FILES = index(WEB);

/* Absolute path of the web file called `name`; throws for unknown names. */
function webFile(name) {
  const found = FILES.get(name);
  if (!found) throw new Error(`${name} is not a file under ${WEB}`);
  return found;
}

/* Text of the web file called `name`. */
const webSource = name => fs.readFileSync(webFile(name), 'utf8');

/* Run the web script called `name` in the vm `context`, named by its path so stack
   traces and coverage point at the real file. */
const runWebScript = (name, context) => vm.runInContext(webSource(name), context, { filename: webFile(name) });

module.exports = { ROOT, WEB, webFile, webSource, runWebScript };
