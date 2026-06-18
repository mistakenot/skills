// pd-cli — a terminal transcript showing the *final shape* of a dev tool / CLI /
// API from the user's point of view: the commands they run and the output they
// get back, with light inline comments. Epic-altitude — it describes the
// experience the work delivers, never the files behind it.
//
//   <pd-cli title="Author and ship a skill" caption="...">
//     <pd-cmd note="describe it once in src/">npx skills new my-skill</pd-cmd>
//     <pd-out>✓ scaffolded src/my-skill/SKILL.md</pd-out>
//   </pd-cli>
//
// pd-cmd — one command line. note= renders as a dimmed `# comment`. status=
//   done|active|todo tints the line so a reader sees what works today vs what's
//   still coming. If the command contains <, >, or &, wrap its text in a nested
//   <script type="text/plain"> to avoid HTML parsing.
// pd-out — the output for the preceding command(s); always rendered dimmed.

import { PdElement, define, el } from './util.js';
import { copyText } from './store.js';

// Text comes from a nested <script type="text/plain"> (use when it contains
// <, >, or &) or the element's own text content.
function readText(host) {
  const script = host.querySelector(':scope > script[type="text/plain"]');
  const raw = script ? script.textContent : host.textContent;
  return raw.replace(/^\n/, '').replace(/\s+$/, '');
}

class PdCli extends PdElement {
  init() {
    const title = this.getAttribute('title');
    const caption = this.getAttribute('caption');
    const rows = [...this.querySelectorAll(':scope > pd-cmd, :scope > pd-out')];

    const body = el('div', { class: 'pd-cli-body' });
    rows.forEach((node) => {
      const text = readText(node);
      if (node.tagName.toLowerCase() === 'pd-cmd') {
        const status = node.getAttribute('status');
        const note = node.getAttribute('note');
        const copy = el('button', { class: 'pd-cli-copy', title: 'Copy command',
          onclick: async () => {
            const ok = await copyText(text);
            copy.textContent = ok ? 'copied' : 'copy';
            setTimeout(() => { copy.textContent = 'copy'; }, 1500);
          } }, 'copy');
        body.append(el('div', { class: 'pd-cli-cmd', 'data-status': status || null }, [
          el('span', { class: 'pd-cli-prompt' }, '$'),
          el('code', { class: 'pd-cli-cmd-text' }, text),
          note ? el('span', { class: 'pd-cli-note' }, '# ' + note) : null,
          copy,
        ]));
      } else {
        body.append(el('pre', { class: 'pd-cli-out' }, el('code', {}, text)));
      }
    });

    this.innerHTML = '';
    const wrap = el('div', { class: 'pd-cli' }, [
      el('div', { class: 'pd-cli-bar' }, [
        el('span', { class: 'pd-cli-dots' }, [el('i'), el('i'), el('i')]),
        title ? el('span', { class: 'pd-cli-title' }, title) : null,
      ]),
      body,
    ]);
    this.append(wrap);
    if (caption) this.append(el('div', { class: 'pd-cli-caption' }, caption));
  }
}

class PdCmd extends PdElement {}
class PdOut extends PdElement {}

define('pd-cli', PdCli);
define('pd-cmd', PdCmd);
define('pd-out', PdOut);
