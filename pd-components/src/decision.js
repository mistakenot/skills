// pd-decision: an authored architectural decision record (ADR). Unlike a
// pd-thread (an append-only review conversation that becomes a decision once
// resolved), a pd-decision is a decision the author/agent made directly — it
// states the call, the rationale, the alternatives, and the consequences with
// no review round-trip required.
//
//   status: accepted (default) | proposed | superseded
//   by:     who made the call (e.g. "agent", "author", a person)
//   summary: optional one-liner surfaced in the <pd-decisions> log
//
// Resolved/rejected pd-threads and every pd-decision both feed the
// <pd-decisions> aggregate log (see threads.js), so the decision history reads
// as one list regardless of how each entry was recorded.

import { PdElement, define, el } from './util.js';

class PdDecision extends PdElement {
  init() {
    const status = this.getAttribute('status') || 'accepted';
    const title = this.getAttribute('title') || 'Decision';
    const by = this.getAttribute('by');
    const date = this.getAttribute('date');

    const meta = [by ? `by ${by}` : null, date].filter(Boolean).join(' · ');
    const head = el('div', { class: 'pd-decision-head' }, [
      el('span', { class: 'pd-badge', 'data-status': status }, status),
      el('strong', { class: 'pd-decision-title' }, title),
      meta ? el('span', { class: 'pd-decision-meta' }, meta) : null,
    ]);

    const body = el('div', { class: 'pd-decision-body' });
    while (this.firstChild) body.append(this.firstChild);
    this.append(head, body);
  }
}

define('pd-decision', PdDecision);
