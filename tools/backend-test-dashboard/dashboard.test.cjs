// DOM harness checks; real HTTP handler coverage is in dashboard-http.test.cjs.
const test = require('node:test');
const assert = require('node:assert/strict');
const {load} = require('./harness.cjs');

test('dashboard JavaScript boots, loads test context and sends parse without privileged headers',async()=>{
  const {nodes,calls}=await load();
  assert.match(nodes.get('connection').textContent,/Backend connected/);
  nodes.get('raw-text').value='fictional Burmese parser input';
  await nodes.get('parse').trigger('click');
  const request=calls.at(-1);
  assert.equal(request.payload.path,'/api/orders/parse');
  assert.equal(request.payload.body.raw_text,'fictional Burmese parser input');
  assert.equal(request.options.headers['X-Dashboard-CSRF'],'test-csrf');
  assert.equal(request.options.headers['X-Dev-Access-Token'],undefined);
  assert.match(nodes.get('output').textContent,/fictional Burmese parser input/);
});

test('HTML-looking backend errors render as text and never enter the activity timeline',async()=>{
  const marker='<svg onload="bad()">private fictional customer detail</svg>';
  const {nodes}=await load((url,p)=>p?.path==='/api/orders/parse'?{status:422,data:{method:'POST',endpoint:'/api/orders/parse',status:422,ok:false,data:{error:{message:marker}}}}:null);
  await nodes.get('parse').trigger('click');
  assert.match(nodes.get('output').textContent,/private fictional customer detail/);
  assert.match(nodes.get('result-status').textContent,/422/);
  const activity=nodes.get('timeline').children.flatMap(row=>row.children.map(c=>c.textContent)).join(' ');
  assert.doesNotMatch(activity,/private fictional customer detail|bad\(\)/);
});

test('network failure produces an error, without mock persistence or success fallback',async()=>{
  const {nodes}=await load((url,p)=>{if(p?.path==='/api/orders/parse')throw Error('Connection unavailable');});
  await nodes.get('parse').trigger('click');
  assert.match(nodes.get('result-status').textContent,/no simulated fallback/);
  assert.match(nodes.get('output').textContent,/Connection unavailable/);
  assert.doesNotMatch(nodes.get('output').textContent,/saved|persisted|success/i);
});

test('a rejected quiet startup read displays the actual failure rather than hiding it',async()=>{
  const {nodes}=await load((url,p)=>p?.path.startsWith('/api/riders')?{status:503,data:{method:'GET',endpoint:'/api/riders',status:503,ok:false,data:{error:{code:'DATABASE_UNAVAILABLE',message:'Test backend unavailable'}}}}:null);
  assert.match(nodes.get('result-status').textContent,/503/);
  assert.match(nodes.get('output').textContent,/DATABASE_UNAVAILABLE/);
});
