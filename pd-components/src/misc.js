// pd-ac: acceptance-criteria card with traceability chips.
//   <pd-ac id="AC-1" title="Rate limit applies" phases="1,2" tests="e2e/rate.spec.ts">
//     <ul><li>Given… </li><li>When… </li><li>Then… </li></ul>
//   </pd-ac>
//
// pd-collapse: ad-hoc progressive-disclosure wrapper. Collapsed by default
// (add `open` to expand); the summary line is the scan layer, the body stays in
// the DOM for agents. Use for long code, tables, or secondary rationale that
// isn't a whole section.
//   <pd-collapse summary="Rationale"> <md>…</md> </pd-collapse>
//
// pd-wire: wireframe placeholder box. pd-note: annotation callout.
// Wireframe sections are otherwise freeform HTML (Tailwind welcome).
//
// pd-contract: document-level completion banner. Scans every pd-ac that carries
// checks, rolls their statuses up the SAME pure way each card does, and renders
// an "n/m ACs proved" banner with a status pill. Check-free ACs do not
// participate. Renders only; verifies nothing.
//   <pd-contract></pd-contract>

import { PdElement, define, el, filesForPhases } from './util.js';
import { parseAcCheck, checkType, AC_CHECK_TYPES } from './ac-check-core.js';
import { rollupAc, rollupContract } from './verify-core.js';

// --- shared status vocabulary (render side) -------------------------------
// Map a rolled-up status to the chip colour-class suffix used by .pd-ac-pill.
// Reuses the existing --pd-ok|warn|bad|neutral variables (no new colour vars):
//   proved → ok (green) · contradicted → bad (red) ·
//   weak & missing → warn (amber) · pending (and anything unknown) → neutral.
const STATUS_CLASS = {
  proved: 'pd-pill-ok',
  contradicted: 'pd-pill-bad',
  weak: 'pd-pill-warn',
  missing: 'pd-pill-warn',
  pending: 'pd-pill-neutral',
};
const statusClass = (s) => STATUS_CLASS[s] || 'pd-pill-neutral';

// Per-check status glyph shown at the start of each rendered check row.
const STATUS_GLYPH = {
  proved: '✓',
  contradicted: '✗',
  weak: '–',
  missing: '–',
  pending: '⏳',
};
const statusGlyph = (s) => STATUS_GLYPH[s] || '⏳';

// Render registry: one entry per check type. `label` is a fixed type label and
// `attr` is the single key attribute surfaced in the row (e.g. test → `name`).
// Adding a new check type is a one-line entry here.
const CHECK_RENDER = {
  command: { label: 'command', attr: 'run' },
  output: { label: 'output', attr: 'run' },
  test: { label: 'test', attr: 'name' },
  'file-exists': { label: 'file-exists', attr: 'path' },
  'file-contains': { label: 'file-contains', attr: 'path' },
};

// Coordinator decision (T4): the evidence child element is <pd-ac-evidence> — a
// light-DOM direct child of a pd-ac-check-*, whose text content is the captured
// evidence. parseAcCheck() returns evidence:null in T1 (it does not read it), so
// the renderer reads this element from the DOM directly. Phase 3's fixture
// authors <pd-ac-evidence>…</pd-ac-evidence>. Schema owner: see this tag.
const evidenceOf = (check) => check.querySelector(':scope > pd-ac-evidence');

// Direct pd-ac-check-* children of an element, paired with their parsed check.
// Used by PdAc.init() itself, which runs BEFORE relocation (checks are still
// direct children at that point).
function checkChildren(root) {
  return [...root.children]
    .filter((c) => checkType(c))
    .map((c) => ({ el: c, parsed: parseAcCheck(c) }));
}

// Tag selector over the five schema-defined check types (schema-driven, not
// hardcoded). A pd-ac never nests another pd-ac, so a descendant query scoped to
// one AC matches exactly that AC's own checks.
const CHECK_SELECTOR = AC_CHECK_TYPES.map((t) => `pd-ac-check-${t}`).join(',');

// All check nodes under an AC, robust to relocation (descendant query): finds
// them whether still direct children (pre-init) or moved into .pd-ac-body
// (post-init). This decouples the contract from pd-ac init order (AC-9).
function checksUnder(ac) {
  return [...ac.querySelectorAll(CHECK_SELECTOR)];
}

// A check-free AC contributes no status to the document contract; only ACs that
// carry checks participate. Returns null for a check-free AC, else its rolled-up
// status (the SAME pure derivation the card uses). Order-independent: uses a
// descendant query so an already-initialised (relocated) AC is still counted.
function acStatusForContract(ac) {
  const checks = checksUnder(ac);
  if (!checks.length) return null;
  return rollupAc(checks.map((c) => parseAcCheck(c).status)).status;
}

// Human single-line provenance stamp from parsed.provenance ({commit,dirty,at}).
// Display only — never validated against git. Returns '' when none present.
function provenanceLine(prov) {
  if (!prov) return '';
  const parts = [];
  if (prov.commit) parts.push(`verified at ${prov.commit}`);
  if (prov.dirty != null && prov.dirty !== '' && prov.dirty !== '0') parts.push(`${prov.dirty} files dirty`);
  if (prov.at) parts.push(prov.at);
  return parts.join(', ');
}

class PdAc extends PdElement {
  init() {
    const id = this.getAttribute('id') || 'AC';
    const phases = (this.getAttribute('phases') || '').split(',').map((s) => s.trim()).filter(Boolean);
    const checks = checkChildren(this);

    // Build the shared head (id chip + title + phase/test chips). The phase chips
    // are kept addressable so the with-checks path can scope the click to them.
    const chips = el('div', { class: 'pd-ac-chips' });
    const phaseChips = phases.map((p) => {
      const chip = el('span', { class: 'pd-chip' }, `phase ${p}`);
      chips.append(chip);
      return chip;
    });
    (this.getAttribute('tests') || '').split(',').map((s) => s.trim()).filter(Boolean)
      .forEach((t) => chips.append(el('span', { class: 'pd-chip pd-chip-test' }, t)));

    const headChildren = [
      el('span', { class: 'pd-chip pd-chip-id' }, id),
      el('strong', {}, this.getAttribute('title') || ''),
      chips,
    ];

    // The pd:phase-selected listener that lights this card when its phases are
    // selected is shared by both paths (AC-7: keep the existing listener).
    window.addEventListener('pd:phase-selected', (e) => {
      const sel = new Set((e.detail?.phases || []).map(String));
      const on = e.detail?.ac === id || (sel.size > 0 && phases.some((p) => sel.has(p)));
      this.classList.toggle('pd-ac-hl', on);
    });

    if (!checks.length) {
      // No checks → keep TODAY'S EXACT behaviour (G1 / AC-8). Already-authored
      // docs render unchanged: head prepended, whole-card click dispatch, body
      // visible, no pill, no disclosure.
      this.prepend(el('div', { class: 'pd-ac-head' }, headChildren));
      if (phases.length) {
        this.classList.add('pd-ac-link');
        this.addEventListener('click', (e) => {
          if (e.target.closest('a, button')) return;
          window.dispatchEvent(new CustomEvent('pd:phase-selected', {
            detail: { phases, files: filesForPhases(phases), source: this, ac: id },
          }));
        });
      }
      return;
    }

    // --- with-checks render path ------------------------------------------
    // 1. Roll the authored check statuses up to one AC status.
    const roll = rollupAc(checks.map((c) => c.parsed.status));

    // 2. Head gains a status pill + an "n/m checks passing" count.
    const pill = el('span', { class: `pd-ac-pill ${statusClass(roll.status)}` }, roll.status);
    const count = el('span', { class: 'pd-ac-count' }, `${roll.passing}/${roll.total} checks passing`);
    const head = el('summary', { class: 'pd-ac-head' }, [...headChildren, pill, count]);

    // Click split (AC-7): clicking a phase chip highlights the traceability
    // without toggling the disclosure (stopPropagation); the summary toggles the
    // <details> natively. Whole-card click is NOT wired in this path.
    if (phases.length) {
      phaseChips.forEach((chip) => {
        chip.classList.add('pd-ac-chip-link');
        chip.addEventListener('click', (e) => {
          e.stopPropagation();
          e.preventDefault();
          window.dispatchEvent(new CustomEvent('pd:phase-selected', {
            detail: { phases, files: filesForPhases(phases), source: this, ac: id },
          }));
        });
      });
    }

    // 3. Disclosure: summary = head; body holds the RELOCATED existing children
    //    (GWT body + the raw, hidden pd-ac-check-* nodes — relocation ≠ removal,
    //    D3/AC-6) followed by the rendered check rows.
    const body = el('div', { class: 'pd-ac-body' });
    while (this.firstChild) body.append(this.firstChild);

    const list = el('div', { class: 'pd-ac-checks' });
    checks.forEach(({ el: checkEl, parsed }) => list.append(this.renderCheckRow(checkEl, parsed)));
    body.append(list);

    // 6. Auto-open on failure (AC-5): contradicted rollup OR explicit `open`.
    const open = roll.status === 'contradicted' || this.hasAttribute('open');
    const details = el('details', { class: 'pd-ac-disclosure', open });
    details.append(head, body);
    this.append(details);
  }

  // One rendered row per check: status glyph + "type · key-attr" label, plus an
  // optional nested evidence disclosure (pd-collapse shape) with a provenance
  // stamp when the check carries a <pd-ac-evidence> child.
  renderCheckRow(checkEl, parsed) {
    const reg = CHECK_RENDER[parsed.type] || { label: parsed.type || 'check', attr: null };
    const status = rollupAc([parsed.status]).status; // normalise null → pending
    const keyVal = reg.attr ? parsed[reg.attr] : null;
    const label = keyVal ? `${reg.label} · ${keyVal}` : reg.label;

    const row = el('div', { class: 'pd-ac-check-row', 'data-status': status }, [
      el('span', { class: 'pd-ac-check-glyph' }, statusGlyph(status)),
      el('span', { class: 'pd-ac-check-label' }, label),
    ]);

    const evidence = evidenceOf(checkEl);
    if (evidence) {
      const evBody = el('div', { class: 'pd-collapse-body' });
      evBody.append(el('pre', { class: 'pd-ac-evidence-text' }, evidence.textContent || ''));
      const prov = provenanceLine(parsed.provenance);
      if (prov) evBody.append(el('div', { class: 'pd-ac-provenance' }, prov));
      const evDetails = el('details', { class: 'pd-collapse' });
      evDetails.append(el('summary', { class: 'pd-collapse-summary' }, 'Evidence'), evBody);
      row.append(evDetails);
    }
    return row;
  }
}

class PdWire extends PdElement {
  init() {
    const h = this.getAttribute('h');
    if (h) this.style.minHeight = h;
    const label = this.getAttribute('label');
    if (label && !this.childNodes.length) this.append(el('span', { class: 'pd-wire-label' }, label));
    else if (label) this.prepend(el('span', { class: 'pd-wire-label' }, label));
  }
}

class PdNote extends PdElement {}

class PdCollapse extends PdElement {
  init() {
    const summary = this.getAttribute('summary') || 'Details';
    const open = this.hasAttribute('open');
    const body = el('div', { class: 'pd-collapse-body' });
    while (this.firstChild) body.append(this.firstChild);
    const details = el('details', { class: 'pd-collapse', open });
    details.append(el('summary', { class: 'pd-collapse-summary' }, summary), body);
    this.append(details);
  }
}

// Document-level contract banner (AC-9). Computes independently from the DOM —
// it does NOT depend on pd-ac init order — by re-deriving each AC's status the
// SAME pure way the card does. Check-free ACs contribute no status.
class PdContract extends PdElement {
  init() {
    const acStatuses = [...document.querySelectorAll('pd-ac')]
      .map((ac) => acStatusForContract(ac))
      .filter((s) => s != null);
    const roll = rollupContract(acStatuses);
    this.append(el('div', { class: 'pd-contract' }, [
      el('span', { class: `pd-ac-pill ${statusClass(roll.status)}` }, roll.status),
      el('span', { class: 'pd-contract-count' }, `${roll.proved}/${roll.total} ACs proved`),
    ]));
  }
}

define('pd-ac', PdAc);
define('pd-wire', PdWire);
define('pd-note', PdNote);
define('pd-collapse', PdCollapse);
define('pd-contract', PdContract);
