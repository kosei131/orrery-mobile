const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('lsr-viewer.html','utf8'),script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function element(){return {value:'',textContent:'',children:[],appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},addEventListener(){}}}
const els=new Map(),get=id=>{if(!els.has(id))els.set(id,element());return els.get(id)};
const ctx={document:{getElementById:get,createElement:element}};vm.createContext(ctx);vm.runInContext(script,ctx);
assert.equal(get('scenario').children.length,6);
for(let i=0;i<6;i++){get('scenario').value=String(i);ctx.render();assert.ok(get('rows').children.length>0);assert.match(get('detail').textContent,/BLOCKED/);assert.match(get('summary').textContent,i%3===0?/RETEST/:/INVALID/);}
assert.match(html,/合成データ専用/);assert.ok(!/\bfetch\s*\(|localStorage|sessionStorage|XMLHttpRequest|WebSocket|innerHTML/.test(script));
console.log('PASS: six synthetic scenarios render, blocked status shown, no network or storage');
