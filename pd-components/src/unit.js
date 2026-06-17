// TypeScript code-unit outline.
//
// pd-unit — an opinionated outline of a single TS code unit (class, service,
//   interface) built around the three things a high-level reviewer checks
//   first, in order:
//     1. what is it called?       → name + kind + extends/implements lineage
//     2. what does it depend on?  → <pd-dep> constructor dependencies
//     3. what is its surface?     → <pd-fn> / <pd-prop> public members
//   Bodies are omitted by design: the rest of the unit is inferable from these.
//
// Use pd-api instead for a language-agnostic symbol dump (one flat member list,
// free-form kind badges). pd-unit is the TS-flavoured, dependency-first variant.

import { PdElement, define, el, esc } from './util.js';
import { highlight } from './highlight.js';

// Render a TS fragment to highlighted HTML, defaulting the language to ts.
function ts(code, lang) {
  return highlight(code, lang || 'ts');
}

// One constructor dependency: `name: Type` plus an optional role note. The
// type is the signal a reviewer scans, so it is highlighted and the name is
// dimmed to a label.
function depRow(dep, lang) {
  const name = dep.getAttribute('name') || '';
  const type = dep.getAttribute('type') || '';
  const access = dep.getAttribute('access'); // private|public|readonly|...
  const note = dep.textContent.trim();
  const sig = el('code', { class: 'pd-dep-sig' });
  sig.innerHTML =
    (access ? `<span class="pd-dep-access">${esc(access)}</span> ` : '') +
    `<span class="pd-dep-name">${esc(name)}</span>` +
    (type ? `<span class="pd-dep-punc">: </span>${ts(type, lang)}` : '');
  return el('div', { class: 'pd-dep' }, [
    sig,
    note ? el('div', { class: 'pd-dep-note' }, note) : null,
  ]);
}

// One public-surface member. <pd-fn> → method, <pd-prop> → property; the tag
// name drives the left-rail kind label so authoring stays terse.
function memberRow(node, lang) {
  const kind = node.tagName.toLowerCase() === 'pd-prop' ? 'prop' : 'fn';
  const sig = node.getAttribute('sig') || node.getAttribute('name') || '';
  const note = node.textContent.trim();
  const sigEl = el('code', { class: 'pd-unit-sig' });
  sigEl.innerHTML = ts(sig, lang);
  return el('div', { class: 'pd-unit-member', 'data-kind': kind }, [
    el('span', { class: 'pd-unit-member-kind' }, kind),
    el('div', { class: 'pd-unit-member-main' }, [
      sigEl,
      note ? el('div', { class: 'pd-unit-member-note' }, note) : null,
    ]),
  ]);
}

function section(label, rows) {
  if (!rows.length) return null;
  return el('div', { class: 'pd-unit-section' }, [
    el('div', { class: 'pd-unit-section-label' }, label),
    el('div', { class: 'pd-unit-section-body' }, rows),
  ]);
}

class PdUnit extends PdElement {
  init() {
    const kind = this.getAttribute('kind') || 'class';
    const name = this.getAttribute('name') || '';
    const ext = this.getAttribute('extends');
    const impl = this.getAttribute('implements');
    const lang = this.getAttribute('lang') || 'ts';
    const path = this.getAttribute('path');
    const caption = this.getAttribute('caption');

    const deps = [...this.querySelectorAll(':scope > pd-dep')];
    const members = [...this.querySelectorAll(':scope > pd-fn, :scope > pd-prop')];

    // ---- identity row: kind, name, lineage, path ----
    const lineage = [];
    if (ext) lineage.push(el('span', { class: 'pd-unit-lin' }, [
      el('span', { class: 'pd-unit-lin-kw' }, 'extends '), ext,
    ]));
    if (impl) lineage.push(el('span', { class: 'pd-unit-lin' }, [
      el('span', { class: 'pd-unit-lin-kw' }, 'implements '), impl,
    ]));

    const head = el('div', { class: 'pd-unit-head' }, [
      el('span', { class: 'pd-chip pd-chip-kind' }, kind),
      el('code', { class: 'pd-unit-name' }, name),
      lineage.length ? el('code', { class: 'pd-unit-lineage' }, lineage) : null,
      path ? el('code', { class: 'pd-unit-path' }, path) : null,
    ]);

    const depsSection = section('Constructor dependencies', deps.map((d) => depRow(d, lang)));
    const apiSection = section('Public API', members.map((m) => memberRow(m, lang)));

    this.innerHTML = '';
    this.append(head);
    if (caption) this.append(el('div', { class: 'pd-unit-caption' }, caption));
    if (depsSection) this.append(depsSection);
    if (apiSection) this.append(apiSection);
  }
}

class PdDep extends PdElement {}
class PdFn extends PdElement {}
class PdProp extends PdElement {}

define('pd-unit', PdUnit);
define('pd-dep', PdDep);
define('pd-fn', PdFn);
define('pd-prop', PdProp);
