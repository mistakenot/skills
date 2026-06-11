// Curated highlight.js — only the languages a planning doc realistically shows.
// Bundled (not lazy-loaded) so pd-code works from file:// with no extra fetch.
// ~18 KB gzip. Add a language here if a doc needs one.

import hljs from 'highlight.js/lib/core';
import go from 'highlight.js/lib/languages/go';
import typescript from 'highlight.js/lib/languages/typescript';
import javascript from 'highlight.js/lib/languages/javascript';
import python from 'highlight.js/lib/languages/python';
import json from 'highlight.js/lib/languages/json';
import bash from 'highlight.js/lib/languages/bash';
import yaml from 'highlight.js/lib/languages/yaml';
import sql from 'highlight.js/lib/languages/sql';
import rust from 'highlight.js/lib/languages/rust';
import diff from 'highlight.js/lib/languages/diff';

for (const [name, lang] of Object.entries({
  go, typescript, javascript, python, json, bash, yaml, sql, rust, diff,
})) {
  hljs.registerLanguage(name, lang);
}
hljs.registerAliases(['ts'], { languageName: 'typescript' });
hljs.registerAliases(['js'], { languageName: 'javascript' });
hljs.registerAliases(['py'], { languageName: 'python' });
hljs.registerAliases(['sh', 'shell'], { languageName: 'bash' });
hljs.registerAliases(['yml'], { languageName: 'yaml' });

export function highlight(code, lang) {
  if (lang && hljs.getLanguage(lang)) {
    return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
  }
  return hljs.highlightAuto(code).value;
}

// Split highlighted HTML into per-line fragments without breaking spans that
// cross newlines (hljs only emits <span>). Lets us add line numbers and
// per-line highlight backgrounds safely.
export function splitLines(html) {
  const out = [];
  const open = [];
  let cur = '';
  const re = /(<[^>]+>)|([^<]+)/g;
  let m;
  while ((m = re.exec(html))) {
    if (m[1]) {
      cur += m[1];
      if (m[1].startsWith('</')) open.pop();
      else if (!m[1].endsWith('/>')) open.push(m[1]);
    } else {
      const parts = m[2].split('\n');
      for (let i = 0; i < parts.length; i++) {
        if (i > 0) {
          cur += '</span>'.repeat(open.length);
          out.push(cur);
          cur = open.join('');
        }
        cur += parts[i];
      }
    }
  }
  out.push(cur);
  return out;
}
