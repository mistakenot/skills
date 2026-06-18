// pd-journey — a user journey at epic altitude: the legs a user travels to reach
// an outcome, told from their point of view. Light-touch flow — no screens, no
// files, no implementation. The app analogue of pd-cli's terminal transcript.
//
//   <pd-journey title="A developer ships a feature" outcome="merged PR, no manual coding">
//     <pd-leg actor="dev" action="runs /new-task" status="done">requirements appear</pd-leg>
//     <pd-leg actor="agent" action="plans → executes" status="active">opens a PR</pd-leg>
//     <pd-leg actor="dev" action="reviews in browser" status="todo">threads resolve, merge</pd-leg>
//   </pd-journey>
//
// Legs auto-number and render as a connected flow. outcome= caps the flow with
// the user-visible result. status= done|active|todo on a leg tints it so the
// reader sees how much of the journey is real today vs still coming.

import { PdElement, define, el, selectEpic } from './util.js';

class PdJourney extends PdElement {
  init() {
    const title = this.getAttribute('title');
    const outcome = this.getAttribute('outcome');
    const caption = this.getAttribute('caption');
    const id = this.getAttribute('id');
    const legs = [...this.querySelectorAll(':scope > pd-leg')];

    const flow = el('div', { class: 'pd-journey-flow' });
    legs.forEach((leg, i) => {
      const actor = leg.getAttribute('actor');
      const action = leg.getAttribute('action') || '';
      const status = leg.getAttribute('status');
      const result = leg.textContent.trim();
      if (i > 0) flow.append(el('span', { class: 'pd-journey-arrow' }, '→'));
      flow.append(el('div', { class: 'pd-journey-leg', 'data-status': status || null }, [
        el('span', { class: 'pd-journey-n' }, String(i + 1)),
        actor ? el('span', { class: 'pd-chip pd-journey-actor' }, actor) : null,
        el('div', { class: 'pd-journey-action' }, action),
        result ? el('div', { class: 'pd-journey-result' }, result) : null,
      ]));
    });
    if (outcome) {
      flow.append(el('span', { class: 'pd-journey-arrow' }, '→'));
      flow.append(el('div', { class: 'pd-journey-outcome' }, [
        el('span', { class: 'pd-journey-outcome-label' }, 'outcome'),
        el('div', {}, outcome),
      ]));
    }

    this.innerHTML = '';
    const wrap = el('div', { class: 'pd-journey' });
    if (title) wrap.append(el('div', { class: 'pd-journey-title' }, title));
    wrap.append(flow);
    this.append(wrap);
    if (caption) this.append(el('div', { class: 'pd-journey-caption' }, caption));

    // With an id, the journey joins the epic graph: clicking its title shows
    // which tasks deliver it; selecting one of those lights it up.
    if (id && title) {
      const t = wrap.querySelector('.pd-journey-title');
      t.classList.add('pd-epic-clickable');
      t.addEventListener('click', () => selectEpic('journey', id, this));
      window.addEventListener('pd:epic-selected', (e) => {
        this.classList.toggle('pd-epic-hl', (e.detail?.journeys || []).includes(id));
      });
    }
  }
}

class PdLeg extends PdElement {}

define('pd-journey', PdJourney);
define('pd-leg', PdLeg);
