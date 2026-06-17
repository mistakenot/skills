// Shared helpers for pd-* components.
//
// Components are upgraded by the parser before their children exist, so every
// component defers its init to DOMContentLoaded via ready(). This also makes
// the bundle safe to load without `defer`.

const pending = [];
let domReady = document.readyState !== 'loading';

if (!domReady) {
  document.addEventListener('DOMContentLoaded', () => {
    domReady = true;
    pending.splice(0).forEach((fn) => fn());
  });
}

export function ready(fn) {
  if (domReady) fn();
  else pending.push(fn);
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? '' : v);
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}

// Base class: defers init until DOM is parsed, guards against double-init.
export class PdElement extends HTMLElement {
  connectedCallback() {
    ready(() => {
      if (this._pdInit) return;
      this._pdInit = true;
      this.init();
    });
  }
  init() {}
}

export function define(name, cls) {
  if (!customElements.get(name)) customElements.define(name, cls);
}

// Threads can target anything with a matching id, a pd-file path, or a
// pd-section id. Count open threads under a root (for tab/file badges).
export function openThreadCount(root) {
  return root.querySelectorAll('pd-thread[status="unresolved"], pd-thread:not([status])').length;
}

// Union of files touched by the given phase numbers — the join behind
// AC → files highlighting (an AC names phases; phases name files).
export function filesForPhases(nums) {
  const want = new Set((nums || []).map(String));
  const set = new Set();
  [...document.querySelectorAll('pd-phase')].forEach((p, i) => {
    const n = p.getAttribute('n') || String(i + 1);
    if (!want.has(n)) return;
    (p.getAttribute('files') || '').split(',').map((s) => s.trim()).filter(Boolean).forEach((f) => set.add(f));
  });
  return [...set];
}
