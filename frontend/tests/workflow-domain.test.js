const test=require('node:test');
const assert=require('node:assert/strict');
const W=require('../js/workflow-domain');
const A=W.ACTORS.admin,R=W.ACTORS.rider,M={role:'removed-role',hubId:'H-1',id:'removed'};
function memory(){const data=new Map();return {getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};}
const make=()=>W.createStore(memory(),{initialState:W.fixtures()});
const command=(s,type,p={},actor=A,meta={})=>s.execute(type,p,actor,meta);
const clock=(s,local='10:00')=>command(s,'clock',{value:`2026-10-20T${local}:00+06:30`});
function dispatched(s,id='LP-2046'){
  if(!s.order(id).received)command(s,'receive',{id});
  command(s,'assign',{id,routeId:'RT-001'});command(s,'dispatch',{routeId:'RT-001'});clock(s);return s.order(id);
}
function confirm(s,changes={}){if(s.linkStatus('LP-2045')!=='active')command(s,'issue_link',{id:'LP-2045'});const o=s.order('LP-2045');s.verify(o.link.token,'1602');return s.confirm(o.link.token,{expectedVersion:o.version,pin:o.anchor,time:W.WINDOWS[0],answer:'At home',note:'Blue gate',...changes});}
test('rules parse Myanmar digits and retain deterministic provenance',()=>{
 const p=W.parse('Name: Test\nPhone: ၀၉၈၈၇၃၄၁၆၀၂\nTownship: Kamayut\nStreet: Hledan Road\nCOD: ၂၈၀၀၀');
 assert.equal(p.phone,'09887341602');assert.equal(p.expected,28000);assert.equal(p.provenance.phone.source,'rule');assert.equal(W.triage(p).level,'green');
});
test('ambiguous contacts, unsupported place and unknown payment never auto-clear',()=>{
 const p=W.parse('Phone: 09887341602\nOther: 09794339082\nTownship: nowhere\nCOD: maybe');
 assert.equal(p.phone,'');assert.equal(W.triage(p).level,'red');assert.equal(p.payment,'unknown');assert.ok(W.blockers(p).length);
});
test('encoding uncertainty is held until explicitly reviewed Unicode text is saved',()=>{
 const s=make(),id='LP-2046';command(s,'edit',{id,fields:{encodingReview:true},reason:'Encoding uncertainty'});
 assert.ok(s.blockers(id).includes('Review Unicode encoding'));
 command(s,'edit',{id,fields:{encodingReview:false,normalized:'Reviewed Unicode'},reason:'Manual Unicode review'});assert.equal(s.order(id).normalized,'Reviewed Unicode');
});
test('batch duplicate detection is explicit and failed batch creation is atomic',()=>{
 const s=make();assert.throws(()=>command(s,'create_batch',{records:[{raw:W.SAMPLE.split('\n\n---')[0]}]}),/duplicate/);
 assert.equal(s.snapshot().orders.length,3);
 command(s,'create_batch',{records:[{raw:W.SAMPLE.split('\n\n---')[0],duplicate:'separate'}]});assert.equal(s.snapshot().orders.length,4);
});
test('public link projection omits private address and phone',()=>{
 const c=make().customer('demo-2045');assert.equal(c.available,true);assert.equal(c.order,undefined);assert.equal(c.phone,undefined);assert.equal(c.pin,undefined);
});
test('phone lock survives new session; malformed checks consume no attempts',()=>{
 const storage=memory(),s=W.createStore(storage,{initialState:W.fixtures()});assert.throws(()=>s.verify('demo-2045','12'),/four/);assert.equal(s.customer('demo-2045').remaining,3);
 for(let i=0;i<3;i++)assert.throws(()=>s.verify('demo-2045','0000'));
 assert.equal(W.createStore(storage,{initialState:W.fixtures()}).customer('demo-2045').status,'locked');
});
test('reissued/revoked/expired links never grant old access',()=>{
 const s=make();command(s,'issue_link',{id:'LP-2045'});assert.equal(s.customer('demo-2045').available,false);
 const token=s.order('LP-2045').link.token;command(s,'revoke_link',{id:'LP-2045'});assert.equal(s.customer(token).status,'revoked');
 command(s,'issue_link',{id:'LP-2045'});const t=s.order('LP-2045').link.token;command(s,'clock',{value:'2026-11-01T01:30:00Z'});assert.equal(s.customer(t).status,'expired');
});
test('confirmation resolves location hold but leaves original triage amber',()=>{
 const s=make();confirm(s);assert.equal(s.order('LP-2045').state,'ready');assert.equal(s.triage('LP-2045').level,'amber');assert.equal(s.order('LP-2045').confirmation.note,'Blue gate');
});
test('confirmation cannot hide an unknown payment hold',()=>{
 const s=make();command(s,'edit',{id:'LP-2045',fields:{payment:'unknown',expected:null},reason:'Amount unclear'});confirm(s);assert.equal(s.order('LP-2045').state,'held');
});
test('repeated nudges use original anchor; cross-township moves inside radius are rejected',()=>{
 const s=make(),o=s.order('LP-2045');confirm(s,{pin:{lat:o.anchor.lat+.003,lng:o.anchor.lng}});
 assert.throws(()=>confirm(s,{pin:{lat:o.anchor.lat+.006,lng:o.anchor.lng}}),/500 m/);
 command(s,'verify_location',{id:o.id,pin:{lat:16.8181,lng:96.1309},reason:'Fixture boundary anchor'});command(s,'issue_link',{id:o.id});const latest=s.order(o.id);s.verify(latest.link.token,'1602');
 assert.throws(()=>s.confirm(latest.link.token,{expectedVersion:latest.version,pin:{lat:16.8179,lng:96.1309},time:W.WINDOWS[0],answer:'At home'}),/township/);
});
test('security COD requires explicit ability to pay and stale versions reject saves',()=>{
 const s=make();assert.throws(()=>confirm(s,{answer:'Leave with security'}),/security recipient/);
 confirm(s,{answer:'Leave with security',securityPays:true});const o=s.order('LP-2045');
 command(s,'incident',{id:o.id,reason:'Record changed'});
 assert.throws(()=>s.confirm(o.link.token,{expectedVersion:o.version,pin:o.anchor,time:o.time,answer:'At home'}),/Conflict/);
});
test('customer self service stops at cutoff or actual dispatch',()=>{
 const s=make();clock(s,'09:00');assert.throws(()=>confirm(s),/cutoff/);
 const b=make();confirm(b);command(b,'assign',{id:'LP-2045',routeId:'RT-001'});command(b,'dispatch',{routeId:'RT-001'});assert.throws(()=>confirm(b),/cutoff/);
});
test('receipt and payment/location readiness gate assignment and dispatch',()=>{
 const s=make();assert.throws(()=>command(s,'assign',{id:'LP-2046',routeId:'RT-001'}),/receipt/);
 assert.throws(()=>command(s,'assign',{id:'LP-2045',routeId:'RT-001'}),/resolved/);
 dispatched(s);assert.equal(s.order('LP-2046').state,'out_for_delivery');assert.throws(()=>command(s,'assign',{id:'LP-2046',routeId:'RT-001'}));
});
test('removed roles cannot manage hub actions and rider cannot access unrelated orders',()=>{
 const s=make();assert.throws(()=>command(s,'receive',{id:'LP-2046'},M),/Admin/);assert.throws(()=>s.order('LP-2046',R),/assigned/);
 assert.throws(()=>s.order('LP-2046',{...M,shopId:'another'}),/access/);
});
test('active stop remains at top while future window ordering remains stable',()=>{
 const s=make();confirm(s,{time:W.WINDOWS[2]});command(s,'receive',{id:'LP-2046'});for(const id of ['LP-2045','LP-2046'])command(s,'assign',{id,routeId:'RT-001'});command(s,'dispatch',{routeId:'RT-001'});
 assert.equal(s.queue(R)[0].id,'LP-2046');command(s,'active_stop',{routeId:'RT-001',stopId:'LP-2045'},R);assert.equal(s.queue(R)[0].id,'LP-2045');
});
test('future windows cannot be handed off early',()=>{
 const s=make();dispatched(s);clock(s,'08:30');assert.throws(()=>command(s,'complete',{id:'LP-2046',amount:35000},R),/window/);
});
test('delivery and cash are atomic and operation replay is idempotent',()=>{
 const s=make();dispatched(s);const meta={operationId:'delivery-once'};command(s,'complete',{id:'LP-2046',amount:35000},R,meta);command(s,'complete',{id:'LP-2046',amount:35000},R,meta);
 assert.equal(s.order('LP-2046').attempts.length,1);assert.equal(s.order('LP-2046').collection.actual,35000);assert.throws(()=>command(s,'complete',{id:'LP-2046',amount:35000},R),/closed/);
});
test('mismatch needs reason and original collection remains after resolution',()=>{
 const s=make();dispatched(s);assert.throws(()=>command(s,'complete',{id:'LP-2046',amount:0},R),/mismatch/);assert.equal(s.order('LP-2046').state,'out_for_delivery');
 command(s,'complete',{id:'LP-2046',amount:34000,reason:'Buyer paid 1000 less'},R);command(s,'resolve_discrepancy',{id:'LP-2046',reason:'Shop accepted adjustment'});
 assert.equal(s.order('LP-2046').collection.actual,34000);assert.ok(s.order('LP-2046').collection.resolution);
});
test('prepaid accepts zero only; fractional and negative amounts rejected',()=>{
 const s=make();command(s,'edit',{id:'LP-2046',fields:{payment:'prepaid',expected:0},reason:'Shop verified paid'});dispatched(s);
 for(const amount of [100,-1,1.5])assert.throws(()=>command(s,'complete',{id:'LP-2046',amount},R),/whole MMK/);
 command(s,'complete',{id:'LP-2046',amount:0},R);assert.equal(s.order('LP-2046').state,'delivered');
});
test('retry future windows and attempt limits enforced; return receipt is separate',()=>{
 const s=make();dispatched(s);assert.throws(()=>command(s,'fail',{id:'LP-2046',reason:W.REASONS[0],resolution:'retry',time:W.WINDOWS[0]},R),/later/);
 command(s,'fail',{id:'LP-2046',reason:W.REASONS[0],resolution:'retry',time:W.WINDOWS[2]},R);clock(s,'14:00');
 assert.throws(()=>command(s,'fail',{id:'LP-2046',reason:W.REASONS[1],resolution:'retry',time:W.WINDOWS[3]},R),/limit/);
 command(s,'fail',{id:'LP-2046',reason:W.REASONS[1],resolution:'return'},R);assert.equal(s.order('LP-2046').state,'return_pending');assert.equal(s.order('LP-2046').attempts.length,2);
 command(s,'return_received',{id:'LP-2046'});assert.equal(s.order('LP-2046').state,'returned');
});
test('before departure cancellation revokes link; after departure requires coordinated return',()=>{
 const s=make();command(s,'cancel',{id:'LP-2045',reason:'Shop cancelled'});assert.equal(s.order('LP-2045').state,'cancelled');assert.equal(s.customer('demo-2045').available,false);
 const b=make();dispatched(b);assert.throws(()=>command(b,'cancel',{id:'LP-2046',reason:'Cancel'}),/acknowledged/);command(b,'cancel',{id:'LP-2046',reason:'Shop request',acknowledged:true});assert.equal(b.order('LP-2046').state,'return_pending');
});
test('offline queue persists, locally replays once and retains version conflicts',()=>{
 const storage=memory(),s=W.createStore(storage,{initialState:W.fixtures()});dispatched(s);command(s,'prepare_offline',{},R);const o=s.order('LP-2046');command(s,'complete',{id:o.id,amount:35000,expectedVersion:o.version},R,{offline:true,operationId:'offline-1'});
 assert.equal(s.order(o.id).state,'out_for_delivery');assert.equal(s.snapshot().outbox[0].status,'pending');
 const reopened=W.createStore(storage,{initialState:W.fixtures()});reopened.replay();reopened.replay();assert.equal(reopened.order(o.id).attempts.length,1);assert.equal(reopened.snapshot().outbox[0].status,'acknowledged');
 const b=make();dispatched(b);command(b,'prepare_offline',{},R);const old=b.order(o.id);command(b,'complete',{id:o.id,amount:35000,expectedVersion:old.version},R,{offline:true});command(b,'incident',{id:o.id,reason:'Changed while offline'});b.replay();assert.equal(b.snapshot().outbox[0].status,'conflict');assert.equal(b.order(o.id).state,'out_for_delivery');
 b.resolvePending(b.snapshot().outbox[0].operationId,'Reviewed actual handoff with rider',true);assert.equal(b.order(o.id).state,'delivered');
});
test('route closeout requires physical returns, actual cash receipt and discrepancy review',()=>{
 const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:34000,reason:'Buyer underpaid'},R);
 command(s,'submit_cash',{routeId:'RT-001',amount:34000},R);assert.throws(()=>command(s,'close_route',{routeId:'RT-001'}),/blocked/);
 command(s,'receive_cash',{routeId:'RT-001',amount:34000});assert.throws(()=>command(s,'close_route',{routeId:'RT-001'}),/blocked/);
 command(s,'resolve_discrepancy',{id:'LP-2046',reason:'Shop agreed'});command(s,'close_route',{routeId:'RT-001'});assert.equal(s.snapshot().routes[0].state,'closed');
});
test('cash handover disagreement remains disputed until documented resolution',()=>{
 const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:35000},R);command(s,'submit_cash',{routeId:'RT-001',amount:35000},R);
 command(s,'receive_cash',{routeId:'RT-001',amount:34000,reason:'Count short'});assert.equal(s.snapshot().routes[0].handover.status,'disputed');
 assert.throws(()=>command(s,'close_route',{routeId:'RT-001'}),/blocked/);command(s,'receive_cash',{routeId:'RT-001',amount:35000});command(s,'close_route',{routeId:'RT-001'});
});
test('returned parcel requires route closure before a new delivery cycle',()=>{
 const s=make();dispatched(s);command(s,'fail',{id:'LP-2046',reason:W.REASONS[3],resolution:'return'},R);command(s,'return_received',{id:'LP-2046'});
 assert.throws(()=>command(s,'replan',{id:'LP-2046',date:'2026-10-21'}),/Close/);command(s,'submit_cash',{routeId:'RT-001',amount:0},R);command(s,'receive_cash',{routeId:'RT-001',amount:0});command(s,'close_route',{routeId:'RT-001'});command(s,'replan',{id:'LP-2046',date:'2026-10-21'});assert.equal(s.order('LP-2046').cycles[0].attempts.length,1);
});
test('storage failure falls back to memory; requested reset removes only old app records',()=>{
 const broken=W.createStore({getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}},{initialState:W.fixtures()});command(broken,'receive',{id:'LP-2046'});assert.equal(broken.persistent(),false);
 const storage=memory();storage.setItem('lannpya.delivery.v1',JSON.stringify({stops:[{id:'old'}]}));storage.setItem('lannpya.workflow.v3',JSON.stringify(W.fixtures()));storage.setItem('unrelated-app','keep');const s=W.createStore(storage);assert.equal(s.snapshot().orders.length,0);assert.equal(s.snapshot().routes.length,0);assert.equal(storage.getItem('lannpya.delivery.v1'),null);assert.equal(storage.getItem('lannpya.workflow.v3'),null);assert.equal(storage.getItem('unrelated-app'),'keep');
});
test('verified customer and rider projections exclude raw chat and full phone',()=>{
 const s=make();s.verify('demo-2045','1602');const customer=s.customer('demo-2045');assert.equal(customer.order.phone,undefined);assert.equal(customer.order.raw,undefined);assert.equal(customer.order.link,undefined);
 dispatched(s);assert.equal(s.order('LP-2046',R).phone,undefined);assert.equal(s.queue(R)[0].raw,undefined);
});
test('coverage policy holds undeparted parcels without moving a dispatched parcel',()=>{
 const s=make();dispatched(s);command(s,'policy',{areas:['sanchaung'],cutoff:540,maxRetries:1,linkDays:7});assert.equal(s.order('LP-2046').state,'out_for_delivery');assert.equal(s.triage('LP-2045').level,'red');assert.equal(s.order('LP-2045').state,'held');
});
test('material corrections revoke the customer link and retain before/after evidence',()=>{
 const s=make();command(s,'edit',{id:'LP-2045',fields:{item:'Updated dress'},reason:'Shop corrected parcel item'});assert.equal(s.customer('demo-2045').status,'revoked');const edit=s.order('LP-2045').corrections[0];assert.equal(edit.changes.item.before,'Floral Summer Dress');assert.equal(edit.changes.item.after,'Updated dress');
});
test('link replacement has a demo cooldown and cannot churn indefinitely',()=>{
 const s=make();for(let i=0;i<3;i++)command(s,'issue_link',{id:'LP-2045'});assert.throws(()=>command(s,'issue_link',{id:'LP-2045'}),/Too many/);clock(s,'08:11');command(s,'issue_link',{id:'LP-2045'});
});
test('offline actions need a prepared queue and retain observer when reviewed',()=>{
 const s=make();dispatched(s);const o=s.order('LP-2046');assert.throws(()=>command(s,'complete',{id:o.id,amount:35000},R,{offline:true}),/Prepare/);command(s,'prepare_offline',{},R);command(s,'complete',{id:o.id,amount:35000,expectedVersion:o.version},R,{offline:true});const observed=s.snapshot().outbox[0];command(s,'incident',{id:o.id,reason:'Review needed'});s.replay();s.resolvePending(observed.operationId,'Verified actual rider handoff',true);const attempt=s.order(o.id).attempts[0];assert.equal(attempt.riderId,R.id);assert.equal(attempt.reviewedBy,A.id);assert.equal(attempt.at,observed.at);
});
test('acknowledged cash cannot be replaced by a new rider submission',()=>{
 const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:35000},R);command(s,'submit_cash',{routeId:'RT-001',amount:35000},R);command(s,'receive_cash',{routeId:'RT-001',amount:35000});assert.throws(()=>command(s,'submit_cash',{routeId:'RT-001',amount:0,reason:'Overwrite'},R),/acknowledged/);assert.equal(s.snapshot().routes[0].handover.received,35000);
});

test('combined hub receipt and close is admin-only, atomic and idempotent with separate audit events',()=>{
 const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:35000},R);command(s,'submit_cash',{routeId:'RT-001',amount:35000},R);
 const payload={routeId:'RT-001',amount:35000,closeWhenReady:true};
 assert.throws(()=>command(s,'receive_cash',payload,R),/Admin access/);assert.equal(s.snapshot().routes[0].handover.status,'submitted');
 const first=command(s,'receive_cash',payload,A,{operationId:'receipt-and-close'});assert.equal(first.value.closed,true);assert.deepEqual(first.value.blockers,[]);
 assert.deepEqual(command(s,'receive_cash',payload,A,{operationId:'receipt-and-close'}),first);const route=s.snapshot().routes[0];assert.equal(route.state,'closed');assert.equal(route.receiptHistory.length,1);
 assert.equal(s.snapshot().events.filter(e=>e.type==='receive_cash').length,1);assert.equal(s.snapshot().events.filter(e=>e.type==='close_route').length,1);
});

test('combined receipt keeps valid receipt while blockers prevent route closure',()=>{
 for(const blocker of ['return','incident','queue','collection']){
  const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:blocker==='collection'?34000:35000,reason:'Documented short payment'},R);command(s,'submit_cash',{routeId:'RT-001',amount:blocker==='collection'?34000:35000},R);
  const state=s.snapshot();if(blocker==='return')state.orders.find(o=>o.id==='LP-2046').state='return_pending';if(blocker==='incident')state.orders.find(o=>o.id==='LP-2046').incident={reason:'Investigating'};if(blocker==='queue')state.outbox.push({status:'conflict',payload:{id:'LP-2046'}});
  const reopened=W.createStore(memory(),{initialState:state});const result=command(reopened,'receive_cash',{routeId:'RT-001',amount:blocker==='collection'?34000:35000,closeWhenReady:true});
  assert.equal(result.value.closed,false,blocker);assert.ok(result.value.blockers.length,blocker);assert.equal(reopened.snapshot().routes[0].state,'closing',blocker);assert.equal(reopened.snapshot().routes[0].handover.status,'received',blocker);assert.equal(reopened.snapshot().routes[0].receiptHistory.length,1,blocker);
 }
});

test('shortcut rejects stale cash totals and stale rider declarations without overwriting receipt',()=>{
 const s=make();dispatched(s);command(s,'complete',{id:'LP-2046',amount:35000},R);
 assert.throws(()=>command(s,'submit_cash',{routeId:'RT-001',amount:34000,recordedTotal:34000},R),/Recorded cash changed/);assert.equal(s.snapshot().routes[0].handover,null);
 command(s,'submit_cash',{routeId:'RT-001',amount:35000},R);command(s,'submit_cash',{routeId:'RT-001',amount:34000,reason:'Recount short'},R);
 assert.throws(()=>command(s,'receive_cash',{routeId:'RT-001',amount:35000,expectedDeclared:35000,closeWhenReady:true}),/handover changed/);assert.equal(s.snapshot().routes[0].receiptHistory,undefined);assert.equal(s.snapshot().routes[0].handover.status,'submitted');
});
function manualFields(s,patch={}){return {name:'Customer',phone:'၀၉၇၉၄၃၃၉၀၈၂',sender:'Sender',areaId:'kamayut',item:'Envelope',payment:'cod',expected:100,date:W.day(s.now()),time:W.ANY_TIME,lat:'',lng:'',...patch};}
test('manual creation is admin-only, validated and atomic; no seeded records or routes return on reload',()=>{
 const storage=memory(),s=W.createStore(storage);assert.deepEqual([...new Set(Object.values(W.ACTORS).map(a=>a.role))].sort(),['admin','customer','rider']);
 assert.throws(()=>command(s,'create_manual',{fields:manualFields(s)},W.ACTORS.customer),/Admin/);assert.throws(()=>command(s,'create_manual',{fields:manualFields(s,{phone:'bad'})}),/phone|mobile/);assert.equal(s.snapshot().orders.length,0);
 const result=command(s,'create_manual',{fields:manualFields(s)}),o=s.order(result.value);assert.equal(o.id,'LP-0001');assert.equal(o.phone,'09794339082');assert.ok(o.link.token);assert.equal(o.received,false);assert.equal(o.anchor,null);
 const reloaded=W.createStore(storage);assert.equal(reloaded.snapshot().orders.length,1);assert.equal(reloaded.snapshot().routes.length,0);assert.equal(reloaded.snapshot().orders[0].id,o.id);
});
test('customer without an anchor can submit a proposal but cannot clear the admin review hold',()=>{
 const s=W.createStore(memory());const id=command(s,'create_manual',{fields:manualFields(s),received:true}).value,o=s.order(id);s.verify(o.link.token,'9082');s.confirm(o.link.token,{pin:{lat:16.8254,lng:96.1309},time:W.ANY_TIME,answer:'At home',note:'Blue gate',expectedVersion:o.version});assert.equal(s.order(id).state,'held');assert.ok(s.order(id).proposedPin);assert.equal(s.order(id).anchor,null);
 assert.throws(()=>command(s,'approve_customer_location',{id,reason:'Unauthorised'},R),/Admin/);command(s,'approve_customer_location',{id,reason:'Checked delivery pin'});assert.equal(s.order(id).state,'ready');assert.equal(s.order(id).confirmation.note,'Blue gate');assert.equal(s.customer(o.link.token).available,true);
});
test('Any time manual orders can dispatch and deliver today without the old fixed clock or cutoff',()=>{
 const s=W.createStore(memory(),{now:()=>Date.parse('2026-10-21T21:30:00+06:30')});const id=command(s,'create_manual',{fields:manualFields(s,{lat:'16.8254',lng:'96.1309'}),received:true,locationReviewed:true}).value,o=s.order(id);assert.equal(s.deadline(id),true);s.verify(o.link.token,'9082');s.confirm(o.link.token,{pin:o.pin,time:W.ANY_TIME,answer:'At home',expectedVersion:o.version});const routeId=command(s,'new_route',{date:o.date,riderId:R.id}).value;command(s,'assign',{id,routeId});command(s,'dispatch',{routeId});command(s,'complete',{id,amount:100},R);assert.equal(s.order(id).state,'delivered');assert.equal(s.deadline(id),false);
});
test('shop prep timeline sets the earliest delivery day and the buyer chooses from the next three days',()=>{
 const s=make();clock(s,'09:00');const today=W.day(s.now());
 assert.throws(()=>command(s,'create_manual',{fields:manualFields(s,{prep:'pre_5'})}),/ready on/);
 const id=command(s,'create_manual',{fields:manualFields(s,{prep:'pre_5',date:W.addDays(today,5)})}).value,o=s.order(id);
 assert.equal(o.readyDate,W.addDays(today,5));
 s.verify(o.link.token,'9082');const c=s.customer(o.link.token);
 assert.deepEqual(c.dates,[5,6,7].map(n=>W.addDays(today,n)));
 assert.throws(()=>s.confirm(o.link.token,{expectedVersion:o.version,pin:{lat:16.8254,lng:96.1309},date:today,time:W.SLOTS[0].time,answer:'At home'}),/days shown/);
 s.confirm(o.link.token,{expectedVersion:o.version,pin:{lat:16.8254,lng:96.1309},date:W.addDays(today,6),time:W.SLOTS[2].time,answer:'At home'});
 assert.equal(s.order(id).date,W.addDays(today,6));assert.equal(s.order(id).confirmation.date,W.addDays(today,6));
 assert.throws(()=>command(s,'edit',{id,fields:{date:W.addDays(today,2)},reason:'Buyer asked',expectedVersion:s.order(id).version}),/ready on/);
});
