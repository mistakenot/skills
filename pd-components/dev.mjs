// Dev server for pd-components.
// Uses esbuild watch to rebuild pd.min.js on src/ changes, and a plain Node
// HTTP server (no host-header validation) to serve planning-doc-workspace/.
//
// Usage: node dev.mjs   (or: npm run dev)
// The shell wrapper dev.sh also registers the port with tailscale serve.

import { context } from 'esbuild';
import { createServer } from 'http';
import { createReadStream, statSync } from 'fs';
import { join, extname } from 'path';
import { fileURLToPath } from 'url';

const LOCAL_PORT = 9173;
const WORKSPACE = join(fileURLToPath(import.meta.url), '../../planning-doc-workspace');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript',
  '.css':  'text/css',
  '.png':  'image/png',
  '.json': 'application/json',
  '.md':   'text/plain; charset=utf-8',
};

const ctx = await context({
  entryPoints: ['src/index.js'],
  bundle: true,
  format: 'iife',
  outfile: '../planning-doc-workspace/preview/pd.min.js',
  loader: { '.css': 'text' },
  define: { __PD_VERSION__: '"dev"' },
  sourcemap: true,
});

await ctx.watch();

createServer((req, res) => {
  let fsPath = join(WORKSPACE, req.url.split('?')[0]);
  try {
    if (statSync(fsPath).isDirectory()) fsPath = join(fsPath, 'index.html');
    const mime = MIME[extname(fsPath)] ?? 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': mime });
    createReadStream(fsPath).pipe(res);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found');
  }
}).listen(LOCAL_PORT);

console.log(`\npd-components dev server`);
console.log(`  local:  http://localhost:${LOCAL_PORT}`);
console.log(`\nWatching src/ for changes and rebuilding pd.min.js.`);
console.log(`Refresh the browser after a rebuild completes.`);
console.log(`Press Ctrl+C to stop.\n`);
