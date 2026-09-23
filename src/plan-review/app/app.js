// plan-review app — open coding over generated plan.html documents.
//
// The plan is shown as-is in a same-origin iframe sized to its content, so the
// page (not the iframe) scrolls and margin notes can sit beside the text they
// annotate. Highlights use the CSS Custom Highlight API: nothing is inserted
// into the plan's DOM, so pd-components keep working and a note never
// disturbs the document it is about.
//
// Notes are anchored by quote + prefix/suffix + pd-tab name (see notes.py),
// re-found on every load by searching the tab's text.

const $ = (sel) => document.querySelector(sel);
const iframe = $('#doc');
const margin = $('#margin');
const offtab = $('#offtab');
const popover = $('#popover');

const S = {
  plans: [],          // [{plan_id, n, fixture_id, verdict, notes, snapshotted}]
  idx: -1,
  detail: null,
  notes: [],          // all live notes (folded server state)
  verdicts: {},
  ranges: new Map(),  // note id -> Range in the current doc (visible or not)
  pending: null,      // {range, quote, prefix, suffix, tab}
  view: 'review',
};

// ---------------------------------------------------------------- server I/O

const QUEUE_KEY = 'plan-review-unsent';

function queued() {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch { return []; }
}
function setQueued(q) {
  try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* private mode */ }
}

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function refreshState() {
  const st = await getJSON('/api/state');
  S.notes = st.notes;
  S.verdicts = st.verdicts;
}

function saveState(text, bad = false) {
  const el = $('#save-state');
  el.textContent = text;
  el.classList.toggle('bad', bad);
}

// Every change is one event; the server appends it to data/notes.jsonl. If the
// server is unreachable the event waits in localStorage and is retried, so a
// restart of the server never loses a note.
async function post(ev) {
  const q = [...queued(), ev];
  setQueued(q);
  await flush();
}

async function flush() {
  let q = queued();
  while (q.length) {
    try {
      const r = await fetch('/api/events', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(q[0]),
      });
      if (r.status === 400) {
        const err = await r.json().catch(() => ({}));
        toast(`Not saved: ${err.error || 'rejected'}`);
      } else if (!r.ok) {
        throw new Error(String(r.status));
      }
      q = q.slice(1);
      setQueued(q);
    } catch {
      saveState(`offline — ${q.length} unsaved change(s), retrying`, true);
      setTimeout(flush, 5000);
      return;
    }
  }
  saveState(`saved ${new Date().toLocaleTimeString()}`);
  await refreshState();
  render();
}

// -------------------------------------------------------------- text anchoring

function docOf() { return iframe.contentDocument; }
function winOf() { return iframe.contentWindow; }

function tabRoot(doc, name) {
  if (!name) return doc.body;
  return [...doc.querySelectorAll('pd-tab')].find((t) => t.getAttribute('name') === name) || null;
}

function tabNameOf(node) {
  const el = node.nodeType === 1 ? node : node.parentElement;
  const tab = el && el.closest('pd-tab');
  return tab ? tab.getAttribute('name') || '' : '';
}

// Offsets are measured with Range.toString(), which concatenates exactly the
// Text nodes a TreeWalker visits — so offsets and the index always agree.
function offsetIn(root, container, offset) {
  const r = root.ownerDocument.createRange();
  r.setStart(root, 0);
  r.setEnd(container, offset);
  return r.toString().length;
}

function textIndex(root) {
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let text = '';
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    nodes.push({ n, start: text.length });
    text += n.data;
  }
  return { text, nodes };
}

function pointAt(index, pos) {
  // Last node starting at or before pos.
  let lo = 0, hi = index.nodes.length - 1, best = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (index.nodes[mid].start <= pos) { best = mid; lo = mid + 1; } else hi = mid - 1;
  }
  const { n, start } = index.nodes[best];
  return [n, Math.min(pos - start, n.data.length)];
}

function commonSuffix(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[a.length - 1 - i] === b[b.length - 1 - i]) i++;
  return i;
}
function commonPrefix(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}

function anchor(doc, note) {
  const root = tabRoot(doc, note.tab);
  if (!root) return null;
  const index = textIndex(root);
  let best = -1, bestScore = -1;
  for (let at = index.text.indexOf(note.quote); at !== -1; at = index.text.indexOf(note.quote, at + 1)) {
    const before = index.text.slice(Math.max(0, at - note.prefix.length), at);
    const after = index.text.slice(at + note.quote.length, at + note.quote.length + note.suffix.length);
    const score = commonSuffix(before, note.prefix) + commonPrefix(after, note.suffix);
    if (score > bestScore) { best = at; bestScore = score; }
  }
  if (best < 0) return null;
  const range = doc.createRange();
  range.setStart(...pointAt(index, best));
  range.setEnd(...pointAt(index, best + note.quote.length));
  return range;
}

// The selection as a note anchor, with surrounding whitespace trimmed off (a
// drag rarely starts exactly on a word); `range` is the trimmed span.
function describeSelection(doc, range) {
  const tab = tabNameOf(range.commonAncestorContainer);
  const root = tabRoot(doc, tab) || doc.body;
  const index = textIndex(root);
  const raw = range.toString();
  const lead = raw.length - raw.trimStart().length;
  const quote = raw.trim();
  const s = offsetIn(root, range.startContainer, range.startOffset) + lead;
  const e = s + quote.length;
  const trimmed = doc.createRange();
  trimmed.setStart(...pointAt(index, s));
  trimmed.setEnd(...pointAt(index, e));
  return {
    tab,
    quote,
    prefix: index.text.slice(Math.max(0, s - 40), s),
    suffix: index.text.slice(e, e + 40),
    range: trimmed,
  };
}

// ------------------------------------------------------------------ highlights

function setHighlight(name, ranges) {
  const win = winOf();
  if (!win || !win.CSS || !win.CSS.highlights) return;
  if (!ranges.length) { win.CSS.highlights.delete(name); return; }
  win.CSS.highlights.set(name, new win.Highlight(...ranges));
}

const DOC_STYLE = `
/* The page scrolls, not the plan: the frame is resized to fit (fitFrame). */
html { overflow: hidden !important; }
::highlight(pr-note) { background-color: rgba(245, 197, 24, .42); }
::highlight(pr-pending) { background-color: rgba(47, 95, 208, .30); }
::highlight(pr-hover) { background-color: rgba(234, 108, 22, .50); }
/* Queued pd comments would never reach anyone here: notes go to the review log. */
.pd-exportbar, .pd-composer, .pd-section-head .pd-btn { display: none !important; }
`;

function planNotes() {
  const pid = S.plans[S.idx]?.plan_id;
  return S.notes.filter((n) => n.plan_id === pid);
}

function reanchor() {
  const doc = docOf();
  S.ranges.clear();
  if (!doc || !doc.body) return;
  for (const n of planNotes()) {
    const r = anchor(doc, n);
    if (r) S.ranges.set(n.id, r);
  }
  setHighlight('pr-note', [...S.ranges.values()]);
}

function visible(range) {
  return range.getClientRects().length > 0;
}

// -------------------------------------------------------------------- margin

function fitFrame() {
  const doc = docOf();
  if (!doc || !doc.documentElement) return;
  const h = doc.documentElement.scrollHeight;
  // The iframe is border-box: its border comes out of the height we set.
  const border = iframe.offsetHeight - iframe.clientHeight;
  if (Math.abs(iframe.clientHeight - h) > 1) iframe.style.height = `${h + border}px`;
  margin.style.height = `${h}px`;
}

function switchTab(name) {
  const doc = docOf();
  const btn = [...doc.querySelectorAll('.pd-tabbtn')].find((b) => b.dataset.name === name);
  if (btn) btn.click();
  requestAnimationFrame(layout);
}

function hot(id, on) {
  const el = margin.querySelector(`.mnote[data-id="${id}"]`);
  if (el) el.classList.toggle('hot', on);
  const r = S.ranges.get(id);
  setHighlight('pr-hover', on && r ? [r] : []);
}

function layout() {
  fitFrame();
  for (const el of margin.querySelectorAll('.mnote')) el.remove();
  const notes = planNotes();
  const frameTop = iframe.getBoundingClientRect().top;
  const marginTop = margin.getBoundingClientRect().top;
  const placed = [];
  const elsewhere = new Map();
  const lost = [];
  for (const n of notes) {
    const r = S.ranges.get(n.id);
    if (!r) { lost.push(n); continue; }
    if (!visible(r)) { elsewhere.set(n.tab, (elsewhere.get(n.tab) || 0) + 1); continue; }
    // Both rects are viewport-relative, so their difference is scroll-free.
    placed.push({ n, y: r.getBoundingClientRect().top + frameTop - marginTop });
  }
  placed.sort((a, b) => a.y - b.y);
  let floor = offtab.offsetHeight ? offtab.offsetHeight + 8 : 0;
  for (const { n, y } of placed) {
    const el = noteEl(n);
    margin.append(el);
    const top = Math.max(y, floor);
    el.style.top = `${top}px`;
    floor = top + el.offsetHeight + 8;
  }

  offtab.innerHTML = '';
  if (elsewhere.size) {
    offtab.append(document.createTextNode('Notes on other tabs: '));
    for (const [tab, count] of elsewhere) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = `${tab || '(no tab)'} · ${count}`;
      b.onclick = () => switchTab(tab);
      offtab.append(b);
    }
  }
  if (lost.length) {
    const d = document.createElement('div');
    d.textContent = `${lost.length} note(s) could not be re-anchored: `
      + lost.map((n) => `“${n.quote.slice(0, 40)}” — ${n.text.slice(0, 60)}`).join(' · ');
    offtab.append(d);
  }
}

function noteEl(n) {
  const el = document.createElement('div');
  el.className = 'mnote';
  el.dataset.id = n.id;
  el.tabIndex = 0;
  const q = document.createElement('div');
  q.className = 'q';
  q.textContent = `“${n.quote}”`;
  const t = document.createElement('div');
  t.className = 't';
  t.textContent = n.text;
  const acts = document.createElement('div');
  acts.className = 'acts';
  const edit = button('Edit', () => editNote(el, n));
  const del = button('Delete', () => {
    if (confirm('Delete this note? (It stays in the event log as deleted.)')) post({ event: 'note.delete', id: n.id });
  });
  acts.append(edit, del);
  el.append(q, t, acts);
  el.addEventListener('mouseenter', () => hot(n.id, true));
  el.addEventListener('mouseleave', () => hot(n.id, false));
  return el;
}

function editNote(el, n) {
  const t = el.querySelector('.t');
  const ta = document.createElement('textarea');
  ta.rows = 3;
  ta.value = n.text;
  t.replaceWith(ta);
  ta.focus();
  const done = (save) => {
    const text = ta.value.trim();
    if (save && text && text !== n.text) post({ event: 'note.update', id: n.id, text });
    else layout();
  };
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); done(true); }
    if (e.key === 'Escape') { e.preventDefault(); done(false); }
  });
  ta.addEventListener('blur', () => done(true));
}

function button(label, onclick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = label;
  b.onclick = onclick;
  return b;
}

// ------------------------------------------------------------------ popover

function openPopover(range) {
  const doc = docOf();
  const d = describeSelection(doc, range);
  if (d.quote.length < 2) return;
  if (d.quote.length > 4000) { toast('Selection too long for a span note — use the plan-level note.'); return; }
  S.pending = d;
  setHighlight('pr-pending', [d.range]);
  winOf().getSelection().removeAllRanges();

  const rr = d.range.getBoundingClientRect();
  const fr = iframe.getBoundingClientRect();
  const width = Math.min(340, window.innerWidth - 32);
  const left = Math.max(16, Math.min(fr.left + rr.left, window.innerWidth - width - 16));
  popover.style.left = `${left + window.scrollX}px`;
  popover.style.top = `${fr.top + rr.bottom + window.scrollY + 6}px`;
  popover.querySelector('.quote').textContent = d.quote;
  const ta = popover.querySelector('textarea');
  ta.value = '';
  popover.hidden = false;
  ta.focus();
}

function closePopover() {
  popover.hidden = true;
  S.pending = null;
  setHighlight('pr-pending', []);
}

popover.querySelector('textarea').addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { e.preventDefault(); closePopover(); return; }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const text = e.target.value.trim();
    const p = S.pending;
    if (!text || !p) return;
    post({
      event: 'note.create', plan_id: S.plans[S.idx].plan_id,
      tab: p.tab, quote: p.quote, prefix: p.prefix, suffix: p.suffix, text,
    });
    closePopover();
  }
});
document.addEventListener('mousedown', (e) => {
  if (!popover.hidden && !popover.contains(e.target)) closePopover();
});

// ------------------------------------------------------------ doc wiring

function noteAtPoint(doc, x, y) {
  const pos = doc.caretPositionFromPoint
    ? doc.caretPositionFromPoint(x, y)
    : doc.caretRangeFromPoint && doc.caretRangeFromPoint(x, y);
  if (!pos) return null;
  const node = pos.offsetNode || pos.startContainer;
  const off = pos.offset ?? pos.startOffset;
  for (const [id, r] of S.ranges) {
    try { if (r.isPointInRange(node, off)) return id; } catch { /* other tree */ }
  }
  return null;
}

function wireDoc() {
  const doc = docOf();
  const style = doc.createElement('style');
  style.textContent = DOC_STYLE;
  doc.head.append(style);

  let hovered = null;
  doc.addEventListener('mousemove', (e) => {
    const id = noteAtPoint(doc, e.clientX, e.clientY);
    if (id === hovered) return;
    if (hovered) hot(hovered, false);
    hovered = id;
    if (id) hot(id, true);
  });
  doc.addEventListener('mouseup', () => {
    const sel = winOf().getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return;
    const range = sel.getRangeAt(0).cloneRange();
    // Let a click on an existing highlight land first.
    setTimeout(() => openPopover(range), 0);
  });
  doc.addEventListener('mousedown', () => { if (!popover.hidden) closePopover(); });
  // Tab switches and <details> toggles move text; re-place notes afterwards.
  doc.addEventListener('click', () => requestAnimationFrame(layout));
  doc.addEventListener('toggle', () => requestAnimationFrame(layout), true);
  doc.addEventListener('keydown', onKey);
  new ResizeObserver(() => layout()).observe(doc.body);
  winOf().addEventListener('hashchange', () => requestAnimationFrame(layout));
}

iframe.addEventListener('load', () => {
  if (!docOf() || !docOf().body) return;
  wireDoc();
  // pd-components render after DOMContentLoaded and mermaid later still; anchor
  // now, and again once late rendering has settled.
  reanchor();
  layout();
  setTimeout(() => { reanchor(); layout(); }, 600);
  setTimeout(() => { reanchor(); layout(); }, 2000);
});

// ------------------------------------------------------------------ rendering

async function openPlan(i, focusNote = null) {
  if (i < 0 || i >= S.plans.length) return;
  closePopover();
  S.idx = i;
  const p = S.plans[i];
  history.replaceState(null, '', `#p=${p.plan_id}`);
  $('#jump').value = p.plan_id;
  S.detail = await getJSON(`/api/plans/${p.plan_id}`);
  $('#fixture').textContent = `#${p.n} · ${S.detail.fixture_id || ''} · ${p.plan_id}`;
  $('#prompt').textContent = S.detail.prompt;
  const tl = $('#transcript-link');
  tl.hidden = !S.detail.has_transcript;
  tl.href = `/plan/${p.plan_id}/transcript.txt`;
  const cb = $('#context-box');
  cb.hidden = !S.detail.has_context;
  cb.open = false;
  $('#context').textContent = '';
  if (S.detail.has_context) {
    fetch(`/plan/${p.plan_id}/context.md`).then((r) => r.text()).then((t) => { $('#context').textContent = t; });
  }
  renderVerdict();
  S.ranges.clear();
  iframe.style.height = '';
  iframe.src = `/plan/${p.plan_id}/plan.html`;
  if (focusNote) {
    iframe.addEventListener('load', () => setTimeout(() => focusOn(focusNote), 700), { once: true });
  }
  window.scrollTo(0, 0);
}

function focusOn(id) {
  const n = S.notes.find((x) => x.id === id);
  if (!n) return;
  const r = S.ranges.get(id);
  if (r && !visible(r)) switchTab(n.tab);
  requestAnimationFrame(() => {
    const rr = S.ranges.get(id);
    if (!rr) return;
    const y = rr.getBoundingClientRect().top + iframe.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: Math.max(0, y - 200), behavior: 'smooth' });
    hot(id, true);
    setTimeout(() => hot(id, false), 1600);
  });
}

function renderVerdict() {
  const pid = S.plans[S.idx]?.plan_id;
  const v = S.verdicts[pid];
  for (const b of document.querySelectorAll('[data-verdict]')) b.classList.toggle('on', v?.verdict === b.dataset.verdict);
  const ta = $('#verdict-text');
  if (document.activeElement !== ta) ta.value = v ? v.text : '';
}

function setVerdict(verdict) {
  const pid = S.plans[S.idx]?.plan_id;
  if (!pid) return;
  post({ event: 'verdict', plan_id: pid, verdict, text: $('#verdict-text').value.trim() });
}

$('#verdict-text').addEventListener('change', (e) => {
  const pid = S.plans[S.idx]?.plan_id;
  const v = S.verdicts[pid];
  const text = e.target.value.trim();
  if (v && text !== v.text) post({ event: 'verdict', plan_id: pid, verdict: v.verdict, text });
  // No verdict yet: the text is saved with the verdict, whenever it is chosen.
  else if (!v && text) saveState('plan-level note unsaved — pick Pass, Fail or Defer', true);
});
for (const b of document.querySelectorAll('[data-verdict]')) b.onclick = () => setVerdict(b.dataset.verdict);

function renderJump() {
  const sel = $('#jump');
  const cur = S.plans[S.idx]?.plan_id;
  sel.innerHTML = '';
  for (const p of S.plans) {
    const o = document.createElement('option');
    o.value = p.plan_id;
    const v = S.verdicts[p.plan_id]?.verdict;
    o.textContent = `${v ? { pass: '✓', fail: '✗', defer: '…' }[v] : '○'} #${p.n} ${p.fixture_id || p.plan_id}`;
    sel.append(o);
  }
  if (cur) sel.value = cur;
}

function render() {
  renderJump();
  renderVerdict();
  reanchor();
  layout();
  if (S.view === 'progress') renderProgress();
}

// ------------------------------------------------------------------ progress

async function renderProgress() {
  const log = await getJSON('/api/log').catch(() => []);
  const byPlan = new Map();
  for (const n of S.notes) {
    if (!byPlan.has(n.plan_id)) byPlan.set(n.plan_id, []);
    byPlan.get(n.plan_id).push(n);
  }
  const counts = { pass: 0, fail: 0, defer: 0 };
  for (const v of Object.values(S.verdicts)) counts[v.verdict] = (counts[v.verdict] || 0) + 1;
  const reviewed = S.plans.filter((p) => S.verdicts[p.plan_id]).length;

  const root = $('#progress');
  root.innerHTML = '';
  const stats = el('div', 'stats');
  for (const [k, v] of [['plans reviewed', `${reviewed} / ${S.plans.length}`], ['pass', counts.pass],
    ['fail', counts.fail], ['defer', counts.defer], ['span notes', S.notes.length]]) {
    const s = el('div', 'stat');
    s.append(el('b', '', String(v)), el('span', '', k));
    stats.append(s);
  }
  root.append(stats);

  root.append(el('h2', '', 'New themes per reviewed plan'));
  if (!log.length) {
    root.append(el('p', 'empty', 'The agent logs how many new themes each reviewed plan surfaced (data/open-coding-log.jsonl). When recent plans stop adding new ones, open coding has saturated.'));
  } else {
    const max = Math.max(1, ...log.map((e) => (e.new_codes || []).length));
    for (const e of log) {
      const row = el('div', 'sat-row');
      const p = S.plans.find((x) => x.plan_id === e.plan_id);
      const bar = el('div', 'sat-bar');
      bar.style.width = `${((e.new_codes || []).length / max) * 100}%`;
      bar.title = (e.new_codes || []).join('\n');
      row.append(el('span', '', p ? `#${p.n} ${e.plan_id.slice(0, 6)}` : e.plan_id.slice(0, 8)), bar,
        el('span', 'muted', `+${(e.new_codes || []).length} new · ${(e.repeat_codes || []).length} repeat`));
      root.append(row);
    }
  }

  root.append(el('h2', '', 'Plans'));
  const table = el('table');
  table.innerHTML = '<thead><tr><th>#</th><th>fixture</th><th>verdict</th><th>notes</th><th>plan-level note</th></tr></thead>';
  const tb = el('tbody');
  for (const p of S.plans) {
    const v = S.verdicts[p.plan_id];
    const tr = el('tr', 'link');
    const chip = v ? el('span', `chip ${v.verdict}`, v.verdict) : el('span', 'muted', '—');
    const cells = [String(p.n), p.fixture_id || p.plan_id, chip, String((byPlan.get(p.plan_id) || []).length), v?.text || ''];
    for (const c of cells) {
      const td = el('td');
      td.append(typeof c === 'string' ? document.createTextNode(c) : c);
      tr.append(td);
    }
    tr.onclick = () => { showView('review'); openPlan(S.plans.indexOf(p)); };
    tb.append(tr);
  }
  table.append(tb);
  root.append(table);

  root.append(el('h2', '', 'All span notes'));
  if (!S.notes.length) root.append(el('p', 'empty', 'No notes yet.'));
  for (const p of S.plans) {
    const ns = byPlan.get(p.plan_id);
    if (!ns) continue;
    root.append(el('div', 'label', `#${p.n} ${p.fixture_id || p.plan_id}`));
    const ul = el('ul', 'nlist');
    for (const n of ns) {
      const li = el('li');
      li.append(el('div', 'q', `“${n.quote.slice(0, 160)}”${n.tab ? ` — ${n.tab}` : ''}`), el('div', 't', n.text));
      li.onclick = () => { showView('review'); openPlan(S.plans.indexOf(p), n.id); };
      ul.append(li);
    }
    root.append(ul);
  }
}

function el(tag, cls = '', text = null) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== null) e.textContent = text;
  return e;
}

function showView(v) {
  S.view = v;
  $('#review-view').hidden = v !== 'review';
  $('#progress-view').hidden = v !== 'progress';
  for (const b of document.querySelectorAll('[data-view]')) b.classList.toggle('on', b.dataset.view === v);
  if (v === 'progress') renderProgress();
  else requestAnimationFrame(layout);
}
for (const b of document.querySelectorAll('[data-view]')) b.onclick = () => showView(b.dataset.view);

// ------------------------------------------------------------------ keys, misc

function editing(e) {
  const t = e.target;
  return t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.isContentEditable);
}

function onKey(e) {
  if (editing(e) || e.metaKey || e.ctrlKey || e.altKey) return;
  if (S.view !== 'review') return;
  const k = e.key;
  if (k === 'ArrowLeft') { e.preventDefault(); openPlan(S.idx - 1); }
  else if (k === 'ArrowRight') { e.preventDefault(); openPlan(S.idx + 1); }
  else if (k === '1') setVerdict('pass');
  else if (k === '2') setVerdict('fail');
  else if (k === 'd') setVerdict('defer');
  else if (k === 'n') { e.preventDefault(); $('#verdict-text').focus(); }
}
document.addEventListener('keydown', onKey);
$('#prev').onclick = () => openPlan(S.idx - 1);
$('#next').onclick = () => openPlan(S.idx + 1);
$('#jump').onchange = (e) => openPlan(S.plans.findIndex((p) => p.plan_id === e.target.value));
window.addEventListener('resize', () => layout());

let toastTimer = null;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}

// New plans can be ingested while the app is open (generate runs in the
// background); pick them up without a reload.
async function pollPlans() {
  try {
    const plans = await getJSON('/api/plans');
    if (plans.length !== S.plans.length) {
      const cur = S.plans[S.idx]?.plan_id;
      const added = plans.length - S.plans.length;
      S.plans = plans;
      S.idx = Math.max(0, plans.findIndex((p) => p.plan_id === cur));
      renderJump();
      if (added > 0) toast(`${added} new plan(s) in the corpus`);
    }
  } catch { /* server restarting */ }
}

async function main() {
  if (!('highlights' in CSS)) toast('This browser lacks the CSS Custom Highlight API — highlights will not show.');
  S.plans = await getJSON('/api/plans');
  await refreshState();
  renderJump();
  if (!S.plans.length) {
    $('#prompt').textContent = 'The corpus is empty. Run `make plan-review ARGS=generate` (or `ingest`) and reload.';
    return;
  }
  const want = (location.hash.match(/p=([0-9a-f]{12})/) || [])[1];
  let i = S.plans.findIndex((p) => p.plan_id === want);
  if (i < 0) i = S.plans.findIndex((p) => !S.verdicts[p.plan_id]);
  await openPlan(i < 0 ? 0 : i);
  if (queued().length) flush();
  setInterval(pollPlans, 15000);
}

main();
