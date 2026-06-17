// Plan-tab file mirror: a synced, read-only copy of the canonical pd-files
// tree, shown next to the phase controls (pd-dag / pd-stepper) so the
// click-through — pick a phase, watch its files light up — is visible in one
// place without tab-hopping.
//
// Fully derived, zero authoring: it clones the already-rendered pd-files tree
// and listens to the same pd:phase-selected event. It only injects when the
// canonical tree lives on a *different* tab from the controls (the Solution →
// Plan split); when they already share a view there's nothing to mirror.

import { ready, el } from './util.js';

function injectPlanFileMirror() {
  const filesEl = document.querySelector('pd-files');
  if (!filesEl) return;
  const tree = filesEl.querySelector('.pd-tree');
  if (!tree) return;
  const filesTab = filesEl.closest('pd-tab');

  // Anchor near the phase controls on another tab — prefer the DAG (you click
  // its nodes there), fall back to the stepper.
  const controls = [...document.querySelectorAll('pd-dag, pd-stepper')]
    .filter((c) => c.closest('pd-tab') && c.closest('pd-tab') !== filesTab);
  const anchor = controls.find((c) => c.tagName === 'PD-DAG') || controls[0];
  if (!anchor) return; // controls share the files' tab — no mirror needed

  const anchorTab = anchor.closest('pd-tab');
  if (anchorTab.querySelector('pd-files')) return; // that tab already shows a tree
  if (anchorTab.querySelector('.pd-files-mirror')) return; // idempotent

  const clone = tree.cloneNode(true);
  clone.querySelectorAll('.pd-tabbadge').forEach((b) => b.remove()); // thread links are dead in a clone
  const wrap = el('div', { class: 'pd-files-mirror' }, [
    el('div', { class: 'pd-files-mirror-label' }, 'Files — synced to the selected phase'),
    clone,
  ]);
  anchor.after(wrap);

  window.addEventListener('pd:phase-selected', (e) => {
    const phaseFiles = e.detail?.files;
    wrap.querySelectorAll('.pd-tree-file').forEach((row) => {
      row.classList.remove('pd-hl', 'pd-dim');
      if (phaseFiles && phaseFiles.length) {
        row.classList.add(phaseFiles.includes(row.dataset.path) ? 'pd-hl' : 'pd-dim');
      }
    });
  });
}

// Runs after all component init in the ready() flush (queueMicrotask defers
// past the synchronous batch), so the canonical pd-files tree already exists.
ready(() => queueMicrotask(injectPlanFileMirror));
