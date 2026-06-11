// Pending-comment store: comments the reviewer types in the browser, queued
// until they copy them out and paste them to their agent. The HTML file on
// disk is never modified by the browser — the agent is the only writer.
//
// Persisted to localStorage so an accidental refresh doesn't lose a review.

const KEY = `pd-pending:${location.pathname}`;

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; }
}

let items = load();

function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(items)); } catch { /* file:// quota etc. */ }
  window.dispatchEvent(new CustomEvent('pd:pending-changed', { detail: { count: items.length } }));
}

export const store = {
  all: () => items.slice(),
  count: () => items.length,

  // entry: { kind: 'reply'|'new', thread?, anchor?, priority?, text }
  add(entry) {
    items.push({ ...entry, ts: new Date().toISOString() });
    persist();
  },

  remove(idx) {
    items.splice(idx, 1);
    persist();
  },

  clear() {
    items = [];
    persist();
  },

  // Compact plain-text export the user pastes back to the agent. The
  // planning-doc skill documents how to merge this into the HTML source.
  serialize(docTitle) {
    const lines = [
      '=== DOC COMMENTS — paste to your agent to merge into the doc ===',
      `doc: ${docTitle || document.title}`,
    ];
    items.forEach((it, i) => {
      if (it.kind === 'reply') {
        lines.push('', `[${i + 1}] REPLY to thread "${it.thread}"${it.anchor ? ` (anchor: ${it.anchor})` : ''}`);
      } else {
        lines.push('', `[${i + 1}] NEW ${it.priority || 'p2'} comment on "${it.thread}"${it.anchor ? ` (anchor: ${it.anchor})` : ''}`);
      }
      lines.push(...it.text.split('\n').map((l) => `    ${l}`));
    });
    lines.push('', '=== END DOC COMMENTS ===');
    return lines.join('\n');
  },
};

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // file:// pages may lack clipboard permission — fall back to a selectable box.
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:10%;left:10%;width:80%;height:60%;z-index:9999';
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand && document.execCommand('copy');
    if (ok) ta.remove();
    else ta.addEventListener('blur', () => ta.remove());
    return !!ok;
  }
}
