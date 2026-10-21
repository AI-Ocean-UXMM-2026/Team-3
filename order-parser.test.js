const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
// Load the bundle the way a browser does: a fresh global with atob but no Node Buffer or require.
const browser={atob};
vm.runInNewContext(fs.readFileSync(require.resolve('./vendor/lannpya-order-parser.js'),'utf8'),browser);
const P=browser.LannPyaOrderParser;
globalThis.LannPyaOrderParser=P;
const W=require('./workflow-domain');
const A=W.ACTORS.admin;
function memory(){const data=new Map();return {getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};}

test('browser bundle runs without Node globals and the prototype detects it',()=>{
 assert.equal(typeof P.parseRules,'function');assert.equal(W.enhanced(),true);
 assert.equal(P.parseRules('Ma Thida\n09 777 123 456').phones[0].number,'09777123456');
});
test('unlabelled Burmese chat order fills name, phone, township, street and COD',()=>{
 const p=W.parse('Ko Min\n09 794 339 082\nအမှတ် ၁၂ သီရိမင်္ဂလာလမ်း ကမာရွတ်\n၃ သောင်း ၅ ထောင် ကျပ်');
 assert.equal(p.name,'Ko Min');assert.equal(p.phone,'09794339082');assert.equal(p.areaId,'kamayut');
 assert.equal(p.street,'No. 12, သီရိမင်္ဂလာလမ်း');assert.equal(p.payment,'cod');assert.equal(p.expected,35000);
 for(const k of ['name','street','expected','payment'])assert.equal(p.provenance[k].parser,'lannpya-order-parser',k);
 assert.equal(W.triage(p).level,'amber');
});
test('labelled fields still win over the parser',()=>{
 const raw=W.SAMPLE.split(/\n\s*---\s*\n/)[1],p=W.parse(raw);
 assert.equal(p.name,'Ko Min');assert.equal(p.street,'Thiri Mingalar Road');assert.equal(p.expected,35000);assert.equal(W.triage(p).level,'green');
 assert.equal(p.provenance.name.parser,undefined);assert.equal(p.provenance.expected.parser,undefined);
});
test('wallet transfer marks the order prepaid with zero to collect',()=>{
 const p=W.parse('Daw Khin Khin\n09-250-987-654\nNo. 45, Baho Road, Sanchaung\nKPay နဲ့ ငွေလွှဲပြီးပါပြီ');
 assert.equal(p.payment,'prepaid');assert.equal(p.expected,0);assert.equal(p.areaId,'sanchaung');assert.equal(p.street,'Baho Road');
 assert.match(p.provenance.payment.evidence,/KBZPay/);
});
test('Zawgyi is converted to Unicode and flagged for a check',()=>{
 const raw='ကိုေဇာ္ေဇာ္\n09 977 654 321\nလႈိင္သာယာ ေဈးအနီး လမ္းၾကားထဲ ဝင္ဝင္ခ်င္း\nCOD 16000',p=W.parse(raw);
 assert.equal(p.raw,raw);assert.match(p.normalized,/လှိုင်သာယာ/);assert.equal(p.encodingReview,false);assert.equal(p.name,'ကိုဇော်ဇော်');
 assert.equal(p.expected,16000);assert.ok(p.warnings.some(w=>/Zawgyi/.test(w)));
 // Hlaing Tharyar is a real township but not a prototype service area, so the order stays red.
 assert.equal(p.areaId,'');assert.ok(p.warnings.some(w=>/hlaing-tharyar is outside/.test(w)));assert.equal(W.triage(p).level,'red');
});
test('ambiguous contacts and amounts never auto-clear',()=>{
 assert.equal(W.parse('Phone: 09887341602\nOther: 09794339082\nTownship: Kamayut').phone,'');
 assert.equal(W.parse('Ma Su\n09887341602\nKamayut\n09794339082').phone,'');
 const p=W.parse('Ma Su\n09887341602\nKamayut\n12000 ks 15000 ks');
 assert.equal(p.payment,'unknown');assert.ok(p.warnings.some(w=>/Several amounts/.test(w)));
 const q=W.parse('Ma Su\n09887341602\nKamayut\nPayment: unknown\n12000 ks');assert.equal(q.payment,'unknown');
});
test('numbered orders written back to back split into separate records',()=>{
 assert.deepEqual(W.split('1. Ma Thida\n09777123456\n2. Ko Zaw\n09795551234'),['1. Ma Thida\n09777123456','2. Ko Zaw\n09795551234']);
 assert.equal(W.split('a\n\n---\n\nb').length,2);
});
test('pasted batch creates orders with parser-filled fields',()=>{
 const s=W.createStore(memory(),{initialState:W.seed()});
 const ids=s.execute('create_batch',{records:[{raw:'Ko Min\n09 794 339 082\nသီရိမင်္ဂလာလမ်း ကမာရွတ်\n၃ သောင်း ၅ ထောင် ကျပ်'}],date:'2026-10-21'},A).value;
 const o=s.order(ids[0]);assert.equal(o.phone,'09794339082');assert.equal(o.areaId,'kamayut');assert.equal(o.expected,35000);assert.equal(o.payment,'cod');
});
