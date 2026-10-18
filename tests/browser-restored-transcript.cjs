/* Read-only browser verification of a real restored long recording; no inference. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = process.env.REAL_BASE || 'http://127.0.0.1:8768';
const JOB = process.env.RESTORED_JOB;
assert(JOB && /^[a-f0-9]{32}$/.test(JOB), 'Provide the restored job ID.');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); const errors = []; const external = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (route.request().url().startsWith(BASE + '/')) return route.continue();
    external.push(true); return route.abort();
  });
  let step = 'read restored metadata';
  let privateName = '';
  try {
    const job = await (await page.request.get(`${BASE}/api/jobs/${JOB}`)).json();
    privateName = job.name;
    const before = await (await page.request.get(`${BASE}/api/jobs/${JOB}/transcript`)).json();
    assert.equal(job.status, 'completed'); assert(job.duration > 3600);
    assert.equal(before.provenance.restoration.inferenceRerun, false);
    step = 'open history';
    await page.goto(BASE + '/#page=history');
    await page.getByRole('button', { name: `Listen & review ${job.name}`, exact: true }).click();
    await page.getByRole('slider', { name: 'Audio position', exact: true }).waitFor();
    step = 'load recording audio';
    await page.waitForFunction(() => document.querySelector('audio')?.readyState >= 1);
    assert.equal(await page.locator('.segment textarea').count(), before.segments.length);
    const late = before.segments.find(segment => segment.start > 3600); assert(late);
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill(String(Math.round(late.start * 10) / 10));
    assert(Math.abs(await page.locator('audio').evaluate(audio => audio.currentTime) - late.start) < .2);
    step = 'play beyond one hour';
    await page.getByRole('button', { name: 'Play', exact: true }).click();
    await page.waitForFunction(start => document.querySelector('audio').currentTime > start + .05, late.start);
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    step = 'check editable draft';
    const first = page.locator('.segment textarea').first();
    const original = await first.inputValue();
    await first.fill(original + ' [unsaved verification draft]');
    await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('0');
    assert.equal(await first.inputValue(), original + ' [unsaved verification draft]');
    assert.equal(await page.getByRole('button', { name: 'Save changes', exact: true }).isEnabled(), true);
    page.once('dialog', dialog => dialog.accept());
    step = 'reload unchanged saved transcript';
    await page.reload();
    await page.locator('.segment textarea').first().waitFor();
    assert.equal(await page.locator('.segment textarea').first().inputValue(), original);
    const after = await (await page.request.get(`${BASE}/api/jobs/${JOB}/transcript`)).json();
    assert.deepEqual(after, before);
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    const report = { historyVisible: true, segmentCount: before.segments.length, duration: before.duration,
      playbackBeyondHour: true, editableDraft: true, savedTranscriptUnchanged: true,
      externalRequests: 0, pageErrors: 0, inferenceRerun: false };
    if (process.env.REAL_REPORT) await fs.writeFile(process.env.REAL_REPORT, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } catch (error) {
    const diagnostic = step === 'load recording audio' ? error.message.split('\n')[0].replaceAll(privateName, '<recording>').slice(0, 160) : error.name;
    console.error(`Restored recording browser verification failed at ${step}: ${diagnostic}`); process.exitCode = 1;
  }
  finally { await browser.close(); }
})();
