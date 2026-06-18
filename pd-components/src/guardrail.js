// pd-guardrail — a constraint every task in the epic inherits. Functional (a
// behavior/invariant that must hold) or non-functional (performance, security,
// cost, …). It's a join-key, not a design: tasks reference its id via honors=,
// so selecting a guard rail lights up its blast radius (every task bound by it)
// and pd-outcome flags any rail no task honors.
//
//   <pd-guardrail id="G1" kind="performance" metric="p99 < 200ms" title="Stays within budget under load">
//     <md>…optional elaboration…</md>
//   </pd-guardrail>
//
// kind: functional (default) | performance | security | cost | a11y |
//   reliability | compat | privacy | operability | scalability. Non-functional
//   kinds are grouped apart by pd-outcome. metric: optional measurable target.

import { PdElement, define, el, selectEpic } from './util.js';

const NONFUNCTIONAL = new Set([
  'performance', 'security', 'cost', 'a11y', 'accessibility', 'reliability',
  'compat', 'compatibility', 'privacy', 'operability', 'scalability', 'observability',
]);

class PdGuardrail extends PdElement {
  init() {
    const id = this.getAttribute('id') || 'G';
    const kind = (this.getAttribute('kind') || 'functional').toLowerCase();
    const metric = this.getAttribute('metric');
    const title = this.getAttribute('title') || '';
    const klass = NONFUNCTIONAL.has(kind) ? 'nonfunctional' : 'functional';
    this.dataset.class = klass;

    this.prepend(el('div', { class: 'pd-guardrail-head' }, [
      el('span', { class: 'pd-chip pd-chip-id' }, id),
      el('span', { class: 'pd-chip pd-guardrail-kind', 'data-class': klass }, kind),
      metric ? el('span', { class: 'pd-chip pd-guardrail-metric' }, metric) : null,
      title ? el('strong', { class: 'pd-guardrail-title' }, title) : null,
    ]));

    this.classList.add('pd-guardrail-link');
    this.addEventListener('click', (e) => {
      if (e.target.closest('a, button')) return;
      selectEpic('guardrail', id, this);
    });
    window.addEventListener('pd:epic-selected', (e) => {
      this.classList.toggle('pd-epic-hl', (e.detail?.guardrails || []).includes(id));
    });
  }
}

define('pd-guardrail', PdGuardrail);
