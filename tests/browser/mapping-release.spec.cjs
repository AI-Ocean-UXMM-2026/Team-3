// Complete local mapping journey at every requested viewport. Synthetic data/GPS; no live maps APIs.
const {test,expect,inspect}=require('./fixtures.cjs');
const path=require('node:path');
const fs=require('node:fs');
const output=path.resolve('.tmp/mapping-release/screenshots');
async function screenshot(page,name){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});}
async function noOverflow(page){expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);}

for(const [width,height] of [[1440,900],[1366,768],[768,1024],[390,844],[360,740]]){
  test.describe(`${width}x${height}`,()=>{
    test.use({hasTouch:width<=768});
    test('GPS, denied permission, pin selection/drag, approval, optimizer, rider COD and replan',async({page})=>{
      await page.setViewportSize({width,height});
      await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
      await page.goto('/#/manual');const form=page.locator('#manual-form');await expect(form).toBeVisible();
      for(const [k,v]of Object.entries({name:'Fictional Mapping Release Buyer',phone:'09790000000',item:'Synthetic shirt',street:'စမ်းသပ်လမ်း',landmark:'Fictional test gate',expected:'25000'}))await form.locator(`[name=${k}]`).fill(v);
      await form.locator('[name=areaId]').selectOption('Hlaing');await form.locator('[name=received]').check();await form.locator('button').last().click();
      await expect(page.locator('#edit-form')).toBeVisible();const id=new URL(page.url()).hash.split('/').at(-1);
      await page.locator('[data-action=issue]').click();const link=page.getByRole('link',{name:'See what the buyer sees'});await expect(link).toBeVisible();
      await page.goto('/'+await link.getAttribute('href'));await expect(page.locator('#verify-form')).toBeVisible();await page.locator('[name=digits]').fill('0000');await page.locator('#verify-form button').click();
      const map=page.locator('#buyer-map');await expect(map).toBeVisible();await expect(page.locator('[name=latitude]')).toHaveValue('');
      await page.evaluate(()=>{const original=navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);globalThis.restoreReleaseGps=()=>navigator.geolocation.getCurrentPosition=original;navigator.geolocation.getCurrentPosition=(_ok,fail)=>fail({code:1});});
      await page.locator('[data-action=get-location]').click();await expect(page.locator('.form-error')).toContainText('permission denied');
      await page.evaluate(()=>restoreReleaseGps());await page.context().grantPermissions(['geolocation']);await page.context().setGeolocation({latitude:16.81,longitude:96.11,accuracy:8});
      await page.locator('[data-action=get-location]').click();await expect(page.locator('[name=latitude]')).toHaveValue('16.81');
      await expect(page.locator('.form-error')).toBeEmpty();
      await expect(page.locator('#map-selection-status')).toContainText('does not independently verify');
      await map.scrollIntoViewIfNeeded();
      if(width<=768){const b=await map.boundingBox();await page.touchscreen.tap(b.x+b.width/2+8,b.y+b.height/2+8);}else await map.click({position:{x:160,y:140}});
      const before=await page.locator('[name=longitude]').inputValue(),pin=page.locator('#buyer-map .leaflet-marker-draggable');await pin.scrollIntoViewIfNeeded();const b=await pin.boundingBox();
      if(width<=768){
        const session=await page.context().newCDPSession(page),x=b.x+15,y=b.y+15;
        await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
        for(let i=1;i<=8;i++)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+4*i,y:y+2*i}]});
        await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await session.detach();
      }else{await page.mouse.move(b.x+15,b.y+15);await page.mouse.down();await page.mouse.move(b.x+55,b.y+35,{steps:8});await page.mouse.up();}
      await expect(page.locator('[name=longitude]')).not.toHaveValue(before);const latitude=await page.locator('[name=latitude]').inputValue();
      await noOverflow(page);await screenshot(page,`${width}-buyer-pin`);
      await page.locator('[name=initial_pin_acknowledged]').check();await page.locator('[name=note]').fill('Synthetic release doorstep note');await page.locator('#customer-form .customer-primary').click();
      await expect(page.locator('.live-notice').filter({hasText:'persisted'})).toBeVisible();expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
      await page.goto('/#/order/'+id);await expect(page.locator('[data-action=approve-location]')).toBeVisible();await page.locator('[data-action=approve-location]').click();
      await page.locator('dialog [name=reason]').fill('Synthetic fixture approval; independent geospatial accuracy unknown');await noOverflow(page);await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
      while(await page.locator('[data-review-request]').count()){await page.locator('[data-review-request]').first().click();await page.locator('dialog [name=reason]').fill('Synthetic buyer availability review');await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);}
      const saved=await inspect(page,'/api/orders/'+id);expect(Number(saved.latitude)).toBe(Number(latitude));expect(saved.confidence_level).toBe('AMBER');
      await page.reload();expect(Number((await inspect(page,'/api/orders/'+id)).latitude)).toBe(Number(latitude));
      await page.goto('/#/routes');const planner=page.locator('#routing-plan-form');await expect(planner).toBeVisible();
      await planner.locator('[name=latitude]').fill('16.8');await planner.locator('[name=longitude]').fill('96.1');await planner.locator('[name=solver_seconds]').fill('1');await planner.locator(`[name="priority-${id}"]`).fill('5');await planner.locator('[name=allow_simulation]').check();await planner.locator('[type=submit]').click();
      await expect(page.locator('#routing-preview')).toContainText('SIMULATED');await expect(page.locator('#routing-preview')).toContainText('Capacity use: 1 / 20');await expect(page.locator('#routing-preview')).toContainText('Priority 5');
      expect((await inspect(page,'/api/orders/'+id)).status).not.toBe('ASSIGNED');
      await noOverflow(page);await screenshot(page,`${width}-route-preview`);
      const commit=page.locator('#commit-routing-plan');await commit.locator('[name=ack]').check();await commit.locator('[name=simulation]').check();await commit.locator('[type=submit]').click();
      await expect(page.locator('[data-action=dispatch-route]')).toBeVisible();await page.locator('[data-action=dispatch-route]').click();await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
      await page.goto('/#/ride');await expect(page.locator('body')).toContainText('Assigned route plan');await expect(page.locator('body')).toContainText('Synthetic release doorstep note');
      await expect(page.locator('.google-road-estimate button[type=submit]')).toBeDisabled();
      const navigation=page.locator('a[href*="google.com/maps/dir"]').first();await expect(navigation).toBeVisible();
      expect(new URL(await navigation.getAttribute('href')).searchParams.has('destination')).toBe(true);
      await page.context().route('https://www.google.com/maps/**',r=>r.fulfill({status:200,contentType:'text/html',body:'Synthetic navigation target; no Google network call'}));
      const popup=page.waitForEvent('popup');await navigation.click();const opened=await popup;await opened.waitForLoadState();expect(opened.url()).toContain('google.com/maps/dir');await opened.close();
      await noOverflow(page);await screenshot(page,`${width}-rider-route`);
      await page.locator('[data-action=delivered]').click();await page.locator('dialog [name=codCollected]').check();await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
      expect((await inspect(page,'/api/orders/'+id)).status).toBe('DELIVERED');
      expect((await inspect(page,'/api/orders/'+id+'/events')).items.some(e=>e.event_type==='DELIVERY_COMPLETED')).toBe(true);
      await page.goto('/#/routes');await expect(page.locator('[data-open-plan]')).toHaveCount(1);await page.locator('[data-open-plan]').click();await expect(page.locator('#routing-preview')).toContainText('STALE');
      await expect(page.locator('#commit-routing-plan')).toHaveCount(0);await page.locator('#replan-routing').click();await expect(page.locator('#routing-preview')).toContainText('Completed/failed/cancelled stops are excluded');
    });
  });
}

test('rider REST refresh reports a disconnect and recovers without duplicate records or simulated saves',async({page})=>{
  page.audit.expectedHttp.add(503);
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await page.goto('/#/ride');const refresh=page.getByRole('button',{name:'Refresh approved stops'});await expect(refresh).toBeVisible();
  let disconnected=true;
  await page.route('**/dashboard/api',route=>{const q=route.request().postDataJSON();if(disconnected&&q.method==='GET'&&q.path.endsWith('/queue'))return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'QUEUE_UNAVAILABLE',message:'Synthetic queue disconnect; refresh again when connected'}})});return route.continue();});
  await refresh.click();await expect(page.locator('body')).toContainText('Synthetic queue disconnect');
  disconnected=false;await refresh.click();await expect(page.locator('body')).toContainText('Stops refreshed.');
  expect((await inspect(page,'/api/orders')).total).toBe(0);
  await expect(page.locator('.queue-button')).toHaveCount(0);
});
