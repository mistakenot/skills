// pd-doc: document shell — header, optional tabs, floating export bar, footer.
// pd-tab: a named page inside pd-doc.
// pd-section: titled section with a stable id and a "+ comment" affordance.

import { PdElement, define, el, openThreadCount } from './util.js';
import { store, copyText } from './store.js';
import { attachComposer } from './threads.js';

class PdDoc extends PdElement {
  init() {
    const title = this.getAttribute('title') || document.title;
    const status = this.getAttribute('status');

    const header = el('header', { class: 'pd-doc-header' }, [
      el('h1', {}, title),
      status ? el('span', { class: 'pd-badge', 'data-status': status }, status) : null,
    ]);
    this.prepend(header);

    this._initPrLink(header);
    this._initTabs(header);
    this._initFooter();
    this._initExportBar(title);
  }

  _initPrLink(header) {
    const pr = this.getAttribute('pr');
    if (!pr) return;
    const bar = el('div', { class: 'pd-pr-link' });
    if (pr === 'pending') {
      bar.append(el('span', { class: 'pd-pr-pending' }, 'PR not available yet'));
    } else {
      const num = pr.match(/\/pull\/(\d+)/);
      const label = num ? `PR #${num[1]}` : 'Pull Request';
      bar.append(el('a', { href: pr, target: '_blank', rel: 'noopener', class: 'pd-pr-badge' }, label));
    }
    header.after(bar);
  }

  _initTabs(header) {
    const tabs = [...this.querySelectorAll(':scope > pd-tab')];
    if (!tabs.length) return;

    const nav = el('nav', { class: 'pd-tabnav', role: 'tablist' });
    tabs.forEach((tab, i) => {
      const name = tab.getAttribute('name') || `Tab ${i + 1}`;
      const open = openThreadCount(tab);
      const btn = el('button', {
        class: 'pd-tabbtn',
        role: 'tab',
        onclick: () => this._select(name),
      }, [name, open ? el('span', { class: 'pd-tabbadge', title: `${open} open thread(s)` }, String(open)) : null]);
      btn.dataset.name = name;
      nav.append(btn);
    });
    const insertAfter = this.querySelector('.pd-pr-link') || header;
    insertAfter.after(nav);
    this._tabs = tabs;
    this._nav = nav;

    // Deep links: #tab:Name selects a tab; #some-id selects the tab containing it.
    const fromHash = () => {
      const h = decodeURIComponent(location.hash.slice(1));
      if (h.startsWith('tab:')) return this._select(h.slice(4));
      const target = h && document.getElementById(h);
      const owner = target && target.closest('pd-tab');
      if (owner) {
        this._select(owner.getAttribute('name'));
        target.scrollIntoView();
      }
    };
    window.addEventListener('hashchange', fromHash);
    this._select(tabs[0].getAttribute('name'));
    fromHash();
  }

  _select(name) {
    this._tabs.forEach((t) => { t.style.display = t.getAttribute('name') === name ? '' : 'none'; });
    this._nav.querySelectorAll('.pd-tabbtn').forEach((b) => {
      b.setAttribute('aria-selected', b.dataset.name === name ? 'true' : 'false');
    });
    if (!location.hash.startsWith('#tab:') || decodeURIComponent(location.hash.slice(5)) !== name) {
      history.replaceState(null, '', `#tab:${encodeURIComponent(name)}`);
    }
  }

  _initFooter() {
    const generated = this.getAttribute('generated');
    const lib = `pd-components ${__PD_VERSION__}`;
    this.append(el('footer', { class: 'pd-doc-footer' },
      [generated ? `Generated ${generated} · ` : '', lib]));
  }

  _initExportBar(title) {
    const bar = el('div', { class: 'pd-exportbar', hidden: true });
    const label = el('span');
    const copyBtn = el('button', {
      class: 'pd-btn pd-btn-primary',
      onclick: async () => {
        const ok = await copyText(store.serialize(title));
        copyBtn.textContent = ok ? 'Copied ✓' : 'Select & copy above';
        setTimeout(() => { copyBtn.textContent = 'Copy for agent'; }, 2000);
      },
    }, 'Copy for agent');
    const clearBtn = el('button', {
      class: 'pd-btn',
      onclick: () => { if (confirm('Discard all pending comments?')) store.clear(); },
    }, 'Clear');
    bar.append(label, copyBtn, clearBtn);
    document.body.append(bar);

    const refresh = () => {
      const n = store.count();
      bar.hidden = n === 0;
      label.textContent = `${n} pending comment${n === 1 ? '' : 's'}`;
    };
    window.addEventListener('pd:pending-changed', refresh);
    refresh();
  }
}

class PdTab extends PdElement {}

class PdSection extends PdElement {
  init() {
    const title = this.getAttribute('title');
    if (!title) return;
    const id = this.id || title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    this.id = id;
    const heading = el('div', { class: 'pd-section-head' }, [
      el('h2', {}, [title, ' ', el('a', { class: 'pd-anchor', href: `#${id}`, title: 'Link to section' }, '#')]),
      el('button', {
        class: 'pd-btn pd-btn-ghost',
        title: 'Queue a comment on this section',
        onclick: (e) => attachComposer(this, { kind: 'new', thread: title, anchor: id }, e.target),
      }, '+ comment'),
    ]);
    this.prepend(heading);
  }
}

define('pd-doc', PdDoc);
define('pd-tab', PdTab);
define('pd-section', PdSection);
