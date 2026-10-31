const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('lsr-viewer.html','utf8'),script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function element(){return {value:'',textContent:'',children:[],appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},addEventListener(){}}}
const els=new Map(),get=id=>{if(!els.has(id))els.set(id,element());return els.get(id)};
const ctx={document:{getElementById:get,createElement:element}};vm.createContext(ctx);vm.runInContext(script,ctx);
assert.equal(get('scenario').children.length,10);
for(let i=0;i<10;i++){get('scenario').value=String(i);ctx.render();assert.ok(get('rows').children.length>0);assert.match(get('detail').textContent,/BLOCKED/);assert.match(get('summary').textContent,i<6&&i%3===0?/RETEST/:/INVALID/);}
for(let i=6;i<10;i++){get('scenario').value=String(i);ctx.render();const rows=get('rows').children;assert.match(rows.at(-1).children[7].textContent,/候補停止/);assert.match(rows.at(-1).children[5].textContent,/判定不能/);assert.match(rows.at(-1).children[6].textContent,i%2===0?/不一致|不足/:/古い/);assert.match(get('detail').textContent,/環境フィルターあり/);assert.match(get('detail').textContent,/再開しません/);}
assert.match(html,/合成データ専用/);assert.ok(!/\bfetch\s*\(|localStorage|sessionStorage|XMLHttpRequest|WebSocket|innerHTML/.test(script));
console.log('PASS: ten synthetic scenarios render, blocked status shown, no network or storage');
