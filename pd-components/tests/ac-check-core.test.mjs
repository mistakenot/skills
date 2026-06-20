// Node unit test for the frozen S1 schema core (src/ac-check-core.js). Guards the
// freeze: exactly five check types, their input attributes, the behavioural flags
// (AC-6), the reserved write-back shape, and parseAcCheck normalisation incl. the
// test portable identity (AC-3). DOM-free — importing the core in Node at all
// proves it is runtime-neutral.
// Run: node pd-components/tests/ac-check-core.test.mjs  (no build needed)

import { strict as assert } from 'node:assert';
import {
  AC_CHECK_SCHEMA,
  AC_CHECK_TYPES,
  AC_STATUS,
  AC_WRITEBACK,
  parseAcCheck,
  checkType,
} from '../src/ac-check-core.js';

let pass = 0, fail = 0;
const errors = [];

function check(label, fn) {
  try { fn(); pass++; console.log(`  ✓ ${label}`); }
  catch (e) { fail++; errors.push(`${label}: ${e.message}`); console.log(`  ✗ ${label} — ${e.message}`); }
}

// Minimal stand-in for a DOM element / node-html-parser node: just getAttribute
// + a tagName, which is all parseAcCheck depends on.
function stubNode(tag, attrs = {}) {
  return {
    tagName: tag.toUpperCase(),
    getAttribute: (n) => (n in attrs ? attrs[n] : null),
  };
}

check('schema has exactly the five check types', () => {
  assert.deepEqual(
    AC_CHECK_TYPES,
    ['command', 'output', 'test', 'file-exists', 'file-contains'],
  );
  assert.equal(Object.keys(AC_CHECK_SCHEMA).length, 5);
});

check('each type declares its input attributes', () => {
  assert.deepEqual(AC_CHECK_SCHEMA.command.attrs, ['run', 'expect-exit']);
  assert.deepEqual(AC_CHECK_SCHEMA.output.attrs, ['run', 'matches']);
  assert.deepEqual(AC_CHECK_SCHEMA.test.attrs, ['report', 'name', 'suite', 'classname', 'file']);
  assert.deepEqual(AC_CHECK_SCHEMA['file-exists'].attrs, ['path']);
  assert.deepEqual(AC_CHECK_SCHEMA['file-contains'].attrs, ['path', 'pattern']);
});

check('behavioural flag: test/output true, file-* false (AC-6)', () => {
  assert.equal(AC_CHECK_SCHEMA.test.behavioural, true);
  assert.equal(AC_CHECK_SCHEMA.output.behavioural, true);
  assert.equal(AC_CHECK_SCHEMA['file-exists'].behavioural, false);
  assert.equal(AC_CHECK_SCHEMA['file-contains'].behavioural, false);
});

check('behavioural flag: command is behavioural only when negative (AC-6)', () => {
  const beh = AC_CHECK_SCHEMA.command.behavioural;
  assert.equal(typeof beh, 'function');
  // negative command (non-zero expect-exit) → behavioural
  assert.equal(beh(parseAcCheck(stubNode('pd-ac-check-command', { run: 'x', 'expect-exit': '1' }))), true);
  // default / explicit exit-0 command → static gate, not behavioural
  assert.equal(beh(parseAcCheck(stubNode('pd-ac-check-command', { run: 'tsc --noEmit' }))), false);
  assert.equal(beh(parseAcCheck(stubNode('pd-ac-check-command', { run: 'x', 'expect-exit': '0' }))), false);
});

check('test carries the identity contract (required/qualifiers/ambiguity)', () => {
  const id = AC_CHECK_SCHEMA.test.identity;
  assert.deepEqual(id.required, ['report', 'name']);
  assert.deepEqual(id.qualifiers, ['suite', 'classname', 'file']);
  assert.match(id.ambiguity, /non-proof/);
});

check('status vocabulary is exactly the five values', () => {
  assert.deepEqual(AC_STATUS, ['proved', 'contradicted', 'weak', 'missing', 'pending']);
  assert.deepEqual(AC_WRITEBACK.status, AC_STATUS);
});

check('evidence-child + provenance attrs are declared reserved', () => {
  assert.equal(AC_WRITEBACK.evidence.kind, 'child-element');
  assert.equal(AC_WRITEBACK.evidence.reserved, true);
  assert.deepEqual(AC_WRITEBACK.provenance.attrs, ['commit', 'dirty', 'at']);
  assert.equal(AC_WRITEBACK.provenance.reserved, true);
});

check('parseAcCheck on a test node exposes the portable identity', () => {
  const node = stubNode('pd-ac-check-test', { report: 'junit.xml', name: 'returns 429', suite: 'rate' });
  let parsed;
  assert.doesNotThrow(() => { parsed = parseAcCheck(node); });
  assert.equal(parsed.type, 'test');
  assert.equal(parsed.report, 'junit.xml');
  assert.equal(parsed.name, 'returns 429');
  assert.equal(parsed.suite, 'rate');
  // absent optional qualifiers come back null
  assert.equal(parsed.classname, null);
  assert.equal(parsed.file, null);
});

check('absent attrs come back null; no status/provenance/evidence authored', () => {
  const parsed = parseAcCheck(stubNode('pd-ac-check-file-contains', {}));
  assert.equal(parsed.type, 'file-contains');
  assert.equal(parsed.path, null);
  assert.equal(parsed.pattern, null);
  assert.equal(parsed.status, null);
  assert.equal(parsed.provenance, null);
  assert.equal(parsed.evidence, null);
});

check('parseAcCheck reads the reserved write-back through if authored', () => {
  const parsed = parseAcCheck(stubNode('pd-ac-check-command', {
    run: 'x', status: 'proved', commit: 'abc', dirty: 'false', at: '2026-06-20',
  }));
  assert.equal(parsed.status, 'proved');
  assert.deepEqual(parsed.provenance, { commit: 'abc', dirty: 'false', at: '2026-06-20' });
});

check('parseAcCheck never throws on a non-check / empty node', () => {
  assert.doesNotThrow(() => parseAcCheck(stubNode('pd-note', {})));
  assert.doesNotThrow(() => parseAcCheck({}));
  assert.doesNotThrow(() => parseAcCheck(null));
  assert.equal(checkType(stubNode('pd-note', {})), null);
});

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { errors.forEach((e) => console.error('  ' + e)); process.exit(1); }
