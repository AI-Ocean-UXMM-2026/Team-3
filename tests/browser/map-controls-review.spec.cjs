const {test,expect}=require('@playwright/test');
const path=require('node:path');
const http=require('node:http'),fs=require('node:fs');
let server,origin;
test.beforeAll(async()=>{
  const root=path.resolve('frontend');
  server=http.createServer((request,response)=>{
    const file=path.resolve(root,'.'+new URL(request.url,'http://localhost').pathname);
    if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){response.writeHead(404).end();return;}
    response.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');
    response.end(fs.readFileSync(file));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
});
test.afterAll(()=>new Promise(resolve=>server.close(resolve)));

for(const width of [390,1280])test(`rider map controls stay usable at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:844});
  await page.route('**/*',route=>route.abort());
  await page.setContent('<main style="padding:16px"><div id="map" class="route-map" style="height:420px;width:100%;max-width:760px"></div></main>');
  await page.addStyleTag({path:path.resolve('frontend/vendor/leaflet/leaflet.css')});
  await page.addStyleTag({path:path.resolve('frontend/css/signboard.css')});
  await page.addScriptTag({path:path.resolve('frontend/vendor/leaflet/leaflet.js')});
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(()=>{
    Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition:success=>success({coords:{latitude:16.8,longitude:96.1}})}});
    LannPyaCustomerMap.riderRouteView(document.querySelector('#map'),{
      rider:{lat:16.8,lng:96.1},dest:{lat:16.805,lng:96.105},
      order:{name:'Fictional delivery stop',street:'Test street'},stopIndex:1,totalStops:1,
    });
  });
  const locate=page.getByRole('button',{name:'Locate my position',exact:true});
  const expand=page.getByRole('button',{name:'Expand delivery map',exact:true});
  await expect(locate).toBeVisible();await expect(expand).toBeVisible();
  for(const button of [locate,expand]){
    const rect=await button.boundingBox();expect(rect.height).toBeGreaterThanOrEqual(48);
    await expect(button.locator('svg')).toHaveCSS('width','20px');
    await expect(button.locator('svg')).toHaveCSS('position','static');
  }
  const a=await locate.boundingBox(),b=await expand.boundingBox();
  expect(a.y).toBe(b.y);expect(a.x+a.width).toBeLessThan(b.x);
  await locate.click();await expect(locate).toBeEnabled();
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,`map-controls-${width}.png`)});
  await expand.click();await expect(page.locator('.rider-map-modal')).toBeVisible();
  await page.getByRole('button',{name:'Close map popup'}).click();
  await expect(page.locator('.rider-map-modal')).toHaveCount(0);
});

test('pin review saves with an empty optional reason',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route(/^https:\/\//,route=>route.abort());
  await page.goto(origin+'/prototype.html#/dispatch');
  await page.waitForFunction(()=>!!window.Workflow);
  expect(errors).toEqual([]);
  await page.evaluate(()=>{
    const initial=Workflow.fixtures(),order=initial.orders[0],area=Workflow.PLACES.find(a=>a.id===order.areaId);
    order.proposedPin={lat:area.lat,lng:area.lng};order.state='held';
    initial.revision=100;localStorage.setItem(Workflow.KEY,JSON.stringify(initial));location.hash='#/order/'+order.id;
  });
  await page.locator('[data-action=approve-location]').first().click();
  const reason=page.getByLabel('Reason (optional)',{exact:true});
  await expect(reason).toBeVisible();await expect(reason).not.toHaveAttribute('required');
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'review-optional-reason.png')});
  await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('dialog')).toHaveCount(0);
  expect(await page.evaluate(()=>Workflow.createStore(localStorage).order('LP-2045').proposedPin)).toBeNull();
});
