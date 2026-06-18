// pd-outcome — the epic-altitude scan strip, fully derived. No attributes. The
// epic analogue of pd-scope: it counts the nouns an epic cares about — user
// journeys, guard rails (functional vs non-functional), tasks (by status, how
// many independently deployable) — and flags coverage gaps:
//   - a guard rail no task honors
//   - a journey/cli (with an id) no task delivers
//   - a task that isn't marked deployable
//
// Communicating that gap set in prose means hand-cross-checking every task
// against every journey and rail; here it's free and stays correct as the doc
// changes. Drop one at the top of the Vision tab.
//
//   <pd-outcome></pd-outcome>

import { PdElement, define, el, csv, openThreadCount } from './util.js';

class PdOutcome extends PdElement {
  init() {
    const journeys = [...document.querySelectorAll('pd-journey, pd-cli')];
    const rails = [...document.querySelectorAll('pd-guardrail')];
    const tasks = [...document.querySelectorAll('pd-task')];

    const strip = el('div', { class: 'pd-scope-strip' });

    // Final-shape units (journeys + CLI transcripts).
    if (journeys.length) {
      strip.append(this._tile(String(journeys.length), journeys.length === 1 ? 'journey' : 'journeys', 'user-facing shape'));
    }

    // Guard rails, split functional vs non-functional.
    if (rails.length) {
      const nf = rails.filter((r) => r.dataset.class === 'nonfunctional').length;
      const fn = rails.length - nf;
      strip.append(this._tile(String(rails.length), rails.length === 1 ? 'guard rail' : 'guard rails',
        `${fn} functional · ${nf} non-functional`));
    }

    // Tasks: status progress + deployability.
    if (tasks.length) {
      const byStatus = (s) => tasks.filter((t) => (t.getAttribute('status') || 'todo') === s).length;
      const done = byStatus('done'); const active = byStatus('active'); const todo = byStatus('todo');
      const deployable = tasks.filter((t) => t.hasAttribute('deployable')).length;
      const bar = el('div', { class: 'pd-scope-bar' }, [
        done ? el('span', { class: 'pd-scope-seg', 'data-k': 'done', style: `flex:${done}` }) : null,
        active ? el('span', { class: 'pd-scope-seg', 'data-k': 'active', style: `flex:${active}` }) : null,
        todo ? el('span', { class: 'pd-scope-seg', 'data-k': 'todo', style: `flex:${todo}` }) : null,
      ]);
      const notDeployable = tasks.length - deployable;
      strip.append(this._tile(String(tasks.length), tasks.length === 1 ? 'task' : 'tasks',
        `${deployable} deployable${notDeployable ? ` · ${notDeployable} not` : ''}`, bar, notDeployable ? 'warn' : null));
    }

    // Coverage gaps — the payload prose can't cheaply convey.
    if (tasks.length && (rails.length || journeys.length)) {
      const honored = new Set(tasks.flatMap((t) => csv(t.getAttribute('honors'))));
      const delivered = new Set(tasks.flatMap((t) => csv(t.getAttribute('delivers'))));
      const orphanRails = rails.filter((r) => r.getAttribute('id') && !honored.has(r.getAttribute('id'))).length;
      const journeyIds = journeys.map((j) => j.getAttribute('id')).filter(Boolean);
      const orphanJourneys = journeyIds.filter((id) => !delivered.has(id)).length;
      const gaps = orphanRails + orphanJourneys;
      const sub = gaps
        ? [orphanRails ? `${orphanRails} rail${orphanRails === 1 ? '' : 's'} unguarded` : null,
           orphanJourneys ? `${orphanJourneys} journey${orphanJourneys === 1 ? '' : 's'} undelivered` : null].filter(Boolean).join(' · ')
        : 'all delivered & guarded';
      strip.append(this._tile(String(gaps), gaps === 1 ? 'coverage gap' : 'coverage gaps', sub, null, gaps ? 'warn' : 'ok'));
    }

    const open = openThreadCount(document);
    if (open) strip.append(this._tile(String(open), open === 1 ? 'open thread' : 'open threads', 'awaiting resolution', null, 'warn'));

    this.append(strip);
  }

  _tile(value, label, sub, extra, tone) {
    return el('div', { class: 'pd-scope-tile', 'data-tone': tone || '' }, [
      el('div', { class: 'pd-scope-value' }, value),
      el('div', { class: 'pd-scope-label' }, label),
      sub ? el('div', { class: 'pd-scope-sub' }, sub) : null,
      extra || null,
    ]);
  }
}

define('pd-outcome', PdOutcome);
