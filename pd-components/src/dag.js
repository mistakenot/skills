// pd-dag: phase dependency graph, fully derived from <pd-phase> elements.
//
// Reads every pd-phase in the document (n, title, status, files, depends-on)
// and renders a layered left-to-right DAG. Two kinds of edge:
//   - solid: an explicit dependency from depends-on="1,2"
//   - dashed warn: an *implicit* conflict — two phases share a file but neither
//     depends on the other, so they can't safely run in parallel. Auto-detected
//     from the files attribute; no agent authoring needed.
//
// Clicking a node broadcasts pd:phase-selected (same event pd-stepper emits) so
// pd-files highlights that phase's files. The graph is the scan-layer answer to
// "what's the shape of this work, what's parallel, what's blocked".
//
//   <pd-dag caption="Execution order"></pd-dag>

import { PdElement, define, el } from './util.js';

const NODE_W = 150;
const NODE_H = 46;
const COL_GAP = 64;
const ROW_GAP = 22;
const PAD = 12;

const numbers = (s) => (s || '').split(',').map((x) => x.trim()).filter(Boolean);

class PdDag extends PdElement {
  init() {
    const phases = [...document.querySelectorAll('pd-phase')].map((p, i) => ({
      n: p.getAttribute('n') || String(i + 1),
      title: p.getAttribute('title') || `Phase ${i + 1}`,
      status: p.getAttribute('status') || 'todo',
      files: numbers(p.getAttribute('files')),
      deps: numbers(p.getAttribute('depends-on')),
      el: p,
    }));
    if (!phases.length) return;

    const byN = new Map(phases.map((p) => [p.n, p]));

    // Rank = longest dependency chain to a root (memoized DFS, cycle-guarded).
    const rankCache = new Map();
    const rank = (p, seen = new Set()) => {
      if (rankCache.has(p.n)) return rankCache.get(p.n);
      if (seen.has(p.n)) return 0; // cycle: treat as root to stay finite
      seen.add(p.n);
      const deps = p.deps.map((d) => byN.get(d)).filter(Boolean);
      const r = deps.length ? Math.max(...deps.map((d) => rank(d, seen) + 1)) : 0;
      rankCache.set(p.n, r);
      return r;
    };
    phases.forEach((p) => { p.rank = rank(p); });

    // Group into columns by rank; lay out each column vertically.
    const cols = [];
    phases.forEach((p) => { (cols[p.rank] ||= []).push(p); });
    const maxRows = Math.max(...cols.map((c) => c.length));
    cols.forEach((col, c) => {
      const colH = col.length * NODE_H + (col.length - 1) * ROW_GAP;
      const fullH = maxRows * NODE_H + (maxRows - 1) * ROW_GAP;
      const y0 = PAD + (fullH - colH) / 2;
      col.forEach((p, r) => {
        p.x = PAD + c * (NODE_W + COL_GAP);
        p.y = y0 + r * (NODE_H + ROW_GAP);
      });
    });

    const width = PAD * 2 + cols.length * NODE_W + (cols.length - 1) * COL_GAP;
    const height = PAD * 2 + maxRows * NODE_H + (maxRows - 1) * ROW_GAP;

    // Conflict edges: shared file, no transitive dependency either direction.
    const reaches = (a, b, seen = new Set()) => {
      if (a.n === b.n) return true;
      if (seen.has(a.n)) return false;
      seen.add(a.n);
      return a.deps.some((d) => { const dp = byN.get(d); return dp && reaches(dp, b, seen); });
    };
    const conflicts = [];
    for (let i = 0; i < phases.length; i++) {
      for (let j = i + 1; j < phases.length; j++) {
        const a = phases[i]; const b = phases[j];
        const shared = a.files.filter((f) => b.files.includes(f));
        if (shared.length && !reaches(a, b) && !reaches(b, a)) {
          conflicts.push({ a, b, shared });
        }
      }
    }

    this.innerHTML = '';
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'pd-dag-svg');
    svg.setAttribute('role', 'img');
    svg.style.maxWidth = `${width}px`;

    const edge = (x1, y1, x2, y2, cls) => {
      const mx = (x1 + x2) / 2;
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
      path.setAttribute('class', cls);
      svg.append(path);
    };

    // Dependency edges (behind nodes).
    phases.forEach((p) => p.deps.forEach((d) => {
      const dep = byN.get(d);
      if (!dep) return;
      edge(dep.x + NODE_W, dep.y + NODE_H / 2, p.x, p.y + NODE_H / 2, 'pd-dag-edge');
    }));
    // Conflict edges.
    conflicts.forEach(({ a, b }) => {
      const [l, r] = a.x <= b.x ? [a, b] : [b, a];
      edge(l.x + NODE_W, l.y + NODE_H / 2, r.x, r.y + NODE_H / 2, 'pd-dag-edge pd-dag-conflict');
    });

    // Nodes.
    phases.forEach((p) => {
      const g = document.createElementNS(NS, 'g');
      g.setAttribute('class', 'pd-dag-node');
      g.setAttribute('data-status', p.status);
      g.setAttribute('tabindex', '0');
      g.setAttribute('role', 'button');
      const select = () => window.dispatchEvent(new CustomEvent('pd:phase-selected', { detail: { phases: [p.n], files: p.files, source: this } }));
      g.addEventListener('click', select);
      g.addEventListener('focus', select);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); } });

      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('x', p.x); rect.setAttribute('y', p.y);
      rect.setAttribute('width', NODE_W); rect.setAttribute('height', NODE_H);
      rect.setAttribute('rx', 8);
      g.append(rect);

      const badge = document.createElementNS(NS, 'text');
      badge.setAttribute('x', p.x + 14); badge.setAttribute('y', p.y + NODE_H / 2 + 4);
      badge.setAttribute('class', 'pd-dag-n');
      badge.textContent = p.n;
      g.append(badge);

      const label = document.createElementNS(NS, 'text');
      label.setAttribute('x', p.x + 30); label.setAttribute('y', p.y + NODE_H / 2 + 4);
      label.setAttribute('class', 'pd-dag-label');
      const t = p.title.length > 18 ? p.title.slice(0, 17) + '…' : p.title;
      label.textContent = t;
      const tt = document.createElementNS(NS, 'title');
      tt.textContent = `${p.title} (${p.status})`;
      g.append(tt, label);

      svg.append(g);
    });

    const caption = this.getAttribute('caption');
    const fig = el('figure', { class: 'pd-dag-figure' });
    fig.append(svg);

    if (conflicts.length) {
      const warns = conflicts.map((c) => `phase ${c.a.n} ↔ ${c.b.n} share ${c.shared.map((f) => f.split('/').pop()).join(', ')}`);
      fig.append(el('div', { class: 'pd-dag-conflicts' }, [
        el('span', { class: 'pd-dag-conflict-mark' }, '⚠ file conflicts (not parallel-safe): '),
        warns.join('; '),
      ]));
    }
    if (caption) fig.append(el('figcaption', {}, caption));
    this.append(fig);

    // Highlight our node(s) for the selected phase set, wherever the selection
    // came from (this graph, the stepper, an AC, keyboard focus).
    window.addEventListener('pd:phase-selected', (e) => {
      const sel = new Set((e.detail?.phases || []).map(String));
      svg.querySelectorAll('.pd-dag-node').forEach((node, idx) => {
        const on = sel.has(String(phases[idx].n));
        node.classList.toggle('pd-dag-on', on);
        node.classList.toggle('pd-dag-off', sel.size > 0 && !on);
      });
    });
  }
}

define('pd-dag', PdDag);
