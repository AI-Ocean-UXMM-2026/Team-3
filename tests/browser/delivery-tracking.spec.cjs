const {test,expect}=require('@playwright/test');
const path=require('node:path');

for(const width of [390,1280])test(`rider and buyer share GPS and road geometry at ${width}px`,async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width,height:1000});
  await page.route('**/*',route=>route.abort());
  await page.setContent('<main style="padding:16px"><h2>Rider delivery route</h2><div id="rider" class="route-map" style="height:380px"></div><h2>Buyer tracking</h2><div id="buyer" class="route-map" style="height:380px"></div></main>');
  for(const file of ['vendor/leaflet/leaflet.css','css/signboard.css'])await page.addStyleTag({path:path.resolve('frontend',file)});
  for(const file of ['vendor/leaflet/leaflet.js','js/customer-map.js'])await page.addScriptTag({path:path.resolve('frontend',file)});
  await page.evaluate(()=>{
    window.tracking={state:'unavailable',position:null,route:null};window.gpsReads=0;window.watchesCleared=0;
    Object.defineProperty(navigator,'geolocation',{value:{
      getCurrentPosition:callback=>{gpsReads++;window.gpsCallback=callback;},watchPosition:()=>7,clearWatch:()=>watchesCleared++
    }});
    const options={rider:{lat:16.8,lng:96.1},dest:{lat:16.81,lng:96.11},order:{name:'Delivery destination'},loadTracking:async position=>{if(position)window.lastReported=position;return structuredClone(tracking);}};
    window.riderView=LannPyaCustomerMap.riderRouteView(document.querySelector('#rider'),options);
    window.buyerView=LannPyaCustomerMap.riderRouteView(document.querySelector('#buyer'),{...options,readOnly:true});
  });
  await expect(page.locator('#buyer')).toContainText('Waiting for the rider');
  expect(await page.evaluate(()=>gpsReads)).toBe(1);
  await expect(page.locator('#buyer button[aria-label="Locate my position"]')).toHaveCount(0);
  await page.getByRole('button',{name:'Expand delivery map',exact:true}).click();
  await expect(page.locator('.rider-map-modal .rider-live-marker')).toHaveCount(0);
  await page.evaluate(async()=>{
    window.tracking={state:'live',position:{lat:16.8,lng:96.1},destination:{lat:16.82,lng:96.12},updated_at:new Date().toISOString(),
      route:{geometry:{type:'LineString',coordinates:[[96.1,16.8],[96.108,16.815],[96.12,16.82]]},distance_meters:1800,duration_seconds:300}};
    gpsCallback({coords:{latitude:16.8,longitude:96.1,accuracy:12},timestamp:Date.now()});
    await riderView.refresh();await buyerView.refresh();
  });
  await expect(page.locator('.rider-map-modal .rider-live-marker')).toHaveCount(1);
  expect(await page.evaluate(()=>lastReported.latitude)).toBe(16.8);
  expect(await page.evaluate(()=>lastReported.accuracy)).toBe(12);
  for(const id of ['rider','buyer']){
    await expect(page.locator(`#${id} .route-info-badge`)).toHaveText('Live GPS · 1.8 km · ~5 min');
    await expect(page.locator(`#${id} .leaflet-overlay-pane path`)).toHaveCount(1);
    const svg=page.locator(`#${id} .leaflet-overlay-pane svg`);
    await expect(svg).toHaveCSS('width',(await svg.getAttribute('width'))+'px');
  }
  // Both renderers draw exactly the same road polyline from the shared snapshot.
  const shapes=await page.locator('main .leaflet-overlay-pane path').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('d')));
  expect(shapes[0]).toBe(shapes[1]);
  await expect(page.locator('.modal-nav-btn')).toHaveAttribute('href',/destination=16.82,96.12/);
  await page.getByRole('button',{name:'Close map popup'}).click();
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,`delivery-tracking-${width}.png`)});
  await page.evaluate(async()=>{
    tracking.state='stale';tracking.updated_at=new Date(Date.now()-120000).toISOString();
    await buyerView.refresh();
  });
  await expect(page.locator('#buyer .route-info-badge')).toContainText('Last location 2 min ago');
  await page.evaluate(async()=>{
    tracking={state:'unavailable',position:null,route:null};await riderView.refresh();
    buyerView.off();
    buyerView=LannPyaCustomerMap.riderRouteView(document.querySelector('#buyer'),{
      rider:{lat:16.8,lng:96.1},dest:{lat:16.82,lng:96.12},order:{name:'Delivery destination'},readOnly:true,
      loadTracking:async()=>{throw Object.assign(new Error('Session ended'),{status:401});}
    });await buyerView.refresh();
  });
  await expect(page.locator('main .rider-live-marker')).toHaveCount(0);
  await expect(page.locator('main .leaflet-overlay-pane path')).toHaveCount(0);
  await page.evaluate(()=>{riderView.off();buyerView.off();});
  expect(await page.evaluate(()=>watchesCleared)).toBe(1);
  expect(errors).toEqual([]);
});
