// pd-thread / pd-comment: append-only review threads. The agent writes these
// into the HTML source; the browser only renders them and queues new input.
//
// Thread lifecycle mirrors the markdown planning workflow:
//   status: unresolved (default) | resolved | rejected
//   priority: p1 (blocking) | p2 (important) | p3 (minor)
//
// Resolved/rejected threads collapse to a single line — history is retained
// in the file, the rendered doc stays clean.
//
// pd-decisions: derives a decision log from every resolved/rejected thread AND
// every authored pd-decision (see decision.js) in the document, in source
// order. Zero extra authoring cost.

import { PdElement, define, el, esc } from './util.js';
import { store } from './store.js';

// Inline composer used by threads (replies) and sections/files (new threads).
export function attachComposer(host, meta, trigger) {
  const existing = host.querySelector(':scope > .pd-composer');
  if (existing) { existing.remove(); return; }

  const ta = el('textarea', {
    class: 'pd-composer-input',
    placeholder: meta.kind === 'reply' ? 'Write a reply…' : 'Write a comment…',
    rows: 3,
  });
  const queue = el('button', { class: 'pd-btn pd-btn-primary' }, 'Queue');
  const cancel = el('button', { class: 'pd-btn' }, 'Cancel');
  const box = el('div', { class: 'pd-composer' }, [ta, el('div', { class: 'pd-composer-actions' }, [queue, cancel])]);

  const submit = () => {
    const text = ta.value.trim();
    if (!text) return;
    store.add({ ...meta, text });
    box.remove();
  };
  queue.addEventListener('click', submit);
  cancel.addEventListener('click', () => box.remove());
  ta.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); }
  });

  if (trigger && trigger.closest('.pd-section-head')) trigger.closest('.pd-section-head').after(box);
  else host.append(box);
  ta.focus();
}

class PdThread extends PdElement {
  init() {
    const status = this.getAttribute('status') || 'unresolved';
    const priority = this.getAttribute('priority') || 'p2';
    const title = this.getAttribute('title') || 'Thread';
    const anchor = this.getAttribute('anchor');
    const closed = status !== 'unresolved';

    const head = el('div', { class: 'pd-thread-head', role: 'button', tabindex: '0' }, [
      el('span', { class: 'pd-badge', 'data-status': status }, status),
      el('span', { class: 'pd-badge', 'data-priority': priority }, priority),
      el('strong', {}, title),
      closed ? el('span', { class: 'pd-thread-toggle' }, 'show history') : null,
    ]);
    this.prepend(head);

    const body = el('div', { class: 'pd-thread-body' });
    [...this.querySelectorAll(':scope > pd-comment')].forEach((c) => body.append(c));
    this.append(body);

    if (closed) {
      this.toggleAttribute('data-collapsed', true);
      const toggle = () => {
        const collapsed = this.toggleAttribute('data-collapsed');
        head.querySelector('.pd-thread-toggle').textContent = collapsed ? 'show history' : 'hide history';
      };
      head.addEventListener('click', toggle);
      head.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    } else {
      const replyBtn = el('button', {
        class: 'pd-btn pd-btn-ghost',
        onclick: () => attachComposer(this, { kind: 'reply', thread: title, anchor }),
      }, 'Reply');
      this.append(el('div', { class: 'pd-thread-actions' }, [replyBtn]));
    }

    // Re-show pending (not yet merged) replies queued for this thread.
    const renderPending = () => {
      body.querySelectorAll('.pd-pending').forEach((n) => n.remove());
      store.all()
        .filter((it) => it.kind === 'reply' && it.thread === title)
        .forEach((it) => body.append(el('div', { class: 'pd-pending' }, [
          el('span', { class: 'pd-pending-label' }, 'pending — copy & paste to your agent to merge'),
          el('div', {}, it.text),
        ])));
    };
    window.addEventListener('pd:pending-changed', renderPending);
    renderPending();
  }
}

class PdComment extends PdElement {}

class PdDecisions extends PdElement {
  init() {
    // Authored decisions plus closed review threads, in document order — both
    // are entries in the same log.
    const items = [...document.querySelectorAll('pd-decision, pd-thread')]
      .filter((n) => n.tagName.toLowerCase() === 'pd-decision'
        || ['resolved', 'rejected'].includes(n.getAttribute('status')));

    this.prepend(el('div', { class: 'pd-section-head' }, [el('h2', {}, this.getAttribute('title') || 'Decisions')]));

    if (!items.length) {
      this.append(el('p', { class: 'pd-muted' }, 'No decisions recorded yet.'));
      return;
    }

    const list = el('ol', { class: 'pd-decision-list' });
    items.forEach((n, i) => {
      const isDecision = n.tagName.toLowerCase() === 'pd-decision';
      const status = n.getAttribute('status') || (isDecision ? 'accepted' : 'unresolved');
      const title = n.getAttribute('title') || (isDecision ? 'Decision' : 'Thread');
      if (!n.id) n.id = `pd-${isDecision ? 'decision' : 'thread'}-${i + 1}`;

      // Outcome line: a pd-decision's `summary` attribute, else a thread's last comment.
      let outcome = n.getAttribute('summary') || '';
      if (!outcome && !isDecision) {
        const comments = n.querySelectorAll('pd-comment');
        const last = comments[comments.length - 1];
        outcome = last ? last.textContent.trim() : '';
      }

      list.append(el('li', {}, [
        el('span', { class: 'pd-badge', 'data-status': status }, status),
        ' ',
        el('a', { href: `#${n.id}` }, title),
        outcome ? el('div', { class: 'pd-decision-outcome' }, outcome) : null,
      ]));
    });
    this.append(list);
  }
}

define('pd-thread', PdThread);
define('pd-comment', PdComment);
define('pd-decisions', PdDecisions);
