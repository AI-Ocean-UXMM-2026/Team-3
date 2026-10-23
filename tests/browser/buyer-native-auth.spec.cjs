// Exercise the normal browser-held buyer credential, without the local BFF.
const {test,expect}=require('@playwright/test');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
let server,origin,lookups,submissions,delayed,expired;
const frontend=path.resolve(__dirname,'../../frontend');
const tokens=['a'.repeat(43),'b'.repeat(43)];
const credentials=['c'.repeat(43),'d'.repeat(43)];
const json=(res,value,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
test.beforeAll(async()=>{
  server=http.createServer(async(req,res)=>{
    const url=new URL(req.url,'http://localhost'),p=url.pathname;
    if(p==='/runtime-config.js'){res.setHeader('Content-Type','text/javascript');res.end('globalThis.LANNPYA_RUNTIME='+JSON.stringify({mode:'SUPABASE_BACKEND',supabaseUrl:'https://auth.example.supabase.co',supabaseKey:'sb_publishable_test',apiBase:origin})+';');return;}
    if(p==='/api/confirm/lookup'){
      const index=lookups++;
      setTimeout(()=>json(res,{token:tokens[index],access_token:credentials[index],token_type:'Bearer',expires_at:new Date(Date.now()+900000).toISOString()}),50);return;
    }
    const match=p.match(/^\/api\/confirm\/([^/]+)(\/details|\/request|\/otp|\/verify)?$/);
    if(match){
      const index=tokens.indexOf(match[1]);
      if(!match[2]){const send=()=>json(res,{state:'VERIFICATION_REQUIRED',delivery_status:'DRAFT',order_reference:'native-buyer-order'});if(delayed&&index===0)setTimeout(send,250);else send();return;}
      if(match[2]==='/otp'){json(res,{mode:'SMS',destination_masked:'••••0000',expires_at:new Date(Date.now()+300000).toISOString(),resend_after:new Date(Date.now()+60000).toISOString()});return;}
      if(match[2]==='/verify'){expired=false;json(res,{access_token:credentials[index],token_type:'Bearer',expires_at:new Date(Date.now()+900000).toISOString()});return;}
      if(expired||req.headers.authorization!=='Bearer '+credentials[index]){json(res,{error:{code:'BUYER_AUTHORIZATION_REQUIRED',message:'Valid buyer authorization is required.'}},401);return;}
      if(match[2]==='/request'){submissions++;json(res,{decision:'REVIEW_REQUIRED'});return;}
      json(res,{order_reference:'native-buyer-order',status:'NEEDS_REVIEW',latitude:null,longitude:null,initial_pin_requires_review:true,policy:{editable:true,remaining_edits:3,initial_submitted:false}});return;
    }
    const file=path.resolve(frontend,'.'+(p==='/'?'/index.html':p));
    if(!file.startsWith(frontend+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
    res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
});
test.afterAll(()=>new Promise(resolve=>server.close(resolve)));
test.beforeEach(()=>{lookups=0;submissions=0;delayed=false;expired=false;});
async function lookup(page,double=false){
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await page.goto(origin+'/#/customer');
  await page.locator('[name=trackingId]').fill('QA-NEW');await page.locator('[name=phone]').fill('09790000000');
  const button=page.locator('#customer-link-form .customer-primary');
  if(double)await button.dblclick();else await button.click();
  await expect(page.locator('#customer-form')).toBeVisible();
}
async function submit(page){
  await page.locator('[name=latitude]').fill('16.8');await page.locator('[name=longitude]').fill('96.1');
  await page.locator('[name=initial_pin_acknowledged]').focus();
  await page.locator('[name=initial_pin_acknowledged]').press('Space');
  const response=page.waitForResponse(r=>r.url().endsWith('/request')&&r.request().method()==='PATCH');
  await page.locator('#customer-form .customer-primary').click();
  expect((await response).status()).toBe(200);
  await expect(page.locator('.delivery-request-confirmed')).toBeVisible();
}
test('new buyer lookup preserves its credential when saving the first address',async({page})=>{
  await lookup(page);await submit(page);expect(submissions).toBe(1);
});
test('double-clicking open delivery cannot lose the new buyer authorization',async({page})=>{
  delayed=true;await lookup(page,true);
  expect(lookups).toBe(1);
  await submit(page);expect(submissions).toBe(1);
});

test('switching to another delivery and returning preserves the original buyer session',async({page})=>{
  await lookup(page);await lookup(page);
  const card=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/confirm/'+tokens[0]);
  await page.goto(origin+'/#/track/'+tokens[0]);await card;
  await submit(page);expect(lookups).toBe(2);expect(submissions).toBe(1);
});

test('real authorization expiry requests verification and keeps the unsaved address draft',async({page})=>{
  await lookup(page);
  await page.locator('[name=latitude]').fill('16.8');await page.locator('[name=longitude]').fill('96.1');
  await page.locator('[name=note]').fill('Keep this new-order draft');
  await page.locator('[name=initial_pin_acknowledged]').focus();await page.locator('[name=initial_pin_acknowledged]').press('Space');
  expired=true;
  const failed=page.waitForResponse(r=>r.url().endsWith('/request'));
  await page.locator('#customer-form .customer-primary').click();expect((await failed).status()).toBe(401);
  await expect(page.locator('#customer-form')).toHaveCount(0);await expect(page.locator('.verification')).toBeVisible();
  await page.getByRole('button',{name:'Send verification code'}).click();
  await page.locator('#verify-form [name=digits]').fill('123456');await page.locator('#verify-form button').click();
  await expect(page.locator('[name=note]')).toHaveValue('Keep this new-order draft');
  await expect(page.locator('[name=latitude]')).toHaveValue('16.8');
  await submit(page);expect(submissions).toBe(1);
});
