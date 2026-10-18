/* Focused actual-browser dirty-navigation and loaded-history regression. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Europe/Warsaw' });
  const page = await context.newPage(); const checks = []; const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => route.request().url().startsWith(BASE + '/') ? route.continue() : route.abort());
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  const seed = JSON.parse(await fs.readFile(ROOT + '/pagination-seed.json', 'utf8'));
  const draft = 'Unsaved synthetic navigation draft.';
  let selected;
  async function respond(action, accept, type = 'confirm') {
    const awaited = page.waitForEvent('dialog'); const operation = action(); const dialog = await awaited;
    assert.equal(dialog.type(), type); if (accept) await dialog.accept(); else await dialog.dismiss();
    try { await operation; } catch (error) { if (type !== 'beforeunload' || !/ERR_ABORTED|Timeout/.test(String(error))) throw error; }
  }
  async function retained() {
    await page.waitForFunction(id => new URLSearchParams(window.location.hash.slice(1)).get('job') === id, selected.id);
    assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'), selected.id);
    assert.equal(await page.locator('.segment textarea').first().inputValue(), draft);
  }
  try {
    await page.goto(BASE); await page.getByText('Local engine ready', { exact: true }).waitFor();
    assert.equal(await page.locator('.job-list button').count(), 50);
    await page.getByRole('button', { name: 'Load older recordings', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.job-list button').length > 50);
    const loaded = await page.locator('.job-list button').count();
    await page.waitForTimeout(2400); assert.equal(await page.locator('.job-list button').count(), loaded);
    await page.locator('.job-list button').filter({ hasText: 'Pagination terminal 00.wav' }).first().waitFor();
    record('51 seeded terminal jobs and one active child retain loaded older history through repeated polling');
    const listing = await (await page.request.get(BASE + '/api/jobs?limit=100')).json();
    while (!listing.jobs.some(job => job.status === 'completed' && job.name === 'picker.wav') && listing.jobs.length < listing.total) {
      const next = await (await page.request.get(`${BASE}/api/jobs?limit=100&offset=${listing.jobs.length}`)).json(); listing.jobs.push(...next.jobs);
    }
    while (await page.locator('.job-list button').count() < listing.jobs.length) {
      const previous = await page.locator('.job-list button').count();
      await page.getByRole('button', { name: 'Load older recordings', exact: true }).click();
      await page.waitForFunction(previous => document.querySelectorAll('.job-list button').length > previous, previous);
    }
    selected = listing.jobs.find(job => job.status === 'completed' && job.name === 'picker.wav'); assert(selected);
    const other = listing.jobs.find(job => job.status === 'completed' && job.name === 'drop.wav'); assert(other);
    await page.locator('.job-list button').filter({ hasText: selected.name }).first().click();
    await page.locator('.segment textarea').first().waitFor();
    const savedText = await page.locator('.segment textarea').first().inputValue();
    await page.locator('.segment textarea').first().fill(draft);
    await respond(() => page.goBack(), false); await retained();
    record('browser Back decline restores current hash and preserves dirty draft');
    await respond(() => page.locator('a.new-recording').click(), false); await retained();
    record('New recording decline preserves dirty draft');
    await respond(() => page.locator('.brand').click(), false); await retained();
    record('home decline preserves dirty draft');
    await respond(() => page.locator('.job-list button').filter({ hasText: other.name }).first().click(), false); await retained();
    record('history selection decline preserves dirty draft');
    await respond(() => page.evaluate(id => { window.location.hash = `job=${id}`; }, other.id), false); await retained();
    record('direct hash change decline preserves dirty draft');
    await respond(() => page.locator('a.new-recording').click(), true); await page.locator('.drop-zone').waitFor();
    await page.locator('.job-list button').filter({ hasText: selected.name }).first().click();
    await page.locator('.segment textarea').first().waitFor();
    assert.equal(await page.locator('.segment textarea').first().inputValue(), savedText);
    record('explicit discard navigates and keeps the previously saved result');
    await page.locator('.segment textarea').first().fill(`Saved synthetic navigation check ${Date.now()}.`);
    await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await page.getByText('Changes saved. All exports use this saved version.').waitFor();
    const unexpected = []; const dismissUnexpected = dialog => { unexpected.push(dialog.type()); dialog.dismiss(); };
    page.on('dialog', dismissUnexpected);
    await page.locator('a.new-recording').click(); await page.locator('.drop-zone').waitFor();
    assert.deepEqual(unexpected, []); page.removeListener('dialog', dismissUnexpected);
    record('successful save clears navigation guard before changing views');
    await page.locator('.job-list button').filter({ hasText: selected.name }).first().click(); await page.locator('.segment textarea').first().waitFor();
    await page.locator('.segment textarea').first().fill(draft);
    await respond(() => page.reload({ timeout: 2000 }), false, 'beforeunload'); await retained();
    record('native beforeunload still guards external refresh and decline retains draft');
    const deletionDialogs = []; const rejectExtra = dialog => { deletionDialogs.push(dialog.type()); dialog.dismiss(); };
    page.on('dialog', rejectExtra);
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    assert((await page.getByRole('alertdialog').innerText()).includes(selected.name));
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.locator('.drop-zone').waitFor(); assert.deepEqual(deletionDialogs, []); page.removeListener('dialog', rejectExtra);
    record('confirmed deletion of dirty disposable job navigates without a second discard prompt');
    const health = await (await page.request.get(BASE + '/api/health')).json();
    const stoppedMessage = 'Local worker stopped. Restart the application to recover interrupted work.';
    await page.route(BASE + '/api/health', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...health, ready: false, worker: { running: false, message: stoppedMessage } }) }));
    await page.getByRole('button', { name: 'Refresh', exact: true }).click(); await page.getByText(stoppedMessage, { exact: true }).waitFor();
    record('stopped-worker readiness shows actionable restart guidance');
    assert.deepEqual(errors, []);
    await fs.writeFile(ROOT + '/browser-navigation-results.json', JSON.stringify({ engine: await browser.version(), checks, seededTerminalJobs: 51, loadedHistoryCount: loaded, pageErrors: errors }, null, 2));
  } catch (error) { console.error(String(error)); process.exitCode = 1; }
  finally {
    const token = (await (await page.request.get(BASE + '/api/session')).json()).token;
    await page.request.post(`${BASE}/api/jobs/${seed.activeId}/cancel`, { headers: { 'X-LocalScribe-Token': token } });
    await browser.close();
  }
})();
