// pd-question: a question the agent needs the HUMAN to answer before the plan
// can move forward. It runs the opposite direction to a pd-thread — there the
// human reviews the agent's work; here the agent blocks on the human. An open
// question is a gate: the headless linter reports it (code "open-question",
// non-zero exit) so an automated step won't proceed past it, and the doc's
// status bar shows "blocked" until every question is answered.
//
//   status:            open (default) | answered
//   priority:          p1 (blocking) | p2 (important) | p3 (minor) — severity / ordering
//   for:               who should answer (optional, e.g. "product", a person's name)
//   recommendedAnswer: the agent's SUGGESTED answer (optional). Surfaces what the
//                      agent would do absent a human ruling, so the human can rubber-
//                      stamp it or override. It is a suggestion, NOT an answer — it
//                      does not resolve the gate; only a <pd-answer> + status="answered"
//                      does. It pre-fills the answer box so accepting it is one click.
//
// The question prose is the element body. The human types an answer in the
// browser (pre-filled with recommendedAnswer when present); it rides the existing
// "Copy for agent" paste-back, and the agent merges it as a <pd-answer by="…">
// child and sets status="answered".
//
//   <pd-question id="Q-1" status="open" priority="p1" for="product"
//                title="Which tier do internal services use?"
//                recommendedAnswer="Separate unlimited tier; key by service id.">
//     Internal callers hit the same gateway. Do they share the public tier's
//     bucket, or get a separate unlimited tier? This changes the limiter's key.
//     <pd-answer by="charlie">Separate unlimited tier; key by service id.</pd-answer>
//   </pd-question>

import { PdElement, define, el } from './util.js';
import { store } from './store.js';
import { attachComposer } from './threads.js';

class PdQuestion extends PdElement {
  init() {
    const status = this.getAttribute('status') || 'open';
    const priority = this.getAttribute('priority') || 'p1';
    const title = this.getAttribute('title') || 'Question';
    const forWho = this.getAttribute('for');
    const recommended = this.getAttribute('recommendedAnswer');
    const anchor = this.id || '';
    const answered = status === 'answered';

    const head = el('div', { class: 'pd-question-head' }, [
      el('span', { class: 'pd-q-flag', 'data-answered': answered ? 'yes' : 'no' },
        answered ? '✔ answered' : '❓ needs your answer'),
      el('span', { class: 'pd-badge', 'data-priority': priority }, priority),
      el('strong', { class: 'pd-question-title' }, title),
      forWho ? el('span', { class: 'pd-question-for' }, `for ${forWho}`) : null,
    ]);

    // Split children: the question prose stays in the body; any authored
    // pd-answer elements move below it.
    const answers = [...this.querySelectorAll(':scope > pd-answer')];
    answers.forEach((a) => a.remove());
    const body = el('div', { class: 'pd-question-body' });
    while (this.firstChild) body.append(this.firstChild);

    // The agent's suggested answer (optional) — shown distinctly so the human
    // can rubber-stamp or override. It is NOT an answer and does not close the
    // gate; only a pd-answer + status="answered" does. Stays visible after
    // answering as the record of what was suggested.
    const rec = recommended
      ? el('div', { class: 'pd-question-rec' }, [
          el('span', { class: 'pd-question-rec-label' }, '💡 agent recommends'),
          el('span', { class: 'pd-question-rec-text' }, recommended),
        ])
      : null;

    const answerWrap = el('div', { class: 'pd-question-answers' }, answers);
    this.append(head, body, rec, answerWrap);

    if (answered) return;

    const answerBtn = el('button', {
      class: 'pd-btn pd-btn-primary',
      onclick: () => attachComposer(this, { kind: 'answer', question: title, anchor, prefill: recommended || '' }),
    }, recommended ? 'Answer (accept or edit)' : 'Answer');
    this.append(el('div', { class: 'pd-question-actions' }, [answerBtn]));

    // Re-show pending (not yet merged) answers queued for this question.
    const renderPending = () => {
      answerWrap.querySelectorAll('.pd-pending').forEach((n) => n.remove());
      store.all()
        .filter((it) => it.kind === 'answer' && it.question === title)
        .forEach((it) => answerWrap.append(el('div', { class: 'pd-pending' }, [
          el('span', { class: 'pd-pending-label' }, 'pending — copy & paste to your agent to merge'),
          el('div', {}, it.text),
        ])));
    };
    window.addEventListener('pd:pending-changed', renderPending);
    renderPending();
  }
}

class PdAnswer extends PdElement {}

define('pd-question', PdQuestion);
define('pd-answer', PdAnswer);
