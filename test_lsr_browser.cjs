// Actual Chromium smoke tests against synthetic static examples. No account access.
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.ORRERY_BROWSER_CHANNEL||undefined});
 try{
  for(const viewport of [{width:390,height:844},{width:1365,height:900}]){
   const context=await browser.newContext({viewport});
   const page=await context.newPage();let errors=0,network=0;
   page.on('pageerror',()=>errors++);
   await page.route(/^https?:\/\//,route=>{network++;return route.abort()});
   await page.goto(pathToFileURL(path.resolve('lsr-viewer.html')).href);
   assert.equal(await page.locator('#scenario option').count(),10);
   assert.match(await page.locator('body').innerText(),/合成データ専用/);
   for(let i=0;i<10;i++){
    await page.selectOption('#scenario',String(i));
    assert.ok(await page.locator('#rows tr').count()>0);
    assert.match(await page.locator('#detail').innerText(),/BLOCKED/);
    assert.match(await page.locator('#summary').innerText(),i<6&&i%3===0?/RETEST/:/INVALID/);
    if(i>=6){
     assert.match(await page.locator('#rows tr').last().locator('td').nth(7).innerText(),/候補停止/);
     assert.match(await page.locator('#rows tr').last().locator('td').nth(6).innerText(),i%2===0?/不一致|不足/:/古い/);
    }
   }
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Whole-page horizontal overflow');
   const select=await page.locator('#scenario').boundingBox();assert.ok(select.height>=40);
   const table=page.locator('.scroll');
   if(viewport.width===390){
    assert.ok(await table.evaluate(e=>e.scrollWidth>e.clientWidth));
    await table.evaluate(e=>e.scrollLeft=e.scrollWidth);
    assert.ok(await table.evaluate(e=>e.scrollLeft>0));
   }
   assert.equal(errors,0,'JavaScript exceptions');assert.equal(network,0,'Unexpected remote request');
   await context.close();
  }
  console.log('PASS: Chromium mobile/desktop, 20 case selections, reasons, table scroll, no remote requests');
 }finally{await browser.close()}
})().catch(()=>{console.error('FAIL: synthetic browser verification; inspect locally without account credentials');process.exit(1)});
