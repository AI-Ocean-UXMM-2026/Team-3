const {test,expect}=require('@playwright/test');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {pythonPath}=require('../../scripts/python_path.cjs');
let child,origin,directory;
test.beforeAll(async()=>{
  directory=fs.mkdtempSync(path.join(os.tmpdir(),'lannpya-native-buyer-'));
  const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));origin='http://127.0.0.1:'+port;
  child=spawn(pythonPath(),[path.resolve('tests/browser/native_buyer_server.py'),String(port),path.join(directory,'buyer.sqlite3'),'demo-otp'],{cwd:path.resolve('.'),windowsHide:true,stdio:['pipe','ignore','pipe']});
  let error='';child.stderr.on('data',chunk=>{error+=chunk.toString();});
  for(let i=0;i<250;i++){
    if(child.exitCode!==null)throw Error('Isolated buyer server failed: '+error);
    try{if((await fetch(origin+'/health')).ok)return;}catch{}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Isolated buyer server did not start: '+error);
});
test.afterAll(async()=>{
  if(child&&child.exitCode===null){const exited=once(child,'exit');child.stdin.end('stop\n');await exited;}
  if(directory&&path.dirname(directory)===path.resolve(os.tmpdir()))fs.rmSync(directory,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});
test('two new orders confirm through the real API and the first remains authorized on return',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await page.route(/^https:\/\/(?:[abc]\.)?tile\.openstreetmap\.org\//,r=>r.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/m9sAAAAASUVORK5CYII=','base64')}));
  const urls=[];
  for(const reference of ['NATIVE-A','NATIVE-B']){
    await page.goto(origin+'/#/customer');
    await page.locator('[name=trackingId]').fill(reference);await page.locator('[name=phone]').fill('09790000000');
    await page.locator('#customer-link-form .customer-primary').click();
    await expect(page.locator('#customer-form')).toBeVisible();urls.push(page.url());
    await expect(page.locator('#buyer-map.leaflet-container')).toBeVisible();
    await expect(page.locator('#load-street-tiles')).toHaveCount(0);
    await expect.poll(()=>page.locator('#buyer-map .leaflet-tile').count()).toBeGreaterThan(0);
    await page.locator('[name=latitude]').fill('16.8');await page.locator('[name=longitude]').fill('96.1');
    await page.locator('[name=initial_pin_acknowledged]').focus();await page.locator('[name=initial_pin_acknowledged]').press('Space');
    await page.locator('[name=time]').selectOption('12:00–14:00');
    const result=page.waitForResponse(r=>r.url().endsWith('/request')&&r.request().method()==='PATCH');
    await page.locator('#customer-form .customer-primary').click();expect((await result).status()).toBe(200);
    await expect(page.locator('.delivery-request-confirmed')).toBeVisible();
  }
  const card=page.waitForResponse(r=>r.url()===origin+'/api/confirm/'+urls[0].split('/track/')[1]);
  await page.goto(urls[0]);await card;
  await page.getByRole('button',{name:'Edit my request'}).click();
  await page.locator('[name=note]').fill('Original delivery remains authorized');
  await page.locator('[name=initial_pin_acknowledged]').focus();await page.locator('[name=initial_pin_acknowledged]').press('Space');
  const edited=page.waitForResponse(r=>r.url().endsWith('/request')&&r.request().method()==='PATCH');
  await page.locator('#customer-form .customer-primary').click();expect((await edited).status()).toBe(200);
  await expect(page.locator('.delivery-request-confirmed')).toContainText('2 edits remain');
  expect(errors).toEqual([]);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'buyer-native-authorization-saved.png'),fullPage:true});
});


for(const fixed of [false,true])test(`connected backend verifies ${fixed?'123456':'the displayed random demo code'} in browser`,async({page})=>{
 const links=JSON.parse(fs.readFileSync(path.join(directory,'buyer.links.json'),'utf8'));
 const token=links[fixed?1:0].split('/').at(-1);
 await page.goto(origin+'/index.html#/track/'+token);
 await page.getByRole('button',{name:'Send verification code'}).click();
 await expect(page.locator('#verify-form')).toBeVisible();
 const displayed=(await page.locator('.verification .num').first().textContent()).trim();
 expect(displayed).toMatch(/^[0-9]{6}$/);
 await page.locator('[name=digits]').fill(fixed?'123456':displayed);
 const verified=page.waitForResponse(r=>r.url().endsWith('/verify')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Verify code',exact:true}).click();
 expect((await verified).status()).toBe(200);
 await expect(page.locator('#customer-form')).toBeVisible();
});
