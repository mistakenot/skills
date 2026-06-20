// Frozen S1 schema + DOM-agnostic parser for AC completion-contract checks.
//
// This is the single source of truth for the five check types a `pd-ac` card may
// carry. Like lint-core.js it is pure and runtime-neutral: it touches nothing
// DOM-bound and depends only on a node exposing getAttribute(), so the same code
// runs in two places with no duplication or drift:
//   - ac-check.js — in-browser: the inert custom elements expose `.check`
//   - (later) the T2 CLI + T4 renderer — import AC_CHECK_SCHEMA and parseAcCheck
//     so they cannot re-implement (and drift from) the schema.
//
// T1 freezes the schema and the parse; it computes NO status and judges NO
// ambiguity. The write-back shape (status/evidence/provenance) is reserved here
// but only WRITTEN by T2.
//
// The five check types (input attributes the author writes):
//   - command        run a command, assert exit code (expect-exit, default 0)
//   - output         run a command, assert stdout matches a regex (matches)
//   - test           look up a testcase in a JUnit XML report by portable identity
//   - file-exists    assert a path exists
//   - file-contains  assert a path matches a pattern

// Reserved write-back vocabulary (reserved, UNUSED in T1 — T2 writes it).
//
// Status maps a check/AC result to the contract's native language:
//   proved (pass) · contradicted (fail) · weak (skipped/todo) ·
//   missing (named test/file absent) · pending (not yet run).
export const AC_STATUS = ['proved', 'contradicted', 'weak', 'missing', 'pending'];

// Evidence is a reserved CHILD element (not an attribute) so it can carry
// multi-line output. Provenance is a set of reserved attributes stamping when
// the write happened and against what tree. Both reserved here, written by T2.
export const AC_WRITEBACK = {
  status: AC_STATUS,
  evidence: { kind: 'child-element', reserved: true },
  provenance: { attrs: ['commit', 'dirty', 'at'], reserved: true },
};

// The frozen schema: exactly the five authorable check types. Each entry lists
// its input attributes and a `behavioural` flag (AC-6) — true when the check
// proves runtime behaviour rather than static presence. A negative `command`
// (non-zero expect-exit) is behavioural too, so the flag is a predicate over the
// parsed check, not a constant.
//
// `test` additionally carries the identity contract: `report` + `name` are the
// required portable identity, `suite`/`classname`/`file` are optional qualifiers,
// and "0-or-many matches = non-proof, never a pass" is recorded as metadata for
// the T3 JUnit adapter to honour.
export const AC_CHECK_SCHEMA = {
  command: {
    attrs: ['run', 'expect-exit'],
    // Behavioural when it asserts a non-zero exit (a negative command); a plain
    // exit-0 command (build/typecheck/lint) is a static gate, not behaviour.
    behavioural: (check) => {
      const code = check?.['expect-exit'];
      return code != null && code !== '0' && code !== 0;
    },
  },
  output: {
    attrs: ['run', 'matches'],
    behavioural: true,
  },
  test: {
    attrs: ['report', 'name', 'suite', 'classname', 'file'],
    behavioural: true,
    identity: {
      required: ['report', 'name'],
      qualifiers: ['suite', 'classname', 'file'],
      // Recorded for T3: the JUnit lookup must treat zero-or-many matches as a
      // non-proof, never as a pass.
      ambiguity: '0-or-many matches = non-proof, never a pass',
    },
  },
  'file-exists': {
    attrs: ['path'],
    behavioural: false,
  },
  'file-contains': {
    attrs: ['path', 'pattern'],
    behavioural: false,
  },
};

// The five check tag suffixes, in schema order. `pd-ac-check-<type>`.
export const AC_CHECK_TYPES = Object.keys(AC_CHECK_SCHEMA);

const get = (node, name) => (node?.getAttribute ? node.getAttribute(name) : null);

// Maps a tag name (e.g. 'pd-ac-check-test' or 'PD-AC-CHECK-TEST') to its check
// type, or null if it is not one of the five. Works for browser elements
// (uppercase tagName) and node-html-parser nodes (lowercase rawTagName).
export function checkType(node) {
  const tag = (node?.tagName || node?.rawTagName || '').toLowerCase();
  const type = tag.replace(/^pd-ac-check-/, '');
  return tag.startsWith('pd-ac-check-') && AC_CHECK_SCHEMA[type] ? type : null;
}

// Reads a check node's attributes into a normalised, plain object. Works against
// a browser element AND a node-html-parser node (both expose getAttribute). It
// computes NO status and judges NO ambiguity, and it NEVER throws — T1 is fully
// permissive (no validation). Absent input attrs come back as null. The reserved
// write-back fields are read through if authored, else null:
//   { type, <input attrs…>, status, provenance, evidence }
export function parseAcCheck(node) {
  const type = checkType(node);
  const out = { type };

  const attrs = (type && AC_CHECK_SCHEMA[type].attrs) || [];
  for (const a of attrs) out[a] = get(node, a);

  // Reserved write-back read-through (null in T1 unless authored ahead of T2).
  out.status = get(node, 'status');
  out.provenance = AC_WRITEBACK.provenance.attrs.reduce((p, a) => {
    p[a] = get(node, a);
    return p;
  }, {});
  if (out.provenance.commit == null && out.provenance.dirty == null && out.provenance.at == null) {
    out.provenance = null;
  }
  // Evidence is a reserved child element; T1 does not read its contents, so it is
  // exposed as null until T2 writes (and this function learns to read) it.
  out.evidence = null;

  return out;
}
