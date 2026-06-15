// <md>: renders markdown content client-side via marked (loaded from CDN on demand).
// No extra script tag needed in the boilerplate — marked is fetched automatically
// when at least one <md> element exists on the page.
//
// Content source (checked in order):
//   1. <script type="text/plain"> child — safe from HTML parsing; handles
//      content containing angle brackets (<textarea>, <SomeTag>, etc.).
//   2. textContent of the <md> element itself — legacy / simple content.

import { ready } from './util.js';

const MARKED_CDN = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
const MD_SEL = 'md:not([data-rendered])';

function dedent(text) {
  const lines = text.split('\n');
  let min = Infinity;
  for (const line of lines) {
    if (!line.trim()) continue;
    const indent = line.match(/^ */)[0].length;
    if (indent < min) min = indent;
  }
  if (!min || min === Infinity) return text;
  return lines.map((l) => l.slice(min)).join('\n');
}

function source(node) {
  const script = node.querySelector(':scope > script[type="text/plain"]');
  return (script ? script.textContent : node.textContent);
}

function render() {
  document.querySelectorAll(MD_SEL).forEach((node) => {
    node.innerHTML = marked.parse(dedent(source(node)));
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
