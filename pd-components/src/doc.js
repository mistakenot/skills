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
    this._initStatusBar();
    this._initFooter();
    this._initExportBar(title);
    this._initSideNav();
  }

  // Full-width banner that reflects the plan's lifecycle. The status attribute
  // declares the stage; the banner overlays derived signals — phase progress
  // when executing, and an automatic "blocked" state when unresolved p1 threads
  // exist. Recomputes on status changes and on a pd:status-refresh event.
  _initStatusBar() {
    const label = el('span', { class: 'pd-sb-label' });
    const bar = el('div', { class: 'pd-statusbar' }, [label]);
    bar.addEventListener('click', () => {
      const t = this._statusJumpTarget;
      if (!t) return;
      const tab = t.closest('pd-tab');
      if (tab && this._tabs) this._select(tab.getAttribute('name'));
      t.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    document.body.append(bar);
    document.body.classList.add('pd-has-statusbar');
    this._statusBar = bar;
    this._statusLabel = label;

    const refresh = () => this._renderStatusBar(this._computeStatus());
    new MutationObserver(refresh).observe(this, { attributes: true, attributeFilter: ['status'] });
    window.addEventListener('pd:status-refresh', refresh);
    refresh();
  }

  _computeStatus() {
    const status = (this.getAttribute('status') || 'draft').toLowerCase();
    const open = [...this.querySelectorAll('pd-thread')]
      .filter((t) => { const s = t.getAttribute('status'); return !s || s === 'unresolved'; });

    // Blocked overrides every stage while any comment thread is unresolved.
    if (open.length || status === 'blocked') {
      const n = open.length;
      return { kind: 'blocked', blockers: open, label: n ? `Blocked — ${n} open comment thread${n === 1 ? '' : 's'}` : 'Blocked' };
    }
    // Lifecycle stage: draft → pending → executing → complete.
    if (['complete', 'merged', 'shipped', 'done'].includes(status)) {
      return { kind: 'complete', label: 'Complete' };
    }
    if (status === 'executing') {
      return { kind: 'executing', label: 'Executing' };
    }
    const labels = { draft: 'Draft', pending: 'Pending', planning: 'Planning', 'in-review': 'In review', approved: 'Approved' };
    return { kind: 'stage', status, label: labels[status] || status };
  }

  _renderStatusBar(s) {
    const bar = this._statusBar;
    bar.dataset.kind = s.kind;
    if (s.status) bar.dataset.status = s.status; else delete bar.dataset.status;
    this._statusLabel.textContent = s.label;
    this._statusJumpTarget = s.kind === 'blocked' ? (s.blockers && s.blockers[0]) : null;
    bar.classList.toggle('pd-sb-clickable', !!this._statusJumpTarget);
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
    this._updateSideNav();
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
        if (ok) store.clear();
        else copyBtn.textContent = 'Select & copy above';
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

  _initSideNav() {
    // Header, PR link and the tab bar stay full-width at the top; everything
    // after the tab bar drops into a [sidenav | body] row, so the page index
    // starts level with the bottom of the tab selector (hierarchy: Tabs > Page
    // index). Falls back to the PR link / header when a doc has no tabs.
    const top = this.querySelector('.pd-tabnav')
      || this.querySelector('.pd-pr-link')
      || this.querySelector('.pd-doc-header');
    const body = el('div', { class: 'pd-doc-body' });
    let node = top ? top.nextSibling : this.firstChild;
    while (node) {
      const next = node.nextSibling;
      body.append(node);
      node = next;
    }
    const nav = el('nav', { class: 'pd-sidenav' });
    const row = el('div', { class: 'pd-doc-row' }, [nav, body]);
    this.append(row);
    this.classList.add('pd-has-sidenav');
    this._sideNav = nav;

    this._sideNavObs = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) this._highlightNavLink(e.target.id);
      }
    }, { rootMargin: '-80px 0px -60% 0px' });

    this._updateSideNav();
  }

  _updateSideNav() {
    const nav = this._sideNav;
    if (!nav) return;
    nav.innerHTML = '';
    this._sideNavObs.disconnect();

    const root = this._tabs
      ? this._tabs.find((t) => t.style.display !== 'none')
      : this;
    if (!root) return;

    for (const sec of root.querySelectorAll('pd-section[title]')) {
      if (!sec.id) continue;
      const link = el('a', {
        class: 'pd-sidenav-link',
        href: `#${sec.id}`,
        onclick(e) {
          e.preventDefault();
          sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      }, sec.getAttribute('title'));
      link.dataset.target = sec.id;
      nav.append(link);
      this._sideNavObs.observe(sec);
    }
  }

  _highlightNavLink(id) {
    if (!this._sideNav) return;
    for (const l of this._sideNav.querySelectorAll('.pd-sidenav-link')) {
      l.classList.toggle('pd-active', l.dataset.target === id);
    }
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

    // summary attr → progressive disclosure. The one-line summary is the
    // always-visible scan layer; the full body collapses into a <details>
    // (collapsed by default, still in the DOM so agents read everything).
    const summary = this.getAttribute('summary');
    if (summary) {
      const body = el('div', { class: 'pd-section-body' });
      while (this.firstChild) body.append(this.firstChild);
      const open = this.hasAttribute('open');
      const details = el('details', { class: 'pd-section-collapse', open });
      details.append(el('summary', { class: 'pd-section-more' }, 'Details'), body);
      this.append(heading, el('p', { class: 'pd-section-summary' }, summary), details);
    } else {
      this.prepend(heading);
    }
  }
}

define('pd-doc', PdDoc);
define('pd-tab', PdTab);
define('pd-section', PdSection);
