// pd-files / pd-file: file-change tree. Source stays flat (one pd-file per
// path — cheap to write and append for an agent); the component renders a
// collapsible GitHub-PR-style tree with add/edit/delete markers, the note for
// each file, and an open-thread badge when a pd-thread anchors to the path.
//
// Listens for pd:phase-selected (from pd-stepper) and highlights the files
// belonging to the selected phase.

import { PdElement, define, el } from './util.js';

const SYMBOLS = { add: '+', edit: '~', delete: '−' };

class PdFile extends PdElement {}

class PdFiles extends PdElement {
  init() {
    const files = [...this.querySelectorAll(':scope > pd-file')].map((f) => ({
      path: f.getAttribute('path') || '',
      change: f.getAttribute('change') || 'edit',
      note: f.textContent.trim(),
    }));

    // Build a nested tree out of the flat path list.
    const root = { dirs: new Map(), files: [] };
    for (const f of files) {
      const parts = f.path.split('/');
      let node = root;
      for (const part of parts.slice(0, -1)) {
        if (!node.dirs.has(part)) node.dirs.set(part, { dirs: new Map(), files: [] });
        node = node.dirs.get(part);
      }
      node.files.push({ ...f, name: parts[parts.length - 1] });
    }

    const renderDir = (node) => {
      const ul = el('ul', { class: 'pd-tree' });
      for (const [name, child] of [...node.dirs.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
        const details = el('details', { open: true }, [el('summary', {}, name + '/')]);
        details.append(renderDir(child));
        ul.append(el('li', {}, details));
      }
      for (const f of node.files.sort((a, b) => a.name.localeCompare(b.name))) {
        const openThreads = document.querySelectorAll(
          `pd-thread[anchor="${CSS.escape(f.path)}"][status="unresolved"], pd-thread[anchor="${CSS.escape(f.path)}"]:not([status])`,
        ).length;
        const row = el('li', { class: 'pd-tree-file', 'data-change': f.change, 'data-path': f.path }, [
          el('span', { class: 'pd-tree-sym' }, SYMBOLS[f.change] || '~'),
          el('code', {}, f.name),
          openThreads ? el('a', {
            class: 'pd-tabbadge', title: `${openThreads} open thread(s)`,
            href: '#', onclick: (e) => { e.preventDefault(); this._jumpToThread(f.path); },
          }, String(openThreads)) : null,
          f.note ? el('span', { class: 'pd-tree-note' }, f.note) : null,
        ]);
        ul.append(row);
      }
      return ul;
    };

    this.append(renderDir(root));

    window.addEventListener('pd:phase-selected', (e) => {
      const phaseFiles = e.detail?.files;
      this.querySelectorAll('.pd-tree-file').forEach((row) => {
        row.classList.remove('pd-hl', 'pd-dim');
        if (phaseFiles && phaseFiles.length) {
          row.classList.add(phaseFiles.includes(row.dataset.path) ? 'pd-hl' : 'pd-dim');
        }
      });
    });
  }

  _jumpToThread(path) {
    const t = document.querySelector(`pd-thread[anchor="${CSS.escape(path)}"]`);
    if (t) t.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

define('pd-file', PdFile);
define('pd-files', PdFiles);
