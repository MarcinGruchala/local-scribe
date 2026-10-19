/* A suggestion must be discoverable from the transcript and lead to its audio/source. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const BASE = process.env.GROUPING_BASE;
const ROOT = process.env.LOCALSCRIBE_GROUPING_TEST_ROOT;
(async()=>{
 const {jobId}=JSON.parse(await fs.readFile(ROOT+'/fixture.json','utf8'));
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
 try {
  const {token}=await(await page.request.get(BASE+'/api/session')).json();
  await fs.writeFile(ROOT+'/mode.txt','mixed');
  await page.request.post(`${BASE}/api/jobs/${jobId}/grouping/apply`,{data:{expectedRevision:0},headers:{'X-LocalScribe-Token':token}});
  await page.request.post(`${BASE}/api/jobs/${jobId}/proofreading`,{data:{expectedRevision:1,segmentIds:['s100','s101']},headers:{'X-LocalScribe-Token':token}});
  await page.goto(BASE+'/#job='+jobId);
  const entry=page.getByRole('tab',{name:/AI suggestions/});await entry.waitFor({timeout:6000});await entry.click();
  const review=page.getByRole('region',{name:'AI proofreading',exact:true});
  await review.getByText('1 correction',{exact:true}).waitFor({timeout:10000});
  await review.getByRole('button',{name:'Needs listening (1)',exact:true}).click();
  assert.equal(await review.getByRole('button',{name:'Accept correction',exact:true}).count(),0);
  assert.equal(await review.locator('input[type=checkbox]').count(),0);
  await review.getByRole('button',{name:'Listen from 01:41',exact:true}).click();
  await page.waitForFunction(()=>Math.abs(document.querySelector('audio').currentTime-101)<2);
  await review.getByRole('button',{name:'Show in transcript',exact:true}).click();
  await page.locator('.segment[data-segment="s101"].selected').waitFor();
  assert.ok(await page.locator('.segment[data-segment="s101"]').isVisible());
  assert.ok(await entry.isVisible());
  await page.goto(BASE+'/#job='+jobId+'&segment=s100');
  await page.locator('.segment[data-segment="s100"].selected').waitFor();
  await page.locator('.segment[data-segment="s100"] textarea').fill('Visible navigation draft.');
  await page.goto(BASE+'/#job='+jobId+'&segment=s101');
  await page.locator('.segment[data-segment="s101"].selected').waitFor();
  assert.equal(await page.locator('.segment[data-segment="s100"] textarea').inputValue(),'Visible navigation draft.');
  console.log('PASS visible suggestions tab -> timestamped correction -> exact source reveal');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
