// In-browser adapter for the shared lint core (lint-core.js). The doc checks its
// own consistency from the structured attributes it already carries, and surfaces
// what it finds two ways —
//   1. a compact panel at the top of the doc (human-visible), and
//   2. a pending "lint" comment queued in the store, so the findings ride the
//      existing "Copy for agent" export straight to the AI.
//
// The actual checks live in lint-core.js, shared verbatim with the CLI linter
// (cli/lint.js) so the two can never drift. This file only does the DOM rendering
// and store wiring that the browser needs.
//
// The lint comment is tagged so it replaces itself on every load (store.setLint)
// instead of piling up, and never disturbs reviewer-typed comments.

import { ready, el } from './util.js';
import { store } from './store.js';
import { collect, findIssues } from './lint-core.js';

function renderPanel(doc, issues) {
  doc.querySelector('.pd-lint')?.remove();
  if (!issues.length) return;
  const panel = el('div', { class: 'pd-lint' }, [
    el('div', { class: 'pd-lint-head' }, `⚠ Plan lint — ${issues.length} issue${issues.length === 1 ? '' : 's'}`),
    el('ul', { class: 'pd-lint-list' }, issues.map((i) => el('li', {}, i.message))),
    el('div', { class: 'pd-lint-foot' }, 'Queued as a pending comment — use “Copy for agent” to send to the agent.'),
  ]);
  const body = doc.querySelector('.pd-doc-body') || doc;
  body.insertBefore(panel, body.firstChild);
}

function queueComment(doc, issues) {
  if (!issues.length) { store.setLint([]); return; }
  const anchor = doc.querySelector('pd-files')?.closest('pd-section')?.id
    || doc.querySelector('pd-section[id]')?.id || '';
  const text = ['Automated plan lint found consistency issues to resolve:', ...issues.map((i) => `- ${i.message}`)].join('\n');
  store.setLint([{ kind: 'new', thread: 'Automated plan lint', anchor, priority: 'p2', text }]);
}

function run() {
  const doc = document.querySelector('pd-doc');
  if (!doc) return;
  // Open questions are surfaced in the browser by pd-question cards and the
  // blocked status bar — not as lint defects to "fix". They stay in the CLI
  // linter (a gate for automated steps); the panel/queue shows only fixables.
  const issues = findIssues(collect(doc)).filter((i) => i.code !== 'open-question');
  renderPanel(doc, issues);
  queueComment(doc, issues);
}

ready(() => queueMicrotask(run));
