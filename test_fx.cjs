// Offline DOM harness: no network, browser storage or broker access.
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = readFileSync('fx.html', 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
function boot(raw) {
  const elements = new Map(); const writes = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {value: ({dailyTarget:'2000',dailyLoss:'500',dailyTrades:'3',lots:'.01',tradeMode:'manual'})[id] || '', style:{}, checked:false,
      textContent:'', innerHTML:'', disabled:false, addEventListener(){}, append(){},
      className:'', appendChild(){}, replaceChildren(){}});
    return elements.get(id);
  }
  const context = {document:{getElementById:element,createElement:()=>element(Symbol())},
    localStorage:{getItem:()=>raw,setItem:(key,value)=>writes.push([key,value])},
    Intl, Date, console, setTimeout(){},confirm:()=>true};
  vm.runInNewContext(script, context);
  return {element,writes};
}
for (const raw of ['{broken', 'null', '{}', '{"cash":10000,"open":[]}']) {
  const {element,writes} = boot(raw);
  assert.equal(writes.length,0, 'unreadable data must not be overwritten');
  assert.equal(element('buy').disabled,true);
  assert.match(element('strategyInfo').textContent,/上書きしていません/);
}
const saved = {cash:12345,open:[],closed:[],notes:{XAUUSD:{bull:'keep my notes'}},series:{},custom:'preserve'};
const app = boot(JSON.stringify(saved));
assert.ok(app.writes.length);
const stored = JSON.parse(app.writes.at(-1)[1]);
assert.equal(stored.cash,saved.cash);
assert.deepEqual(stored.notes,saved.notes);
assert.equal(stored.custom,'preserve');
assert.match(app.element('tickinfo').textContent,/SIMULATED/);
assert.equal(app.element('arm').textContent === '自動模擬運用: ON',false);
assert.ok(!/\bfetch\s*\(|XMLHttpRequest|WebSocket/.test(script));
app.element('next').onclick();
assert.match(app.element('price').textContent,/\d/);
for (const file of ['index.html','business.html','fx.html','mt5-viewer.html','tradingview.html']) {
  for (const match of readFileSync(file,'utf8').matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
    new vm.Script(match[1],{filename:file});
  }
}
console.log('PASS: corrupt storage preserved; existing notes/balance preserved; simulated chart advances; inline scripts compile.');
