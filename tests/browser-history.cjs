/* Archive navigation and pagination checks against the fixture-only server. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage(); const errors = []; const checks = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => route.request().url().startsWith(BASE + '/') ? route.continue() : route.abort());
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  const historyLink = () => page.getByRole('link', { name: 'Transcript history', exact: true }).first();
  try {
    const listing = await (await page.request.get(`${BASE}/api/jobs?limit=100`)).json();
    const completed = listing.jobs.filter(job => ['completed', 'completed_with_warnings'].includes(job.status));
    assert(completed.length >= 2, 'Run the existing browser smoke workflow to create fixture transcripts first.');
    const older = completed[1];
    const savedTranscript = await (await page.request.get(`${BASE}/api/jobs/${older.id}/transcript`)).json();
    const jobs = Array.from({ length: 125 }, (_, i) => ({ ...completed[0], id: `archive-fixture-${i}`, name: `Failed fixture ${i}.wav`, status: 'failed' }));
    jobs[2] = { ...completed[0], name: 'Recent saved interview.wav', options: { ...completed[0].options, language: 'en' } };
    jobs[115] = { ...older, name: 'Żółć archived interview.wav', status: 'completed_with_warnings', options: { ...older.options, language: 'pl' } };
    const offsets = [];
    await page.route('**/api/jobs?*', route => {
      const params = new URL(route.request().url()).searchParams;
      const offset = Number(params.get('offset') || 0); const limit = Number(params.get('limit') || 20);
      offsets.push(offset);
      return route.fulfill({ json: { jobs: jobs.slice(offset, offset + limit), total: jobs.length } });
    });
    await page.goto(BASE); await historyLink().click();
    await page.getByText('2 of 2 saved recordings · newest first', { exact: true }).waitFor();
    assert.equal(await page.locator('.history-recordings li').count(), 2);
    assert(offsets.includes(100), 'The archive loads beyond the first two metadata pages.');
    await page.getByRole('searchbox', { name: 'Search recordings', exact: true }).fill('żółć');
    assert.equal(await page.locator('.history-recordings li').count(), 1);
    await page.getByLabel('Filter by transcription language', { exact: true }).selectOption('en');
    await page.getByRole('heading', { name: 'No matching recordings', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await page.getByLabel('Filter by transcription language', { exact: true }).selectOption('pl');
    assert.equal(await page.locator('.history-recordings li').count(), 1);
    await page.getByText('Review warnings', { exact: true }).waitFor();
    record('archive loads all metadata pages, excludes unfinished jobs, and supports Unicode file search and language filters');

    await page.getByRole('button', { name: 'Listen & review Żółć archived interview.wav', exact: true }).click();
    await page.getByRole('slider', { name: 'Audio position', exact: true }).waitFor();
    assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'), older.id);
    assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('view'), 'review');
    assert.equal(await page.locator('.segment textarea').first().inputValue(), savedTranscript.segments[0].editedText ?? savedTranscript.segments[0].text);
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('2.4');
    assert(Math.abs(await page.locator('audio').evaluate(audio => audio.currentTime) - 2.4) < 0.15);
    await page.reload(); await page.getByRole('slider', { name: 'Audio position', exact: true }).waitFor();
    record('historical recordings open directly in review with saved text, seekable audio and a reloadable URL');

    const draft = 'Unsaved archive review draft.';
    await page.locator('.segment textarea').first().fill(draft);
    const dialogs = [];
    const dismiss = dialog => { dialogs.push(dialog.type()); return dialog.dismiss(); };
    page.on('dialog', dismiss);
    await page.getByRole('button', { name: 'Transcript', exact: true }).click();
    await page.getByRole('button', { name: 'Listen & review', exact: true }).click();
    assert.equal(await page.locator('.segment textarea').first().inputValue(), draft);
    assert.deepEqual(dialogs, []);
    await historyLink().click();
    await page.waitForFunction(() => new URLSearchParams(window.location.hash.slice(1)).get('view') === 'review');
    assert.equal(await page.locator('.segment textarea').first().inputValue(), draft);
    assert.deepEqual(dialogs, ['confirm']);
    page.removeListener('dialog', dismiss);
    page.once('dialog', dialog => dialog.accept());
    await page.locator('.history-back').click();
    await page.getByRole('heading', { name: 'Transcript history', exact: true }).waitFor();
    await page.getByText('2 of 2 saved recordings · newest first', { exact: true }).waitFor();
    record('view switching keeps drafts without prompting, while leaving a dirty historical transcript requires explicit discard');

    for (const width of [1280, 760, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
      await page.screenshot({ path: `${ROOT}/browser-history-${width}.png`, fullPage: true });
    }
    record('history layout fits desktop, tablet and mobile widths');

    await page.unroute('**/api/jobs?*');
    await page.route('**/api/jobs?*', route => route.fulfill({ status: 500, json: { error: { message: 'Synthetic archive load failure.' } } }));
    await page.getByRole('button', { name: 'Refresh history', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'The list may be incomplete.' }).waitFor();
    await page.unroute('**/api/jobs?*');
    await page.route('**/api/jobs?*', route => route.fulfill({ json: { jobs: [], total: 0 } }));
    await page.getByRole('button', { name: 'Refresh history', exact: true }).click();
    await page.getByRole('heading', { name: 'No saved transcripts yet', exact: true }).waitFor();
    record('loading failures are explicit and refresh recovers to a useful empty state');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ checks, pageErrors: errors }));
  } catch (error) {
    await page.screenshot({ path: ROOT + '/browser-history-failure.png', fullPage: true });
    console.error(error); process.exitCode = 1;
  } finally { await browser.close(); }
})();
