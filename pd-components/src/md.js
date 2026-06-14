// <md>: renders markdown content client-side via marked (loaded from CDN on demand).
// No extra script tag needed in the boilerplate — marked is fetched automatically
// when at least one <md> element exists on the page.

import { ready } from './util.js';

const MARKED_CDN = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';

function render() {
  document.querySelectorAll('md:not([data-rendered])').forEach((node) => {
    node.innerHTML = marked.parse(node.textContent);
    node.dataset.rendered = '';
  });
}

ready(() => {
  if (!document.querySelector('md')) return;
  if (window.marked) { render(); return; }
  const s = document.createElement('script');
  s.src = MARKED_CDN;
  s.onload = render;
  document.head.append(s);
});
