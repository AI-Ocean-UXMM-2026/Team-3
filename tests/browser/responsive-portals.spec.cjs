const {test,expect}=require('@playwright/test');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
let server,origin;
test.beforeAll(async()=>{
  const root=path.resolve('frontend');
  server=http.createServer((req,res)=>{
    const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
    if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404).end();return;}
    res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');
    res.end(fs.readFileSync(file));
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));origin='http://127.0.0.1:'+server.address().port;
});
test.afterAll(()=>new Promise(r=>server.close(r)));

for(const width of [390,1280])test(`rider navigation stays above map and portals adapt at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  await page.route(/^https:\/\//,r=>r.abort());
  await page.goto(origin+'/prototype.html');
  await page.waitForFunction(()=>!!window.Workflow);
  await page.evaluate(()=>{
    const state=Workflow.fixtures(),o=state.orders[0];
    o.state='out_for_delivery';o.routeId='test-route';o.responseStatus='ACCEPTED';o.accepted={legacy:true};o.pin={lat:16.8,lng:96.1};
    state.routes=[{id:'test-route',riderId:Workflow.ACTORS.rider.id,date:o.date,state:'in_progress',orderIds:[o.id],active:o.id,pickedUpAt:state.clock}];
    localStorage.setItem(Workflow.KEY,JSON.stringify(state));localStorage.setItem(Workflow.RESET_MARKER,'done');
    localStorage.setItem('lannpya.signedOut','{}');location.hash='#/ride';
  });
  await page.reload();
  await expect(page.locator('.rider-osm-route-map')).toBeVisible();
  // The prototype does not bundle maps; mount the same live map renderer here.
  await page.addStyleTag({path:path.resolve('frontend/vendor/leaflet/leaflet.css')});
  await page.addScriptTag({path:path.resolve('frontend/vendor/leaflet/leaflet.js')});
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(()=>Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition(){},watchPosition(){return 1;},clearWatch(){}}}));
  await page.evaluate(()=>LannPyaCustomerMap.riderRouteView(document.querySelector('.rider-osm-route-map'),{
    rider:{lat:16.79,lng:96.09},dest:{lat:16.8,lng:96.1},order:{name:'Ma Thandar'},
    loadTracking:async()=>({state:'live',position:{lat:16.79,lng:96.09},destination:{lat:16.8,lng:96.1},updated_at:new Date().toISOString(),route:{geometry:{type:'LineString',coordinates:[[96.09,16.79],[96.095,16.796],[96.1,16.8]]},distance_meters:1200,duration_seconds:180}})
  }));
  await expect(page.locator('.route-info-badge')).toContainText('Live GPS');
  await page.locator('.rider-menu summary').click();
  const links=page.locator('.rider-menu nav .rider-tab');
  for(let i=0;i<await links.count();i++){
    await expect.poll(()=>links.nth(i).evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));})).toBe(true);
  }
  await page.locator('.rider-menu summary').click();
  await expect(page.locator('.rider-menu')).not.toHaveAttribute('open');
  await expect(page.locator('.rider-menu nav')).not.toBeVisible();
  const wrap=await page.locator('.rider-wrap').boundingBox(),map=await page.locator('.rider-osm-route-map').boundingBox(),body=await page.locator('.rider-body').boundingBox();
  if(width>=1024){expect(wrap.width).toBeGreaterThan(1000);expect(map.x+map.width).toBeLessThanOrEqual(body.x);}
  else{expect(wrap.width).toBeLessThanOrEqual(520);expect(body.y).toBeGreaterThanOrEqual(map.y+map.height);}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,`responsive-rider-${width}.png`),fullPage:true});
  await page.goto(origin+'/prototype.html#/customer');
  await expect(page.locator('#customer-link-form')).toBeVisible();
  const customer=await page.locator('.customer-wrap').boundingBox(),sign=await page.locator('.customer-sign').boundingBox(),form=await page.locator('#customer-link-form').boundingBox();
  if(width>=1024){expect(customer.width).toBeGreaterThan(1000);expect(form.x).toBeGreaterThan(sign.x+sign.width);}
  else{expect(customer.width).toBeLessThanOrEqual(480);expect(form.y).toBeGreaterThanOrEqual(sign.y+sign.height);}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,`responsive-customer-${width}.png`),fullPage:true});
  await page.goto(origin+'/prototype.html#/track/demo-2045');
  await expect(page.locator('.customer-overview .customer-details')).toBeVisible();
  await expect(page.locator('.customer-workflow .verification')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
