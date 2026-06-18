// pd-task — one unit of an epic's decomposition. NOT a phase: no files, no
// steps. It carries only what the epic cares about — what it advances and how
// it sequences:
//   id, title, status (todo|active|done), depends-on (other task ids),
//   delivers (journey/cli ids), honors (guard-rail ids),
//   deployable (independently shippable), gated (behind a feature flag),
//   href (link to its plan.html once planned).
// Selecting a task lights up the journeys it delivers and the guard rails it
// honors; selecting one of those lights up this card.
//
// pd-breakdown — derived dependency DAG over every pd-task (depends-on edges).
// Zero authoring beyond the cards. The deployment sequence at a glance: roots
// on the left, each column builds on the last.
//
//   <pd-task id="T1" title="Token-bucket limiter" status="done"
//            deployable delivers="J1" honors="G2">…intent…</pd-task>
//   <pd-breakdown caption="Build order"></pd-breakdown>

import { PdElement, define, el, csv, selectEpic } from './util.js';

class PdTask extends PdElement {
  init() {
    const id = this.getAttribute('id') || 'T';
    const title = this.getAttribute('title') || '';
    const status = this.getAttribute('status') || 'todo';
    const href = this.getAttribute('href');
    const deployable = this.hasAttribute('deployable');
    const gated = this.hasAttribute('gated');
    const delivers = csv(this.getAttribute('delivers'));
    const honors = csv(this.getAttribute('honors'));
    const deps = csv(this.getAttribute('depends-on'));
    this.dataset.status = status;

    const chips = el('div', { class: 'pd-task-chips' }, [
      deployable ? el('span', { class: 'pd-chip pd-task-deploy' }, 'deployable') : null,
      gated ? el('span', { class: 'pd-chip pd-task-gated' }, 'feature-gated') : null,
      ...delivers.map((j) => el('span', { class: 'pd-chip pd-task-delivers' }, `delivers ${j}`)),
      ...honors.map((g) => el('span', { class: 'pd-chip pd-task-honors' }, `honors ${g}`)),
    ]);

    this.prepend(el('div', { class: 'pd-task-head' }, [
      el('span', { class: 'pd-chip pd-chip-id' }, id),
      el('strong', { class: 'pd-task-title' }, title),
      href ? el('a', { class: 'pd-task-link', href, target: '_blank', rel: 'noopener' }, 'plan ↗') : null,
      chips,
    ]));
    if (deps.length) this.append(el('div', { class: 'pd-task-deps' }, `depends on ${deps.join(', ')}`));

    this.classList.add('pd-task-card');
    this.addEventListener('click', (e) => {
      if (e.target.closest('a, button')) return;
      selectEpic('task', id, this);
    });
    window.addEventListener('pd:epic-selected', (e) => {
      this.classList.toggle('pd-epic-hl', (e.detail?.tasks || []).includes(id));
    });
  }
}

const NODE_W = 158;
const NODE_H = 44;
const COL_GAP = 60;
const ROW_GAP = 20;
const PAD = 12;

class PdBreakdown extends PdElement {
  init() {
    const tasks = [...document.querySelectorAll('pd-task')].map((t, i) => ({
      id: t.getAttribute('id') || `T${i + 1}`,
      title: t.getAttribute('title') || `Task ${i + 1}`,
      status: t.getAttribute('status') || 'todo',
      deps: csv(t.getAttribute('depends-on')),
    }));
    if (!tasks.length) return;
    const byId = new Map(tasks.map((t) => [t.id, t]));

    // Rank = longest dependency chain to a root (cycle-guarded).
    const cache = new Map();
    const rank = (t, seen = new Set()) => {
      if (cache.has(t.id)) return cache.get(t.id);
      if (seen.has(t.id)) return 0;
      seen.add(t.id);
      const deps = t.deps.map((d) => byId.get(d)).filter(Boolean);
      const r = deps.length ? Math.max(...deps.map((d) => rank(d, seen) + 1)) : 0;
      cache.set(t.id, r);
      return r;
    };
    tasks.forEach((t) => { t.rank = rank(t); });

    const cols = [];
    tasks.forEach((t) => { (cols[t.rank] ||= []).push(t); });
    const maxRows = Math.max(...cols.map((c) => c.length));
    cols.forEach((col, c) => {
      const colH = col.length * NODE_H + (col.length - 1) * ROW_GAP;
      const fullH = maxRows * NODE_H + (maxRows - 1) * ROW_GAP;
      const y0 = PAD + (fullH - colH) / 2;
      col.forEach((t, r) => { t.x = PAD + c * (NODE_W + COL_GAP); t.y = y0 + r * (NODE_H + ROW_GAP); });
    });

    const width = PAD * 2 + cols.length * NODE_W + (cols.length - 1) * COL_GAP;
    const height = PAD * 2 + maxRows * NODE_H + (maxRows - 1) * ROW_GAP;

    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'pd-dag-svg');
    svg.setAttribute('role', 'img');
    svg.style.maxWidth = `${width}px`;

    const edge = (x1, y1, x2, y2) => {
      const mx = (x1 + x2) / 2;
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
      path.setAttribute('class', 'pd-dag-edge');
      svg.append(path);
    };
    tasks.forEach((t) => t.deps.forEach((d) => {
      const dep = byId.get(d);
      if (dep) edge(dep.x + NODE_W, dep.y + NODE_H / 2, t.x, t.y + NODE_H / 2);
    }));

    tasks.forEach((t) => {
      const g = document.createElementNS(NS, 'g');
      g.setAttribute('class', 'pd-dag-node');
      g.setAttribute('data-status', t.status);
      g.setAttribute('tabindex', '0');
      g.setAttribute('role', 'button');
      const select = () => selectEpic('task', t.id, this);
      g.addEventListener('click', select);
      g.addEventListener('focus', select);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); } });

      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('x', t.x); rect.setAttribute('y', t.y);
      rect.setAttribute('width', NODE_W); rect.setAttribute('height', NODE_H);
      rect.setAttribute('rx', 8);
      g.append(rect);

      const badge = document.createElementNS(NS, 'text');
      badge.setAttribute('x', t.x + 12); badge.setAttribute('y', t.y + NODE_H / 2 + 4);
      badge.setAttribute('class', 'pd-dag-n');
      badge.textContent = t.id;
      g.append(badge);

      const label = document.createElementNS(NS, 'text');
      label.setAttribute('x', t.x + 12 + t.id.length * 8 + 6); label.setAttribute('y', t.y + NODE_H / 2 + 4);
      label.setAttribute('class', 'pd-dag-label');
      label.textContent = t.title.length > 16 ? t.title.slice(0, 15) + '…' : t.title;
      const tt = document.createElementNS(NS, 'title');
      tt.textContent = `${t.id}: ${t.title} (${t.status})`;
      g.append(tt, label);

      svg.append(g);
    });

    this.innerHTML = '';
    const fig = el('figure', { class: 'pd-dag-figure' }, [svg]);
    const caption = this.getAttribute('caption');
    if (caption) fig.append(el('figcaption', {}, caption));
    this.append(fig);

    window.addEventListener('pd:epic-selected', (e) => {
      const sel = new Set(e.detail?.tasks || []);
      svg.querySelectorAll('.pd-dag-node').forEach((node, i) => {
        const on = sel.has(tasks[i].id);
        node.classList.toggle('pd-dag-on', on);
        node.classList.toggle('pd-dag-off', sel.size > 0 && !on);
      });
    });
  }
}

define('pd-task', PdTask);
define('pd-breakdown', PdBreakdown);
