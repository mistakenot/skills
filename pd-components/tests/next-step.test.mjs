// Playwright test for the pd-doc next-prompt "Next step" banner.
// Run: node pd-components/tests/next-step.test.mjs   (needs `npm run build` first)

import { chromium } from 'playwright';
import { strict as assert } from 'node:assert';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture = 'file://' + resolve(__dirname, 'fixtures/next-step.html');

let browser, page;
let pass = 0, fail = 0;
const errors = [];

async function check(label, fn) {
  try { await fn(); pass++; console.log(`  ✓ ${label}`); }
  catch (e) { fail++; errors.push(`${label}: ${e.message}`); console.log(`  ✗ ${label} — ${e.message}`); }
}

try {
  browser = await chromium.launch();
  page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
  await page.goto(fixture);
  await page.waitForTimeout(600);

  await check('banner renders when next-prompt is set', async () => {
    assert.equal(await page.locator('.pd-nextstep').count(), 1);
  });

  await check('banner shows the prompt verbatim', async () => {
    assert.equal((await page.locator('.pd-next-cmd').textContent()).trim(), '/new-solution 042');
  });

  await check('banner sits above the tab bar (top region)', async () => {
    const order = await page.evaluate(() => {
      const ns = document.querySelector('.pd-nextstep');
      const nav = document.querySelector('.pd-tabnav');
      return ns.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING ? 'before' : 'after';
    });
    assert.equal(order, 'before');
  });

  await check('clean doc is not dimmed', async () => {
    assert.equal(await page.locator('.pd-nextstep.pd-next-blocked').count(), 0);
  });

  await check('copy button copies the prompt to the clipboard', async () => {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.locator('.pd-next-copy').click();
    await page.waitForTimeout(100);
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert.equal(clip, '/new-solution 042');
  });

  await check('banner dims when an open thread blocks the doc', async () => {
    await page.evaluate(() => {
      const doc = document.querySelector('pd-doc');
      const t = document.createElement('pd-thread');
      t.setAttribute('anchor', 'r1');
      t.setAttribute('status', 'unresolved');
      t.setAttribute('priority', 'p1');
      t.setAttribute('title', 'blocker');
      doc.querySelector('pd-section').after(t);
      window.dispatchEvent(new CustomEvent('pd:status-refresh'));
    });
    await page.waitForTimeout(100);
    assert.equal(await page.locator('.pd-nextstep.pd-next-blocked').count(), 1);
  });
} finally {
  if (browser) await browser.close();
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { errors.forEach((e) => console.log('  ✗ ' + e)); process.exit(1); }
