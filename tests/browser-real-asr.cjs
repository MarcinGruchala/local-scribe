/* Real cached-model browser check. No model/readiness mocks; no transcript logs. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = 'http://127.0.0.1:8767';
const ROOT = '/private/tmp/localscribe-real';
const SAMPLE = process.env.REAL_SAMPLE || '/private/tmp/localscribe-validation/jfk.flac';
const LANGUAGE = process.env.REAL_LANGUAGE || 'en';
assert(['en', 'pl'].includes(LANGUAGE));

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true, timezoneId: 'Europe/Warsaw' });
  const page = await context.newPage();
  const external = []; const errors = []; const checks = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (!route.request().url().startsWith(BASE + '/')) { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const record = name => { checks.push(name); console.log('PASS ' + name); };
  try {
    await page.goto(BASE);
    const health = await (await page.request.get(BASE + '/api/health')).json();
    assert(health.models.fast.ready); assert.equal(health.models.diarization.ready, false);
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose a file', exact: true }).click();
    await (await chooser).setFiles(SAMPLE);
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isDisabled(), true);
    await page.getByLabel('Language', { exact: true }).selectOption(LANGUAGE);
    await page.locator('input[type=checkbox]').uncheck();
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isEnabled(), true);
    record('real readiness blocks missing diarization and permits explicit ASR-only selection');
    const start = performance.now();
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await page.locator('.status-badge').filter({ hasText: 'Completed' }).waitFor({ timeout: 180000 });
    await page.locator('.segment textarea').first().waitFor();
    const browserWallSeconds = (performance.now() - start) / 1000;
    const jobId = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'); assert(jobId);
    const detailPath = `${BASE}/api/jobs/${jobId}`;
    const job = await (await page.request.get(detailPath)).json();
    const transcript = await (await page.request.get(detailPath + '/transcript')).json();
    assert.equal(job.status, 'completed'); assert.equal(job.options.language, LANGUAGE); assert.equal(job.options.diarization, false);
    assert(transcript.segments.length > 0); assert.equal(transcript.language, LANGUAGE);
    assert.equal(transcript.provenance.asr.engine, 'mlx-whisper'); assert.equal(transcript.provenance.asr.device, 'gpu');
    assert.equal(transcript.provenance.diarization.status, 'disabled');
    record('actual local MLX GPU source-language transcription completes with diarization disabled');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    const lastSegment = transcript.segments[transcript.segments.length - 1];
    await page.locator('.timestamp').last().click();
    assert(Math.abs(await page.locator('audio').evaluate(audio => audio.currentTime) - lastSegment.start) < 1.1);
    await page.locator('audio').focus(); await page.locator('audio').press('Space');
    await page.waitForTimeout(300);
    assert.equal(await page.locator('audio').evaluate(audio => audio.paused), false, 'Native audio controls must start playback from keyboard.');
    await page.locator('audio').press('Space');
    assert.equal(await page.locator('audio').evaluate(audio => audio.paused), true);
    record('normalized real media seeks by timestamp and plays through native keyboard controls');
    await page.locator('.segment textarea').first().fill('Public-sample validation edit.');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText('Changes saved. All exports use this saved version.').waitFor();
    await page.reload(); await page.locator('.segment textarea').first().waitFor();
    assert.equal(await page.locator('.segment textarea').first().inputValue(), 'Public-sample validation edit.');
    record('real inference result supports persisted editing');
    for (const format of ['TXT', 'SRT', 'VTT', 'JSON']) {
      const pending = page.waitForEvent('download'); await page.getByRole('link', { name: format, exact: true }).click();
      const download = await pending; const value = await fs.readFile(await download.path(), 'utf8');
      assert(value.includes('Public-sample validation edit.'));
      if (format === 'JSON') { const json = JSON.parse(value); assert.equal(json.provenance.asr.revision, transcript.provenance.asr.revision); }
      record(format + ' real-result export downloaded independently');
    }
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click(); await page.locator('.drop-zone').waitFor();
    assert.equal((await page.request.get(detailPath)).status(), 404);
    record('real job deletes through confirmation and becomes unavailable');
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    const report = { engine: await browser.version(), checks, browserWallSeconds, duration: transcript.duration,
      stageTimings: transcript.stageTimings, model: { repo: transcript.provenance.asr.repo, revision: transcript.provenance.asr.revision, engine: transcript.provenance.asr.engine, device: transcript.provenance.asr.device },
      externalRequests: external.length, pageErrors: errors, diarization: 'explicitly disabled; required asset unavailable',
      language: LANGUAGE, qualityGate: 'not measured; public short sample only' };
    await fs.writeFile(ROOT + '/browser-real-asr-' + LANGUAGE + '-results.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } catch (error) { console.error(String(error)); process.exitCode = 1; }
  finally { await browser.close(); }
})();
