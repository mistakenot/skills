// pd-trace: traceability matrix, fully derived from <pd-ac> elements. Each AC
// already carries phases="1,2" and tests="a.spec.ts" — pd-trace scans them all
// and renders an AC × Phase × Test grid so coverage gaps pop at a glance.
//
// A row with no phase or no test is flagged: those are the holes a reviewer
// most needs to see. No new agent authoring — the data is already on pd-ac.
//
//   <pd-trace caption="Acceptance coverage"></pd-trace>

import { PdElement, define, el } from './util.js';

const list = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean);

class PdTrace extends PdElement {
  init() {
    const acs = [...document.querySelectorAll('pd-ac')];
    if (!acs.length) return;

    // Stable union of phase numbers across the doc (prefer pd-phase order).
    const phaseNs = [...document.querySelectorAll('pd-phase')].map((p, i) => p.getAttribute('n') || String(i + 1));
    const acPhases = acs.flatMap((a) => list(a.getAttribute('phases')));
    const phases = [...new Set([...phaseNs, ...acPhases])];

    const head = el('tr', {}, [
      el('th', {}, 'Criterion'),
      ...phases.map((n) => el('th', { class: 'pd-trace-ph', title: `Phase ${n}` }, n)),
      el('th', {}, 'Tests'),
    ]);

    const rows = acs.map((a) => {
      const id = a.getAttribute('id') || 'AC';
      const title = a.getAttribute('title') || '';
      const ph = list(a.getAttribute('phases'));
      const tests = list(a.getAttribute('tests'));
      const gap = !ph.length || !tests.length;

      const cells = phases.map((n) =>
        el('td', { class: 'pd-trace-cell' }, ph.includes(n)
          ? el('span', { class: 'pd-trace-dot', title: `Phase ${n} covers ${id}` }, '●')
          : ''));

      const testCell = tests.length
        ? el('td', { class: 'pd-trace-tests' }, tests.map((t) => el('code', { class: 'pd-chip pd-chip-test', title: t }, t.split('/').pop())))
        : el('td', { class: 'pd-trace-tests pd-trace-missing' }, 'none');

      return el('tr', { 'data-gap': gap ? '' : null }, [
        el('th', { class: 'pd-trace-ac', scope: 'row' }, [
          el('span', { class: 'pd-chip pd-chip-id' }, id),
          el('span', { class: 'pd-trace-ac-title' }, title),
          gap ? el('span', { class: 'pd-trace-flag', title: !ph.length ? 'no phase scheduled' : 'no test specified' }, '⚠') : null,
        ]),
        ...cells,
        testCell,
      ]);
    });

    const gaps = acs.filter((a) => !list(a.getAttribute('phases')).length || !list(a.getAttribute('tests')).length).length;
    const caption = this.getAttribute('caption');

    const table = el('table', { class: 'pd-trace-table' }, [
      el('thead', {}, head),
      el('tbody', {}, rows),
    ]);
    const fig = el('figure', { class: 'pd-trace-figure' }, [table]);
    if (gaps) fig.append(el('div', { class: 'pd-trace-summary pd-trace-missing' }, `${gaps} criterion${gaps === 1 ? '' : 'a'} with a coverage gap`));
    if (caption) fig.append(el('figcaption', {}, caption));
    this.append(fig);
  }
}

define('pd-trace', PdTrace);
