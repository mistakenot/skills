// CLI adapter for the shared lint core (../lint-core.js). Lets an agent lint a
// planning doc headlessly — no browser, no copy/paste round-trip:
//
//   node pd-lint.mjs ./path/to/plan.html [more.html ...]
//
// Emits JSON to stdout and exits non-zero when any file has issues, so it drops
// straight into a CI step or an agent's tool loop. The checks are identical to
// the in-browser linter because both import the same lint-core.js.
//
// Built (bundled with node-html-parser inlined) to dist/pd-lint.mjs by build.mjs;
// that single-file bundle is what ships into the planning-doc skill.

import { readFileSync } from 'node:fs';
import { parse } from 'node-html-parser';
import { collect, findIssues } from '../lint-core.js';

function lintFile(file) {
  try {
    const html = readFileSync(file, 'utf8');
    const root = parse(html);
    const issues = findIssues(collect(root));
    return { file, ok: issues.length === 0, issueCount: issues.length, issues };
  } catch (err) {
    return { file, ok: false, error: err.message, issues: [] };
  }
}

function main(argv) {
  const files = argv.filter((a) => !a.startsWith('-'));
  if (!files.length) {
    process.stderr.write('usage: node pd-lint.mjs <plan.html> [more.html ...]\n');
    process.exit(2);
  }

  const results = files.map(lintFile);
  const clean = results.every((r) => r.ok);
  // Single file: emit the bare result; multiple: emit a summary envelope.
  const output = results.length === 1
    ? results[0]
    : { ok: clean, fileCount: results.length, results };

  process.stdout.write(JSON.stringify(output, null, 2) + '\n');
  process.exit(clean ? 0 : 1);
}

main(process.argv.slice(2));
