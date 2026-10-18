/* Focused fixture-only checks for degraded, overlap, disabled and failure states. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1024, height: 900 }, timezoneId: 'Europe/Warsaw' });
  const page = await context.newPage(); const checks = []; const external = []; const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => route.request().url().startsWith(BASE + '/') ? route.continue() : (external.push(route.request().url()), route.abort()));
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  async function picker(filename) {
    const chooser = page.waitForEvent('filechooser'); const button = page.getByRole('button', { name: 'Choose a file', exact: true });
    await button.focus(); await button.press('Enter'); await (await chooser).setFiles(`${ROOT}/fixtures/${filename}`);
  }
  async function syntheticDrop(names) {
    const transfer = await page.evaluateHandle(names => {
      const data = new DataTransfer(); names.forEach(name => data.items.add(new File(['synthetic drop'], name, { type: 'audio/wav' }))); return data;
    }, names);
    await page.locator('.drop-zone').dispatchEvent('drop', { dataTransfer: transfer }); await transfer.dispose();
  }
  async function submit() { const button = page.getByRole('button', { name: 'Transcribe recording', exact: true }); await button.focus(); await button.press('Enter'); }
  async function home() { await page.locator('a.new-recording').click(); await page.locator('.drop-zone').waitFor(); }
  try {
    await fs.writeFile(ROOT + '/missing-models', 'test-only readiness flag');
    await page.goto(BASE); await page.getByText('Setup needed', { exact: true }).waitFor();
    await picker('degraded.wav');
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isDisabled(), true);
    await page.getByText('Set up the selected local transcription model before importing.').waitFor();
    await fs.unlink(ROOT + '/missing-models');
    await page.getByRole('button', { name: 'Refresh', exact: true }).click(); await page.getByText('Local engine ready', { exact: true }).waitFor();
    record('missing cached ASR assets show actionable readiness and disable submission');
    await fs.writeFile(ROOT + '/fixtures/empty.wav', '');
    await page.getByLabel('Choose a recording', { exact: true }).setInputFiles(ROOT + '/fixtures/empty.wav');
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isDisabled(), true);
    assert.equal(await page.locator('.drop-zone strong').innerText(), 'Drop your recording here');
    await picker('degraded.wav'); await syntheticDrop(['first.wav', 'second.wav']);
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isDisabled(), true);
    assert.equal(await page.locator('.drop-zone strong').innerText(), 'Drop your recording here');
    record('rejected empty file and multi-file drop clear prior valid selection and disable import');
    await picker('degraded.wav');
    await page.route(BASE + '/api/jobs', async route => { if (route.request().method() === 'POST') await new Promise(resolve => setTimeout(resolve, 2000)); await route.continue(); });
    await submit(); await page.locator('.upload-progress').waitFor(); await syntheticDrop(['replacement.wav']);
    assert.equal(await page.locator('.drop-zone strong').innerText(), 'degraded.wav');
    record('drop during pending upload cannot replace the displayed recording');
    await page.locator('.status-badge').filter({ hasText: 'Completed with warnings' }).waitFor(); await page.unroute(BASE + '/api/jobs');
    await page.getByText('Speaker diarization failed. Text is preserved; speaker labels are unavailable.').waitFor();
    assert.equal(await page.locator('.segment-meta strong').allTextContents().then(values => values.every(value => value === 'Speaker unavailable')), true);
    assert.equal(await page.locator('.segment textarea').first().inputValue(), 'Synthetic browser fixture first speaker.');
    assert.equal(await page.locator('.speaker-names input').count(), 0); assert.equal(await page.getByText('Overlapping speech', { exact: true }).count(), 0);
    record('keyboard picker and Enter submission complete degraded job with preserved text, warning and explicit unknown speakers');
    await home(); await picker('overlap.wav'); await submit();
    await page.getByText('Overlapping speech', { exact: true }).waitFor();
    assert.equal(await page.locator('.segment-meta strong').first().innerText(), 'Speaker 1');
    record('successful speaker fixture displays overlap indicator and stable anonymous speaker label');
    await home(); await picker('text-only.wav'); await page.locator('input[type=checkbox]').uncheck(); await submit();
    await page.locator('.segment textarea').first().waitFor();
    assert.equal(await page.locator('.status-badge').innerText(), 'Completed');
    assert.equal(await page.locator('.job-meta').innerText().then(value => value.includes('Text only')), true);
    assert.equal(await page.locator('.segment-meta strong').allTextContents().then(values => values.every(value => value === 'Text only')), true);
    assert.equal(await page.locator('.notice.warning').count(), 0);
    const jobId = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job');
    const detailPath = `${BASE}/api/jobs/${jobId}`;
    const result = await (await page.request.get(detailPath + '/transcript')).json();
    assert.equal(result.provenance.diarization.status, 'disabled');
    record('intentional ASR-only result shows Text only without diarization-failure warning');
    const job = await (await page.request.get(detailPath)).json();
    await page.route(detailPath, route => route.request().method() === 'DELETE'
      ? route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'deletion_failed', message: 'Synthetic deletion failure. Retry deletion.' } }) })
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...job, status: 'deletion_failed', error: { code: 'deletion_failed', message: 'Synthetic deletion failure. Retry deletion.' } }) }));
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click(); assert((await page.getByRole('alertdialog').innerText()).includes('text-only.wav')); await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.getByRole('button', { name: 'Retry deletion', exact: true }).waitFor();
    await page.unroute(detailPath);
    await page.getByRole('button', { name: 'Retry deletion', exact: true }).click(); await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.locator('.drop-zone').waitFor(); assert.equal((await page.request.get(detailPath)).status(), 404);
    record('injected deletion failure refreshes retry state; confirmed retry deletes actual fixture job');
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    await fs.writeFile(ROOT + '/browser-state-results.json', JSON.stringify({ engine: await browser.version(), checks, externalRequests: external.length, pageErrors: errors, inference: 'test-only deterministic child' }, null, 2));
  } catch (error) { console.error(String(error)); process.exitCode = 1; }
  finally { await fs.rm(ROOT + '/missing-models', { force: true }); await browser.close(); }
})();
