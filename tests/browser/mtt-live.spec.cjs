const {test,expect,inspect,enter}=require('./fixtures.cjs');
const fs=require('node:fs');
const path=require('node:path');
// Map/network tests use local Leaflet. Optional remote font delivery is independent of API correctness.
test.beforeEach(async({page})=>{await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));});
async function manual(page){
  await page.goto('/#/manual');
  const f=page.locator('#manual-form');await expect(f).toBeVisible();
  for(const [k,v]of Object.entries({name:'Fictional MTT Buyer',phone:'09790000000',item:'Fictional shirt',sender:'Fictional Test Shop',street:'စမ်းသပ်လမ်း',landmark:'Fictional red gate',expected:'25000'}))await f.locator(`[name=${k}]`).fill(v);
  await f.locator('[name=areaId]').selectOption('Hlaing');
  await f.locator('[name=date]').fill(new Date(Date.now()+23400000).toISOString().slice(0,10));
  await f.locator('[name=received]').check();
  await f.locator('button[type=submit],button:not([type])').last().click();
  await page.locator('.created-dialog [data-created=open]').click();
  await expect(page.locator('#edit-form')).toBeVisible();
  return new URL(page.url()).hash.split('/').at(-1);
}
async function buyerLink(page){
  await page.locator('[data-action=issue]').click();
  const link=page.getByRole('link',{name:'See what the buyer sees'});await expect(link).toBeVisible();
  return link.getAttribute('href');
}
async function buyer(page,link){
  const token=new URL(link,page.url()).hash.split('/').at(-1);
  await page.goto('/#/track/'+encodeURIComponent(token));
  await expect(page.locator('[data-action=request-otp]')).toBeVisible();
  await page.locator('[data-action=request-otp]').click();
  await expect(page.locator('#verify-form')).toBeVisible();
  const preview=page.locator('.verification .demo-hint').filter({hasText:'SIMULATION ONLY'});
  await expect(preview).toBeVisible();
  const code=await preview.locator('.num').textContent();
  await page.locator('#verify-form [name=digits]').fill(code.trim());
  await page.locator('#verify-form button.customer-primary').click();
  await expect(page.locator('#buyer-map.leaflet-container')).toBeVisible();
}
async function screenshot(page,name){
  const dir=path.resolve(process.env.LANNPYA_SCREENSHOT_DIR||'docs/mtt-integration/screenshots');fs.mkdirSync(dir,{recursive:true});
  await page.screenshot({path:path.join(dir,name+'.png'),fullPage:true});
}
function dashboardPathResponse(page,path){
  return page.waitForResponse(response=>{
    const request=response.request();if(request.method()!=='POST'||!request.url().endsWith('/dashboard/api'))return false;
    try{const actual=request.postDataJSON()?.path||'';return actual===path||!path.includes('?')&&actual.startsWith(path+'?');}catch{return false;}
  });
}
async function selectRider(page,riderId){
  const ridersLoaded=dashboardPathResponse(page,'/api/riders?page=1&page_size=100');
  await page.goto('/#/dispatch');
  await ridersLoaded;
  const key=await page.evaluate(id=>Object.entries(window.Workflow.ACTORS).find(([,a])=>a.id===id)?.[0],riderId);
  expect(key,`functional app rider picker includes ${riderId}`).toBeTruthy();
  const queueLoaded=page.waitForResponse(response=>{
    const request=response.request();if(request.method()!=='POST'||!request.url().endsWith('/dashboard/api'))return false;
    try{return /^\/api\/riders\/[^/]+\/queue$/.test((request.postDataJSON()?.path||'').split('?')[0]);}catch{return false;}
  });
  const plansLoaded=page.waitForResponse(response=>{
    const request=response.request();if(request.method()!=='POST'||!request.url().endsWith('/dashboard/api'))return false;
    try{return /^\/api\/riders\/[^/]+\/route-plans$/.test((request.postDataJSON()?.path||'').split('?')[0]);}catch{return false;}
  });
  await page.evaluate(()=>{location.hash='#/ride';});
  await Promise.all([queueLoaded,plansLoaded]);
  await expect(page.locator('details.rider-demo')).toBeVisible();
  const picker=page.locator('#rider-picker');
  const selectedQueue=dashboardPathResponse(page,`/api/riders/${riderId}/queue`);
  const selectedPlans=dashboardPathResponse(page,`/api/riders/${riderId}/route-plans`);
  await picker.evaluate((el,value)=>{if(![...el.options].some(option=>option.value===value))throw Error('Rider preview option is missing.');el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));},key);
  await Promise.all([selectedQueue,selectedPlans]);
}
test('MTT browser creates persistent order, buyer pin, dispatcher review, rider COD and history',async({page})=>{
  await enter(page);
  await page.locator('#new-rider-form [name=name]').fill('Fictional MTT replacement rider');
  await page.locator('#new-rider-form button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText('Saved in the backend database');
  const availableRiders=(await inspect(page,'/api/riders')).items.filter(r=>r.operational_status==='AVAILABLE');
  expect(availableRiders.length).toBeGreaterThanOrEqual(2);
  const id=await manual(page),before=await inspect(page,'/api/orders/'+id);
  expect(before.customer_name).toBe('Fictional MTT Buyer');expect(before.latitude).toBeNull();expect(before.confidence_level).toBe('AMBER');
  await page.reload();await expect(page.locator('#edit-form [name=name]')).toHaveValue('Fictional MTT Buyer');
  const link=await buyerLink(page);await buyer(page,link);
  await expect(page.locator('[name=latitude]')).toHaveValue('');
  await page.locator('#buyer-map').click({position:{x:160,y:140}});
  const first=await page.locator('[name=longitude]').inputValue();
  const pin=page.locator('.leaflet-marker-draggable');const box=await pin.boundingBox();
  await page.mouse.move(box.x+15,box.y+15);await page.mouse.down();await page.mouse.move(box.x+65,box.y+45,{steps:8});await page.mouse.up();
  await expect(page.locator('[name=longitude]')).not.toHaveValue(first);
  const latitude=await page.locator('[name=latitude]').inputValue();
  await page.locator('[name=initial_pin_acknowledged]').check();
  await page.locator('[name=note]').fill('စမ်းသပ်မှတ်ချက် — call at fictional gate');
  await page.locator('#customer-form .customer-primary').click();
  await expect(page.locator('.delivery-request-confirmed')).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await page.goto('/#/order/'+id);await expect(page.locator('[data-action=approve-location]')).toBeVisible();
  await page.locator('[data-action=approve-location]').click();
  await page.locator('dialog [name=reason]').fill('Synthetic test review, no independent geospatial claim');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  const approved=await inspect(page,'/api/orders/'+id);expect(Number(approved.latitude)).toBe(Number(latitude));expect(approved.confidence_level).toBe('AMBER');
  while(await page.locator('[data-review-request]').count()){
    await page.locator('[data-review-request]').first().click();await page.locator('dialog [name=reason]').fill('Synthetic review of buyer availability and delivery instructions');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  }
  await screenshot(page,'mtt-dispatcher-desktop');
  await page.setViewportSize({width:390,height:844});await screenshot(page,'mtt-dispatcher-mobile');
  await page.setViewportSize({width:1440,height:900});
  await expect(page.locator('[data-action=assign]')).toHaveText(/Reconfirm and find a rider/);
  await page.locator('[data-action=assign]').click();
  await expect(page.locator('dialog')).toContainText('You won’t choose a rider here');
  await expect(page.locator('dialog select')).toHaveCount(0);
  await page.locator('dialog [name=acknowledge]').check();
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  let offers=(await inspect(page,`/api/orders/${id}/assignments?page=1&page_size=100`)).items;
  expect(offers).toHaveLength(1);const firstOffer=offers[0];expect(firstOffer.response_status).toBe('PENDING');
  await selectRider(page,firstOffer.rider_id);
  await expect(page.locator('.stop-name')).toContainText('Fictional MTT Buyer');
  await expect(page.locator('[data-action=accept]')).toBeVisible();
  await expect(page.locator('[data-action=delivered]')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});await screenshot(page,'mtt-rider-offer-mobile');
  await page.locator('[data-action=decline]').click();
  offers=(await inspect(page,`/api/orders/${id}/assignments?page=1&page_size=100`)).items;
  expect(offers).toHaveLength(2);const replacement=offers.at(-1);
  expect(replacement.response_status).toBe('PENDING');expect(replacement.rider_id).not.toBe(firstOffer.rider_id);
  await selectRider(page,replacement.rider_id);
  await expect(page.locator('[data-action=accept]')).toBeVisible();
  await expect(page.locator('[data-action=delivered]')).toHaveCount(0);
  await page.locator('[data-action=accept]').click();
  await expect(page.locator('.stop-actions')).toContainText('Offer accepted');
  await expect(page.locator('[data-action=delivered]')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});await screenshot(page,'mtt-rider-accepted-mobile');
  const routes=(await inspect(page,'/api/routes')).items;
  const route=routes.find(r=>r.items.some(o=>o.id===id));expect(route).toBeTruthy();expect(route.state).toBe('draft');
  await page.setViewportSize({width:1440,height:900});await page.goto('/#/routes/'+route.id);
  await page.locator('[data-action=dispatch-route]').click();
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('OUT_FOR_DELIVERY');
  await selectRider(page,replacement.rider_id);
  await expect(page.locator('[data-action=delivered]')).toBeVisible();
  await page.locator('[data-action=delivered]').click();
  await expect(page.locator('dialog [name=codCollected]')).toBeVisible();
  await page.locator('dialog [name=amount]').fill('25000');
  await page.locator('dialog [name=codCollected]').check();
  await screenshot(page,'mtt-rider-cod-desktop');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('DELIVERED');
  await page.goto('/#/ride/handover');await expect(page.locator('[data-action=submit-cash]')).toBeVisible();
  await page.locator('[data-action=submit-cash]').click();
  await expect(page.locator('#toast')).toContainText('Cash handed over');
  await page.goto('/#/closeout');await expect(page.locator('[data-action=receive-cash]')).toBeVisible();
  await page.locator('[data-action=receive-cash]').click();
  await page.locator('dialog [name=amount]').fill('25000');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/routes')).items.find(r=>r.id===route.id).state).toBe('closed');
  await screenshot(page,'mtt-hub-closeout-desktop');
  await page.goto('/#/order/'+id);await page.getByText('History',{exact:true}).click();
  await expect(page.locator('details').filter({has:page.getByText('History',{exact:true})})).toContainText(/DELIVERED|DELIVERY_COMPLETED/i);
  await page.reload();expect((await inspect(page,'/api/orders/'+id)).status).toBe('DELIVERED');
  const events=await inspect(page,`/api/orders/${id}/events`);expect(events.total).toBeGreaterThan(5);
});
test('MTT raw Burmese import uses backend parser and preserves original input',async({page})=>{
  await page.goto('/#/new');await expect(page.locator('#batch-raw')).toBeVisible();
  const raw='name: Fictional MTT Chat Buyer, ၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ COD ၂၅၀၀၀ ကျပ်၊ address: Fictional gate';
  await page.locator('#batch-raw').fill(raw);await page.locator('[data-action=parse]').click();
  await expect(page.locator('#parse-results')).toContainText('09790000000');await expect(page.locator('#parse-results')).toContainText('mock');
  await page.locator('#live-parcel-item').fill('Fictional Burmese chat parcel');await page.locator('[data-action=commit-batch]').click();
  await expect(page).toHaveURL(/#\/dispatch$/);const orders=await inspect(page,'/api/orders');expect(orders.total).toBe(1);expect(orders.items[0].original_message).toBe(raw);expect(orders.items[0].cod_amount).toBe('25000');expect(orders.items[0].latitude).toBeNull();
});
test('MTT reschedule is a separate review request; location review cannot approve it silently',async({page})=>{
  const id=await manual(page),link=await buyerLink(page);await buyer(page,link);
  await page.locator('#buyer-map').click({position:{x:140,y:150}});await page.locator('[name=initial_pin_acknowledged]').check();
  await page.locator('[name=answer]').selectOption('Reschedule');await page.locator('#customer-form [name=date]').fill(new Date(Date.now()+23400000+86400000).toISOString().slice(0,10));await page.locator('#customer-form [name=time]').selectOption('10:00–12:00');
  await page.locator('#customer-form .customer-primary').click();await expect(page.locator('.delivery-request-confirmed')).toBeVisible();
  await page.goto('/#/order/'+id);await expect(page.locator('[data-review-request]')).toBeVisible();
  await page.locator('[data-action=approve-location]').click();await page.locator('dialog [name=reason]').fill('Synthetic location review only');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  let requests=(await inspect(page,`/api/orders/${id}/buyer-requests`)).items;expect(requests.find(r=>r.kind==='RESPONSE').resolution).toBeNull();
  await page.locator('[data-review-request]').click();await page.locator('dialog [name=reason]').fill('Synthetic courier review of cross-day request');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  requests=(await inspect(page,`/api/orders/${id}/buyer-requests`)).items;expect(requests.find(r=>r.kind==='RESPONSE').resolution).toBe('APPROVE');
  const order=await inspect(page,'/api/orders/'+id);expect(new Date(order.delivery_time_window.split('/')[0]).toLocaleTimeString('en-GB',{timeZone:'Asia/Yangon',hour:'2-digit',minute:'2-digit'})).toBe('10:00');expect(order.parsing_metadata.parcel.delivery_day).toBe(new Date(Date.now()+23400000+86400000).toISOString().slice(0,10));
});
test('MTT unavailable GPS, timeout and missing map library preserve manual selection',async({page})=>{
  await manual(page);const link=await buyerLink(page);await buyer(page,link);
  for(const [code,message]of [[2,'unavailable'],[3,'timed out']]){
    await page.evaluate(code=>{navigator.geolocation.getCurrentPosition=(_ok,fail)=>fail({code});},code);
    await page.locator('[data-action=get-location]').click();await expect(page.locator('.form-error')).toContainText(message);
  }
  await page.evaluate(()=>{globalThis.LannPyaCustomerMap.destroy();globalThis.L=undefined;});
  await page.locator('[data-action=refresh-customer]').click();await expect(page.locator('#buyer-map')).toContainText('Map library unavailable');
  await page.locator('[name=latitude]').fill('91');await page.locator('[name=longitude]').fill('96');await page.locator('[name=initial_pin_acknowledged]').check();await page.locator('#customer-form .customer-primary').click();
  expect(await page.locator('[name=latitude]').evaluate(n=>n.validity.rangeOverflow)).toBe(true);
});
test('MTT missing runtime configuration cannot silently activate demo mode',async({page})=>{
  await page.route('**/runtime-config.js',r=>r.fulfill({status:200,contentType:'text/javascript',body:''}));
  await page.goto('/');await expect(page.getByRole('heading',{name:'CONNECTION_ERROR'})).toBeVisible();await expect(page.locator('#manual-form')).toHaveCount(0);
});
test('MTT device GPS only after click, permission denial recovers with manual pin',async({page})=>{
  const context=page.context();
  await manual(page);const link=await buyerLink(page);await buyer(page,link);
  await expect(page.locator('[name=latitude]')).toHaveValue('');
  await context.grantPermissions(['geolocation']);await context.setGeolocation({latitude:16.81,longitude:96.14});
  await page.evaluate(()=>{const original=navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);navigator.geolocation.getCurrentPosition=(ok,fail,options)=>{globalThis.qaGpsOptions=options;return original(ok,fail,options);};});
  await page.locator('[data-action=get-location]').click();await expect(page.locator('[name=latitude]')).toHaveValue('16.81');
  expect(await page.evaluate(()=>globalThis.qaGpsOptions)).toMatchObject({enableHighAccuracy:true,maximumAge:0});await expect(page.locator('#map-selection-status')).toContainText('does not independently verify');
  await context.clearPermissions();
  await page.evaluate(()=>{navigator.geolocation.getCurrentPosition=(_ok,fail)=>fail({code:1});});
  await page.locator('[data-action=get-location]').click();await expect(page.locator('.form-error')).toContainText('permission denied');
  await page.locator('#buyer-map').click({position:{x:120,y:150}});await expect(page.locator('[name=latitude]')).not.toHaveValue('16.81');
  await page.setViewportSize({width:390,height:844});await screenshot(page,'buyer-mobile-map');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
test('MTT three incorrect attempts lock the real link and expose no address',async({page})=>{
  const id=await manual(page),link=await buyerLink(page);await page.goto('/'+link);
  await expect(page.locator('[data-action=request-otp]')).toBeVisible();await expect(page.locator('body')).not.toContainText('Fictional red gate');await page.locator('[data-action=request-otp]').click();
  for(let i=0;i<3;i++){await page.locator('[name=digits]').fill('999999');await page.locator('#verify-form button').click();if(i<2)await expect(page.locator('.form-error')).not.toBeEmpty();}
  await expect(page.getByRole('heading',{name:'This link is locked'})).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
});
test('MTT failed live creation stays an error, never a demo success',async({page})=>{
  await page.goto('/#/manual');await expect(page.locator('#manual-form')).toBeVisible();
  await page.route('**/dashboard/api',async route=>{
    const q=route.request().postDataJSON();if(q.method==='POST'&&q.path==='/api/orders')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'DATABASE_UNAVAILABLE',message:'Synthetic database failure'}})});return route.continue();
  });
  const f=page.locator('#manual-form');for(const [k,v]of Object.entries({name:'Fictional Error Buyer',phone:'09790000000',item:'Synthetic shirt',expected:'100'}))await f.locator(`[name=${k}]`).fill(v);
  await f.locator('button').last().click();await expect(page.locator('.form-error')).toContainText('Synthetic database failure');expect((await inspect(page,'/api/orders')).total).toBe(0);page.audit.expectedHttp.add(503);
});
