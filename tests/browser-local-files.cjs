/* Real Chromium + filesystem checks with the deterministic, model-free HTTP harness. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const BASE = 'http://127.0.0.1:8766';
const ROOT = '/private/tmp/localscribe-browser';
const FORMATS = ['txt', 'srt', 'vtt', 'json'];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage(); const checks = []; const errors = []; const external = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    if (route.request().url().startsWith(BASE + '/')) return route.continue();
    external.push(route.request().url()); return route.abort();
  });
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  let jobId;
  const job = async () => (await page.request.get(`${BASE}/api/jobs/${jobId}`)).json();
  async function filesMatchExports(expectedText, expectedName) {
    const current = await job(); assert.equal(current.localFiles.status, 'ready');
    const directory = current.localFiles.directory;
    assert.equal(current.localFiles.files.length, 4);
    assert.equal(await page.getByLabel('Transcript folder', { exact: true }).inputValue(), directory);
    for (const format of FORMATS) {
      const filename = path.join(directory, 'transcript.' + format);
      assert(current.localFiles.files.includes(filename));
      const content = await fs.readFile(filename, 'utf8');
      const exported = await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=${format}`);
      assert.equal(exported.status(), 200); assert.equal(content, await exported.text());
      assert(content.includes(expectedText)); assert(content.includes(expectedName));
    }
    return directory;
  }
  try {
    await page.goto(BASE); await page.getByText('Local engine ready', { exact: true }).waitFor();
    const health = await (await page.request.get(BASE + '/api/health')).json();
    assert.equal(await page.getByLabel('Recordings and transcripts folder', { exact: true }).inputValue(), health.storage.dataRoot);
    await page.getByRole('button', { name: 'Copy recordings and transcripts folder', exact: true }).click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), health.storage.dataRoot);
    record('configured absolute storage path is visible and copies to the clipboard');
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Choose a file', exact: true }).click();
    await (await chooser).setFiles(path.join(ROOT, 'fixtures', 'picker.wav'));
    await page.getByRole('button', { name: 'Transcribe recording', exact: true }).click();
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    jobId = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'); assert(jobId);
    await page.locator('.local-file-names span').filter({ hasText: 'transcript.json' }).waitFor();
    const directory = await filesMatchExports('Synthetic browser fixture first speaker.', 'Speaker 1');
    record('completed fixture publishes all four readable files matching independent HTTP exports');
    await page.getByRole('button', { name: 'Copy transcript folder', exact: true }).click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), directory);
    record('completed recording exposes its own copyable transcript folder');
    const edited = 'Saved synthetic local file revision.';
    const name = 'Anonymous local speaker';
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill(edited);
    await page.getByRole('textbox', { name: 'Display name for speaker_1', exact: true }).fill(name);
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByText('Changes saved. All exports use this saved version.').waitFor();
    await filesMatchExports(edited, name);
    assert.equal((await job()).localFiles.savedRevision, 1);
    record('saved text and speaker-name edits update every local file and descriptor revision');
    await page.reload(); await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), edited);
    await filesMatchExports(edited, name);
    await page.locator('a.new-recording').click();
    const history = page.locator('.job-list button').filter({ hasText: 'picker.wav' }).first();
    await history.click(); await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).waitFor();
    assert.equal(new URLSearchParams(new URL(page.url()).hash.slice(1)).get('job'), jobId);
    record('reload and browsable history restore saved transcript and file location');
    const descriptor = await job();
    let descriptorReads = 0;
    await page.route(`${BASE}/api/jobs/${jobId}`, route => {
      descriptorReads += 1;
      if (descriptorReads > 1) return route.continue();
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...descriptor, localFiles: { ...descriptor.localFiles, status: 'pending', message: null } }) });
    });
    await page.reload(); await page.getByText('Updating the local transcript files…', { exact: true }).waitFor();
    await page.locator('.local-file-names span').filter({ hasText: 'transcript.json' }).waitFor();
    assert.equal(descriptorReads, 2);
    await page.waitForTimeout(1300); assert.equal(descriptorReads, 2);
    await page.unroute(`${BASE}/api/jobs/${jobId}`);
    record('pending local copy status polls until ready and terminal descriptor polling then stops');
    await page.route(`${BASE}/api/jobs/${jobId}`, route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...descriptor, localFiles: { ...descriptor.localFiles, status: 'error', message: 'Synthetic local copy failure.' } }) }));
    await page.reload(); await page.getByText('Synthetic local copy failure.', { exact: true }).waitFor();
    await page.route(`${BASE}/api/jobs/${jobId}/local-files`, route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'fixture_local_file_failure', message: 'Synthetic repair failure.' } }) }));
    await page.getByRole('button', { name: 'Retry local files', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'Synthetic repair failure.' }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), edited);
    await page.unroute(`${BASE}/api/jobs/${jobId}/local-files`);
    await page.unroute(`${BASE}/api/jobs/${jobId}`);
    await fs.unlink(path.join(directory, 'transcript.txt'));
    await page.getByRole('button', { name: 'Retry local files', exact: true }).click();
    await page.locator('.local-file-names span').filter({ hasText: 'transcript.txt' }).waitFor();
    await filesMatchExports(edited, name);
    record('injected copy/repair errors remain visible; actual authenticated retry repairs a missing file without losing saved edits');
    for (const width of [1024, 760, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
      await page.screenshot({ path: path.join(ROOT, `browser-local-files-${width}.png`), fullPage: true });
    }
    record('copyable absolute paths fit narrow desktop and mobile layouts');
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.locator('.drop-zone').waitFor();
    assert.equal((await page.request.get(`${BASE}/api/jobs/${jobId}`)).status(), 404);
    await assert.rejects(fs.stat(directory), { code: 'ENOENT' });
    await page.reload(); await page.locator('.drop-zone').waitFor();
    const historyJobs = await (await page.request.get(BASE + '/api/jobs?limit=100')).json();
    assert(!historyJobs.jobs.some(value => value.id === jobId));
    record('confirmed deletion removes all local files and history stays deleted after refresh');
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    const report = { engine: await browser.version(), checks, pageErrors: errors, externalRequests: external.length, inference: 'deterministic fixture only; no model jobs', jobDeleted: true };
    await fs.writeFile(path.join(ROOT, 'browser-local-files-results.json'), JSON.stringify(report, null, 2));
  } catch (error) { console.error(error); process.exitCode = 1; }
  finally { await browser.close(); }
})();
