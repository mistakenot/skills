// pd-ac: acceptance-criteria card with traceability chips.
//   <pd-ac id="AC-1" title="Rate limit applies" phases="1,2" tests="e2e/rate.spec.ts">
//     <ul><li>Given… </li><li>When… </li><li>Then… </li></ul>
//   </pd-ac>
//
// pd-collapse: ad-hoc progressive-disclosure wrapper. Collapsed by default
// (add `open` to expand); the summary line is the scan layer, the body stays in
// the DOM for agents. Use for long code, tables, or secondary rationale that
// isn't a whole section.
//   <pd-collapse summary="Rationale"> <md>…</md> </pd-collapse>
//
// pd-wire: wireframe placeholder box. pd-note: annotation callout.
// Wireframe sections are otherwise freeform HTML (Tailwind welcome).

import { PdElement, define, el, filesForPhases } from './util.js';

class PdAc extends PdElement {
  init() {
    const id = this.getAttribute('id') || 'AC';
    const phases = (this.getAttribute('phases') || '').split(',').map((s) => s.trim()).filter(Boolean);

    const chips = el('div', { class: 'pd-ac-chips' });
    phases.forEach((p) => chips.append(el('span', { class: 'pd-chip' }, `phase ${p}`)));
    (this.getAttribute('tests') || '').split(',').map((s) => s.trim()).filter(Boolean)
      .forEach((t) => chips.append(el('span', { class: 'pd-chip pd-chip-test' }, t)));

    this.prepend(el('div', { class: 'pd-ac-head' }, [
      el('span', { class: 'pd-chip pd-chip-id' }, id),
      el('strong', {}, this.getAttribute('title') || ''),
      chips,
    ]));

    // Click an AC to highlight the phases and files that satisfy it (reverse
    // traceability), and light up this card when its phases are selected.
    if (phases.length) {
      this.classList.add('pd-ac-link');
      this.addEventListener('click', (e) => {
        if (e.target.closest('a, button')) return;
        window.dispatchEvent(new CustomEvent('pd:phase-selected', {
          detail: { phases, files: filesForPhases(phases), source: this, ac: id },
        }));
      });
    }
    window.addEventListener('pd:phase-selected', (e) => {
      const sel = new Set((e.detail?.phases || []).map(String));
      const on = e.detail?.ac === id || (sel.size > 0 && phases.some((p) => sel.has(p)));
      this.classList.toggle('pd-ac-hl', on);
    });
  }
}

class PdWire extends PdElement {
  init() {
    const h = this.getAttribute('h');
    if (h) this.style.minHeight = h;
    const label = this.getAttribute('label');
    if (label && !this.childNodes.length) this.append(el('span', { class: 'pd-wire-label' }, label));
    else if (label) this.prepend(el('span', { class: 'pd-wire-label' }, label));
  }
}

class PdNote extends PdElement {}

class PdCollapse extends PdElement {
  init() {
    const summary = this.getAttribute('summary') || 'Details';
    const open = this.hasAttribute('open');
    const body = el('div', { class: 'pd-collapse-body' });
    while (this.firstChild) body.append(this.firstChild);
    const details = el('details', { class: 'pd-collapse', open });
    details.append(el('summary', { class: 'pd-collapse-summary' }, summary), body);
    this.append(details);
  }
}

define('pd-ac', PdAc);
define('pd-wire', PdWire);
define('pd-note', PdNote);
define('pd-collapse', PdCollapse);
