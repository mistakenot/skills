// Playwright test for pd-sidenav: presence, tab-sync, scroll-spy, responsive.
// Run: node pd-components/tests/sidenav.test.mjs

import { chromium } from 'playwright';
import { strict as assert } from 'node:assert';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture = 'file://' + resolve(__dirname, 'fixtures/sidenav.html');

let browser, page;
let pass = 0, fail = 0;
const errors = [];

async function check(label, fn) {
  try {
    await fn();
    pass++;
    console.log(`  ✓ ${label}`);
  } catch (e) {
    fail++;
    errors.push(`${label}: ${e.message}`);
    console.log(`  ✗ ${label} — ${e.message}`);
  }
}

try {
  browser = await chromium.launch();

  // ── Wide viewport: sidenav visible ─────────────────────────
  console.log('\n── sidenav at 1440px ──');
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(fixture);
  await page.waitForTimeout(800);

  await check('sidenav element exists', async () => {
    const count = await page.locator('.pd-sidenav').count();
    assert.equal(count, 1);
  });

  await check('sidenav is visible', async () => {
    const visible = await page.locator('.pd-sidenav').isVisible();
    assert.ok(visible);
  });

  await check('doc-body wrapper exists', async () => {
    const count = await page.locator('.pd-doc-body').count();
    assert.equal(count, 1);
  });

  await check('pd-doc has flex layout class', async () => {
    const has = await page.locator('pd-doc').evaluate(el => el.classList.contains('pd-has-sidenav'));
    assert.ok(has);
  });

  await check('Overview tab: 3 nav links', async () => {
    const count = await page.locator('.pd-sidenav-link').count();
    assert.equal(count, 3);
  });

  await check('nav link text matches section titles', async () => {
    const texts = await page.locator('.pd-sidenav-link').allTextContents();
    assert.deepEqual(texts, ['Problem', 'Goals', 'Constraints']);
  });

  await check('nav links have correct href anchors', async () => {
    const hrefs = await page.locator('.pd-sidenav-link').evaluateAll(
      els => els.map(el => el.getAttribute('href'))
    );
    assert.deepEqual(hrefs, ['#problem', '#goals', '#constraints']);
  });

  await check('first link has active class (scroll-spy)', async () => {
    const has = await page.locator('.pd-sidenav-link').first().evaluate(
      el => el.classList.contains('pd-active')
    );
    assert.ok(has);
  });

  // ── Tab switch updates sidenav ─────────────────────────────
  console.log('\n── tab switch ──');

  await page.locator('.pd-tabbtn', { hasText: 'Solution' }).click();
  await page.waitForTimeout(300);

  await check('Solution tab: 2 nav links', async () => {
    const count = await page.locator('.pd-sidenav-link').count();
    assert.equal(count, 2);
  });

  await check('Solution nav link text matches', async () => {
    const texts = await page.locator('.pd-sidenav-link').allTextContents();
    assert.deepEqual(texts, ['Approach', 'Files']);
  });

  // Switch back
  await page.locator('.pd-tabbtn', { hasText: 'Overview' }).click();
  await page.waitForTimeout(300);

  await check('back to Overview: 3 nav links', async () => {
    const count = await page.locator('.pd-sidenav-link').count();
    assert.equal(count, 3);
  });

  // ── Scroll-spy: scrolling updates active link ──────────────
  console.log('\n── scroll-spy ──');

  await page.locator('#goals').evaluate(el => el.scrollIntoView());
  await page.waitForTimeout(400);

  await check('after scrolling to Goals, Goals link is active', async () => {
    const active = await page.locator('.pd-sidenav-link.pd-active').textContent();
    assert.equal(active, 'Goals');
  });

  await check('Problem link is no longer active', async () => {
    const has = await page.locator('.pd-sidenav-link').first().evaluate(
      el => el.classList.contains('pd-active')
    );
    assert.ok(!has);
  });

  // ── Click nav link scrolls to section ──────────────────────
  console.log('\n── nav link click ──');

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(200);

  await page.locator('.pd-sidenav-link', { hasText: 'Constraints' }).click();
  await page.waitForTimeout(600);

  await check('clicking Constraints link scrolls section into view', async () => {
    const inView = await page.locator('#constraints').evaluate(el => {
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.top < window.innerHeight;
    });
    assert.ok(inView);
  });

  // ── Narrow viewport: sidenav hidden ────────────────────────
  console.log('\n── narrow viewport (1024px) ──');

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.waitForTimeout(200);

  await check('sidenav hidden at 1024px', async () => {
    const visible = await page.locator('.pd-sidenav').isVisible();
    assert.ok(!visible);
  });

  await check('pd-doc not using flex at narrow width', async () => {
    const display = await page.locator('pd-doc').evaluate(
      el => getComputedStyle(el).display
    );
    assert.equal(display, 'block');
  });

  // ── Widen again: sidenav reappears ─────────────────────────
  console.log('\n── re-widen (1440px) ──');

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);

  await check('sidenav visible again after widening', async () => {
    const visible = await page.locator('.pd-sidenav').isVisible();
    assert.ok(visible);
  });

  await page.close();
} finally {
  if (browser) await browser.close();
}

// ── Summary ──────────────────────────────────────────────────
console.log('\n════════════════════════════════════════');
console.log(`PASS: ${pass}  FAIL: ${fail}`);
if (errors.length) {
  console.log('\nFailures:');
  for (const e of errors) console.log(`  ✗ ${e}`);
  console.log('════════════════════════════════════════');
  process.exit(1);
} else {
  console.log('ALL PASS ✓');
  console.log('════════════════════════════════════════');
}
