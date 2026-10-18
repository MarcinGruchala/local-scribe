/* Full real cached-model browser validation. No inference/readiness mocks. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const BASE = process.env.REAL_BASE || 'http://127.0.0.1:8767';
const ROOT = process.env.REAL_OUTPUT_ROOT || '/private/tmp/localscribe-full-offline';
const SAMPLE = process.env.REAL_SAMPLE || '/private/tmp/localscribe-validation/fleurs-en.wav';
const LANGUAGE = process.env.REAL_LANGUAGE || 'en';
const CASE = process.env.REAL_CASE || LANGUAGE;
const COUNT = process.env.REAL_SPEAKER_COUNT ? Number(process.env.REAL_SPEAKER_COUNT) : null;
assert(['auto', 'en', 'pl'].includes(LANGUAGE));
assert(COUNT === null || Number.isInteger(COUNT) && COUNT >= 1 && COUNT <= 10);
assert(/^[a-z0-9-]+$/.test(CASE));
assert.equal(new URL(BASE).hostname, '127.0.0.1');
const checkout = path.resolve(__dirname, '..');
assert.equal(path.resolve(ROOT) === checkout || path.resolve(ROOT).startsWith(checkout + path.sep), false);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true, timezoneId: 'Europe/Warsaw' });
  const page = await context.newPage();
  const external = []; const errors = []; const checks = [];
  let jobId = null;
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (!route.request().url().startsWith(BASE + '/')) { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const record = name => { checks.push(name); console.log('PASS ' + name); };
  async function cleanup() {
    if (!jobId) return;
    const detail = `${BASE}/api/jobs/${jobId}`;
    const token = (await (await page.request.get(BASE + '/api/session')).json()).token;
    const headers = { 'X-LocalScribe-Token': token };
    for (let attempt = 0; attempt < 40; attempt++) {
      const response = await page.request.get(detail);
      if (response.status() === 404) return;
      const job = await response.json();
      if (['completed', 'failed', 'cancelled', 'deletion_failed'].includes(job.status)) {
        const deleted = await page.request.delete(detail, { headers });
        assert.equal(deleted.status(), 204, 'Own validation job must be deleted.');
        return;
      }
      if (job.status !== 'cancelling') await page.request.post(detail + '/cancel', { headers });
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    throw new Error('Own validation job could not reach a terminal state for cleanup.');
  }
  try {
    await page.goto(BASE);
    const health = await (await page.request.get(BASE + '/api/health')).json();
    assert(health.models.fast.ready); assert(health.models.diarization.ready); assert(health.worker?.running);
    assert.equal(await page.locator('input[type=checkbox]').isChecked(), true);
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose a file', exact: true }).click();
    await (await chooser).setFiles(SAMPLE);
    await page.getByLabel('Language', { exact: true }).selectOption(LANGUAGE);
    await page.getByLabel('Speaker count', { exact: true }).selectOption(COUNT === null ? '' : String(COUNT));
    assert.equal(await page.getByRole('button', { name: 'Transcribe recording', exact: true }).isEnabled(), true);
    record('real complete readiness permits default speaker-enabled import');
    const started = performance.now();
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await page.locator('.status-badge').waitFor();
    jobId = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'); assert(jobId);
    await page.locator('.status-badge').filter({ hasText: 'Completed' }).waitFor({ timeout: 600000 });
    await page.locator('.segment textarea').first().waitFor();
    const browserWallSeconds = (performance.now() - started) / 1000;
    const detail = `${BASE}/api/jobs/${jobId}`;
    const job = await (await page.request.get(detail)).json();
    const localDirectory = job.localFiles.directory;
    assert.equal(job.localFiles.status, 'ready');
    for (const format of ['txt', 'srt', 'vtt', 'json']) {
      const exported = await page.request.get(detail + '/export?format=' + format);
      assert.equal(exported.status(), 200);
      assert.equal(await fs.readFile(path.join(localDirectory, 'transcript.' + format), 'utf8'), await exported.text());
    }
    record('real inference automatically saves four local files matching the canonical exports');
    const transcript = await (await page.request.get(detail + '/transcript')).json();
    assert.equal(job.status, 'completed'); assert.equal(job.options.language, LANGUAGE); assert.equal(job.options.diarization, true); assert.equal(job.options.speakerCount, COUNT);
    assert.equal(transcript.requestedLanguage, LANGUAGE);
    if (LANGUAGE !== 'auto') assert.equal(transcript.language, LANGUAGE);
    assert(transcript.segments.length > 0); assert(transcript.speakers.length > 0);
    assert(transcript.regularTurns.length > 0); assert(transcript.exclusiveTurns.length > 0);
    assert.equal(transcript.warnings.some(warning => warning.code === 'diarization_failed'), false);
    assert.equal(transcript.provenance.asr.engine, 'mlx-whisper'); assert.equal(transcript.provenance.asr.device, 'gpu');
    assert.equal(transcript.provenance.diarization.engine, 'pyannote.audio'); assert.equal(transcript.provenance.diarization.device, 'cpu');
    assert.equal(transcript.provenance.diarization.ready, true);
    for (const profile of ['fast', 'diarization']) {
      const provenance = profile === 'fast' ? transcript.provenance.asr : transcript.provenance.diarization;
      assert.equal(job.modelSettings[profile].revision, provenance.revision);
      assert.equal(transcript.provenance.requestedModels[profile].revision, provenance.revision);
      assert.equal(health.models[profile].revision, provenance.revision);
    }
    assert.deepEqual(transcript.speakers.map(speaker => speaker.id), transcript.speakers.map((_, index) => `speaker_${index + 1}`));
    const known = new Set(transcript.speakers.map(speaker => speaker.id));
    for (const collection of [transcript.segments, transcript.words, transcript.regularTurns, transcript.exclusiveTurns]) {
      assert(collection.every(item => item.speakerId === null || known.has(item.speakerId)));
    }
    assert(transcript.provenance.runtime.packages.mlx); assert(transcript.provenance.runtime.packages.torchcodec);
    record('actual MLX GPU transcription and CPU Community-1 produce stable speaker references and both turn forms');
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
    const last = transcript.segments[transcript.segments.length - 1];
    await page.locator('.timestamp').last().click();
    assert(Math.abs(await page.locator('audio').evaluate(audio => audio.currentTime) - last.start) < 1.1);
    await page.locator('audio').focus(); await page.locator('audio').press('Space'); await page.waitForTimeout(300);
    assert.equal(await page.locator('audio').evaluate(audio => audio.paused), false);
    await page.locator('audio').press('Space'); assert.equal(await page.locator('audio').evaluate(audio => audio.paused), true);
    assert(await page.locator('.segment.playing').count() > 0);
    record('real normalized media seeks and plays with active transcript segment');
    const named = transcript.speakers.find(speaker => transcript.segments.some(segment => segment.speakerId === speaker.id)); assert(named);
    await page.locator('.segment textarea').first().fill('Public-sample validation edit.');
    await page.getByRole('textbox', { name: `Display name for ${named.id}`, exact: true }).fill('Validation speaker A');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText('Changes saved. All exports use this saved version.').waitFor();
    await page.reload(); await page.locator('.segment textarea').first().waitFor();
    assert.equal(await page.locator('.segment textarea').first().inputValue(), 'Public-sample validation edit.');
    assert.equal(await page.getByRole('textbox', { name: `Display name for ${named.id}`, exact: true }).inputValue(), 'Validation speaker A');
    const saved = await (await page.request.get(detail + '/transcript')).json();
    assert.deepEqual(saved.speakers.map(speaker => speaker.id), transcript.speakers.map(speaker => speaker.id));
    assert.deepEqual(saved.regularTurns, transcript.regularTurns); assert.deepEqual(saved.exclusiveTurns, transcript.exclusiveTurns);
    record('text and real speaker-name edits persist through reload without changing speaker IDs or turns');
    for (const format of ['TXT', 'SRT', 'VTT', 'JSON']) {
      const pending = page.waitForEvent('download'); await page.getByRole('link', { name: format, exact: true }).click();
      const download = await pending; const contents = await fs.readFile(await download.path(), 'utf8');
      assert.equal(await fs.readFile(path.join(localDirectory, 'transcript.' + format.toLowerCase()), 'utf8'), contents);
      assert(contents.includes('Public-sample validation edit.')); assert(contents.includes('Validation speaker A'));
      if (format === 'SRT') assert(/\d{2}:\d{2}:\d{2},\d{3} -->/.test(contents));
      if (format === 'VTT') assert(contents.startsWith('WEBVTT'));
      if (format === 'JSON') {
        const exported = JSON.parse(contents); assert.equal(exported.provenance.diarization.revision, transcript.provenance.diarization.revision);
        assert.deepEqual(exported.regularTurns, transcript.regularTurns); assert.deepEqual(exported.exclusiveTurns, transcript.exclusiveTurns);
      }
      record(format + ' complete-result export independently downloads saved edits');
    }
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    assert((await page.getByRole('alertdialog').innerText()).includes(job.name));
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click(); await page.locator('.drop-zone').waitFor();
    assert.equal((await page.request.get(detail)).status(), 404); jobId = null;
    await assert.rejects(fs.stat(localDirectory), { code: 'ENOENT' });
    record('only the new validation recording is deleted through named confirmation');
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    const report = { browser: await browser.version(), checks, case: CASE, requestedLanguage: LANGUAGE, detectedLanguage: transcript.language,
      duration: transcript.duration, browserWallSeconds, stageTimings: transcript.stageTimings,
      counts: { segments: transcript.segments.length, speakers: transcript.speakers.length, regularTurns: transcript.regularTurns.length, exclusiveTurns: transcript.exclusiveTurns.length },
      models: { asr: { repo: transcript.provenance.asr.repo, revision: transcript.provenance.asr.revision, engine: transcript.provenance.asr.engine, device: transcript.provenance.asr.device },
        diarization: { repo: transcript.provenance.diarization.repo, revision: transcript.provenance.diarization.revision, engine: transcript.provenance.diarization.engine, device: transcript.provenance.diarization.device } },
      warningCodes: transcript.warnings.map(warning => warning.code), externalRequests: external.length, pageErrors: errors,
      qualityGate: 'not measured; short public or constructed sample functional validation' };
    await fs.mkdir(ROOT, { recursive: true }); await fs.writeFile(`${ROOT}/browser-full-${CASE}-results.json`, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } catch (error) { console.error(String(error)); process.exitCode = 1; }
  finally {
    try { await cleanup(); } catch (error) { console.error(String(error)); process.exitCode = 1; }
    await browser.close();
  }
})();
