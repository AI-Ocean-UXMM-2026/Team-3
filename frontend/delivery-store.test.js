const test = require('node:test');
const assert = require('node:assert/strict');
const {createStore,BASE,distance} = require('./delivery-store.js');
const memory=()=>{const data=new Map();return {getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)};};
const confirmation={pin:BASE,time:'16:00–18:00',answer:'At home',note:'Blue gate'};
test('customer edits require phone verification; three incorrect attempts lock the link',()=>{
 const s=createStore(memory());assert.throws(()=>s.confirm(confirmation),/Verify/);
 assert.throws(()=>s.verify('0000'),/2 attempts/);assert.throws(()=>s.verify('0000'),/1 attempts/);
 assert.throws(()=>s.verify('0000'),/locked/);assert.throws(()=>s.verify('1602'),/locked/);
 assert.equal(s.stop('LP-2045').locked,true);
});
test('confirmation persists, reorders the queue, and verification does not persist',()=>{
 const storage=memory(),s=createStore(storage);s.verify('1602');s.confirm(confirmation);
 assert.equal(s.queue()[0].id,'LP-2044');assert.equal(s.stop('LP-2045').confirmed,true);
 const reopened=createStore(storage);assert.equal(reopened.stop('LP-2045').note,'Blue gate');assert.equal(reopened.verified(),false);
 assert.equal(reopened.snapshot().events[0].type,'buyer_confirmed');
});
test('geofence rejects pins beyond 500 metres',()=>{
 const s=createStore(memory());s.verify('1602');const outside={lat:BASE.lat+.01,lng:BASE.lng};
 assert.ok(distance(BASE,outside)>500);assert.throws(()=>s.confirm({...confirmation,pin:outside}),/500 m/);assert.equal(s.stop('LP-2045').confirmed,false);
});
test('COD records once, flags mismatches and prohibits prepaid cash collection',()=>{
 const s=createStore(memory());assert.throws(()=>s.complete('LP-2043',100),/prepaid/);assert.throws(()=>s.complete('LP-2045',-1),/whole MMK/);
 s.complete('LP-2045',27000);assert.equal(s.stop('LP-2045').discrepancy,true);assert.throws(()=>s.complete('LP-2045',28000),/closed/);assert.ok(!s.queue().some(x=>x.id==='LP-2045'));
});
test('retry stays in queue at a later window; return removes the stop',()=>{
 const s=createStore(memory());s.fail('LP-2045','Not at home','retry');assert.equal(s.stop('LP-2045').time,'16:00–18:00');assert.equal(s.queue().at(-1).id,'LP-2045');
 s.fail('LP-2045','Buyer refused','return');assert.ok(!s.queue().some(x=>x.id==='LP-2045'));
});
test('storage fallback and other-tab refresh preserve delivery transitions',()=>{
 const broken=createStore({getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}});broken.verify('1602');broken.confirm(confirmation);assert.equal(broken.persistent(),false);
 const shared=memory(),a=createStore(shared),b=createStore(shared);a.complete('LP-2045',28000);b.refresh();assert.equal(b.stop('LP-2045').state,'delivered');
});
