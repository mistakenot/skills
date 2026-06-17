// Self-linting plans: the doc checks its own consistency from the structured
// attributes it already carries, and surfaces what it finds two ways —
//   1. a compact panel at the top of the doc (human-visible), and
//   2. a pending "lint" comment queued in the store, so the findings ride the
//      existing "Copy for agent" export straight to the AI.
//
// Checks (all derived, no new authoring):
//   - a file in the pd-files tree that no phase touches (unplanned change)
//   - a file a phase touches that's missing from the tree (untracked change)
//   - depends-on pointing at a phase that doesn't exist
//   - a dependency cycle among phases
//
// The lint comment is tagged so it replaces itself on every load (store.setLint)
// instead of piling up, and never disturbs reviewer-typed comments.

import { ready, el } from './util.js';
import { store } from './store.js';

const split = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean);

function collect(doc) {
  const phases = [...doc.querySelectorAll('pd-phase')].map((p, i) => ({
    n: p.getAttribute('n') || String(i + 1),
    files: split(p.getAttribute('files')),
    deps: split(p.getAttribute('depends-on')),
  }));
  const filePaths = [...doc.querySelectorAll('pd-file')].map((f) => f.getAttribute('path') || '').filter(Boolean);
  return { phases, filePaths };
}

function findIssues({ phases, filePaths }) {
  const issues = [];
  const inTree = new Set(filePaths);
  const touched = new Set(phases.flatMap((p) => p.files));
  const known = new Set(phases.map((p) => p.n));

  if (phases.length && filePaths.length) {
    filePaths.filter((f) => !touched.has(f)).forEach((f) =>
      issues.push(`File ${f} is in the file tree but no phase touches it.`));
    phases.forEach((p) => p.files.filter((f) => !inTree.has(f)).forEach((f) =>
      issues.push(`Phase ${p.n} touches ${f}, which is missing from the file tree.`)));
  }

  phases.forEach((p) => p.deps.filter((d) => !known.has(d)).forEach((d) =>
    issues.push(`Phase ${p.n} depends on phase ${d}, which doesn't exist.`)));

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
  cycles.forEach((c) => issues.push(`Dependency cycle among phases: ${c}.`));

  return issues;
}

function renderPanel(doc, issues) {
  doc.querySelector('.pd-lint')?.remove();
  if (!issues.length) return;
  const panel = el('div', { class: 'pd-lint' }, [
    el('div', { class: 'pd-lint-head' }, `⚠ Plan lint — ${issues.length} issue${issues.length === 1 ? '' : 's'}`),
    el('ul', { class: 'pd-lint-list' }, issues.map((i) => el('li', {}, i))),
    el('div', { class: 'pd-lint-foot' }, 'Queued as a pending comment — use “Copy for agent” to send to the agent.'),
  ]);
  const body = doc.querySelector('.pd-doc-body') || doc;
  body.insertBefore(panel, body.firstChild);
}

function queueComment(doc, issues) {
  if (!issues.length) { store.setLint([]); return; }
  const anchor = doc.querySelector('pd-files')?.closest('pd-section')?.id
    || doc.querySelector('pd-section[id]')?.id || '';
  const text = ['Automated plan lint found consistency issues to resolve:', ...issues.map((i) => `- ${i}`)].join('\n');
  store.setLint([{ kind: 'new', thread: 'Automated plan lint', anchor, priority: 'p2', text }]);
}

function run() {
  const doc = document.querySelector('pd-doc');
  if (!doc) return;
  const issues = findIssues(collect(doc));
  renderPanel(doc, issues);
  queueComment(doc, issues);
}

ready(() => queueMicrotask(run));
