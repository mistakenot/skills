// pd-stepper / pd-phase: clickable walkthrough of plan phases.
//
// Non-linear by design — reviewers jump straight to the phase they care
// about. Selecting a phase shows its body and broadcasts pd:phase-selected so
// pd-files can highlight the files that phase touches.
//
//   <pd-stepper>
//     <pd-phase n="1" title="Schema" files="src/db/schema.ts" status="done">
//       ...freeform detail, pd-mermaid, etc...
//     </pd-phase>
//   </pd-stepper>

import { PdElement, define, el } from './util.js';

class PdPhase extends PdElement {
  init() {
    // Render the phase's files inline so the Plan tab is self-sufficient for an
    // executing agent — the file-change *tree* lives on the Solution tab (the
    // end-state, human-reviewed); the Plan is the recipe.
    const files = (this.getAttribute('files') || '').split(',').map((s) => s.trim()).filter(Boolean);
    if (!files.length) return;
    const list = el('div', { class: 'pd-phase-files' }, [
      el('span', { class: 'pd-phase-files-label' }, 'touches'),
      ...files.map((f) => el('code', { class: 'pd-phase-file', title: f }, f.split('/').pop())),
    ]);
    this.append(list);
  }
}

class PdStepper extends PdElement {
  init() {
    const phases = [...this.querySelectorAll(':scope > pd-phase')];
    if (!phases.length) return;

    const nav = el('div', { class: 'pd-steps', role: 'tablist' });
    const allBtn = el('button', { class: 'pd-step', onclick: () => this._select(null) }, 'All');
    nav.append(allBtn);

    phases.forEach((p, i) => {
      const n = p.getAttribute('n') || String(i + 1);
      const status = p.getAttribute('status') || 'todo';
      const btn = el('button', {
        class: 'pd-step', 'data-status': status,
        onclick: () => this._select(i),
      }, [el('span', { class: 'pd-step-n' }, n), p.getAttribute('title') || `Phase ${n}`]);
      nav.append(btn);
    });

    this.prepend(nav);
    this._phases = phases;
    this._nav = nav;

    this.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const delta = e.key === 'ArrowRight' ? 1 : -1;
      const next = this._selected == null
        ? (delta > 0 ? 0 : phases.length - 1)
        : Math.min(phases.length - 1, Math.max(0, this._selected + delta));
      this._select(next);
    });

    this._select(null);
  }

  _select(idx) {
    this._selected = idx;
    this._phases.forEach((p, i) => {
      p.style.display = idx == null || i === idx ? '' : 'none';
      p.toggleAttribute('data-active', i === idx);
    });
    [...this._nav.children].forEach((b, i) => {
      b.setAttribute('aria-selected', (idx == null ? i === 0 : i === idx + 1) ? 'true' : 'false');
    });
    const files = idx == null ? null
      : (this._phases[idx].getAttribute('files') || '').split(',').map((s) => s.trim()).filter(Boolean);
    window.dispatchEvent(new CustomEvent('pd:phase-selected', { detail: { files } }));
  }
}

define('pd-phase', PdPhase);
define('pd-stepper', PdStepper);
