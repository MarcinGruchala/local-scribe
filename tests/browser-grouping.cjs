/* Actual Chromium + real fixture backend. No model or private transcript data. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = process.env.GROUPING_BASE || 'http://127.0.0.1:8770';
const ROOT = process.env.LOCALSCRIBE_GROUPING_TEST_ROOT;

(async () => {
  const { jobId } = JSON.parse(await fs.readFile(ROOT + '/fixture.json', 'utf8'));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); const errors = []; const checks = [];
  page.on('pageerror', e => errors.push(e.message));
  const external = [];
  await context.route('**/*', route => {
    if (route.request().url().startsWith(BASE + '/')) return route.continue();
    external.push(route.request().url()); return route.abort();
  });
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  try {
    if (process.env.UI_CONTRACT_FIXTURE === '1') {
      // Explicit HTTP contract stub for test-first UI work before backend integration.
      await page.route('**/api/jobs/*/transcript', async route => {
        const response = await route.fetch(); const value = await response.json();
        value.grouping = { manualSplits: [], blocks: [
          { id: 's000', segmentIds: ['s000', 's001'], start: 0, end: 1.8, speakerId: 'speaker_1', text: 'Word0. Word1.' },
          ...value.segments.slice(2).map(segment => ({ ...segment, segmentIds: [segment.id] }))
        ] };
        await route.fulfill({ response, json: value });
      });
      await page.route('**/api/jobs/*/history', route => route.fulfill({ json: { revision: 0, canUndo: false, canRedo: false, operations: [] } }));
      await page.route('**/api/jobs/*/grouping/preview', async route => {
        const transcript = await (await page.request.get(`${BASE}/api/jobs/${jobId}/transcript`)).json();
        await route.fulfill({ json: { revision: 0, beforeCount: 400, afterCount: 8, changed: true,
          blocks: [{ id: 's000', segmentIds: ['s000', 's001'], start: 0, end: 1.8, speakerId: 'speaker_1', text: 'Word0. Word1.' }] } });
        assert.equal(transcript.segments.length, 400);
      });
    }
    await page.goto(`${BASE}/#job=${jobId}`);
    await page.getByRole('button', { name: 'Preview grouping', exact: true }).waitFor({ timeout: 5000 });
    assert.equal(await page.getByLabel('Grouping scope', { exact: true }).inputValue(), 'entire');
    await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
    await page.getByRole('region', { name: 'Grouping preview', exact: true }).waitFor();
    assert.match(await page.getByRole('region', { name: 'Grouping preview', exact: true }).innerText(), /400 segments/);
    assert.equal((await (await page.request.get(`${BASE}/api/jobs/${jobId}/transcript`)).json()).revision, 0);
    await page.getByRole('button', { name: 'Cancel grouping', exact: true }).click();
    assert.equal(await page.getByRole('region', { name: 'Grouping preview', exact: true }).count(), 0);
    record('entire recording default; one preview scans 400 segments and cancel leaves revision unchanged');
    await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
    await page.getByRole('button', { name: 'Apply all', exact: true }).waitFor({ timeout: 3000 });
    assert.equal(await page.getByRole('button', { name: 'Undo saved operation', exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole('button', { name: 'Redo saved operation', exact: true }).isDisabled(), true);
    record('aggregate Apply all and persistent-history controls are available');
    if (process.env.UI_CONTRACT_FIXTURE === '1') {
      await page.locator('[data-block="s000"] .block-text').waitFor({ timeout: 3000 });
      assert.equal(await page.locator('[data-block="s000"] .block-text').innerText(), 'Word0. Word1.');
      await page.getByRole('button', { name: 'Split before s001', exact: true }).waitFor();
      record('grouped reading view retains expandable editable source segments and manual source-boundary split');
      await page.route('**/api/jobs/*/grouping/apply', async route => {
        const value = await (await page.request.get(`${BASE}/api/jobs/${jobId}/transcript`)).json();
        value.revision = 1;
        value.grouping = { manualSplits: [], blocks: [
          { id: 's000', segmentIds: ['s000', 's001'], start: 0, end: 1.8, speakerId: 'speaker_1', text: 'Word0. Word1.' },
          ...value.segments.slice(2).map(segment => ({ ...segment, segmentIds: [segment.id] }))
        ] };
        value.grouping.blocks = value.grouping.blocks.filter(block => !['s100', 's101'].includes(block.id));
        value.grouping.blocks.splice(99, 0, { id: 's100', segmentIds: ['s100', 's101'], start: 100, end: 101.8, speakerId: 'speaker_1', text: 'Word100. Word101.' });
        await route.fulfill({ json: value });
      });
      await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
      await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('399.9');
      await page.getByRole('searchbox', { name: 'Find in transcript', exact: true }).fill('Word100.');
      await page.locator('[data-segment="s100"].match').waitFor();
      await page.getByRole('button', { name: 'Apply all', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.save-state')?.textContent.includes('revision 1'));
      assert.equal(await page.locator('[data-segment="s100"].match').isVisible(), true);
      record('applying grouping re-reveals an unchanged single-result search inside newly collapsed sources');
    }
    if (process.env.UI_CONTRACT_FIXTURE !== '1') {
      const transcript = () => page.request.get(`${BASE}/api/jobs/${jobId}/transcript`).then(response => response.json());
      const history = () => page.request.get(`${BASE}/api/jobs/${jobId}/history`).then(response => response.json());
      const immutablePath = `${ROOT}/store/jobs/${jobId}/attempts/1/published.json`;
      const immutable = await fs.readFile(immutablePath, 'utf8');
      const originalSrt = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=srt`)).text();
      const waitRevision = revision => page.waitForFunction(revision => document.querySelector('.save-state')?.textContent.includes(`revision ${revision}`), revision);
      const revealFirst = async () => {
        const details = page.locator('.block-sources').first();
        if (await details.count() && !(await details.evaluate(element => element.open))) await details.locator('summary').click();
      };
      await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
      await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('399.9');
      await page.getByRole('searchbox', { name: 'Find in transcript', exact: true }).fill('Word100.');
      await page.getByRole('button', { name: 'Apply all', exact: true }).click();
      await waitRevision(1);
      assert.equal(await page.locator('.segment[data-segment="s100"].match').isVisible(), true);
      await page.getByRole('searchbox', { name: 'Find in transcript', exact: true }).fill('');
      const grouped = await transcript();
      assert.equal(grouped.grouping.blocks.length, 9);
      assert.deepEqual(grouped.grouping.blocks.flatMap(block => block.segmentIds), Array.from({ length: 400 }, (_, i) => `s${String(i).padStart(3, '0')}`));
      assert.equal((await history()).operations.length, 1);
      assert.equal(await page.locator('.transcript-block').count(), 8);
      assert.equal(await fs.readFile(immutablePath, 'utf8'), immutable);
      record('one Apply all saves 400 source segments into 9 blocks as one history operation');
      await page.getByRole('button', { name: 'Undo saved operation', exact: true }).click(); await waitRevision(2);
      assert.equal((await transcript()).grouping.blocks.length, 400);
      await page.getByRole('button', { name: 'Redo saved operation', exact: true }).click(); await waitRevision(3);
      assert.deepEqual((await transcript()).grouping, grouped.grouping);
      record('one Undo reverses the entire grouping batch; Redo restores exact source partitions');
      await revealFirst();
      await page.getByRole('button', { name: 'Split before s010', exact: true }).click(); await waitRevision(4);
      assert.deepEqual((await transcript()).grouping.manualSplits, ['s010']);
      await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
      await page.getByRole('region', { name: 'Grouping preview', exact: true }).waitFor();
      if (!(await page.getByRole('button', { name: 'Apply all', exact: true }).isDisabled())) {
        await page.getByRole('button', { name: 'Apply all', exact: true }).click(); await waitRevision(5);
      } else await page.getByRole('button', { name: 'Cancel grouping', exact: true }).click();
      const afterSplit = await transcript();
      assert.deepEqual(afterSplit.grouping.manualSplits, ['s010']);
      assert.equal(afterSplit.grouping.blocks[0].segmentIds.length, 10);
      await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
      await page.getByRole('region', { name: 'Grouping preview', exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Apply all', exact: true }).isDisabled(), true);
      await page.getByRole('button', { name: 'Cancel grouping', exact: true }).click();
      assert.equal((await transcript()).revision, afterSplit.revision);
      record('manual source-boundary split survives regrouping and repeated no-op adds no revision');
      await page.getByLabel('Grouping scope', { exact: true }).selectOption('selection');
      await page.getByLabel('First source segment', { exact: true }).selectOption('100');
      await page.getByLabel('Last source segment', { exact: true }).selectOption('119');
      await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
      await page.getByRole('region', { name: 'Grouping preview', exact: true }).waitFor();
      assert.match(await page.getByRole('region', { name: 'Grouping preview', exact: true }).innerText(), /20 segments/);
      await page.getByRole('button', { name: 'Cancel grouping', exact: true }).click();
      await page.getByLabel('Grouping scope', { exact: true }).selectOption('entire');
      record('secondary selection uses an explicit contiguous source range and cancellation is non-mutating');
      await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
      await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('15.1');
      await page.waitForFunction(() => document.querySelector('.segment.playing')?.dataset.segment === 's015');
      assert.equal(await page.locator('.segment[data-segment="s015"]').isVisible(), true);
      await page.getByRole('slider', { name: 'Audio position', exact: true }).fill('15.9');
      await page.waitForFunction(() => !document.querySelector('.transcript-block.playing'));
      await page.getByRole('searchbox', { name: 'Find in transcript', exact: true }).fill('Word300.');
      await page.locator('[data-segment="s300"].match').waitFor();
      assert.equal(await page.locator('.segment[data-segment="s300"]').isVisible(), true);
      await page.getByRole('searchbox', { name: 'Find in transcript', exact: true }).fill('');
      record('grouped playback/search reveal exact source segments; internal silence is not highlighted');
      await revealFirst();
      const stale = await context.newPage();
      await stale.goto(`${BASE}/#job=${jobId}`);
      const staleSources = stale.locator('.block-sources').first();
      await staleSources.waitFor();
      if (!(await staleSources.evaluate(element => element.open))) await staleSources.locator('summary').click();
      await stale.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Draft in second tab.');
      await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Saved manual text.');
      const manualRevision = afterSplit.revision + 1;
      await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await waitRevision(manualRevision);
      await stale.getByRole('button', { name: 'Save changes', exact: true }).click();
      await stale.getByRole('alert').filter({ hasText: 'The transcript changed.' }).waitFor();
      assert.equal(await stale.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), 'Draft in second tab.');
      assert.equal((await transcript()).segments[0].editedText, 'Saved manual text.');
      stale.on('dialog', dialog => dialog.accept());
      await stale.getByRole('button', { name: 'Discard changes', exact: true }).click();
      await stale.getByText('Unsaved changes', { exact: true }).waitFor({ state: 'hidden' });
      await stale.close();
      record('stale tab returns conflict without losing visible draft; explicit discard loads latest saved revision');
      await page.getByRole('button', { name: 'Undo saved operation', exact: true }).click(); await waitRevision(manualRevision + 1);
      assert.equal((await transcript()).segments[0].editedText, null);
      await page.getByRole('button', { name: 'Redo saved operation', exact: true }).click(); await waitRevision(manualRevision + 2);
      assert.equal((await transcript()).segments[0].editedText, 'Saved manual text.');
      await page.getByRole('button', { name: 'Undo saved operation', exact: true }).click(); await waitRevision(manualRevision + 3);
      await revealFirst();
      await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Branch after Undo.');
      await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await waitRevision(manualRevision + 4);
      assert.equal((await history()).canRedo, false);
      record('manual saved text Undo/Redo is exact; a new edit after Undo invalidates Redo');
      const saved = await transcript();
      const currentJson = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=json`)).json();
      const originalJson = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=json&source=original`)).json();
      const segmentedJson = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=json&layout=segmented`)).json();
      assert.equal(currentJson.schemaVersion, 2); assert.equal(originalJson.schemaVersion, 1); assert.equal(segmentedJson.schemaVersion, 1);
      assert.equal(originalJson.segments[0].text, 'Word0.'); assert.equal(originalJson.segments[0].editedText, null);
      const srt = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=srt`)).text();
      assert.deepEqual(srt.split('\n').filter(line => line.includes(' --> ')), originalSrt.split('\n').filter(line => line.includes(' --> ')));
      const txt = await (await page.request.get(`${BASE}/api/jobs/${jobId}/export?format=txt`)).text();
      assert.equal(await fs.readFile(`${ROOT}/store/jobs/${jobId}/transcript.txt`, 'utf8'), txt);
      assert.match(txt, /Branch after Undo\. Word1\./);
      assert.equal(await fs.readFile(immutablePath, 'utf8'), immutable);
      record('grouped/current JSON v2, source JSON v1 and saved TXT copies agree; SRT cue timing and originals unchanged');
      for (const width of [1440, 760, 390]) {
        await page.setViewportSize({ width, height: 1000 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
        await page.locator('.cleanup-tools').scrollIntoViewIfNeeded();
        await page.screenshot({ path: `${ROOT}/grouping-${width}.png`, fullPage: true });
        await page.getByRole('button', { name: 'Preview grouping', exact: true }).click();
        await page.getByRole('region', { name: 'Grouping preview', exact: true }).waitFor();
        await page.getByRole('button', { name: 'Cancel grouping', exact: true }).click();
      }
      record('desktop/tablet/390px layouts retain usable one-shot preview and no horizontal overflow');
      await page.setViewportSize({ width: 1440, height: 1000 });
      await fs.writeFile(`${ROOT}/before-restart.json`, JSON.stringify({ saved, immutable }));
    }
    await page.getByLabel('Export source', { exact: true }).selectOption('original');
    await page.getByLabel('Export layout', { exact: true }).selectOption('segmented');
    assert.match(await page.getByRole('link', { name: 'TXT', exact: true }).getAttribute('href'), /source=original&layout=segmented/);
    await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).fill('Visible manual draft.');
    assert.equal(await page.getByRole('button', { name: 'Preview grouping', exact: true }).isDisabled(), true);
    assert.equal(await page.getByRole('button', { name: 'Undo saved operation', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Discard changes', exact: true }).waitFor({ timeout: 3000 });
    record('original/segmented export selection is explicit and manual drafts gate grouping/history');
    await page.route('**/api/jobs/*/transcript', route => route.request().method() === 'PATCH' ? route.abort('connectionfailed') : route.fallback());
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: 'Your edits are still shown' }).waitFor();
    assert.equal(await page.getByRole('textbox', { name: 'Transcript at 00:00', exact: true }).inputValue(), 'Visible manual draft.');
    record('disconnected save preserves the visible manual draft and does not publish it');
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    const result = { checks, pageErrors: errors, externalRequests: external, contractStub: process.env.UI_CONTRACT_FIXTURE === '1' };
    await fs.writeFile(ROOT + '/browser-grouping-results.json', JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(error); process.exitCode = 1;
    await page.screenshot({ path: ROOT + '/grouping-failure.png', fullPage: true }).catch(captureError => console.error('Failure capture:', captureError.message));
  } finally { await browser.close(); }
})();
