// Unit test for the DOM-free rollup core (src/verify-core.js). Imports the pure
// module directly (no browser, no customElements, no build step) and pins the
// frozen severity algebra: worst-wins, proved-iff-all-proved, null→pending, and
// malformed-safe. Guards the S2/G5 shared contract used by the browser now and
// the deferred CLI later. Covers AC-2 (rollupAc) and the AC-9 core (rollupContract).
// Run: node pd-components/tests/verify-core.test.mjs  (no build required)

import { strict as assert } from 'node:assert';
import { SEVERITY_ORDER, rollupAc, rollupContract } from '../src/verify-core.js';

let pass = 0, fail = 0;
const errors = [];

function check(label, fn) {
  try { fn(); pass++; console.log(`  ✓ ${label}`); }
  catch (e) { fail++; errors.push(`${label}: ${e.message}`); console.log(`  ✗ ${label} — ${e.message}`); }
}

// --- severity order (the frozen contract) ---

check('severity order is contradicted ≻ missing ≻ weak ≻ pending ≻ proved', () => {
  assert.deepEqual(SEVERITY_ORDER, ['contradicted', 'missing', 'weak', 'pending', 'proved']);
});

// --- rollupAc (AC-2) ---

check('all proved → proved; passing = total', () => {
  assert.deepEqual(rollupAc(['proved', 'proved', 'proved']), { status: 'proved', passing: 3, total: 3 });
});

check('proved only when EVERY input is proved', () => {
  // A single non-proved value drops the rollup off `proved`.
  assert.equal(rollupAc(['proved', 'proved', 'weak']).status, 'weak');
  assert.equal(rollupAc(['proved', 'pending']).status, 'pending');
});

check('worst-wins across the whole severity order (representative mixed pairs)', () => {
  // contradicted beats everything below it.
  assert.equal(rollupAc(['proved', 'missing', 'contradicted']).status, 'contradicted');
  assert.equal(rollupAc(['contradicted', 'pending']).status, 'contradicted');
  // missing beats weak/pending/proved.
  assert.equal(rollupAc(['weak', 'missing', 'proved']).status, 'missing');
  assert.equal(rollupAc(['missing', 'weak']).status, 'missing');
  // weak beats pending/proved.
  assert.equal(rollupAc(['pending', 'weak', 'proved']).status, 'weak');
  // pending beats proved.
  assert.equal(rollupAc(['pending', 'proved']).status, 'pending');
});

check('passing counts only proved; total = length', () => {
  const r = rollupAc(['proved', 'weak', 'proved', 'contradicted']);
  assert.equal(r.passing, 2);
  assert.equal(r.total, 4);
});

check('null / absent / unknown normalise to pending (severity)', () => {
  // null and undefined rank as pending — so a proved+null pair is pending, not proved.
  assert.equal(rollupAc(['proved', null]).status, 'pending');
  assert.equal(rollupAc(['proved', undefined]).status, 'pending');
  // an unknown string also normalises to pending.
  assert.equal(rollupAc(['proved', 'bogus']).status, 'pending');
  // normalised-pending values are NOT counted as passing.
  assert.equal(rollupAc([null, 'bogus']).passing, 0);
  assert.equal(rollupAc([null, 'bogus']).total, 2);
});

check('empty array → {pending, 0, 0} (an empty AC has no checks)', () => {
  assert.deepEqual(rollupAc([]), { status: 'pending', passing: 0, total: 0 });
});

check('malformed (non-array) input is treated as empty and never throws', () => {
  for (const bad of [undefined, null, 'proved', 42, {}, { length: 2 }]) {
    assert.deepEqual(rollupAc(bad), { status: 'pending', passing: 0, total: 0 });
  }
});

// --- rollupContract (AC-9 core) ---

check('contract proved iff every AC proved; proved/total count', () => {
  assert.deepEqual(rollupContract(['proved', 'proved']), { status: 'proved', proved: 2, total: 2 });
  // one non-proved AC drops the contract off proved.
  const r = rollupContract(['proved', 'proved', 'contradicted']);
  assert.equal(r.status, 'contradicted');
  assert.equal(r.proved, 2);
  assert.equal(r.total, 3);
});

check('contract worst-severity wins otherwise (same algebra as rollupAc)', () => {
  assert.equal(rollupContract(['proved', 'weak', 'missing']).status, 'missing');
  assert.equal(rollupContract(['pending', 'proved']).status, 'pending');
  assert.equal(rollupContract(['contradicted', 'missing', 'weak']).status, 'contradicted');
});

check('contract null/unknown → pending; empty and malformed are safe', () => {
  assert.equal(rollupContract(['proved', null]).status, 'pending');
  assert.equal(rollupContract(['proved', 'bogus']).status, 'pending');
  assert.deepEqual(rollupContract([]), { status: 'pending', proved: 0, total: 0 });
  for (const bad of [undefined, null, 'proved', 7, {}]) {
    assert.deepEqual(rollupContract(bad), { status: 'pending', proved: 0, total: 0 });
  }
});

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { errors.forEach((e) => console.error('  ' + e)); process.exit(1); }
