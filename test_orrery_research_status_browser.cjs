// Actual loopback server + real Chromium; all market data are injected fixtures.
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const script=`import threading
from test_orrery_research_worker import WorkerTests
from orrery_research_status import make_server
from lsr04_tick_archive import _encode
f=WorkerTests(); f.setUp()
try:
 r=f.job(); receipt=f.root/'viewer_receipt.json'; receipt.write_bytes(_encode(r))
 server=make_server(f.folder(r),receipt,'a'*43,port=0)
 print(server.server_port,flush=True)
 server.serve_forever()
finally:
 f.doCleanups()
`;
(async()=>{
  const child=spawn('python',['-u','-c',script],{stdio:['ignore','pipe','pipe']});
  let browser;
  try {
    const port=await new Promise((resolve,reject)=>{
      let output='';
      const timer=setTimeout(()=>reject(Error('Server timeout')),15000);
      child.once('error',e=>{clearTimeout(timer);reject(e)});
      child.once('exit',()=>{clearTimeout(timer);reject(Error('Server exited'))});
      child.stdout.on('data',chunk=>{
        output+=chunk.toString();
        const line=output.split('\n')[0].trim();
        if(/^\d+$/.test(line)){clearTimeout(timer);resolve(Number(line))}
      });
    });
    browser=await chromium.launch({headless:true,channel:process.env.ORRERY_BROWSER_CHANNEL||undefined});
    const page=await browser.newPage({viewport:{width:390,height:844}});
    let errors=0; page.on('pageerror',()=>errors++);
    await page.goto(`http://127.0.0.1:${port}/`);
    assert.equal(await page.locator('#state').textContent(),'未認証');
    assert.equal(await page.locator('#result section').count(),0);
    await page.fill('#key','b'.repeat(43)); await page.click('#unlock');
    await page.waitForFunction(()=>document.getElementById('state').textContent.includes('接続・認証失敗'));
    assert.equal(await page.locator('#result section').count(),0);
    await page.fill('#key','a'.repeat(43)); await page.click('#unlock');
    await page.waitForFunction(()=>document.querySelectorAll('#result section').length===2);
    assert.equal(await page.inputValue('#key'),'');
    assert.ok((await page.locator('#result').textContent()).includes('不明'));
    assert.ok((await page.locator('#state').textContent()).includes('稼働状況は不明'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);
    await page.route('**/api/runs',route=>route.abort());
    await page.click('#refresh');
    await page.waitForFunction(()=>document.getElementById('state').textContent.includes('接続・認証失敗'));
    assert.equal(await page.locator('#result section').count(),0);
    await page.unroute('**/api/runs');
    await page.fill('#key','a'.repeat(43)); await page.click('#unlock');
    await page.waitForFunction(()=>document.querySelectorAll('#result section').length===2);
    let release;
    const hold=new Promise(resolve=>release=resolve);
    await page.route('**/api/runs',async route=>{await hold;await route.continue()});
    await page.click('#refresh');
    await page.waitForFunction(()=>document.getElementById('state').textContent.includes('確認中'));
    await page.click('#logout');
    const response=page.waitForResponse(r=>r.url().endsWith('/api/runs'));
    release(); await response;
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#state').textContent(),'未認証');
    assert.equal(await page.locator('#result section').count(),0);
    assert.equal(await page.locator('#refresh').isDisabled(),true);
    assert.equal(errors,0);
    console.log('PASS: fixed research viewer, auth, mobile width, network failure clearing and logout race (synthetic only)');
  } finally {
    if(browser)await browser.close();
    child.kill();
  }
})().catch(error=>{console.error('FAIL: research viewer browser',error.message);process.exitCode=1});
