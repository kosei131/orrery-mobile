// Exercise the actual offline server and actual acquired CSV, never MT5.
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
  const child=spawn(process.env.ORRERY_PYTHON||'python',['-u','mt5_local_dashboard.py',
    '--history-dir','research_artifacts_20261101/public_xau_bars',
    '--research-results','research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json'],
    {env:{...process.env,PYTHONUTF8:'1'}});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{
      let output='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),15000);
      child.stdout.on('data',chunk=>{output+=chunk;const match=output.match(/http:\/\/127\.0\.0\.1:8765\/#[\w-]+/);if(match){clearTimeout(timer);resolve(match[0]);}});
      child.on('exit',()=>{clearTimeout(timer);reject(Error('Server stopped before startup'));});
    });
    browser=await chromium.launch({headless:true,channel:process.env.ORRERY_BROWSER_CHANNEL||'chrome'});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelectorAll('#charts rect').length>20);
    assert.match(await page.locator('#state').textContent(),/PUBLIC HISTORY/);
    assert.match(await page.locator('#summary').textContent(),/UNKNOWN/);
    assert.match(await page.locator('#analysis').textContent(),/ATR14/);
    assert.match(await page.locator('#analysis').textContent(),/Reason:/);
    assert.match(await page.locator('#results').textContent(),/LSR02.*candidates 0/);
    for(const frame of ['15m','4H','5m']){
      await page.selectOption('#chartFrame',frame);
      assert.ok(await page.locator('#charts rect').count()>1);
    }
    if(process.env.ORRERY_SCREENSHOT)await page.screenshot({path:path.resolve(process.env.ORRERY_SCREENSHOT),fullPage:true});
    console.log('PASS: actual offline server, acquired CSV candles, indicators, reasons, unknown account values and matched strategy results');
  }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error('FAIL: offline research chart verification: '+e.message.replace(/#[\w-]+/g,'#[REDACTED]'));process.exitCode=1;});
