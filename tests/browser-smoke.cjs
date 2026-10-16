/* Actual Chromium workflow checks against the explicit fixture-only server. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  // This broad workflow explicitly discards test drafts; focused navigation tests assert each guard.
  page.on('dialog', dialog => dialog.accept());
  const requests = []; const external = []; const errors = []; const checks = [];
  page.on('request', request => { requests.push({ url: request.url(), method: request.method() }); });
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (!route.request().url().startsWith(BASE + '/')) { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  await page.addInitScript(() => {
    window.__observedUploadProgress = [];
    new MutationObserver(() => {
      const element = document.querySelector('.upload-progress');
      if (element) window.__observedUploadProgress.push(element.textContent);
    }).observe(document, { childList: true, subtree: true, characterData: true });
  });
  const record = name => { checks.push(name); console.log('PASS ' + name); };
  const status = value => page.locator('.status-badge').filter({ hasText: value }).waitFor();
  async function home() { await page.locator('a.new-recording').click(); await page.locator('.drop-zone').waitFor(); }
  async function picker(filename) {
    const chooserPromise = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose a file', exact: true }).click();
    await (await chooserPromise).setFiles(path.join(ROOT, 'fixtures', filename));
  }
  async function drop(filename) {
    const bytes = Array.from(await fs.readFile(path.join(ROOT, 'fixtures', filename)));
    const transfer = await page.evaluateHandle(({ bytes, filename }) => {
      const data = new DataTransfer(); data.items.add(new File([new Uint8Array(bytes)], filename, { type: 'audio/wav' })); return data;
    }, { bytes, filename });
    await page.locator('.drop-zone').dispatchEvent('drop', { dataTransfer: transfer });
    await transfer.dispose();
  }
  const id = () => new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job');
  async function auth() { return (await (await page.request.get(BASE + '/api/session')).json()).token; }
  async function transcript(jobId) { return (await page.request.get(`${BASE}/api/jobs/${jobId}/transcript`)).json(); }
  try {
    await page.goto(BASE);
    await page.getByText('Local engine ready', { exact: true }).waitFor();
    assert.deepEqual(await page.locator('label').filter({ hasText: 'Model profile' }).locator('option').allTextContents(), ['Fast']);
    record('same-origin health and model-specific readiness; unavailable Quality hidden');
    const cdp = await context.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 20, downloadThroughput: 10000000, uploadThroughput: 64000 });
    await picker('picker.wav');
    await page.getByLabel('Language', { exact: true }).selectOption('en');
    await page.getByLabel('Speaker count', { exact: true }).selectOption('2');
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await status('Transcribing');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
    const pickerId = id(); assert(pickerId);
    const observed = await page.evaluate(() => window.__observedUploadProgress);
    assert(observed.length > 0, 'Measured or indeterminate upload progress must appear.');
    assert(observed.some(value => /%|Upload complete/.test(value)), 'A computable upload event must be displayed for the fixture.');
    await page.reload(); await page.locator('.status-badge').waitFor(); assert.equal(id(), pickerId);
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    record('native file picker upload, measured upload state, active stage survives browser reload');
    const detailPath = `${BASE}/api/jobs/${pickerId}`;
    await page.waitForTimeout(500);
    const before = requests.filter(request => request.url === detailPath && request.method === 'GET').length;
    await page.waitForTimeout(2200);
    assert.equal(requests.filter(request => request.url === detailPath && request.method === 'GET').length, before);
    record('detail polling stops in terminal state');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    await page.getByRole('button', { name: 'Seek to 00:02', exact: true }).click();
    assert(Math.abs(await page.locator('audio').evaluate(audio => audio.currentTime) - 2) < 0.2);
    assert.equal(await page.locator('.segment.playing textarea').getAttribute('aria-label'), 'Transcript at 00:02');
    await page.locator('audio').evaluate(audio => audio.play());
    await page.waitForTimeout(300);
    assert(await page.locator('audio').evaluate(audio => audio.currentTime > 2.1 && !audio.paused));
    await page.locator('audio').evaluate(audio => audio.pause());
    record('decoded WAV playback, timestamp seeking, active segment follows player time');
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Edited synthetic fixture text.');
    await page.getByRole('textbox', { name: 'Display name for speaker_1', exact: true }).fill('Anonymous A');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText('Changes saved. All exports use this saved version.').waitFor();
    await page.reload();
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), 'Edited synthetic fixture text.');
    assert.equal(await page.getByRole('textbox', { name: 'Display name for speaker_1', exact: true }).inputValue(), 'Anonymous A');
    record('text and speaker display-name edits persist across full reload');
    for (const format of ['TXT', 'SRT', 'VTT', 'JSON']) {
      const downloaded = page.waitForEvent('download'); await page.getByRole('link', { name: format, exact: true }).click();
      const download = await downloaded;
      const content = await fs.readFile(await download.path(), 'utf8');
      assert(content.includes('Edited synthetic fixture text.')); assert(content.includes('Anonymous A'));
      if (format === 'SRT') assert(content.includes('00:00:00,000 --> 00:00:02,000'));
      if (format === 'VTT') assert(content.startsWith('WEBVTT'));
      if (format === 'JSON') assert.equal(JSON.parse(content).schemaVersion, 1);
      record(format + ' independently downloaded with saved edits and valid marker');
    }
    const revision = (await transcript(pickerId)).revision;
    const externalSave = await page.request.patch(`${detailPath}/transcript`, { headers: { 'X-LocalScribe-Token': await auth() }, data: { revision, texts: { s2: 'Concurrent saved synthetic edit.' }, names: {} } });
    assert.equal(externalSave.status(), 200);
    const draft = 'Unsaved local draft retained after conflict.';
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill(draft);
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.locator('[role=alert]').filter({ hasText: 'Your edits are still shown' }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), draft);
    assert.equal((await transcript(pickerId)).segments[0].editedText, 'Edited synthetic fixture text.');
    record('real revision conflict returns 409 and retains unsaved draft and prior saved text');
    await page.reload(); await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    await page.route('**/api/jobs/*/transcript', async route => route.request().method() === 'PATCH'
      ? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'fixture_save_failure', message: 'Synthetic save failure.' } }) }) : route.continue());
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Draft retained after synthetic write failure.');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText(/Synthetic save failure/).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), 'Draft retained after synthetic write failure.');
    assert.equal((await transcript(pickerId)).segments[0].editedText, 'Edited synthetic fixture text.');
    await page.unroute('**/api/jobs/*/transcript');
    record('injected HTTP save failure retains draft and does not alter server saved result');
    await home(); await drop('drop.wav');
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    record('external-style file drop imports and completes');
    await home(); await picker('slow-active.wav');
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click(); await status('Transcribing');
    const activeId = id();
    await home(); await drop('slow-queued.wav');
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click(); await status('Queued');
    const queuedId = id();
    await page.getByRole('button', { name: 'Cancel job', exact: true }).click(); await status('Cancelled');
    record('second import queues behind one active child; queued cancellation succeeds');
    await page.getByRole('button', { name: 'Retry job', exact: true }).click();
    await page.getByRole('button', { name: 'Keep current result', exact: true }).click();
    assert.equal((await (await page.request.get(`${BASE}/api/jobs/${queuedId}`)).json()).status, 'cancelled');
    await page.getByRole('button', { name: 'Retry job', exact: true }).click();
    await page.getByRole('button', { name: 'Retry recording', exact: true }).click(); await status('Queued');
    await page.getByRole('button', { name: 'Cancel job', exact: true }).click(); await status('Cancelled');
    record('retry confirmation can be dismissed or accepted; cancelled queued job requeues');
    await page.locator('.job-list button').filter({ hasText: 'slow-active.wav' }).click();
    await status('Transcribing'); await page.getByRole('button', { name: 'Cancel job', exact: true }).click(); await status('Cancelled');
    const stopped = await (await page.request.get(`${BASE}/api/jobs/${activeId}`)).json(); assert.equal(stopped.status, 'cancelled');
    await page.getByRole('button', { name: 'Retry job', exact: true }).click(); await page.getByRole('button', { name: 'Retry recording', exact: true }).click();
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    assert.equal((await (await page.request.get(`${BASE}/api/jobs/${activeId}`)).json()).attempt, 2);
    record('active process cancellation reaches terminal state; retry completes attempt 2');
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    await page.getByRole('button', { name: 'Keep recording', exact: true }).click();
    assert.equal((await page.request.get(`${BASE}/api/jobs/${activeId}`)).status(), 200);
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.locator('.drop-zone').waitFor();
    assert.equal((await page.request.get(`${BASE}/api/jobs/${activeId}`)).status(), 404);
    await assert.rejects(fs.stat(path.join(ROOT, 'store', 'jobs', activeId)), { code: 'ENOENT' });
    record('delete confirmation dismisses safely; accepted delete removes job and owned directory');
    for (const width of [1024, 760, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      assert.equal(overflow, false, `No horizontal overflow at ${width}px.`);
      await page.screenshot({ path: path.join(ROOT, `browser-${width}.png`), fullPage: false });
      await page.locator('.job-list button').filter({ hasText: 'picker.wav' }).first().click();
      await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
      await page.screenshot({ path: path.join(ROOT, `browser-detail-${width}.png`), fullPage: false });
      await home();
      record(`import and transcript layouts at ${width}px have no horizontal overflow`);
    }
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    record('all observed browser resources remain loopback; no uncaught page errors');
    const report = { engine: await browser.version(), checks, externalRequests: external.length, pageErrors: errors, requestCount: requests.length, inference: 'deterministic test-only child; no model weights' };
    await fs.writeFile(path.join(ROOT, 'browser-results.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } catch (error) {
    await page.screenshot({ path: path.join(ROOT, 'browser-failure.png'), fullPage: true });
    console.error(error); console.error('URL', page.url()); console.error('PAGE', await page.locator('body').innerText());
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
