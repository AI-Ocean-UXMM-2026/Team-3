const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const W=require('../js/workflow-domain');
const {environment}=require('./test-dom');
const source=fs.readFileSync(require.resolve('../js/functional-app.js'),'utf8');
const A=W.ACTORS.admin,R=W.ACTORS.rider;
function boot(hash='#/dispatch',prepare,empty=false){const data=new Map(),storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};const store=W.createStore(storage,{initialState:empty?W.seed():W.fixtures()});prepare?.(store);const e=environment(storage,hash);e.ctx.window.Workflow=W;vm.runInNewContext(source,e.ctx);return {...e,store:()=>{const s=W.createStore(storage);s.refresh();return s;}};}
async function bootLive(hash='#/manual'){
 const data=new Map(),storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)},e=environment(storage,hash);
 e.ctx.window.Workflow=W;e.ctx.window.LANNPYA_RUNTIME.mode='LIVE_BACKEND';e.ctx.window.LannPyaLiveStore={create:async()=>({refresh(){},sync:async()=>{},now:()=>Date.now(),persistent:()=>true,snapshot:()=>({orders:[],routes:[],outbox:[],clockMode:'live',policy:{areas:W.PLACES.map(p=>p.id),cutoff:900,enforceCutoff:true}})})};
 vm.runInNewContext(source,e.ctx);await new Promise(resolve=>setImmediate(resolve));return e;
}
function departed(s){for(const [t,p]of [['receive',{id:'LP-2046'}],['assign',{id:'LP-2046',routeId:'RT-001'}],['dispatch',{routeId:'RT-001'}],['clock',{value:'2026-10-20T10:00:00+06:30'}]])s.execute(t,p,A);}
async function verify(e,code){if(!e.find('#verify-form'))await e.action('request-otp',e.ctx.location.hash.split('/').at(-1));await e.submit('#verify-form',{digits:code});}

test('created order confirmation can close or return to the board without deleting the order',async()=>{
 const e=boot('#/manual',null,true);
 const fields={name:'Test buyer',phone:'09794339082',item:'Envelope',payment:'prepaid',expected:'0',areaId:'kamayut',prep:'ready_now',date:W.day(e.store().now())};
 await e.submit('#manual-form',fields);
 const id=e.store().snapshot().orders[0].id;
 const close=e.find('[data-created="close"]');assert.ok(close,'Creation confirmation needs a close control');
 await close.click();assert.equal(e.find('dialog'),null);assert.match(e.ctx.location.hash,/manual/);assert.equal(e.store().order(id).item,'Envelope');
 await e.submit('#manual-form',{...fields,name:'Second buyer',phone:'09794339083'});
 await e.find('[data-created="board"]').click();assert.equal(e.ctx.location.hash,'#/dispatch');assert.equal(e.store().snapshot().orders.length,2);
});

test('record edit action shares the disposition row with its dropdown',async()=>{
 const e=boot('#/new');e.find('#batch-raw').value='Name: Test buyer\nPhone: 09794339082\nTownship: Kamayut\nCOD: 1000';
 const reading=e.action('parse');await e.tick(100);await reading;
 const controls=e.find('.record-controls');assert.ok(controls,'Disposition and Edit need a shared row');
 assert.ok(controls.querySelector('[data-choice="0"]'));assert.ok(controls.querySelector('[data-action="edit-row"]'));
});
test('all workspace routes render actual controls without runtime errors',()=>{
 const e=boot();for(const path of ['dispatch','create','new','manual','order/LP-2045','routes','buyers','exceptions','closeout','analytics','settings','scenarios','ride','track/demo-2045','track/invalid']){e.ctx.location.hash='#/'+path;assert.doesNotMatch(e.root.textContent,/Unable to open this view/,path);assert.ok(e.root.textContent.length>100,path);}
});
test('Create order chooser routes to the original paste and manual forms',()=>{
 const e=boot('#/create');assert.match(e.root.textContent,/Create order/);assert.match(e.root.textContent,/Paste order/);assert.match(e.root.textContent,/Form \(enter manually\)/);
 const createTab=e.find('.tabs a');assert.equal(createTab.querySelector('.en').textContent,'Create order');assert.equal(createTab.attributes.href,'#/create');assert.equal(createTab.attributes['aria-current'],'page');
 const options=e.all('.create-options a');assert.deepEqual(options.map(a=>a.attributes.href),['#/new','#/manual']);
 e.ctx.location.hash=options[0].attributes.href;assert.ok(e.find('#batch-raw'));assert.equal(e.find('#batch-raw').value,'');
 e.ctx.location.hash=options[1].attributes.href;assert.ok(e.find('#manual-form'));
});
test('manual delivery address has no dispatcher pin controls and live adaptation renders cleanly',async()=>{
 const e=await bootLive();assert.doesNotMatch(e.root.textContent,/Unable to open this view/);assert.ok(e.find('#manual-form'),e.root.textContent);
 const form=e.find('#manual-form'),where=[...form.querySelectorAll('section')].find(s=>s.querySelector('h2')?.textContent==='Where to deliver');
 assert.ok(where);assert.ok(where.querySelector('[name="areaId"]'));assert.ok(where.querySelector('[name="street"]'));assert.ok(where.querySelector('[name="landmark"]'));assert.ok(where.querySelector('[name="floor"]'));
 assert.equal(where.querySelector('[name="lat"]'),null);assert.equal(where.querySelector('[name="lng"]'),null);assert.equal(where.querySelector('[name="locationReviewed"]'),null);assert.equal(where.querySelector('details'),null);
 e.ctx.location.hash='#/create';assert.doesNotMatch(e.root.textContent,/Unable to open this view/);
});
test('customer verifies and saves one response through real form handlers',async()=>{
 const e=boot('#/track/demo-2045');assert.doesNotMatch(e.root.textContent,/SIMULATION ONLY/);await e.action('request-otp','demo-2045');assert.match(e.root.textContent,/SIMULATION ONLY/);assert.match(e.root.textContent,/123456/);assert.doesNotMatch(e.root.textContent,/last four/i);await e.submit('#verify-form',{digits:'123456'});assert.ok(e.find('#customer-form'));
 await e.submit('#customer-form',{answer:'At home',time:W.WINDOWS[1],note:'Gate B'});assert.equal(e.store().order('LP-2045').confirmation.note,'Gate B');assert.match(e.root.textContent,/Your answer is saved/);assert.equal(e.find('#customer-form'),null);await e.action('edit-customer','demo-2045');assert.ok(e.find('#customer-form'));await e.submit('#customer-form',{answer:'At home',time:W.WINDOWS[1],note:'Gate C'});assert.equal(e.store().order('LP-2045').confirmation.note,'Gate C');assert.equal(e.store().order('LP-2045').location,'buyer_confirmed');
});
test('wrong checks and cutoff show recovery screens, not successful confirmation',async()=>{
 const e=boot('#/track/demo-2045');for(let i=0;i<3;i++)await verify(e,'000000');assert.match(e.root.textContent,/This link is locked/);assert.equal(e.store().customer('demo-2045').available,false);
 const b=boot('#/track/demo-2045',s=>s.execute('clock',{value:'2026-10-20T09:00:00+06:30'},A));await verify(b,'123456');assert.match(b.root.textContent,/view-only/);assert.equal(b.find('#customer-form'),null);
});
test('admin field corrections, hub receipt and assignment controls mutate shared records',async()=>{
 const e=boot('#/order/LP-2046');await e.submit('#edit-form',{reason:'Confirm item label',item:'Reviewed phone case'});assert.equal(e.store().order('LP-2046').item,'Reviewed phone case');
 await e.action('receive','LP-2046');await e.action('assign','LP-2046');await e.submit('dialog form',{acknowledge:true});const route=e.store().order('LP-2046').routeId;assert.equal(e.store().order('LP-2046').state,'assigned');assert.equal(e.store().order('LP-2046').responseStatus,'PENDING');
 e.ctx.location.hash='#/ride';await e.action('accept','LP-2046');e.ctx.location.hash='#/routes';assert.ok(e.find('a.route-tile'));e.ctx.location.hash='#/routes/'+route;assert.ok(e.find('#app-sheet'));await e.action('dispatch-route',route);await e.submit('dialog form');assert.equal(e.store().order('LP-2046').state,'out_for_delivery');
});
test('delivered undo is exactly timed; cash dialog cancellation does not complete delivery',async()=>{
 const e=boot('#/ride',departed);await e.action('picked-up','RT-001');await e.action('delivered','LP-2046');await e.tick(1999);assert.equal(e.find('dialog'),null);await e.action('delivered','LP-2046');await e.tick(100);assert.equal(e.find('dialog'),null);assert.equal(e.store().order('LP-2046').state,'out_for_delivery');
 await e.action('delivered','LP-2046');await e.tick(2000);assert.ok(e.find('dialog'));e.find('[data-dismiss]').click();assert.equal(e.store().order('LP-2046').state,'out_for_delivery');
});
test('rider completes COD via the timed controller and hub can finish cash closeout',async()=>{
 const e=boot('#/ride',departed);await e.action('picked-up','RT-001');await e.action('delivered','LP-2046');await e.tick(2000);await e.submit('dialog form',{amount:'35000'});assert.equal(e.store().order('LP-2046').collection.actual,35000);
 e.ctx.location.hash='#/ride/handover';await e.action('submit-cash','RT-001');assert.equal(e.find('dialog'),null);assert.equal(e.store().snapshot().routes[0].handover.declared,35000);assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='submit-cash'));
 e.ctx.location.hash='#/closeout';assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='close-route'));await e.action('receive-cash','RT-001');assert.equal(e.find('[name="amount"]').value,'');assert.equal(e.find('#cash-difference').hidden,true);
 await e.submit('dialog form');assert.match(e.find('dialog').textContent,/Enter the amount you physically counted/);assert.equal(e.store().snapshot().routes[0].handover.status,'submitted');
 await e.submit('dialog form',{amount:'35000'});assert.equal(e.store().snapshot().routes[0].state,'closed');assert.equal(e.find('dialog'),null);
});

test('different handover amount retains reasons and admin disputes without silently closing',async()=>{
 const e=boot('#/ride',s=>{departed(s);s.execute('complete',{id:'LP-2046',amount:35000},R);});
 e.ctx.location.hash='#/ride/handover';await e.action('different-cash','RT-001');const field=e.find('[name="amount"]');field.value='34000';field.oninput();assert.equal(e.find('#cash-difference').hidden,false);assert.equal(e.find('[name="reason"]').required,true);
 await e.submit('dialog form');assert.match(e.find('dialog').textContent,/Explain the difference/);assert.equal(e.store().snapshot().routes[0].handover,null);
 await e.submit('dialog form',{reason:'Counted short at hub'});assert.equal(e.store().snapshot().routes[0].handover.declared,34000);
 e.ctx.location.hash='#/closeout';await e.action('receive-cash','RT-001');await e.submit('dialog form',{amount:'34000',reason:'Hub counted short'});assert.equal(e.store().snapshot().routes[0].handover.status,'disputed');assert.equal(e.store().snapshot().routes[0].state,'closing');assert.match(e.root.textContent,/cash difference unresolved/);
 await e.action('receive-cash','RT-001');await e.submit('dialog form',{amount:'35000'});assert.match(e.find('dialog').textContent,/Explain the cash difference/);
 await e.submit('dialog form',{amount:'35000',reason:'Recovered missing cash; verified with rider',resolve:true});assert.equal(e.store().snapshot().routes[0].state,'closed');assert.equal(e.store().snapshot().routes[0].receiptHistory.length,2);
});

test('receipt is saved but collection differences still block shortcut closure',async()=>{
 const e=boot('#/ride',s=>{departed(s);s.execute('complete',{id:'LP-2046',amount:34000,reason:'Recipient paid short'},R);});
 e.ctx.location.hash='#/ride/handover';await e.action('submit-cash','RT-001');e.ctx.location.hash='#/closeout';await e.action('receive-cash','RT-001');await e.submit('dialog form',{amount:'34000'});
 assert.equal(e.store().snapshot().routes[0].handover.status,'received');assert.equal(e.store().snapshot().routes[0].state,'closing');assert.match(e.root.textContent,/LP-2046: resolve collection difference/);assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='close-route'));
 e.ctx.location.hash='#/order/LP-2046';await e.action('discrepancy','LP-2046');await e.submit('dialog form',{reason:'Admin accepted documented adjustment'});
 e.ctx.location.hash='#/closeout';await e.action('close-route','RT-001');assert.equal(e.store().snapshot().routes[0].state,'closed');
});

test('zero cash route uses the same short flow and failed handover does not submit',async()=>{
 const e=boot('#/ride',s=>{departed(s);s.execute('fail',{id:'LP-2046',reason:W.REASONS[0],resolution:'return'},R);s.execute('return_received',{id:'LP-2046'},A);});
 e.ctx.location.hash='#/scenarios';e.find('#scenario').value='save_failure';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/ride/handover';await e.action('submit-cash','RT-001');assert.equal(e.store().snapshot().routes[0].handover,null);
 e.ctx.location.hash='#/scenarios';e.find('#scenario').value='normal';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/ride/handover';await e.action('submit-cash','RT-001');assert.equal(e.store().snapshot().routes[0].handover.declared,0);
 e.ctx.location.hash='#/closeout';await e.action('receive-cash','RT-001');await e.submit('dialog form',{amount:'0'});assert.equal(e.store().snapshot().routes[0].state,'closed');
});
test('customer nudges do not walk the fixed anchor past 500 metres',async()=>{
 const e=boot('#/track/demo-2045');await verify(e,'123456');const right=()=>e.all('[data-nudge]').find(b=>b.dataset.nudge==='50,0');for(let i=0;i<15;i++)await right().click();assert.ok(parseFloat(e.find('#pin-distance').textContent)<501);
 await e.submit('#customer-form');const o=e.store().order('LP-2045');assert.ok(W.distance(o.anchor,o.pin)<=500);
});
test('batch preview imports valid rows while retaining simulated failed drafts',async()=>{
 const e=boot('#/scenarios');e.find('#scenario').value='parse_failure';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/new';
 const raw='Name: New A\nPhone: 09887341602\nTownship: Kamayut\nStreet: Hledan Road\nCOD: 5000\nItem: New A\nInvoice: NEW-A\n\n---\n\nName: New B\nPhone: 09794339082\nTownship: Kamayut\nStreet: Hledan Road\nCOD: 6000\nItem: New B\nInvoice: NEW-B';
 e.find('#batch-raw').value=raw;const parsing=e.action('parse');for(let i=0;i<8;i++)await e.tick(100);await parsing;assert.match(e.root.textContent,/1 couldn’t be read/);await e.action('commit-batch');assert.equal(e.store().snapshot().orders.length,4);assert.match(e.root.textContent,/Record 1/);assert.match(e.root.textContent,/Simulated parser error/);
 e.ctx.location.hash='#/scenarios';e.find('#scenario').value='normal';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/new';const retry=e.action('retry-row','0');await e.tick(100);await retry;await e.action('commit-batch');assert.equal(e.store().snapshot().orders.length,5);
});
test('failed save retains customer form and the same form can be retried',async()=>{
 const e=boot('#/scenarios');e.find('#scenario').value='save_failure';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/track/demo-2045';await verify(e,'123456');await e.submit('#customer-form',{note:'Keep this draft'});assert.equal(e.store().order('LP-2045').confirmation,null);assert.match(e.root.textContent,/Simulated save failure/);assert.equal(e.find('#customer-form').querySelector('[name="note"]').value,'Keep this draft');
 e.ctx.location.hash='#/scenarios';e.find('#scenario').value='normal';e.find('#scenario').onchange({target:e.find('#scenario')});e.ctx.location.hash='#/track/demo-2045';await e.submit('#customer-form');assert.equal(e.store().order('LP-2045').confirmation.note,'Keep this draft');
});
test('offline controller queues a handoff; conflict review preserves it until resolution',async()=>{
 const e=boot('#/ride',departed);await e.action('prepare-offline');e.ctx.location.hash='#/scenarios';e.find('#offline-mode').checked=true;e.find('#offline-mode').onchange({target:e.find('#offline-mode')});e.ctx.location.hash='#/ride';await e.action('picked-up','RT-001');await e.action('delivered','LP-2046');await e.tick(2000);await e.submit('dialog form',{amount:'35000'});assert.equal(e.store().snapshot().outbox[0].status,'pending');assert.equal(e.store().order('LP-2046').state,'out_for_delivery');
 e.ctx.location.hash='#/scenarios';await e.action('stale');e.find('#offline-mode').checked=false;e.find('#offline-mode').onchange({target:e.find('#offline-mode')});await e.action('replay');assert.equal(e.store().snapshot().outbox[0].status,'conflict');await e.action('resolve-outbox',e.store().snapshot().outbox[0].operationId);await e.submit('dialog form',{reason:'Checked actual handoff with rider',accept:'yes'});assert.equal(e.store().order('LP-2046').state,'delivered');
});
test('rider failure requires the hub to acknowledge physical return',async()=>{
 const e=boot('#/ride',departed);await e.action('picked-up','RT-001');await e.action('failed','LP-2046');await e.submit('dialog form',{reason:W.REASONS[3],resolution:'return'});assert.equal(e.store().order('LP-2046').state,'return_pending');e.ctx.location.hash='#/order/LP-2046';await e.action('return-received','LP-2046');assert.equal(e.store().order('LP-2046').state,'returned');
});
test('stale customer drafts have a visible reload recovery action',async()=>{
 const e=boot('#/track/demo-2045');await verify(e,'123456');const s=e.store();s.execute('incident',{id:'LP-2045',reason:'Changed by another operator'},A);await e.submit('#customer-form');assert.match(e.root.textContent,/Conflict/);await e.action('refresh-customer','demo-2045');assert.equal(e.find('#customer-form').dataset.version,String(e.store().order('LP-2045').version));
});
test('empty workspace has exactly three app sides, manual entry and a useful customer landing',()=>{
 const e=boot('#/dispatch',null,true);assert.equal(e.store().snapshot().orders.length,0);assert.equal(e.store().snapshot().routes.length,0);assert.match(e.root.innerHTML,/#\/manual/);assert.doesNotMatch(e.root.textContent,/merchant/i);assert.equal(e.find('#actor-picker'),null);
 e.ctx.location.hash='#/customer';assert.match(e.root.textContent,/No active customer links/);assert.ok(e.find('#customer-link-form'));assert.equal(e.find('#verify-form'),null);
 e.ctx.location.hash='#/manual';assert.ok(e.find('#manual-form'));assert.equal(e.find('#manual-form').querySelector('[name="time"]').value,W.ANY_TIME);
});
test('manual order → buyer reviews → dispatcher approval → accepted offer → departure and delivery',async()=>{
 const e=boot('#/manual',null,true);
 await e.submit('#manual-form',{name:'Test customer',phone:'09794339082',sender:'Sender office',item:'Document envelope',payment:'cod',expected:'100',areaId:'kamayut',received:true,prep:'ready_now',date:W.day(e.store().now())});
 let order=e.store().snapshot().orders[0];assert.ok(order);assert.equal(order.state,'held');assert.equal(order.time,W.ANY_TIME);assert.equal(order.pin,null);assert.equal(order.anchor,null);assert.equal(order.location,'unresolved');assert.ok(order.link.token);assert.match(e.ctx.location.hash,/manual/);assert.match(e.find('dialog').textContent,/Order LP-0001 created/);
 e.ctx.location.hash='#/customer';assert.match(e.root.textContent,/Document envelope/);
 await e.submit('#customer-link-form',{link:`file:///prototype/index.html#/track/${order.link.token}`});
 await verify(e,'123456');assert.ok(e.find('[name="latitude"]'));
 await e.action('preview-location','kamayut');await e.submit('#customer-form',{answer:'At home',time:W.WINDOWS[0],note:'Ring the bell'});
 order=e.store().order(order.id);assert.equal(order.state,'held');assert.equal(order.location,'buyer_submitted');assert.equal(order.confirmation.note,'Ring the bell');assert.match(e.root.textContent,/The shop is checking your pin/);
 e.ctx.location.hash='#/order/'+order.id;await e.action('approve-location',order.id);await e.submit('dialog form',{reason:'Admin checked the delivery point'});assert.equal(e.store().order(order.id).state,'ready');
 e.ctx.location.hash='#/order/'+order.id;await e.action('assign',order.id);await e.submit('dialog form',{acknowledge:true});order=e.store().order(order.id);const route=order.routeId;assert.equal(order.responseStatus,'PENDING');
 e.ctx.location.hash='#/ride';assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='delivered'));await e.action('accept',order.id);assert.equal(e.store().order(order.id).responseStatus,'ACCEPTED');
 e.ctx.location.hash='#/routes/'+route;await e.action('dispatch-route',route);await e.submit('dialog form');assert.equal(e.store().order(order.id).state,'out_for_delivery');
 e.ctx.location.hash='#/ride';assert.ok(e.find('.hub-pickup'));assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='delivered'));assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='submit-cash'));
 await e.action('pick',route+'|'+order.id);await e.action('picked-up',route);assert.match(e.root.textContent,/Delivery stop: Test customer/);e.store().execute('clock',{value:order.date+'T10:00:00+06:30'},A);await e.action('delivered',order.id);await e.tick(2000);await e.submit('dialog form',{amount:'100'});assert.equal(e.store().order(order.id).state,'delivered');assert.equal(e.store().order(order.id).collection.actual,100);
 e.ctx.location.hash='#/track/'+order.link.token;assert.match(e.root.textContent,/Your parcel was delivered/);
});
test('customer action buttons cannot accidentally submit a location form',async()=>{
 const e=boot('#/manual',null,true);await e.submit('#manual-form',{name:'Customer',phone:'09794339082',item:'Parcel',payment:'prepaid',expected:'0',areaId:'kamayut'});const o=e.store().snapshot().orders[0];e.ctx.location.hash='#/track/'+o.link.token;await verify(e,'123456');for(const b of e.find('#customer-form').querySelectorAll('[data-action]'))assert.equal(b.attributes.type,'button');await e.action('preview-location','kamayut');assert.equal(e.store().order(o.id).confirmation,null);
});
test('customer with no verified anchor can recover a stale initial-location form',async()=>{
 const e=boot('#/manual',null,true);await e.submit('#manual-form',{name:'Customer',phone:'09794339082',item:'Parcel',payment:'prepaid',expected:'0',areaId:'kamayut'});const o=e.store().snapshot().orders[0];e.ctx.location.hash='#/track/'+o.link.token;await verify(e,'123456');await e.action('preview-location','kamayut');e.store().execute('incident',{id:o.id,reason:'Admin updated parcel'},A);await e.submit('#customer-form');assert.match(e.root.textContent,/Conflict/);await e.action('refresh-customer',o.link.token);assert.equal(e.find('#customer-form').dataset.version,String(e.store().order(o.id).version));
});
test('delivered stops leave Deliveries and wait on the Cash handover page until the route closes',async()=>{
 const e=boot('#/ride',s=>{departed(s);s.execute('complete',{id:'LP-2046',amount:35000},R);});assert.ok(!e.all('[data-action="select-stop"]').some(b=>b.dataset.id==='LP-2046'));assert.ok(!e.find('[data-action="submit-cash"]'));
 e.ctx.location.hash='#/ride/handover';assert.match(e.root.textContent,/In this handover/);assert.match(e.root.textContent,/LP-2046/);assert.ok(e.find('[data-action="submit-cash"]'));
 e.ctx.location.hash='#/ride/history';assert.match(e.root.textContent,/No past deliveries yet/);assert.ok(!e.find('.stop-card'));
});
test('language switch shows one language at a time and is offered on every role',async()=>{
 const e=boot('#/dispatch');assert.ok(e.find('[data-action="lang"]'));await e.action('lang','my');const cls=()=>(e.ctx.document.body.attributes.class||'').split(' ');assert.ok(cls().includes('lang-my'));assert.ok(!cls().includes('lang-en'));
 await e.action('lang','en');assert.ok(cls().includes('lang-en'));
 e.ctx.location.hash='#/ride';assert.ok(e.find('.rider-head [data-action="lang"]'));
});
test('rider menu opens four separate pages and an empty Returned page says so',async()=>{
 const e=boot('#/ride',departed);const links=e.all('.rider-menu a.rider-tab').map(a=>a.attributes.href);assert.deepEqual(links,['#/ride','#/ride/returns','#/ride/handover','#/ride/history']);
 e.ctx.location.hash='#/ride/returns';assert.match(e.root.textContent,/No returned orders/);assert.ok(!e.find('.stop-card'));assert.ok(!e.find('#local-ride-queue'));
 const f=boot('#/ride/returns',s=>{departed(s);s.execute('fail',{id:'LP-2046',reason:W.REASONS[0],resolution:'return'},R);});assert.match(f.root.textContent,/LP-2046/);assert.doesNotMatch(f.root.textContent,/No returned orders/);
});
test('after an accepted offer the rider collects every parcel at the hub before the first stop',async()=>{
 const e=boot('#/ride',departed);assert.equal(e.store().order('LP-2046').responseStatus,'ACCEPTED');assert.ok(e.find('.hub-pickup'));assert.ok(!e.all('[data-action]').some(b=>b.dataset.action==='delivered'));
 assert.match(e.root.textContent,/Pick up at the hub first/);await e.action('pick','RT-001|LP-2046');await e.action('picked-up','RT-001');
 assert.ok(e.store().snapshot().routes[0].pickedUpAt);assert.equal(e.find('.hub-pickup'),null);assert.ok(e.all('[data-action]').some(b=>b.dataset.action==='delivered'));
});
test('Riders page lists the built-in riders and opens the add form',async()=>{
 const e=boot('#/riders');assert.match(e.root.textContent,/Ko Aung/);assert.match(e.root.textContent,/Ko Wai/);await e.action('rider-form','open');assert.ok(e.find('#rider-form'));
});
