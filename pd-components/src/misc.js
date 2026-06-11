// pd-ac: acceptance-criteria card with traceability chips.
//   <pd-ac id="AC-1" title="Rate limit applies" phases="1,2" tests="e2e/rate.spec.ts">
//     <ul><li>Given… </li><li>When… </li><li>Then… </li></ul>
//   </pd-ac>
//
// pd-wire: wireframe placeholder box. pd-note: annotation callout.
// Wireframe sections are otherwise freeform HTML (Tailwind welcome).

import { PdElement, define, el } from './util.js';

class PdAc extends PdElement {
  init() {
    const chips = el('div', { class: 'pd-ac-chips' });
    (this.getAttribute('phases') || '').split(',').map((s) => s.trim()).filter(Boolean)
      .forEach((p) => chips.append(el('span', { class: 'pd-chip' }, `phase ${p}`)));
    (this.getAttribute('tests') || '').split(',').map((s) => s.trim()).filter(Boolean)
      .forEach((t) => chips.append(el('span', { class: 'pd-chip pd-chip-test' }, t)));

    this.prepend(el('div', { class: 'pd-ac-head' }, [
      el('span', { class: 'pd-chip pd-chip-id' }, this.getAttribute('id') || 'AC'),
      el('strong', {}, this.getAttribute('title') || ''),
      chips,
    ]));
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

define('pd-ac', PdAc);
define('pd-wire', PdWire);
define('pd-note', PdNote);
