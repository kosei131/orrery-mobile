const fs=require('fs'),assert=require('assert');
const s=fs.readFileSync('lsr-chart-preview.html','utf8');
for(const v of ['SYNTHETIC PREVIEW','id="tp"','id="sl"','id="lots"','id="result"','2.6 LEVEL','SUPPORT','RESISTANCE','WAIT']) assert(s.includes(v),'Missing '+v);
assert(!s.includes('order_send'));
console.log('Synthetic chart preview smoke PASS');
