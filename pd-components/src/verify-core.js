// Shared, DOM-agnostic rollup core for AC completion contracts.
//
// This is the single source of truth for the rollup algebra — how a set of
// check statuses folds into one AC status, and how a set of AC statuses folds
// into one contract status. Like lint-core.js and ac-check-core.js it is pure
// and runtime-neutral: it touches nothing DOM-bound, performs NO I/O, and never
// throws — so the same code runs in two places with no duplication or drift:
//   - misc.js  — in-browser: PdAc / PdContract roll up authored child statuses
//   - (deferred) the T2 CLI — imports the SAME algebra to write real verdicts
//
// The frozen contract (seam S2 / G5, accepted by the user in plan.html):
//   - severity order:  contradicted ≻ missing ≻ weak ≻ pending ≻ proved
//     (contradicted is worst, proved is best; worst-severity present wins)
//   - an AC / contract is `proved` ONLY when EVERY input is `proved`
//   - null / absent / unknown status normalises to `pending`

// The severity order, worst-first. This is the single source of truth for the
// rollup; the rank map below is derived from it. Index 0 is the worst status.
export const SEVERITY_ORDER = ['contradicted', 'missing', 'weak', 'pending', 'proved'];

// rank[status] → its position in SEVERITY_ORDER (0 = worst). Used to pick the
// worst-severity status present. Statuses not in the order rank as `pending`.
const RANK = new Map(SEVERITY_ORDER.map((s, i) => [s, i]));

// Normalise any value to a known status: null / undefined / unknown → pending.
const norm = (s) => (RANK.has(s) ? s : 'pending');

// Folds a list of normalised statuses to one status under the frozen contract:
// `proved` only when every input is `proved`, else the worst-severity present.
// An empty list has no checks to contradict it, so it folds to `pending`.
function fold(statuses) {
  if (!statuses.length) return 'pending';
  if (statuses.every((s) => s === 'proved')) return 'proved';
  let worst = statuses[0];
  for (const s of statuses) {
    if (RANK.get(s) < RANK.get(worst)) worst = s;
  }
  return worst;
}

// Rolls a list of check statuses up to one AC status.
//   total   = number of checks
//   passing = number of checks equal to 'proved'
//   status  = 'proved' only when every check is 'proved', else worst-severity;
//             an empty / malformed (non-array) input is 'pending' (no checks).
// Non-array input is treated as empty. Never throws.
export function rollupAc(statuses) {
  const list = (Array.isArray(statuses) ? statuses : []).map(norm);
  const passing = list.filter((s) => s === 'proved').length;
  return { status: fold(list), passing, total: list.length };
}

// Rolls a list of per-AC statuses up to one document-level contract status,
// reusing the SAME severity algebra. Drives the <pd-contract> banner (AC-9).
//   total  = number of ACs
//   proved = number of ACs equal to 'proved'
//   status = 'proved' only when every AC is 'proved', else worst-severity;
//            an empty / malformed (non-array) input is 'pending'.
// Non-array input is treated as empty. Never throws.
export function rollupContract(acStatuses) {
  const list = (Array.isArray(acStatuses) ? acStatuses : []).map(norm);
  const proved = list.filter((s) => s === 'proved').length;
  return { status: fold(list), proved, total: list.length };
}
