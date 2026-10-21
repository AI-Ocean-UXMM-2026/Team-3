import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import {environment} from './test-dom.js';
import {LocalWorkspaceApi as WorkspaceApi,context,today,townships,mmk,tokenFrom} from '../js/local-api.mjs';

const source=fs.readFileSync(new URL('../js/api-workspace.mjs',import.meta.url),'utf8').replace(/^import[^\r\n]*\r?\n/,'').replace(/\nload\(\);\s*$/,'\nglobalThis.ready=load();');
const token='A'.repeat(43),secret='x'.repeat(48);
const order={id:'o1',status:'NEEDS_REVIEW',version:1,customer_name:'Buyer',customer_phone:'09791234567',township:'Kamaryut',street:'Hledan',cod_amount:'25000',latitude:'16.8254',longitude:'96.1309',confidence_level:'AMBER',parsing_metadata:{parcel:{item:'Envelope',delivery_day:today(),hub_received_at:'now'}}};
function setup(t,hash='#/admin',override){
 const calls=[];
 const backendFetch=async(url,opts={})=>{
  calls.push({url,opts});const path=new URL(url).pathname;
  const custom=override?.(path,opts);if(custom)return custom;
  let data={};
  if(path==='/api/session')data={id:url.includes(':8001')?'rider1':'admin1',name:'Test',role:url.includes(':8001')?'Rider':'Admin'};
  else if(path==='/api/routes')data={items:[],total:0};
  else if(path==='/api/riders')data={items:[{id:'rider1',name:'Ko Aung',operational_status:'AVAILABLE'}],total:1};
  else if(path==='/api/orders')data=opts.method==='POST'?order:{items:[order],total:1};
  else if(path==='/api/orders/o1')data=order;
  else if(path.endsWith('/buyer-requests'))data={items:[],total:0};
  else if(path.endsWith('/confirmation-link'))data={confirmation_url:'/confirm/'+token};
  else if(path.endsWith('/verify'))data={access_token:'bearer',token_type:'Bearer',expires_at:'later'};
  else if(path.endsWith('/details'))data={order_reference:'o1',status:'NEEDS_REVIEW',township:'Kamaryut',policy:{}};
  else if(path.includes('/api/confirm/'))data={order_reference:'o1',state:'VERIFICATION_REQUIRED',delivery_status:'NEEDS_REVIEW'};
  else if(path.endsWith('/queue'))data={items:[]};
  return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
 };
 t.mock.method(globalThis,'fetch',async(url,opts={})=>{
   const path=new URL(url).pathname;
   if(path==='/dashboard/bootstrap')return new Response(JSON.stringify({test_mode:true,csrf:'fixture-csrf'}));
   if(path!=='/dashboard/api')throw Error('Unexpected frontend transport route');
   const call=JSON.parse(opts.body),base=call.actor==='rider'?'http://127.0.0.1:8001':'http://127.0.0.1:8000';
   const endpoint=call.path.replace('@buyer',token);
   const result=await backendFetch(base+endpoint,{method:call.method,headers:{},body:call.body==null?undefined:JSON.stringify(call.body)});
   let data=await result.json();
   if(endpoint.endsWith('/confirmation-link')&&result.ok)data={buyer_handle:token};
   if(endpoint.endsWith('/verify')&&result.ok)data={verified:true};
   return new Response(JSON.stringify({data,status:result.status,endpoint,ok:result.ok}),{status:result.status,headers:{'Content-Type':'application/json'}});
 });
 const e=environment(null,hash);Object.assign(e.ctx,{WorkspaceApi,context,today,townships,mmk,tokenFrom,crypto,clearTimeout:e.ctx.clearTimeout,history:{replaceState:(_s,_t,url)=>{e.replacedUrl=url;}}});
 Object.assign(e.ctx.location,{origin:'http://127.0.0.1:8000',protocol:'http:',pathname:'/api.html'});
 vm.runInNewContext(source,e.ctx);
 return {...e,calls,get replacedUrl(){return e.replacedUrl;},async flush(){for(let n=0;n<20;n++)await e.tick(0);}};
}

test('API admin connection and order form render without touching local prototype storage',async t=>{
 const e=setup(t);await e.ctx.ready;assert.ok(e.find('#connect-form'));
 await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});assert.ok(e.find('#create-form'));assert.match(e.root.textContent,/API records are separate/);assert.doesNotMatch(e.root.textContent,/Merchant/);
 e.ctx.location.hash='#/order/o1';await e.flush();assert.ok(e.find('#edit-api-form'));await e.action('link','o1');assert.match(e.find('[name="generated-link"]').value,/#\/track\//);assert.equal(e.calls.at(-1).opts.headers['X-Dev-Access-Token'],undefined);
});

test('a fresh parse clears stale extracted fields and resets prepaid selection',async t=>{
 let count=0;
 const e=setup(t,'#/admin',path=>path==='/api/orders/parse'?new Response(JSON.stringify({
   address:count++?{cod_amount:5000}:{phone_number:'09790000000',township:'Hlaing',cod_amount:0},
   confidence:count===1?'AMBER':'RED',ai:{status:'not_requested'},validation_reasons:[],
 }),{headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 await e.submit('#parse-form',{raw:'First fictional order'});
 assert.equal(e.find('#create-form [name="customer_phone"]').value,'09790000000');
 assert.equal(e.find('#create-form [name="payment"]').value,'prepaid');
 await e.submit('#parse-form',{raw:'Second incomplete fictional order'});
 assert.equal(e.find('#create-form [name="customer_phone"]').value,'');
 assert.equal(e.find('#create-form [name="township"]').value,'');
 assert.equal(e.find('#create-form [name="payment"]').value,'cod');
});

test('successful writes keep their confirmation notice after refreshed data renders',async t=>{
 const e=setup(t);await e.ctx.ready;
 await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 await e.submit('#new-rider-form',{name:'Fictional QA rider'});
 assert.match(e.find('#api-status').textContent,/Saved in the backend database/);
 assert.equal(e.find('#api-status').hidden,false);
});

test('persisted history sorts chronologically and omits private event metadata',async t=>{
 const e=setup(t,'#/admin',path=>path.endsWith('/events')?new Response(JSON.stringify({items:[
  {id:'b',event_type:'DELIVERY_COMPLETED',previous_status:'OUT_FOR_DELIVERY',new_status:'DELIVERED',created_at:'2026-10-21T12:00:00Z',metadata:{phone:'09790000000',instructions:'private-note'}},
  {id:'a',event_type:'DELIVERY_STARTED',previous_status:'ASSIGNED',new_status:'OUT_FOR_DELIVERY',created_at:'2026-10-21T11:00:00Z',metadata:{authorization:'private-token'}},
 ],total:2}),{headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 e.ctx.location.hash='#/order/o1';await e.flush();
 const history=e.find('#delivery-history');assert.equal(history.querySelectorAll('li').length,2);
 assert.match(history.querySelector('li').textContent,/DELIVERY STARTED/);
 assert.doesNotMatch(history.textContent,/09790000000|private-note|private-token/);
});

test('history read failure is explicit while the saved order remains usable',async t=>{
 const e=setup(t,'#/admin',path=>path.endsWith('/events')?new Response(JSON.stringify({error:{code:'UNAVAILABLE',message:'private-upstream-detail'}}),{status:503,headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 e.ctx.location.hash='#/order/o1';await e.flush();
 assert.ok(e.find('#edit-api-form'));assert.match(e.find('#delivery-history').textContent,/could not be loaded/);
 assert.doesNotMatch(e.find('#delivery-history').textContent,/private-upstream-detail/);
});

test('API customer card verifies using only its own bearer and erases token from current URL',async t=>{
 const e=setup(t,'#/track/'+token);await e.ctx.ready;assert.ok(e.find('#verify-api-form'));assert.equal(e.replacedUrl,'/api.html#/customer');
 await e.submit('#verify-api-form',{digits:'4567'});assert.ok(e.find('#buyer-location-form'));assert.ok(e.find('#buyer-response-form'));assert.ok(e.calls.every(c=>!c.opts.headers?.['X-Dev-Access-Token']));assert.equal(e.calls.at(-1).opts.headers.Authorization,undefined);
});

test('API customer failures keep entered form and never display a saved confirmation',async t=>{
 const e=setup(t,'#/track/'+token,(path)=>path.endsWith('/verify')?new Response(JSON.stringify({error:{code:'BUYER_VERIFICATION_FAILED',message:'Verification failed'}}),{status:403,headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#verify-api-form',{digits:'0000'});assert.equal(e.find('[name="digits"]').value,'0000');assert.match(e.find('#api-status').textContent,/Verification failed/);assert.equal(e.find('#buyer-location-form'),null);
});

test('API rider delivery form waits two seconds, preserves actual amount, and only then saves',async t=>{
 const stop={order_id:'o1',order_version:2,status:'OUT_FOR_DELIVERY',customer_name:'Buyer',cod_amount:'25000'};
 const e=setup(t,'#/rider',(path)=>path.endsWith('/queue')?new Response(JSON.stringify({items:[stop]}),{headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8001'});await e.action('deliver','o1');assert.equal(e.find('dialog [type="submit"]').disabled,true);await e.tick(1999);assert.equal(e.find('dialog [type="submit"]').disabled,true);await e.tick(1);assert.equal(e.find('dialog [type="submit"]').disabled,false);
 await e.submit('dialog form',{amount:'24000',reason:'Recipient paid short'});const call=e.calls.find(c=>c.url.includes('/deliveries/'));const body=JSON.parse(call.opts.body);assert.equal(body.actual_amount,24000);assert.equal(body.difference_reason,'Recipient paid short');assert.equal(e.find('dialog'),null);
});

test('reference-themed admin counts come from API records and section shortcuts do not issue writes',async t=>{
 const e=setup(t);await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 assert.equal(e.find('.dashboard-balance strong').textContent,'1');assert.ok(e.find('.api-sidebar'));assert.ok(e.find('.order-table'));assert.ok(e.find('#add-order'));assert.match(e.root.textContent,/COD amount/);assert.doesNotMatch(e.root.textContent,/Ethereum|USDC|BaseApp/);
 const link=e.all('[data-section]').find(a=>a.dataset.section==='add-order');const before=e.calls.length;const hash=e.ctx.location.hash;await link.click();assert.equal(e.calls.length,before);assert.equal(e.ctx.location.hash,hash);
});

test('reference-themed customer progress never labels a review order confirmed',async t=>{
 const e=setup(t,'#/track/'+token);await e.ctx.ready;assert.ok(e.find('.customer-hero'));assert.ok(e.find('.courier-art'));assert.match(e.find('.customer-hero h1').textContent,/made simple/);assert.doesNotMatch(e.find('.customer-hero h1').textContent,/confirmed/);assert.equal(e.find('.delivery-progress .is-current').textContent,'Order received');assert.match(e.body.attributes.class,/role-customer/);
});

test('reference-themed rider uses illustrative geography and existing real delivery controls',async t=>{
 const stop={order_id:'o1',order_version:2,status:'OUT_FOR_DELIVERY',customer_name:'Buyer',township:'Kamaryut',street:'Hledan Road',cod_amount:'25000'};
 const e=setup(t,'#/rider',path=>path.endsWith('/queue')?new Response(JSON.stringify({items:[stop]}),{headers:{'Content-Type':'application/json'}}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8001'});assert.ok(e.find('.route-map'));assert.ok(e.find('.rider-bottom-nav'));assert.match(e.find('.map-disclaimer').textContent,/Illustrative/);assert.match(e.find('.map-destination').textContent,/Hledan Road/);assert.match(e.find('.stop-payment').textContent,/25,000 MMK/);assert.doesNotMatch(e.root.textContent,/21 min|Visa|US\$/);assert.ok(e.all('[data-action]').some(b=>b.dataset.action==='deliver'&&b.dataset.id==='o1'));
});

const reply=data=>new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
test('admin prepares, records explicit receipt and assigns in one call, then dispatches from the same order',async t=>{
 let saved={...order,status:'DRAFT',parsing_metadata:{parcel:{...order.parsing_metadata.parcel,hub_received_at:null}}},route=null;
 const e=setup(t,'#/admin',(path,opts)=>{
  if(path==='/api/orders/o1')return reply(saved);
  if(path==='/api/routes')return reply({items:route?[route]:[],total:route?1:0});
  if(path.endsWith('/prepare-assignment')){
   route={id:'route1',rider_id:'rider1',version:1,day:today(),state:'draft',items:[{id:'o1',status:'ASSIGNED',name:'Buyer'}],recorded_total:0,blockers:[]};
   saved={...saved,status:'ASSIGNED',version:5,parsing_metadata:{parcel:{...saved.parsing_metadata.parcel,hub_received_at:'now',route_id:route.id}}};
   return reply({order:saved,route});
  }
  if(path.endsWith('/actions'))return reply({...route,state:'dispatched'});
 });
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});e.ctx.location.hash='#/order/o1';await e.flush();
 assert.ok(e.find('#prepare-assignment-form'));
 await e.submit('#prepare-assignment-form',{selection:'rider:rider1',ack:true});assert.match(e.find('#api-status').textContent,/physical hub receipt/);
 assert.equal(e.calls.filter(c=>c.url.endsWith('/prepare-assignment')).length,0);
 await e.submit('#prepare-assignment-form',{selection:'rider:rider1',received:true,ack:true});
 const prep=e.calls.filter(c=>c.url.endsWith('/prepare-assignment'));assert.equal(prep.length,1);assert.equal(e.calls.filter(c=>c.opts.method==='PATCH').length,0);
 assert.deepEqual(JSON.parse(prep[0].opts.body),{request_id:JSON.parse(prep[0].opts.body).request_id,expected_version:1,rider_id:'rider1',receive_at_hub:true,acknowledge_unverified_location:true});
 assert.equal(e.find('#prepare-assignment-form'),null);assert.ok(e.all('[data-action]').some(b=>b.dataset.action==='dispatch'));
 assert.equal(e.calls.filter(c=>c.url.endsWith('/actions')).length,0);
 await e.action('dispatch','route1');assert.match(e.find('dialog').textContent,/physically present/);await e.submit('dialog form');
 assert.equal(JSON.parse(e.calls.find(c=>c.url.endsWith('/actions')).opts.body).action,'DISPATCH');
});

test('prepare retry keeps request identity and form after a network error',async t=>{
 const sent=[];
 const e=setup(t,'#/admin',(path,opts)=>{
  if(path.endsWith('/prepare-assignment')){sent.push(JSON.parse(opts.body));throw new TypeError('Connection interrupted');}
 });
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});e.ctx.location.hash='#/order/o1';await e.flush();
 await e.submit('#prepare-assignment-form',{selection:'rider:rider1',ack:true});assert.ok(e.find('#prepare-assignment-form'));assert.match(e.find('#api-status').textContent,/No success was confirmed/);
 await e.submit('#prepare-assignment-form');assert.deepEqual(sent[0],sent[1]);
});

test('pending customer review blocks the short prepare path without approving anything automatically',async t=>{
 const e=setup(t,'#/admin',path=>path.endsWith('/buyer-requests')?reply({items:[{id:'b1',kind:'LOCATION',decision:'REVIEW_REQUIRED',resolution:null,reason_codes:['INITIAL_PIN_REQUIRES_REVIEW'],submitted_values:{latitude:'16.8',longitude:'96.1'}}],total:1}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});e.ctx.location.hash='#/order/o1';await e.flush();
 assert.equal(e.find('#prepare-assignment-form'),null);assert.match(e.find('#prepare-parcel').textContent,/1 customer update/);assert.ok(e.all('[data-action]').some(b=>b.dataset.action==='review'));assert.equal(e.calls.filter(c=>['POST','PATCH'].includes(c.opts.method)).length,0);
});

test('future draft route explains its departure day instead of offering an unusable dispatch action',async t=>{
 const future=new Date(Date.now()+23400000+86400000).toISOString().slice(0,10);
 const route={id:'r1',rider_id:'rider1',day:future,state:'draft',items:[{id:'o1',status:'ASSIGNED',name:'Buyer'}],recorded_total:0,blockers:[]};
 const e=setup(t,'#/admin',path=>path==='/api/routes'?reply({items:[route],total:1}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8000'});
 assert.match(e.root.textContent,/Departure is scheduled for/);assert.equal(e.all('[data-action]').some(b=>b.dataset.action==='dispatch'),false);
});

test('rider current stop advances after delivery; other stops stay in a collapsible queue',async t=>{
 let stops=[{order_id:'o1',order_version:2,status:'OUT_FOR_DELIVERY',customer_name:'First buyer',cod_amount:'25000'},{order_id:'o2',order_version:3,status:'OUT_FOR_DELIVERY',customer_name:'Second buyer',cod_amount:'0'}];
 const e=setup(t,'#/rider',(path,opts)=>{
  if(path.endsWith('/queue'))return reply({items:stops});
  if(path.includes('/deliveries/')){stops=stops.slice(1);return reply({});}
 });
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8001'});
 assert.match(e.find('.current-stop').textContent,/First buyer/);assert.match(e.find('.remaining-stops summary').textContent,/1/);
 await e.action('deliver','o1');await e.tick(2000);await e.submit('dialog form',{amount:'25000'});
 assert.match(e.find('.current-stop').textContent,/Second buyer/);assert.equal(e.find('.remaining-stops'),null);
});

for(const [name,route,title,canHandover] of [
 ['physical returns',{state:'dispatched',items:[{id:'o1',status:'FAILED',return_received:false}]},/Return 1 parcel/,false],
 ['cash handover',{state:'dispatched',items:[{id:'o1',status:'DELIVERED'}]},/hand over your cash/,true],
 ['hub receipt',{state:'closing',items:[{id:'o1',status:'DELIVERED'}],handover:{status:'submitted',declared:25000}},/Waiting for hub cash receipt/,false],
 ['admin review',{state:'closing',items:[{id:'o1',status:'DELIVERED'}],handover:{status:'received',declared:25000,received:25000},blockers:['Resolve incident']},/Hub review still needed/,false],
 ['route departure',{state:'draft',items:[{id:'o1',status:'ASSIGNED'}]},/Waiting for admin departure/,false]
])test('rider empty queue explains '+name+' rather than showing a finished route',async t=>{
 const r={id:'r1',rider_id:'rider1',version:1,day:today(),recorded_total:25000,blockers:[],...route};
 const e=setup(t,'#/rider',path=>path==='/api/routes'?reply({items:[r],total:1}):null);
 await e.ctx.ready;await e.submit('#connect-form',{base:'http://127.0.0.1:8001'});
 assert.match(e.find('.rider-overview h1').textContent,title);assert.equal(e.all('[data-action]').some(b=>b.dataset.action==='handover'),canHandover);assert.doesNotMatch(e.root.textContent,/all caught up/);
});
