/* Actual-browser listening view checks against the fixture-only server. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); const errors = []; const checks = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => route.request().url().startsWith(BASE + '/') ? route.continue() : route.abort());
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  const review = () => page.getByRole('button', { name: 'Listen & review', exact: true }).click();
  const transcriptView = () => page.getByRole('button', { name: 'Transcript', exact: true }).click();
  const audioTime = () => page.locator('audio').evaluate(audio => audio.currentTime);
  let jobId;
  try {
    await page.goto(BASE);
    await page.getByLabel('Choose a recording', { exact: true }).setInputFiles(ROOT + '/fixtures/picker.wav');
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    jobId = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    await review();
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('2.4');
    assert(Math.abs(await audioTime() - 2.4) < 0.15);
    assert.equal(await page.locator('.segment.playing textarea').getAttribute('aria-label'), 'Transcript at 00:02');
    await page.getByLabel('Playback speed', { exact: true }).selectOption('0.75');
    await page.getByRole('button', { name: 'Play', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('audio').currentTime > 2.5 && !document.querySelector('audio').paused);
    await transcriptView();
    assert.equal(await page.locator('audio').evaluate(audio => audio.paused), false);
    assert.equal(await page.locator('audio').evaluate(audio => audio.playbackRate), 0.75);
    await review(); await page.getByRole('button', { name: 'Pause', exact: true }).click();
    assert.equal(await page.locator('audio').evaluate(audio => audio.paused), true);
    record('scrubbing, active segment, playback, speed and uninterrupted view switching');

    await page.getByRole('button', { name: 'Back 5 seconds', exact: true }).click();
    assert.equal(await audioTime(), 0);
    await page.getByRole('button', { name: 'Forward 5 seconds', exact: true }).click();
    assert(Math.abs(await audioTime() - 5) < 0.15);
    await page.getByRole('button', { name: 'Forward 5 seconds', exact: true }).click();
    assert.equal(await audioTime(), 6);
    await page.getByRole('button', { name: 'Hear Speaker 1', exact: true }).click();
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    assert(await audioTime() < 1);
    await page.getByRole('button', { name: 'Seek to 00:02', exact: true }).click();
    assert(Math.abs(await audioTime() - 2) < 0.15);
    record('skip controls clamp to media bounds; speaker previews and timestamps seek correctly');

    await page.getByRole('textbox', { name: 'Display name for speaker_2', exact: true }).fill('Review Speaker');
    await page.getByRole('textbox', { name: 'Transcript at 00:02', exact: true }).fill('Reviewed synthetic transcript.');
    assert.equal(await page.locator('.now-speaking').innerText(), 'Review Speaker');
    await transcriptView();
    assert.equal(await page.getByRole('textbox', { name: 'Display name for speaker_2', exact: true }).inputValue(), 'Review Speaker');
    await review();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:02', exact: true }).inputValue(), 'Reviewed synthetic transcript.');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText('Changes saved. All exports use this saved version.', { exact: true }).waitFor();
    const saved = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=json`)).json();
    assert.equal(saved.speakers[1].displayName, 'Review Speaker');
    assert.equal(saved.segments[1].editedText, 'Reviewed synthetic transcript.');
    await page.reload(); await review();
    assert.equal(await page.getByRole('textbox', { name: 'Display name for speaker_2', exact: true }).inputValue(), 'Review Speaker');
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:02', exact: true }).inputValue(), 'Reviewed synthetic transcript.');
    record('speaker names and text survive view switches, save, JSON export and reload');

    for (const width of [1440, 1024, 760, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
      await page.locator('.recording-views').scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${ROOT}/browser-review-${width}.png`, fullPage: true });
    }
    record('listening view has no horizontal overflow at desktop, tablet and phone widths');

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.route('**/api/jobs/*/transcript', async route => {
      const response = await route.fetch(); const value = await response.json();
      value.segments = Array.from({ length: 30 }, (_, i) => ({ ...value.segments[i % 2], id: `review-fixture-${i}`, start: i / 5, end: (i + 1) / 5 }));
      await route.fulfill({ response, json: value });
    });
    await page.reload(); await review();
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('5');
    await page.waitForFunction(() => document.querySelector('.segments').scrollTop > 500);
    await page.getByRole('checkbox', { name: 'Follow audio', exact: true }).uncheck();
    const scrollTop = await page.locator('.segments').evaluate(element => element.scrollTop);
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('0');
    assert.equal(await page.locator('.segments').evaluate(element => element.scrollTop), scrollTop);
    await page.getByRole('checkbox', { name: 'Follow audio', exact: true }).check();
    await page.waitForFunction(() => document.querySelector('.segments').scrollTop === 0);
    record('follow audio scrolls within the transcript and can be disabled for manual browsing');

    await page.unroute('**/api/jobs/*/transcript');
    await page.route('**/api/jobs/*/media', route => route.fulfill({ status: 404, body: 'Fixture audio unavailable' }));
    await page.reload(); await review();
    await page.getByRole('alert').filter({ hasText: 'The recording audio could not be loaded.' }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Play', exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:02', exact: true }).inputValue(), 'Reviewed synthetic transcript.');
    record('missing audio disables playback with an explicit error and preserves the editable transcript');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ checks, pageErrors: errors }));
  } catch (error) {
    await page.screenshot({ path: ROOT + '/browser-review-failure.png', fullPage: true });
    console.error(error); process.exitCode = 1;
  } finally {
    if (jobId) {
      const session = await (await page.request.get(BASE + '/api/session')).json();
      await page.request.delete(`${BASE}/api/jobs/${jobId}`, { headers: { 'X-LocalScribe-Token': session.token } });
    }
    await browser.close();
  }
})();
