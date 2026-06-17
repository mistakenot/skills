// pd-scope: at-a-glance summary strip, fully derived from the document. No
// attributes — drop it at the top of the first tab and it computes itself from
// the pd-phase / pd-file / pd-ac / pd-thread elements already in the doc.
//
//   phases (+ done/active/todo progress) · file changes (+/~/−) · ACs
//   (+ coverage gaps) · open threads
//
// This is the scan layer: a human groks the size, progress and coverage of the
// whole plan from one row without reading a word of prose.
//
//   <pd-scope></pd-scope>

import { PdElement, define, el, openThreadCount } from './util.js';

const has = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean).length > 0;

class PdScope extends PdElement {
  init() {
    const phases = [...document.querySelectorAll('pd-phase')];
    const files = [...document.querySelectorAll('pd-file')];
    const acs = [...document.querySelectorAll('pd-ac')];

    const byStatus = (s) => phases.filter((p) => (p.getAttribute('status') || 'todo') === s).length;
    const done = byStatus('done'); const active = byStatus('active'); const todo = byStatus('todo');

    const byChange = (c) => files.filter((f) => (f.getAttribute('change') || 'edit') === c).length;
    const add = byChange('add'); const edit = byChange('edit'); const del = byChange('delete');

    const acsNoTests = acs.filter((a) => !has(a.getAttribute('tests'))).length;
    const acsNoPhase = acs.filter((a) => !has(a.getAttribute('phases'))).length;
    const open = openThreadCount(document);

    const strip = el('div', { class: 'pd-scope-strip' });

    // Phases tile carries a progress bar.
    if (phases.length) {
      const bar = el('div', { class: 'pd-scope-bar' }, [
        done ? el('span', { class: 'pd-scope-seg', 'data-k': 'done', style: `flex:${done}` }) : null,
        active ? el('span', { class: 'pd-scope-seg', 'data-k': 'active', style: `flex:${active}` }) : null,
        todo ? el('span', { class: 'pd-scope-seg', 'data-k': 'todo', style: `flex:${todo}` }) : null,
      ]);
      strip.append(this._tile(String(phases.length), phases.length === 1 ? 'phase' : 'phases',
        `${done} done · ${active} active · ${todo} todo`, bar));
    }

    if (files.length) {
      const sub = [add ? `+${add}` : null, edit ? `~${edit}` : null, del ? `−${del}` : null].filter(Boolean).join('  ');
      strip.append(this._tile(String(files.length), files.length === 1 ? 'file' : 'files', sub));
    }

    if (acs.length) {
      const gap = acsNoTests || acsNoPhase;
      const sub = gap
        ? `${acsNoTests} untested${acsNoPhase ? ` · ${acsNoPhase} unscheduled` : ''}`
        : 'all covered';
      strip.append(this._tile(String(acs.length), acs.length === 1 ? 'criterion' : 'criteria', sub, null, gap ? 'warn' : 'ok'));
    }

    if (open) {
      strip.append(this._tile(String(open), open === 1 ? 'open thread' : 'open threads', 'awaiting resolution', null, 'warn'));
    }

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

define('pd-scope', PdScope);
