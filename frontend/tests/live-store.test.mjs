import test from 'node:test';
import assert from 'node:assert/strict';
import {createLiveStore,projectOrder} from '../js/live-store.mjs';
const original={id:'synthetic-order',version:1,customer_name:'Fictional buyer',customer_phone:'09790000000',status:'DRAFT',confidence_level:'AMBER',confidence_reasons:[{message:'Location not verified'}],latitude:null,longitude:null,cod_amount:'25000',ai_availability_status:'mock',parsing_metadata:{parcel:{item:'Test shirt',delivery_day:'2026-10-23'}},field_sources:{}};
const W=()=>({ACTORS:{admin:{id:'dispatch',role:'admin'},rider:{id:'old-demo-id',role:'rider'}},PLACES:[],ANY_TIME:'Any time',day:()=> '2026-10-23',addDays:()=> '2026-10-24'});
function apiFixture(){
  const calls=[];
  const api={connections:{},async connect(side,origin,actorId){api.connections[side]={actor:{id:actorId||(side==='admin'?'dispatch':'rider'),name:'Fictional actor'}};},async all(side,path){calls.push({side,path});return path==='/api/orders'?[structuredClone(original)]:path==='/api/riders'?[{id:'rider',name:'Fictional rider'},{id:'other',name:'Other fictional rider'}]:[];},async call(side,path,options){calls.push({side,path,...options});if(path.endsWith('/queue'))return {items:[]};return {id:'created'};},openBuyer(){api.buyer={card:async()=>({state:'VERIFICATION_REQUIRED',order_reference:'public-reference'})};}};
  return {api,calls};
}
const setup=async(route='dispatch')=>{const f=apiFixture();const dictionary=W();return {...f,dictionary,store:await createLiveStore(dictionary,{api:f.api,origin:'http://127.0.0.1:8780',route})};};
test('live projection never manufactures coordinates, anchors or GREEN',()=>{
 const o=projectOrder(original);assert.equal(o.pin,null);assert.equal(o.anchor,null);assert.equal(o.confidence,'AMBER');assert.equal(o.expected,25000);
 const p=projectOrder({...original,latitude:'0',longitude:'0'});assert.deepEqual(p.pin,{lat:0,lng:0});assert.equal(p.location,'manual_unverified');
});
test('opening a buyer capability never fetches dispatcher orders or riders',async()=>{
 const {calls,store}=await setup('track/'+'a'.repeat(43));assert.deepEqual(calls,[]);assert.deepEqual(store.snapshot().orders,[]);assert.equal(store.customer('a'.repeat(43)).verified,false);
});
test('entering buyer view clears private dispatcher projections',async()=>{
 const {store}=await setup();assert.equal(store.snapshot().orders.length,1);assert.equal(store.linkStatus(original.id),'not_loaded');await store.sync('track/'+'a'.repeat(43));assert.equal(store.snapshot().orders.length,0);
});
test('unavailable backend cannot create a local fake order',async t=>{
 const {api,store}=await setup();t.mock.getter(globalThis,'navigator',()=>({onLine:true}));api.call=async()=>{throw Error('Synthetic DB unavailable');};
 await assert.rejects(store.execute('create_manual',{fields:{name:'Fictional',phone:'09790000000',areaId:'Hlaing',payment:'prepaid',item:'Shirt',date:'2026-10-23'}}),/DB unavailable/);assert.equal(store.snapshot().orders.length,1);
});
test('unsupported live operations and offline mutations fail explicitly',async t=>{
 const {store}=await setup();t.mock.getter(globalThis,'navigator',()=>({onLine:true}));await assert.rejects(store.execute('clock'),/Unsupported in LIVE_BACKEND/);
 t.mock.getter(globalThis,'navigator',()=>({onLine:false}));await assert.rejects(store.execute('receive',{id:original.id}),/CONNECTION_ERROR/);assert.equal(store.snapshot().orders[0].received,false);
});
test('raw imports use actual backend parsing, preserve input and report partial writes',async t=>{
 const {api,store,calls}=await setup();t.mock.getter(globalThis,'navigator',()=>({onLine:true}));
 let count=0;const fn=api.call;api.call=async(...args)=>{if(++count===2)throw Error('Synthetic write rejection');return fn(...args);};
 await assert.rejects(store.execute('create_batch',{records:[{raw:'Original Burmese ၁၂'},{raw:'Other input'}],item:'Shirt',date:'2026-10-23'}),/1 order\(s\) persisted/);
 const written=calls.find(c=>c.method==='POST');assert.equal(written.body.raw_text,'Original Burmese ၁၂');assert.equal(written.body.structured,undefined);assert.equal(written.body.parcel.item,'Shirt');
});
test('switching rider loads only the actual assigned rider queue',async()=>{
 const {calls,store}=await setup('ride');assert.equal(store.snapshot().orders.length,0);assert.ok(calls.some(c=>c.path==='/api/riders/rider/queue'&&c.side==='rider'));assert.ok(!calls.some(c=>c.path==='/api/orders'));const other=await setup();await other.store.sync('ride');await other.store.selectRider('other');assert.equal(other.dictionary.ACTORS.rider.id,'rider');assert.equal(other.dictionary.ACTORS.rider2.id,'other');assert.equal(other.store.riderActor().id,'other');assert.ok(other.calls.some(c=>c.path==='/api/riders/other/queue'));
});
test('live parser projection uses server classification and AI status, no client geocoding',async()=>{
 const {api,store}=await setup();api.call=async()=>({address:{phone_number:'09790000000',township:'Hlaing',cod_amount:6000},confidence:'AMBER',validation_reasons:[{message:'Unverified'}],ai:{status:'mock',message:'No real extraction'}});
 const r=await store.parse('original');assert.equal(r.phone,'09790000000');assert.equal(r.expected,6000);assert.equal(r.confidence,'amber');assert.equal(r.pin,null);assert.ok(r.warnings.some(x=>x.includes('mock')));
});

const pendingReviews=()=>[
 {id:'location-row',request_id:'location-request',kind:'LOCATION',decision:'REVIEW_REQUIRED',resolution:null,submitted_values:{latitude:'16.82',longitude:'96.13'}},
 {id:'response-row',request_id:'response-request',kind:'RESPONSE',decision:'REVIEW_REQUIRED',resolution:null,submitted_values:{action:'AVAILABLE',instructions:'Call at the gate'}}
];
async function reviewSetup(){
 const f=apiFixture(),updates=pendingReviews(),all=f.api.all;
 f.api.all=async(side,path)=>path.endsWith('/buyer-requests')?structuredClone(updates):all(side,path);
 f.api.order=async()=>structuredClone(original);
 const call=f.api.call;f.api.call=async(side,path,options)=>{const r=updates.find(r=>path.endsWith('/buyer-requests/'+r.id));if(r&&options.method==='PATCH')r.resolution=options.body.decision;return call(side,path,options);};
 const store=await createLiveStore(W(),{api:f.api,origin:'http://127.0.0.1:8780',route:'order/'+original.id});
 return {...f,store,updates};
}

test('pending buyer reviews remain explicit until both location and response have been resolved',async t=>{
 t.mock.getter(globalThis,'navigator',()=>({onLine:true}));const {store,calls}=await reviewSetup();
 assert.equal(store.order(original.id).pendingBuyerReviewCount,2);
 assert.ok(store.blockers(original.id).some(b=>/2 buyer requests/.test(b)));
 await store.execute('approve_customer_location',{id:original.id,requestId:'location-request',reason:'Checked the buyer pin'});
 assert.equal(store.order(original.id).pendingBuyerReviewCount,1);
 assert.equal(store.requests()[0].kind,'RESPONSE');
 await store.execute('approve_customer_location',{id:original.id,requestId:'response-request',reason:'Checked availability and instructions'});
 assert.equal(store.order(original.id).pendingBuyerReviewCount,0);
 assert.deepEqual(store.requests(),[]);
 assert.deepEqual(calls.filter(c=>c.method==='PATCH').map(c=>c.path),['/api/orders/synthetic-order/buyer-requests/location-row','/api/orders/synthetic-order/buyer-requests/response-row']);
});

test('reconfirmation checks buyer reviews before sending automatic allocation',async t=>{
 t.mock.getter(globalThis,'navigator',()=>({onLine:true}));const {store,api,updates}=await reviewSetup();let allocated=0;
 api.autoAssignment=async()=>{allocated++;return {allocation_status:'ASSIGNED',assignment:{rider_id:'rider'},route:{id:'route'}};};
 await assert.rejects(store.execute('assign',{id:original.id,acknowledge:true}),/Review.*buyer request/);
 assert.equal(allocated,0);
 updates.forEach(r=>r.resolution='APPROVE');
 await store.execute('assign',{id:original.id,acknowledge:true});assert.equal(allocated,1);
});

test('dispatcher reconfirmation uses server auto-allocation and keeps a no-rider result waiting',async t=>{
 t.mock.getter(globalThis,'navigator',()=>({onLine:true}));const {store,api,calls}=await setup();api.order=async()=>structuredClone(original);let body;
 api.autoAssignment=async(order,options,requestId)=>{body={order,options,requestId};return {allocation_status:'WAITING_FOR_RIDER',reason:'NO_AVAILABLE_RIDER',assignment:null,route:null};};
 await store.execute('assign',{id:original.id,acknowledge:true});
 assert.equal(body.order.id,original.id);assert.deepEqual(body.options,{received:false,acknowledge:true});
 assert.equal(store.order(original.id).allocationStatus,'WAITING_FOR_RIDER');
 assert.equal(store.order(original.id).routeId,null);assert.equal(store.snapshot().routes.length,0);
 assert.ok(!calls.some(c=>c.path?.endsWith('/prepare-assignment')));
});

test('stale rider-offer reply refreshes the queue and never fabricates acceptance',async t=>{
 t.mock.getter(globalThis,'navigator',()=>({onLine:true}));const {api,store}=await setup('ride'),offer={order_id:'synthetic-order',order_version:4,assignment_id:'offer-1',offer_version:2,response_status:'PENDING',status:'ASSIGNED',customer_name:'Fictional buyer'};
 let queueCalls=0;api.call=async(side,path)=>path.endsWith('/queue')?(queueCalls++,{items:[structuredClone(offer)]}):path.endsWith('/route-plans')?{items:[]}:{items:[]};await store.sync('ride');let replyCalls=0;
 api.respondToOffer=async(row,action,requestId)=>{replyCalls++;assert.equal(row.assignment_id,'offer-1');assert.equal(row.offer_version,2);assert.equal(action,'ACCEPT');assert.ok(requestId);throw Object.assign(new Error('Stale rider offer'),{status:409});};
 await assert.rejects(store.execute('offer_response',{id:'synthetic-order',action:'ACCEPT'},{id:'rider'}),/Stale rider offer/);
 assert.equal(replyCalls,1);assert.equal(queueCalls,2);
 assert.equal(store.order('synthetic-order').responseStatus,'PENDING');
});

test('live buyer OTP preview is separate from the public challenge and is cleared after verification',async()=>{
 const token='a'.repeat(43),f=apiFixture();f.api.openBuyer=()=>{f.api.buyer={card:async()=>({state:'VERIFICATION_REQUIRED'}),requestOtp:async()=>({challenge_id:'challenge',destination_masked:'••••4567',expires_at:'later',resend_after:'soon',mode:'DEMO'}),demoCode:async()=>({simulation:true,code:'123456',notice:'SIMULATION ONLY'}),verify:async code=>assert.equal(code,'123456'),details:async()=>({order_reference:'buyer-ref',status:'CONFIRMED'})};};
 const store=await createLiveStore(W(),{api:f.api,origin:'http://127.0.0.1:8780',route:'track/'+token});await store.requestOtp(token);
 assert.equal(store.customer(token).verified,false);assert.equal(store.customer(token).otpPreview.simulation,true);assert.equal(store.customer(token).simulationOnly,true);assert.deepEqual(store.customer(token).order,{});
 await store.verify(token,'123456');assert.equal(store.customer(token).verified,true);assert.equal(store.customer(token).otpPreview,null);assert.equal(store.customer(token).simulationOnly,false);
});

test('buyer confirmation keeps submitted values only after both writes succeed',async t=>{
 t.mock.getter(globalThis,'navigator',()=>({onLine:true}));const f=apiFixture(),token='a'.repeat(43);let failResponse=false;
 f.api.openBuyer=()=>{f.api.buyer={card:async()=>({state:'VERIFICATION_REQUIRED'}),verify:async()=>{},details:async()=>({order_reference:'buyer-ref',status:'NEEDS_REVIEW',initial_pin_requires_review:true}),location:async()=>({decision:'REVIEW_REQUIRED'}),respond:async()=>{if(failResponse)throw Error('Response rejected');return {decision:'REVIEW_REQUIRED'};}};};
 const store=await createLiveStore(W(),{api:f.api,origin:'http://127.0.0.1:8780',route:'track/'+token});await store.verify(token,'0000');
 const request={pin:{lat:16.82,lng:96.13},answer:'At home',time:'Any time',note:'Call at the gate',date:'2026-10-23',acknowledged:true};
 failResponse=true;await assert.rejects(store.confirm(token,request),/availability was not saved/);assert.equal(store.customer(token).order.confirmation,null);
 failResponse=false;await store.confirm(token,request);
 assert.equal(store.customer(token).order.confirmation.note,'Call at the gate');assert.deepEqual(store.customer(token).order.confirmation.pin,request.pin);assert.equal(store.customer(token).order.confirmation.date,request.date);
});
