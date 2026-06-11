// pd-mermaid: renders mermaid source via beautiful-mermaid (bundled — no
// extra network fetch). Theme colors come from the pd CSS variables so
// diagrams follow light/dark mode, and re-render live on scheme change.
//
// beautiful-mermaid supports: flowchart/graph, sequenceDiagram,
// stateDiagram(-v2), classDiagram, erDiagram, xychart-beta. Anything else
// throws a clear parse error and we fall back to showing the source — the
// doc still communicates, just less prettily.

import { renderMermaidSVG } from 'beautiful-mermaid';
import { PdElement, define, el } from './util.js';

function themeColors() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim() || undefined;
  return {
    bg: v('--pd-bg'), fg: v('--pd-fg'), muted: v('--pd-muted'),
    border: v('--pd-border'), accent: v('--pd-accent'),
    font: 'Inter, system-ui, sans-serif',
  };
}

class PdMermaid extends PdElement {
  init() {
    this._source = this.textContent.trim();
    this.textContent = '';
    this._render();

    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener?.('change', () => this._render());
  }

  _render() {
    const caption = this.getAttribute('caption');
    this.innerHTML = '';
    try {
      const svg = renderMermaidSVG(this._source, themeColors());
      const wrap = el('figure', { class: 'pd-mermaid-figure' });
      wrap.innerHTML = svg;
      if (caption) wrap.append(el('figcaption', {}, caption));
      this.append(wrap);
    } catch (err) {
      this.append(el('div', { class: 'pd-mermaid-fallback' }, [
        el('div', { class: 'pd-muted' },
          `Diagram could not be rendered (${String(err.message || err).split('\n')[0]}) — source:`),
        el('pre', {}, el('code', {}, this._source)),
      ]));
    }
  }
}

define('pd-mermaid', PdMermaid);
