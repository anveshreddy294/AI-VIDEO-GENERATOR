import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';

const BRAVE_PATH = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
const BASE_URL = 'http://127.0.0.1:5175';
const TEST_EMAIL = process.env.VISUALAI_AUTH_TEST_EMAIL || 'romeoragnorak@gmail.com';
const TEST_PASS = process.env.VISUALAI_AUTH_TEST_PASSWORD || 'anvesh2942008';

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
  console.log('=== STARTING VISUALAI LEARNING WORKSPACE ACCEPTANCE SUITE ===');
  const browser = await puppeteer.launch({ executablePath: BRAVE_PATH, headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--window-size=1280,800'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  const consoleErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  try {
    console.log('\n--- 1. Landing and dashboard choices ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle0' });
    assert.match(await page.title(), /VisualAI/i);
    assert.equal(await page.$eval('.brand-name', element => element.textContent.trim()), 'VisualAI');

    console.log('\n--- 2. Real sign in and session restoration ---');
    await page.goto(`${BASE_URL}/signin`, { waitUntil: 'networkidle0' });
    await page.type('#signin-email', TEST_EMAIL);
    await page.type('#signin-pass', TEST_PASS);
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 15000 }), page.click('.signin-submit-btn')]);
    assert.ok(page.url().includes('/app/dashboard'));
    await page.waitForSelector('.app-top-bar', { timeout: 10000 });
    assert.match(await text(page), /What would you like to learn today\?/i);
    assert.match(await text(page), /Learn a Topic/i);
    assert.match(await text(page), /Upload Study Material/i);
    assert.match(await text(page), /Continue Learning/i);
    await page.reload({ waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/dashboard'));
    assert.ok(await page.$('.user-name-tag'));

    console.log('\n--- 3. My Learning and one lesson workspace ---');
    await page.goto(`${BASE_URL}/app/explore`, { waitUntil: 'networkidle0' });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /My Learning/i);
    await clickText(page, 'button', 'Binary Search Trees');
    await new Promise(resolve => setTimeout(resolve, 600));
    await page.goto(`${BASE_URL}/app/studio?tab=learn`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.learning-workspace-tabs', { timeout: 8000 });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);
    assert.equal(await page.$$eval('.learning-workspace-tab', tabs => tabs.length), 6);
    assert.match(await text(page), /Your Learning Workspace/i);

    console.log('\n--- 4. Workspace tabs preserve lesson context ---');
    for (const tab of ['Notes', 'Visualize', 'Practice', 'Ask AI']) {
      await clickText(page, '.learning-workspace-tab', tab);
      await new Promise(resolve => setTimeout(resolve, 250));
      assert.match(await text(page), new RegExp(tab === 'Ask AI' ? 'Ask a question about this lesson' : tab, 'i'));
      assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);
    }
    await page.reload({ waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('tab=ask'));
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /Binary Search Trees/i);

    console.log('\n--- 5. Practice and legacy deep link ---');
    await page.goto(`${BASE_URL}/app/assessment`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/studio?tab=practice'));
    assert.match(await text(page), /Check your understanding|Practice is ready/i);

    console.log('\n--- 6. Materials and truthful source states ---');
    await page.goto(`${BASE_URL}/app/library`, { waitUntil: 'networkidle0' });
    assert.match(await page.$eval('.page-heading', element => element.textContent.trim()), /My Materials/i);
    const materialText = await text(page);
    assert.ok(/Ready to learn|Preparing document search|Material read|Reading your material/i.test(materialText));

    console.log('\n--- 7. Video tab and authenticated playback boundary ---');
    await page.goto(`${BASE_URL}/app/video`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/app/studio?tab=video'));
    await page.waitForSelector('.learning-workspace-tabs', { timeout: 8000 });
    await new Promise(resolve => setTimeout(resolve, 2500));
    const video = await page.$('video');
    if (video) {
      const props = await page.$eval('video', element => ({ src: element.src, controls: element.controls, readyState: element.readyState }));
      assert.equal(props.controls, true);
      assert.ok(props.src.startsWith('blob:') || props.src === '');
      console.log('Video element:', props);
    } else {
      assert.match(await text(page), /Generate an explanation video|Video is optional|being prepared/i);
    }

    console.log('\n--- 8. Logout and protected route ---');
    await page.goto(`${BASE_URL}/app/profile`, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.identity-card-actions button', { timeout: 8000 });
    await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 10000 }), page.click('.identity-card-actions button')]);
    assert.ok(page.url().includes('/signin'));
    assert.equal(await page.evaluate(() => sessionStorage.getItem('visualai.auth.session')), null);
    await page.goto(`${BASE_URL}/app/dashboard`, { waitUntil: 'networkidle0' });
    assert.ok(page.url().includes('/signin'));
    console.log('\n=== ALL LEARNING WORKSPACE BROWSER TESTS PASSED ===');
    if (consoleErrors.length) console.log('Browser console errors observed:', consoleErrors);
  } finally {
    await browser.close();
  }
}

runBrowserAcceptance().catch(error => { console.error('Browser acceptance failed:', error); process.exitCode = 1; });
