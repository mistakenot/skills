// Shared, DOM-agnostic lint core for planning docs.
//
// This is the single source of truth for the consistency checks. It is consumed
// by two adapters, which must never re-implement the rules themselves:
//   - lint.js      — in-browser: renders a panel + queues a "Copy for agent" comment
//   - cli/lint.js  — CLI: emits JSON for an agent to read without a browser
//
// It depends only on a DOM-like `root` exposing querySelector/querySelectorAll
// whose results expose getAttribute(). That contract is satisfied by the browser
// `document`/element and by node-html-parser's nodes, so the same code runs both
// places with no duplication or drift.
//
// Checks (all derived from attributes the doc already carries — no new authoring):
//   - unplanned-file:    a file in the pd-files tree that no phase touches
//   - untracked-file:    a file a phase touches that's missing from the tree
//   - missing-dep:       depends-on pointing at a phase that doesn't exist
//   - dependency-cycle:  a dependency cycle among phases
//   - open-question:     a pd-question awaiting a human answer (a gate, not a
//                        defect — surface it to the human, don't "fix" it)

const split = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean);

// Scope to the <pd-doc> element when present (mirrors the browser linter, which
// runs against the mounted pd-doc), else fall back to the whole root.
function scope(root) {
  return root.querySelector?.('pd-doc') || root;
}

export function collect(root) {
  const doc = scope(root);
  const phases = [...doc.querySelectorAll('pd-phase')].map((p, i) => ({
    n: p.getAttribute('n') || String(i + 1),
    files: split(p.getAttribute('files')),
    deps: split(p.getAttribute('depends-on')),
  }));
  const filePaths = [...doc.querySelectorAll('pd-file')]
    .map((f) => f.getAttribute('path') || '')
    .filter(Boolean);
  const openQuestions = [...doc.querySelectorAll('pd-question')]
    .filter((q) => (q.getAttribute('status') || 'open') !== 'answered')
    .map((q, i) => ({
      id: q.getAttribute('id') || `Q${i + 1}`,
      priority: q.getAttribute('priority') || 'p1',
      title: q.getAttribute('title') || 'Question',
    }));
  return { phases, filePaths, openQuestions };
}

// Returns an array of { code, message } issue objects. The message wording is
// stable — the browser comment export and the CLI JSON both surface it verbatim.
export function findIssues({ phases, filePaths, openQuestions }) {
  const issues = [];
  const add = (code, message) => issues.push({ code, message });

  const inTree = new Set(filePaths);
  const touched = new Set(phases.flatMap((p) => p.files));
  const known = new Set(phases.map((p) => p.n));

  if (phases.length && filePaths.length) {
    filePaths.filter((f) => !touched.has(f)).forEach((f) =>
      add('unplanned-file', `File ${f} is in the file tree but no phase touches it.`));
    phases.forEach((p) => p.files.filter((f) => !inTree.has(f)).forEach((f) =>
      add('untracked-file', `Phase ${p.n} touches ${f}, which is missing from the file tree.`)));
  }

  phases.forEach((p) => p.deps.filter((d) => !known.has(d)).forEach((d) =>
    add('missing-dep', `Phase ${p.n} depends on phase ${d}, which doesn't exist.`)));

  // Cycle detection (DFS with grey/black colouring).
  const byN = new Map(phases.map((p) => [p.n, p]));
  const color = new Map();
  const cycles = new Set();
  const dfs = (n, path) => {
    color.set(n, 1); path.push(n);
    for (const d of (byN.get(n)?.deps || [])) {
      if (!byN.has(d)) continue;
      const c = color.get(d) || 0;
      if (c === 1) cycles.add(path.slice(path.indexOf(d)).concat(d).join(' → '));
      else if (c === 0) dfs(d, path);
    }
    path.pop(); color.set(n, 2);
  };
  phases.forEach((p) => { if ((color.get(p.n) || 0) === 0) dfs(p.n, []); });
  cycles.forEach((c) => add('dependency-cycle', `Dependency cycle among phases: ${c}.`));

  // Open questions are a human gate, not a defect: an automated step shouldn't
  // proceed while any remain. Each issue carries id/priority so a caller can act
  // on them structurally, not just read the message.
  (openQuestions || []).forEach((q) => issues.push({
    code: 'open-question',
    id: q.id,
    priority: q.priority,
    message: `Question ${q.id} (${q.priority}) "${q.title}" is awaiting a human answer.`,
  }));

  return issues;
}

// Convenience: collect + findIssues against a root in one call.
export function lint(root) {
  return findIssues(collect(root));
}
