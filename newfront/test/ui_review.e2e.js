import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const phase = process.env.UI_REVIEW_PHASE || 'after';
const base = process.env.UI_REVIEW_URL || 'http://127.0.0.1:5175';
const output = new URL(`../../docs/ui-modernization/${phase}/`, import.meta.url);
const email = process.env.VISUALAI_AUTH_TEST_EMAIL;
const password = process.env.VISUALAI_AUTH_TEST_PASSWORD;
assert.ok(email && password, 'Set VISUALAI_AUTH_TEST_EMAIL and VISUALAI_AUTH_TEST_PASSWORD');
await mkdir(output, { recursive: true });
const browser = await puppeteer.launch({ executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const page = await browser.newPage();
const errors = [];
const measurements = [];
page.on('pageerror', error => errors.push(error.message));
// This review uses existing content only. An unexpected generation request is a failure.
await page.setRequestInterception(true);
page.on('request', request => {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()) && !/\/auth\//.test(request.url())) {
    errors.push(`Unexpected mutation: ${request.method()} ${new URL(request.url()).pathname}`);
    request.abort();
  } else request.continue();
});
try {
  await page.setViewport({ width: 1366, height: 900 });
  await page.goto(`${base}/signin`, { waitUntil: 'networkidle0' });
  await page.type('#signin-email', email);
  await page.type('#signin-pass', password);
  await page.click('.signin-submit-btn');
  await page.waitForSelector('.app-top-bar', { timeout: 30000 });
  await page.goto(`${base}/app/explore`, { waitUntil: 'networkidle0' });
  const opened = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('.saved-lesson-actions-row .btn-atelier-primary')];
    const button = buttons.find(node => node.textContent.includes('Binary Search Trees')) || buttons[0];
    button?.click();
    return Boolean(button);
  });
  assert.ok(opened, 'At least one saved lesson is required');
  await page.waitForSelector('.learning-workspace-tabs', { timeout: 20000 });
  const routes = { landing: '/', demo: '/demo', dashboard: '/app/dashboard', materials: '/app/library', learn: '/app/studio?tab=learn', video: '/app/studio?tab=video', learning: '/app/explore', profile: '/app/profile', signin: '/signin', terms: '/terms', privacy: '/privacy' };
  for (const width of phase === 'before' ? [375, 1366] : [320, 375, 430, 768, 1366, 1920]) {
    await page.setViewport({ width, height: 900 });
    for (const [name, route] of Object.entries(routes)) {
      await page.goto(`${base}${route}`, { waitUntil: 'networkidle0' });
      await page.evaluate(() => document.fonts.ready);
      await new Promise(resolve => setTimeout(resolve, 500));
      const metric = await page.evaluate(() => ({
        width: innerWidth, documentWidth: document.documentElement.scrollWidth,
        heading: document.querySelector('h1')?.textContent,
        headingSize: document.querySelector('h1') ? getComputedStyle(document.querySelector('h1')).fontSize : null,
        buttonRadius: document.querySelector('.btn-atelier-primary') ? getComputedStyle(document.querySelector('.btn-atelier-primary')).borderRadius : null,
        overflow: [...document.querySelectorAll('body *')].filter(el => {
          const r = el.getBoundingClientRect();
          return r.width && (r.right > innerWidth + 1 || r.left < -1) && getComputedStyle(el).position !== 'fixed';
        }).slice(0, 8).map(el => el.className)
      }));
      measurements.push({ page: name, ...metric });
      if ([375, 1366].includes(width) && ['landing', 'demo', 'dashboard', 'materials', 'learn', 'video'].includes(name)) {
        await page.screenshot({ path: new URL(`${name}-${width}.png`, output).pathname, fullPage: true });
      }
      if (phase === 'after' && metric.documentWidth > width + 1) errors.push(`${name} at ${width}px overflows to ${metric.documentWidth}px`);
    }
  }
  await writeFile(new URL('measurements.json', output), JSON.stringify({ measurements, errors }, null, 2));
  assert.deepEqual(errors, [], 'Browser runtime, mutation, and document overflow checks');
  console.log(`${phase}: ${measurements.length} page/viewport checks; screenshots saved in docs/ui-modernization/${phase}`);
} finally { await browser.close(); }
