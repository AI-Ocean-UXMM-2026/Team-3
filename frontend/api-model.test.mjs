import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkspaceApi, manualPayload, tokenFrom, mmk, today} from './api-model.mjs';

const secret='local-only-test-token-'+'x'.repeat(40),token='A'.repeat(43);
const reply=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const fields={customer_name:' Test buyer ',customer_phone:'09791234567',township:'Kamaryut',item:'Envelope',payment:'cod',cod_amount:'25000',delivery_day:today()};

test('manual API payload has no merchant dependency, exact money and no invented GPS',()=>{
 const body=manualPayload(fields);assert.equal(body.merchant_id,undefined);assert.equal(body.structured.cod_amount,'25000');assert.equal(body.structured.latitude,undefined);assert.equal(body.parcel.delivery_day,today());assert.equal(body.parcel.item,'Envelope');
 assert.equal(manualPayload({...fields,payment:'prepaid',cod_amount:'999'}).structured.cod_amount,'0');
 for(const value of ['','-1','1.5','1000000001','1e5'])assert.throws(()=>mmk(value));
 assert.throws(()=>manualPayload({...fields,cod_amount:'0'}),/positive/);assert.throws(()=>manualPayload({...fields,latitude:'16.8'}),/both coordinates/);
});

test('private customer links accept native and hash formats without malformed tokens',()=>{
 assert.equal(tokenFrom('http://127.0.0.1:8000/confirm/'+token),token);assert.equal(tokenFrom('http://127.0.0.1:8000/api.html#/track/'+token),token);assert.equal(tokenFrom(token),token);assert.throws(()=>tokenFrom('demo-2045'));
});

test('API role is server-bound and admin/rider/customer credentials are separate',async t=>{
 const calls=[];t.mock.method(globalThis,'fetch',async(url,opts)=>{calls.push({url,opts});if(url.endsWith('/api/session'))return reply({id:url.includes(':8001')?'rider-id':'admin-id',name:'Test',role:url.includes(':8001')?'Rider':'Admin'});if(url.endsWith('/verify'))return reply({access_token:'buyer-bearer-only',token_type:'Bearer',expires_at:'later'});return reply({items:[],total:0});});
 const api=new WorkspaceApi();await api.connect('admin','http://127.0.0.1:8000',secret);await api.connect('rider','http://127.0.0.1:8001',secret+'rider');await assert.rejects(()=>api.connect('rider','http://127.0.0.1:8000',secret),/belongs to Admin/);
 api.openBuyer('http://127.0.0.1:8000',token);await api.buyer.card();await api.buyer.verify('4567');await api.buyer.details();
 const buyer=calls.filter(c=>c.url.includes('/api/confirm/'));assert.ok(buyer.every(c=>!c.opts.headers['X-Dev-Access-Token']));assert.equal(buyer.at(-1).opts.headers.Authorization,'Bearer buyer-bearer-only');
 await api.call('rider','/api/routes');assert.equal(calls.at(-1).opts.headers['X-Dev-Access-Token'],secret+'rider');assert.equal(calls.at(-1).opts.headers.Authorization,undefined);
 api.disconnect('admin');await assert.rejects(()=>api.order('x'),/Connect/);
});

test('ready action waits for actual server transitions and requires explicit map review',async t=>{
 const calls=[];t.mock.method(globalThis,'fetch',async(url,opts)=>{if(url.endsWith('/session'))return reply({id:'admin',role:'Admin'});const b=JSON.parse(opts.body);calls.push(b);return reply({id:'o',version:b.expected_version+1,status:b.status});});
 const api=new WorkspaceApi();await api.connect('admin','http://127.0.0.1:8000',secret);await assert.rejects(()=>api.ready({id:'o',status:'DRAFT',version:1},false),/explicitly acknowledge/);
 const row=await api.ready({id:'o',status:'DRAFT',version:1},true);assert.equal(row.status,'READY_FOR_DISPATCH');assert.deepEqual(calls.map(c=>c.expected_version),[1,2,3]);assert.equal(calls[2].acknowledge_unverified_location,true);
});

test('network/conflict errors never become successful local saves; 401 clears only matching connection',async t=>{
 let fail=false;t.mock.method(globalThis,'fetch',async(url)=>{if(url.endsWith('/session'))return reply({id:'admin',role:'Admin'});if(fail==='network')throw new TypeError('Network unavailable');return reply({error:{code:'VERSION_CONFLICT',message:'Changed'}},fail?401:409);});
 const api=new WorkspaceApi();await api.connect('admin','http://127.0.0.1:8000',secret);await assert.rejects(()=>api.order('o'),{status:409});assert.ok(api.connections.admin);
 fail='network';await assert.rejects(()=>api.create(fields),TypeError);assert.ok(api.connections.admin);
 fail=true;await assert.rejects(()=>api.order('o'),{status:401});assert.equal(api.connections.admin,undefined);
});

test('delivery and combined closeout carry actual amounts, current versions and stable retry identity',async t=>{
 const calls=[];t.mock.method(globalThis,'fetch',async(url,opts)=>{if(url.endsWith('/session'))return reply({id:url.includes(':8001')?'rider-id':'admin-id',role:url.includes(':8001')?'Rider':'Admin'});calls.push({url,body:JSON.parse(opts.body)});return reply({state:'closed'});});
 const api=new WorkspaceApi();await api.connect('admin','http://127.0.0.1:8000',secret);await api.connect('rider','http://127.0.0.1:8001',secret);
 await api.delivery({order_id:'o',order_version:4},'DELIVERED',{actual_amount:25000,cod_collected:true},'operation-1');assert.equal(calls[0].body.actual_amount,25000);assert.equal(calls[0].body.expected_version,4);
 await api.routeAction('admin',{id:'r',version:5},'RECEIVE_CLOSE',{amount:25000},'receipt-1');await api.routeAction('admin',{id:'r',version:5},'RECEIVE_CLOSE',{amount:25000},'receipt-1');assert.deepEqual(calls[1],calls[2]);
});

test('atomic preparation uses one versioned request for either route choice and never dispatches',async t=>{
 const calls=[];t.mock.method(globalThis,'fetch',async(url,opts)=>{if(url.endsWith('/session'))return reply({id:'a',role:'Admin'});calls.push({url,body:JSON.parse(opts.body)});return reply({route:{id:'r'}});});
 const api=new WorkspaceApi();await api.connect('admin','http://127.0.0.1:8000',secret);
 const order={id:'o',version:2,parsing_metadata:{parcel:{}}};
 assert.throws(()=>api.prepareAssignment(order,'rider:person',{received:true}),/acknowledge/);
 assert.throws(()=>api.prepareAssignment(order,'rider:person',{acknowledge:true}),/physical hub receipt/);
 assert.throws(()=>api.prepareAssignment(order,'',{received:true,acknowledge:true}),/Choose/);
 await api.prepareAssignment(order,'rider:person',{received:true,acknowledge:true},'same-request');
 await api.prepareAssignment(order,'rider:person',{received:true,acknowledge:true},'same-request');
 assert.deepEqual(calls[0],calls[1]);assert.equal(calls[0].body.expected_version,2);assert.equal(calls[0].body.rider_id,'person');assert.equal(calls[0].body.route_id,undefined);
 await api.prepareAssignment(order,'route:existing',{received:true,acknowledge:true},'other-request');
 assert.equal(calls[2].body.route_id,'existing');assert.equal(calls[2].body.rider_id,undefined);assert.ok(calls.every(c=>c.url.endsWith('/prepare-assignment')));
});
