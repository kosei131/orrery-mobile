// Deterministic browser-script timer tests; no MT5 or localhost connection.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=require('node:child_process').execFileSync('python',['-c','import mt5_local_dashboard as d; print(d.HTML)'],{encoding:'utf8'});const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,{textContent:'',disabled:false,replaceChildren(){},appendChild(){}});return elements.get(id)};
let calls=[],interval,delay,timers=new Map(),timerId=0;
const context={document:{getElementById:get,createElement:()=>({textContent:'',appendChild(){}})},location:{hash:'#test-only',pathname:'/'},history:{replaceState(){}},Intl,AbortController,
 setInterval(fn,ms){interval=fn;delay=ms;},setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout(id){timers.delete(id)},
 fetch(url,options){return new Promise((resolve,reject)=>{options.signal.addEventListener('abort',()=>reject(Error('Timed out')));calls.push({resolve,reject,options})})}};
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 vm.createContext(context);vm.runInContext(script,context);
 assert.equal(delay,1000);assert.equal(calls.length,1);assert.equal(get('refresh').disabled,true);
 interval();get('refresh').onclick();assert.equal(calls.length,1,'No overlap while request pending');
 assert.equal(calls[0].options.headers['X-Orrery-Token'],'test-only');assert.equal(calls[0].options.cache,'no-store');
 calls[0].resolve({ok:true,json:async()=>({status:'SIMULATED_TEST_DATA',broker_server:'SIMULATED',account_last4:'0000',checked_at_utc:'TEST',balance:1,equity:1,margin_free:1,currency:'USD',history_7d_count:0,positions:[]})});
 await flush();assert.equal(get('refresh').disabled,false);assert.match(get('state').textContent,/TEST DATA/);assert.equal(timers.size,0);
 interval();assert.equal(calls.length,2);assert.equal([...timers.values()][0].ms,5000);
 [...timers.values()][0].fn();await flush();assert.match(get('state').textContent,/ERROR/);assert.equal(get('summary').textContent,'');assert.equal(get('refresh').disabled,false);
 interval();assert.equal(calls.length,3,'Polling recovers after timeout');calls[2].resolve({ok:false,json:async()=>({error:'DEMO unavailable'})});await flush();assert.match(get('state').textContent,/ERROR/);
 console.log('PASS: 1s request interval, serialized polling, timeout recovery, failure clearing and simulation label');
})().catch(e=>{console.error(e.message);process.exit(1)});
