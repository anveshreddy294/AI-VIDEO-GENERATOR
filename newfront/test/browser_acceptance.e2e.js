import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';

const BRAVE_PATH = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
const BASE_URL = 'http://127.0.0.1:5175';
const TEST_EMAIL = process.env.VISUALAI_AUTH_TEST_EMAIL;
const TEST_PASS = process.env.VISUALAI_AUTH_TEST_PASSWORD;
assert.ok(TEST_EMAIL && TEST_PASS, 'Set VISUALAI_AUTH_TEST_EMAIL and VISUALAI_AUTH_TEST_PASSWORD');

const text = page => page.evaluate(() => document.body.innerText);
const clickText = async (page, selector, label) => {
  const clicked = await page.evaluate(({ selector, label }) => {
    const element = [...document.querySelectorAll(selector)].find(node => node.textContent.includes(label));
    if (!element) return false;
    element.click();
    return true;
  }, { selector, label });
  assert.equal(clicked, true, `Expected to find ${label}`);
};

async function runBrowserAcceptance() {
  const browser = await puppeteer.launch({ executablePath: BRAVE_PATH, headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(error.message));
  try {
    console.log('1. Landing and identity');
    await page.goto(BASE_URL, { waitUntil: 'networkidle0' });
    assert.match(await page.title(), /VisualAI/i);
    assert.equal(await page.$eval('.brand-name', element => element.textContent.trim()), 'VisualAI');
    assert.ok(await page.$('a[href="/terms"]'));
    assert.ok(await page.$('a[href="/privacy"]'));

    console.log('2. Real sign in and session restoration');
    await page.goto(`${BASE_URL}/signin`, { waitUntil: 'networkidle0' });
    await page.type('#signin-email', TEST_EMAIL);
    await page.type('#signin-pass', TEST_PASS);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 30000 }), page.click('.signin-submit-btn')]);
    assert.ok(page.url().includes('/app/dashboard'));
    await page.waitForSelector('.app-top-bar', { timeout: 10000 });
    assert.match(await text(page), /What would you like to learn today\?/i);
    assert.match(await text(page), /Learn a Topic/i);
    assert.match(await text(page), /Upload Study Material/i);
    assert.match(await text(page), /Continue Learning/i);
    await page.reload({ waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/dashboard'));
    assert.ok(await page.$('.user-name-tag'));

    console.log('3. Saved lesson workspace');
    await page.goto(`${BASE_URL}/app/explore`, { waitUntil: 'networkidle0' });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /My Learning/i);
    await clickText(page, '.saved-lesson-actions-row button', 'Binary Search Trees');
    await page.waitForSelector('.learning-workspace-tabs', { timeout: 15000 });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);
    assert.equal(await page.$$eval('.learning-workspace-tab', tabs => tabs.length), 6);
    assert.match(await text(page), /Your Learning Workspace/i);

    console.log('4. Tabs preserve lesson context');
    for (const tab of ['Notes', 'Visualize', 'Practice', 'Ask AI']) {
      await clickText(page, '.learning-workspace-tab', tab);
      await new Promise(resolve => setTimeout(resolve, 250));
      assert.match(await text(page), new RegExp(tab === 'Ask AI' ? 'Ask a question about this lesson' : tab, 'i'));
      assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);
    }
    await page.reload({ waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('tab=ask'));
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);

    console.log('5. Practice and legacy deep link');
    await page.goto(`${BASE_URL}/app/assessment`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/studio?tab=practice'));
    assert.match(await text(page), /Check your understanding|Practice is ready/i);

    console.log('6. Materials and real readiness');
    await page.goto(`${BASE_URL}/app/library`, { waitUntil: 'networkidle0' });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /My Materials/i);
    assert.match(await text(page), /Ready to learn|Preparing document search|Material read|Reading your material/i);
    assert.ok(await page.$('.workflow-stepper'));
    assert.equal(await page.$eval('button[type="submit"]', button => button.disabled), true);

    console.log('7. Video and authorized Blob playback');
    await page.goto(`${BASE_URL}/app/video`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/studio?tab=video'));
    await page.waitForSelector('.learning-workspace-tabs', { timeout: 10000 });
    await new Promise(resolve => setTimeout(resolve, 2500));
    assert.equal(await page.$$eval('.video-workflow .workflow-step', steps => steps.length), 4);
    const video = await page.$('video');
    if (video) {
      const props = await page.$eval('video', element => ({ src: element.src, controls: element.controls, readyState: element.readyState }));
      assert.equal(props.controls, true);
      assert.ok(props.src.startsWith('blob:'));
      await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2, { timeout: 30000 });
    } else assert.match(await text(page), /Generate an explanation video|Video is optional|being prepared/i);

    console.log('8. Keyboard navigation and logout protection');
    await page.setViewport({ width: 375, height: 800 });
    await page.focus('.app-brand-lockup-btn');
    await page.keyboard.press('Enter');
    assert.equal(await page.$eval('.app-brand-lockup-btn', node => node.getAttribute('aria-expanded')), 'true');
    await page.focus('.sidebar-nav-item');
    await page.keyboard.press('Escape');
    assert.equal(await page.$eval('.app-brand-lockup-btn', node => node.getAttribute('aria-expanded')), 'false');
    await page.goto(`${BASE_URL}/app/profile`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.identity-card-actions button', { timeout: 10000 });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 15000 }), page.click('.identity-card-actions button')]);
    assert.ok(page.url().includes('/signin'));
    assert.equal(await page.evaluate(() => sessionStorage.getItem('visualai.auth.session')), null);
    await page.goto(`${BASE_URL}/app/dashboard`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/signin'));
    assert.deepEqual(pageErrors, []);
    console.log('All learning workspace browser checks passed.');
    if (consoleErrors.length) console.log('Browser console errors observed:', consoleErrors);
  } finally { await browser.close(); }
}

runBrowserAcceptance().catch(error => { console.error('Browser acceptance failed:', error); process.exitCode = 1; });
