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
