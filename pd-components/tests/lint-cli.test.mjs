// Test for the CLI linter bundle (dist/pd-lint.mjs). Verifies the shared
// lint-core checks fire headlessly and exit codes are correct.
// Run: node pd-components/tests/lint-cli.test.mjs  (requires `npm run build` first)

import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cli = resolve(__dirname, '../dist/pd-lint.mjs');
const fixture = (name) => resolve(__dirname, 'fixtures', name);

let pass = 0, fail = 0;
const errors = [];

// Runs the CLI; returns { code, json }. Never throws on non-zero exit.
function run(...args) {
  try {
    const out = execFileSync('node', [cli, ...args], { encoding: 'utf8' });
    return { code: 0, json: JSON.parse(out) };
  } catch (e) {
    return { code: e.status, json: JSON.parse(e.stdout) };
  }
}

function check(label, fn) {
  try { fn(); pass++; console.log(`  ✓ ${label}`); }
  catch (e) { fail++; errors.push(`${label}: ${e.message}`); console.log(`  ✗ ${label} — ${e.message}`); }
}

check('clean doc → ok, exit 0', () => {
  const { code, json } = run(fixture('lint-clean.html'));
  assert.equal(code, 0);
  assert.equal(json.ok, true);
  assert.equal(json.issueCount, 0);
});

check('problem doc → exit 1 with all four codes', () => {
  const { code, json } = run(fixture('lint-issues.html'));
  assert.equal(code, 1);
  assert.equal(json.ok, false);
  const codes = new Set(json.issues.map((i) => i.code));
  for (const c of ['unplanned-file', 'untracked-file', 'missing-dep', 'dependency-cycle']) {
    assert.ok(codes.has(c), `missing issue code: ${c}`);
  }
});

check('open question → open-question issue (only the unanswered one), exit 1', () => {
  const { code, json } = run(fixture('lint-issues.html'));
  assert.equal(code, 1);
  const questions = json.issues.filter((i) => i.code === 'open-question');
  assert.equal(questions.length, 1, 'only the unanswered question should be reported');
  assert.equal(questions[0].id, 'Q-1');
  assert.equal(questions[0].priority, 'p1');
});

check('clean doc has no open-question issue', () => {
  const { json } = run(fixture('lint-clean.html'));
  assert.ok(!json.issues.some((i) => i.code === 'open-question'));
});

check('multiple files → summary envelope, exit 1 if any fail', () => {
  const { code, json } = run(fixture('lint-clean.html'), fixture('lint-issues.html'));
  assert.equal(code, 1);
  assert.equal(json.fileCount, 2);
  assert.equal(json.results[0].ok, true);
  assert.equal(json.results[1].ok, false);
});

check('no args → usage error, exit 2', () => {
  let code = 0;
  try { execFileSync('node', [cli], { encoding: 'utf8' }); }
  catch (e) { code = e.status; }
  assert.equal(code, 2);
});

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { errors.forEach((e) => console.error('  ' + e)); process.exit(1); }
