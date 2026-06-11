// Code-oriented components.
//
// pd-code  — a syntax-highlighted snippet with an optional file header, line
//            numbers, emphasized lines, and a copy button.
// pd-api   — a token-efficient outline of a code symbol (class, interface,
//            struct, module, …): the public surface only — signatures + doc
//            comments, no bodies. pd-member is one entry.
//
// pd-api is intentionally generic: `kind` on the container and on members are
// free-form labels rendered as badges, so the same component outlines a Go
// struct, a TS class, a REST route table, or a SQL schema without new tags.

import { PdElement, define, el, esc } from './util.js';
import { highlight, splitLines } from './highlight.js';
import { copyText } from './store.js';

// Code text comes either from a nested <script type="text/plain"> (use this
// when the code contains <, >, or &) or from the element's own text content.
function readCode(host) {
  const script = host.querySelector(':scope > script[type="text/plain"]');
  const raw = script ? script.textContent : host.textContent;
  return raw.replace(/^\n/, '').replace(/\s+$/, '');
}

function parseRanges(spec) {
  const set = new Set();
  if (!spec) return set;
  for (const part of spec.split(',')) {
    const [a, b] = part.split('-').map((n) => parseInt(n.trim(), 10));
    if (Number.isNaN(a)) continue;
    for (let i = a; i <= (Number.isNaN(b) ? a : b); i++) set.add(i);
  }
  return set;
}

class PdCode extends PdElement {
  init() {
    const lang = this.getAttribute('lang') || '';
    const path = this.getAttribute('path');
    const caption = this.getAttribute('caption');
    const showLines = this.hasAttribute('lines');
    const hl = parseRanges(this.getAttribute('highlight'));
    const code = readCode(this);
    this.innerHTML = '';

    const wrap = el('div', { class: 'pd-code' });
    if (showLines) wrap.classList.add('has-lines');

    if (path || lang) {
      const copy = el('button', { class: 'pd-code-copy', title: 'Copy code',
        onclick: async () => {
          const ok = await copyText(code);
          copy.textContent = ok ? 'copied' : 'copy';
          setTimeout(() => { copy.textContent = 'copy'; }, 1500);
        } }, 'copy');
      wrap.append(el('div', { class: 'pd-code-head' }, [
        path ? el('code', { class: 'pd-code-path' }, path) : el('span', {}),
        el('span', { class: 'pd-code-head-r' }, [
          lang ? el('span', { class: 'pd-code-lang' }, lang) : null,
          copy,
        ]),
      ]));
    }

    const lines = splitLines(highlight(code, lang));
    const codeEl = el('code');
    lines.forEach((html, i) => {
      const line = el('span', { class: 'pd-code-line' });
      if (hl.has(i + 1)) line.dataset.hl = '';
      line.innerHTML = html || ' ';
      codeEl.append(line);
    });
    wrap.append(el('pre', {}, codeEl));
    if (caption) wrap.append(el('div', { class: 'pd-code-caption' }, caption));
    this.append(wrap);
  }
}

class PdApi extends PdElement {
  init() {
    const kind = this.getAttribute('kind') || 'class';
    const name = this.getAttribute('name') || '';
    const lang = this.getAttribute('lang') || '';
    const path = this.getAttribute('path');
    const caption = this.getAttribute('caption');
    const members = [...this.querySelectorAll(':scope > pd-member')];

    const head = el('div', { class: 'pd-api-head' }, [
      el('span', { class: 'pd-chip pd-chip-kind' }, kind),
      el('code', { class: 'pd-api-name' }, name),
      path ? el('code', { class: 'pd-api-path' }, path) : null,
    ]);

    const body = el('div', { class: 'pd-api-body' });
    members.forEach((mem) => {
      const mkind = mem.getAttribute('kind') || 'method';
      const sig = mem.getAttribute('sig') || mem.getAttribute('name') || '';
      const note = mem.textContent.trim();
      const sigHtml = el('code', { class: 'pd-member-sig' });
      sigHtml.innerHTML = highlight(sig, lang);
      body.append(el('div', { class: 'pd-member', 'data-kind': mkind }, [
        el('span', { class: 'pd-member-kind' }, mkind),
        el('div', { class: 'pd-member-main' }, [
          sigHtml,
          note ? el('div', { class: 'pd-member-note' }, note) : null,
        ]),
      ]));
    });

    this.innerHTML = '';
    this.append(head);
    if (caption) this.append(el('div', { class: 'pd-api-caption' }, caption));
    this.append(body);
  }
}

class PdMember extends PdElement {}

define('pd-code', PdCode);
define('pd-api', PdApi);
define('pd-member', PdMember);
