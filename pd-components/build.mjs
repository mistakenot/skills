// Builds dist/pd.min.js (single classic IIFE bundle, beautiful-mermaid
// included) and dist/llms.txt (agent-facing reference, version-stamped).
//
// Release flow (see README.md): bump version in package.json → npm run build
// → commit → tag pd-v<version> → push tag. jsDelivr serves the tag
// immutably; llms.txt fetched from @main always points at the latest tag.

import { build } from 'esbuild';
import { readFileSync, writeFileSync } from 'node:fs';

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
const tag = `pd-v${pkg.version}`;
const cdnBase = `https://cdn.jsdelivr.net/gh/mistakenot/skills@${tag}/pd-components/dist`;

const result = await build({
  entryPoints: ['src/index.js'],
  bundle: true,
  minify: true,
  format: 'iife',
  target: ['chrome111', 'firefox113', 'safari16.4'],
  outfile: 'dist/pd.min.js',
  loader: { '.css': 'text' },
  define: { __PD_VERSION__: JSON.stringify(pkg.version) },
  banner: { js: `/* pd-components v${pkg.version} — https://github.com/mistakenot/skills (MIT). Bundles beautiful-mermaid (MIT). */` },
  metafile: true,
});

const llms = readFileSync('llms.template.txt', 'utf8')
  .replaceAll('{{VERSION}}', pkg.version)
  .replaceAll('{{TAG}}', tag)
  .replaceAll('{{CDN_BASE}}', cdnBase);
writeFileSync('dist/llms.txt', llms);

const bytes = Object.values(result.metafile.outputs).find((o) => o.entryPoint)?.bytes ?? 0;
console.log(`pd.min.js ${(bytes / 1024).toFixed(0)} KB · llms.txt ${(llms.length / 1024).toFixed(1)} KB · tag ${tag}`);
