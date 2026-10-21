const {test,expect,inspect}=require('./fixtures.cjs');
const fs=require('node:fs');
const path=require('node:path');
test.beforeEach(async({page})=>{await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));});
async function order(page,name,coordinates=true){
  await page.goto('/#/manual');const f=page.locator('#manual-form');await expect(f).toBeVisible();
  for(const [k,v]of Object.entries({name,phone:'09790000000',item:'Fictional routing parcel',street:'Synthetic test street',landmark:'စမ်းသပ် ဂိတ်',expected:'25000'}))await f.locator(`[name=${k}]`).fill(v);
  await f.locator('[name=areaId]').selectOption('Hlaing');await f.locator('[name=received]').check();
  if(coordinates){await f.getByText('Known map coordinates (optional)',{exact:true}).click();await f.locator('[name=lat]').fill('16.81');await f.locator('[name=lng]').fill('96.11');await f.locator('[name=locationReviewed]').check();}
  await f.locator('button').last().click();await expect(page.locator('#edit-form')).toBeVisible();
  const id=new URL(page.url()).hash.split('/').at(-1);
  if(coordinates){
    await page.locator('[data-action=issue]').click();const link=page.getByRole('link',{name:'See what the buyer sees'});await expect(link).toBeVisible();const href=await link.getAttribute('href');
    await page.goto('/'+href);await expect(page.locator('#verify-form')).toBeVisible();await page.locator('[name=digits]').fill('0000');await page.locator('#verify-form button').click();
    await expect(page.locator('#customer-form')).toBeVisible();await page.locator('[name=latitude]').fill('16.81');await page.locator('[name=longitude]').fill('96.11');await page.locator('[name=initial_pin_acknowledged]').check();await page.locator('#customer-form .customer-primary').click();await expect(page.locator('.live-notice').filter({hasText:'persisted'})).toBeVisible();
    await page.goto('/#/order/'+id);await expect(page.locator('#edit-form')).toBeVisible();
    if(await page.locator('[data-action=approve-location]').count()){await page.locator('[data-action=approve-location]').click();await page.locator('dialog [name=reason]').fill('Synthetic buyer point review; independent accuracy unknown');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);}
    while(await page.locator('[data-review-request]').count()){await page.locator('[data-review-request]').first().click();await page.locator('dialog [name=reason]').fill('Synthetic availability review');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);}
  }
  return id;
}
async function plan(page){
  await page.goto('/#/routes');const f=page.locator('#routing-plan-form');await expect(f).toBeVisible();
  await f.locator('[name=latitude]').fill('16.8');await f.locator('[name=longitude]').fill('96.1');
  await f.locator('[name=solver_seconds]').fill('1');await f.locator('[name=allow_simulation]').check();
  await f.locator('[type=submit]').click();await expect(page.locator('#routing-preview')).toContainText('OR-Tools');
  return f;
}
async function shot(page,name){const dir=path.resolve('docs/mapping-routing/screenshots');fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,name+'.png'),fullPage:true});}

test('routing preview, explicit commit, map geometry, rider COD and safe remaining-stop replan',async({page})=>{
  const first=await order(page,'Fictional Route Buyer A'),second=await order(page,'Fictional Route Buyer B');
  await plan(page);await expect(page.locator('#routing-preview')).toContainText('SIMULATED');
  await expect(page.locator('[data-plan-map].leaflet-container')).toHaveCount(1);
  expect((await inspect(page,'/api/orders/'+first)).status).not.toBe('ASSIGNED');
  expect((await inspect(page,'/api/orders/'+second)).status).not.toBe('ASSIGNED');
  await shot(page,'dispatcher-preview-desktop');
  const c=page.locator('#commit-routing-plan');await c.locator('[name=ack]').check();await c.locator('[name=simulation]').check();await c.locator('[type=submit]').click();
  await expect(page.locator('[data-action=dispatch-route]')).toBeVisible();
  const plans=await inspect(page,'/api/routes/plans');expect(plans.items[0].state).toBe('COMMITTED');expect(plans.items[0].stale).toBe(false);
  await page.reload();await expect(page.locator('[data-open-plan]')).toHaveCount(1);
  await page.locator('[data-open-plan]').click();await expect(page.locator('#routing-preview')).toContainText('COMMITTED');
  await page.locator('[data-action=dispatch-route]').click();await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  await page.goto('/#/ride');await expect(page.locator('body')).toContainText('Assigned route plan');
  await expect(page.locator('[data-plan-map].leaflet-container')).toHaveCount(1);
  await expect(page.locator('a[href*="google.com/maps/dir"]')).toBeVisible();
  await page.locator('[data-action=delivered]').click();await page.locator('dialog [name=codCollected]').check();await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  const all=await inspect(page,'/api/orders');expect(all.items.filter(o=>o.status==='DELIVERED')).toHaveLength(1);
  await plan(page);await expect(page.locator('#routing-preview')).toContainText('Stop 1');
  const re=page.locator('#commit-routing-plan');await re.locator('[name=ack]').check();await re.locator('[name=simulation]').check();await re.locator('[type=submit]').click();
  await expect(page.locator('[data-open-plan]')).toHaveCount(2);
  await page.setViewportSize({width:390,height:844});await shot(page,'dispatcher-planning-mobile');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  const done=all.items.find(o=>o.status==='DELIVERED');const events=await inspect(page,`/api/orders/${done.id}/events`);expect(events.items.some(e=>e.event_type==='DELIVERY_COMPLETED')).toBe(true);
});

test('saved preview becomes stale after a real order correction and cannot be committed',async({page})=>{
  const id=await order(page,'Fictional Stale Buyer');await plan(page);
  await page.goto('/#/order/'+id);await page.locator('#edit-form [name=landmark]').fill('Synthetic corrected gate');await page.locator('#edit-form button').last().click();
  await page.goto('/#/routes');await expect(page.locator('[data-open-plan]')).toHaveCount(1);await page.locator('[data-open-plan]').click();
  await expect(page.locator('#routing-preview')).toContainText('STALE');await expect(page.locator('#commit-routing-plan')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).status).not.toBe('ASSIGNED');
});

test('missing pins and unavailable routing remain explicit failures, never simulated success',async({page})=>{
  const id=await order(page,'Fictional Missing Pin',false);
  await page.goto('/#/routes');const f=page.locator('#routing-plan-form');await expect(f).toBeVisible();await f.locator(`[name="order-${id}"]`).check();
  await f.locator('[name=latitude]').fill('16.8');await f.locator('[name=longitude]').fill('96.1');await f.locator('[name=allow_simulation]').check();await f.locator('[type=submit]').click();
  await expect(page.locator('#routing-preview')).toContainText('MISSING_DELIVERY_PIN');
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await page.route('**/dashboard/api',r=>{const q=r.request().postDataJSON();return q.path==='/api/routes/optimize'?r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'ROUTING_KEY_MISSING',message:'Configure a routing provider server-side'}})}):r.continue();});
  await f.locator('[type=submit]').click();await expect(page.locator('#routing-error')).toContainText('ROUTING_KEY_MISSING');page.audit.expectedHttp.add(503);
});
