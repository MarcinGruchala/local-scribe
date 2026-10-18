/* Restart acceptance: new HTTP process + new browser, same isolated fixture store. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = process.env.GROUPING_BASE || 'http://127.0.0.1:8770';
const ROOT = process.env.LOCALSCRIBE_GROUPING_TEST_ROOT;

(async () => {
  const { jobId } = JSON.parse(await fs.readFile(ROOT + '/fixture.json', 'utf8'));
  const { saved, immutable } = JSON.parse(await fs.readFile(ROOT + '/before-restart.json', 'utf8'));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXECUTABLE });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); const errors = []; const checks = [];
  page.on('pageerror', error => errors.push(error.message));
  const record = text => { checks.push(text); console.log('PASS ' + text); };
  const transcript = () => page.request.get(`${BASE}/api/jobs/${jobId}/transcript`).then(response => response.json());
  try {
    await page.goto(`${BASE}/#job=${jobId}`);
    await page.getByRole('button', { name: 'Undo saved operation', exact: true }).waitFor();
    assert.deepEqual(await transcript(), saved);
    const history = await (await page.request.get(`${BASE}/api/jobs/${jobId}/history`)).json();
    assert.equal(history.canUndo, true); assert.equal(history.canRedo, false);
    let revision = saved.revision;
    for (const operation of history.operations.slice().reverse()) {
      await page.getByRole('button', { name: 'Undo saved operation', exact: true }).click();
      await page.waitForFunction(revision => document.querySelector('.save-state')?.textContent.includes(`revision ${revision}`), ++revision);
      if (operation === history.operations[0]) assert.equal((await transcript()).grouping.blocks.length, 400);
    }
    const undone = await transcript();
    assert.equal(undone.segments[0].editedText, null);
    assert.equal(undone.grouping.blocks.length, 400);
    assert.deepEqual(undone.grouping.manualSplits, []);
    record('restart retains exact saved text and linear history; one final Undo reverses the whole original grouping');
    for (const _ of history.operations) {
      await page.getByRole('button', { name: 'Redo saved operation', exact: true }).click();
      await page.waitForFunction(revision => document.querySelector('.save-state')?.textContent.includes(`revision ${revision}`), ++revision);
    }
    const redone = await transcript();
    assert.deepEqual(redone, { ...saved, revision });
    assert.equal(await fs.readFile(`${ROOT}/store/jobs/${jobId}/attempts/1/published.json`, 'utf8'), immutable);
    record('all Redo operations after restart restore exact saved text, partitions and manual split; originals unchanged');
    await page.getByRole('button', { name: 'Delete recording', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.getByRole('heading', { name: 'Make every conversation readable.', exact: true }).waitFor();
    assert.equal((await page.request.get(`${BASE}/api/jobs/${jobId}/history`)).status(), 404);
    assert.equal(await fs.stat(`${ROOT}/store/jobs/${jobId}`).then(() => true, () => false), false);
    assert.equal(await fs.readFile(`${ROOT}/no-models/shared-ownership-sentinel`, 'utf8'), 'Synthetic ownership marker, not model weights.');
    record('explicit recording deletion removes media/copies/history ownership without touching shared models');
    assert.deepEqual(errors, []);
    const result = { checks, pageErrors: errors };
    await fs.writeFile(ROOT + '/browser-restart-results.json', JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(error); process.exitCode = 1;
    await page.screenshot({ path: ROOT + '/grouping-restart-failure.png', fullPage: true }).catch(captureError => console.error('Failure capture:', captureError.message));
  } finally { await browser.close(); }
})();
