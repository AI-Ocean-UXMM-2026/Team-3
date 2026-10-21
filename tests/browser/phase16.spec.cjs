const {test,expect,create,link,verify,approve,assignDispatch,inspect,shot}=require('./fixtures.cjs');

test('Leaflet click and real marker drag submit a reviewed pin that reaches the rider queue',async({page})=>{
  const id=await create(page),url=await link(page),buyer=await page.context().newPage();await verify(buyer,url);
  const map=buyer.locator('#buyer-map');await expect(map).toBeVisible();
  await expect(buyer.locator('.leaflet-marker-icon')).toHaveCount(0);
  await expect(buyer.locator('[name=latitude]')).toHaveValue('');
  await map.click({position:{x:150,y:130}});
  const marker=buyer.locator('.leaflet-marker-icon');await expect(marker).toBeVisible();
  const before=await buyer.locator('[name=latitude]').inputValue(),box=await marker.boundingBox();
  await buyer.mouse.move(box.x+15,box.y+15);await buyer.mouse.down();
  await buyer.mouse.move(box.x+65,box.y+50,{steps:10});await buyer.mouse.up();
  await expect(buyer.locator('[name=latitude]')).not.toHaveValue(before);
  const lat=Number(await buyer.locator('[name=latitude]').inputValue()),lng=Number(await buyer.locator('[name=longitude]').inputValue());
  expect(Math.abs(lat)).toBeLessThanOrEqual(90);expect(Math.abs(lng)).toBeLessThanOrEqual(180);
  await buyer.locator('[name=initial_pin_acknowledged]').check();
  await buyer.locator('#buyer-location-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('awaiting admin review');
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await approve(page,id);const saved=await inspect(page,'/api/orders/'+id);
  expect(Number(saved.latitude)).toBe(lat);expect(Number(saved.longitude)).toBe(lng);expect(saved.confidence_level).toBe('AMBER');
  await expect(page.locator('#delivery-history')).toContainText('BUYER LOCATION');
  await expect(page.locator('#delivery-history')).toContainText('BUYER REQUEST REVIEWED');
  await assignDispatch(page);await page.locator('.role-switch a[href="#/rider"]').click();
  await page.locator('#connect-form button[type=submit]').click();
  const nav=page.getByRole('link',{name:/Open Google Maps/});await expect(nav).toBeVisible();
  expect(new URL(await nav.getAttribute('href')).searchParams.get('destination').split(',').map(Number)).toEqual([lat,lng]);
  await shot(buyer,'phase16-customer-selected-pin');
});

test('Chromium geolocation denial and granted synthetic sensor update only the local selection',async({page})=>{
  const id=await create(page),url=await link(page),buyer=await page.context().newPage();await verify(buyer,url);
  await buyer.context().grantPermissions([]);
  await buyer.locator('[data-action=gps]').click();await expect(buyer.locator('#api-status')).toContainText('GPS permission denied');
  await expect(buyer.locator('[name=latitude]')).toHaveValue('');
  await buyer.context().setGeolocation({latitude:16.8,longitude:96.15});
  await buyer.context().grantPermissions(['geolocation']);
  await buyer.locator('[data-action=gps]').click();await expect(buyer.locator('[name=latitude]')).toHaveValue('16.8000000');
  await expect(buyer.locator('.leaflet-marker-icon')).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
});

test('street tiles are opt-in and mocked at the browser boundary without external requests',async({page})=>{
  await create(page);const url=await link(page);
  const buyer=await page.context().newPage();let tiles=0;
  await buyer.route('https://tile.openstreetmap.org/**',async route=>{tiles++;await route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6d8sAAAAASUVORK5CYII=','base64')});});
  await verify(buyer,url);await expect(buyer.locator('#buyer-map')).toBeVisible();expect(tiles).toBe(0);
  await buyer.locator('#load-street-tiles').click();await expect.poll(()=>tiles).toBeGreaterThan(0);
  await expect(buyer.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
});

test('history displays real chronological completion events without private metadata',async({page})=>{
  const id=await create(page,{pin:true});await assignDispatch(page);
  await page.locator('.role-switch a[href="#/rider"]').click();await page.locator('#connect-form button[type=submit]').click();
  await page.locator('[data-action=deliver]').click();await expect(page.locator('dialog button[type=submit]')).toBeEnabled();
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  await page.locator('.role-switch a[href="#/admin"]').click();await page.locator(`a[href="#/order/${id}"]`).first().click();
  const history=page.locator('#delivery-history');await expect(history).toContainText('DELIVERY COMPLETED');
  await expect(history).toContainText('DELIVERY STARTED');await expect(history).toContainText(/ASSIGN/);
  const times=await history.locator('time').evaluateAll(xs=>xs.map(x=>x.dateTime));expect(times).toEqual([...times].sort());
  const stored=(await inspect(page,`/api/orders/${id}/events`)).items;
  expect(await history.locator('li').count()).toBe(stored.length);
  await expect(history).not.toContainText('09790000000');await expect(history).not.toContainText('Fictional Red Gate');
  await shot(page,'phase16-persisted-delivery-history');
});

test('empty and failed event-history reads are explicit and do not break saved order viewing',async({page})=>{
  const id=await create(page);page.audit.expectedHttp.add(503);let failure=true;
  await page.route('**/dashboard/api',async route=>{
    const call=route.request().postDataJSON();if(call.path.split('?')[0].endsWith('/events'))return route.fulfill({status:failure?503:200,contentType:'application/json',body:JSON.stringify(failure?{error:{code:'TEST_OUTAGE',message:'Injected test failure'}}:{data:{items:[],total:0,page:1,page_size:100}})});
    return route.continue();
  });
  await page.locator('[data-action=refresh]').first().click();await expect(page.locator('#delivery-history')).toContainText('could not be loaded');
  await expect(page.locator('#edit-api-form')).toBeVisible();failure=false;
  await page.locator('#delivery-history [data-action=refresh]').click();await expect(page.locator('#delivery-history')).toContainText('No delivery events yet');
  await page.unroute('**/dashboard/api');await page.locator('[data-action=refresh]').first().click();
  await expect(page.locator('#delivery-history li').first()).toBeVisible();expect((await inspect(page,'/api/orders/'+id)).status).toBe('DRAFT');
});
