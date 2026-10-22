const {test,expect}=require('@playwright/test');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
let server,origin;
const frontend=path.resolve(__dirname,'../../frontend');
const user={id:'19640f05-a071-455f-8997-8548d6c07066',email:'dispatch@gmail.com',email_confirmed_at:new Date().toISOString(),aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()};
const jwt=[Buffer.from('{"alg":"HS256"}').toString('base64url'),Buffer.from(JSON.stringify({sub:user.id,exp:Math.floor(Date.now()/1000)+3600,aud:'authenticated'})).toString('base64url'),'test-signature'].join('.');
test.beforeAll(async()=>{
  server=http.createServer((req,res)=>{
    const pathname=new URL(req.url,'http://localhost').pathname;
    if(pathname==='/runtime-config.js'){res.setHeader('Content-Type','text/javascript');res.end('globalThis.LANNPYA_RUNTIME='+JSON.stringify({mode:'SUPABASE_BACKEND',supabaseUrl:'https://auth.example.supabase.co',supabaseKey:'sb_publishable_test',apiBase:origin})+';');return;}
    if(pathname.startsWith('/api/')){res.setHeader('Content-Type','application/json');if(!req.headers.authorization){res.writeHead(401);res.end('{}');return;}res.end(JSON.stringify(pathname==='/api/session'?{id:user.id,name:'Test Dispatcher',role:'Dispatcher'}:{items:[],total:0}));return;}
    const file=path.resolve(frontend,'.'+(pathname==='/'?'/index.html':pathname));
    if(!file.startsWith(frontend+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
    const ext=path.extname(file);res.setHeader('Content-Type',({'.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[ext]||'application/octet-stream');res.end(fs.readFileSync(file));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
});
test.afterAll(()=>new Promise(resolve=>server.close(resolve)));
async function setup(page){
  const requests=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://auth.example.supabase.co/**',async route=>{
    const request=route.request(),url=new URL(request.url());requests.push({path:url.pathname,body:request.postDataJSON()});
    let status=200,body={};
    if(url.pathname.endsWith('/token'))body={access_token:jwt,refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user};
    if(url.pathname.endsWith('/verify')){
      if(request.postDataJSON()?.token==='654321')body={access_token:jwt,refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user};
      else{status=403;body={code:403,error_code:'otp_expired',msg:'Token expired'};}
    }
    if(url.pathname.endsWith('/user'))body=user;
    await route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'*'},body:JSON.stringify(body)});
  });
  await page.goto(origin);await expect(page.getByRole('tab',{name:'Sign in',exact:true})).toBeVisible();
  return {requests,errors};
}
test('password login unlocks database workspace; logout restores sign-in',async({page})=>{
  const {requests,errors}=await setup(page);
  await page.locator('#auth-email').fill(user.email);await page.getByLabel('Password',{exact:true}).fill('Three quiet rivers 47!');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('.signin')).toHaveCount(0);await expect(page.locator('[data-action="sign-out"]').first()).toBeVisible();
  await page.locator('[data-action="sign-out"]').first().click();await expect(page.getByRole('tab',{name:'Sign in',exact:true})).toBeVisible();
  expect(requests.some(r=>r.path.endsWith('/logout'))).toBeTruthy();expect(errors).toEqual([]);
});
test('email-code flow refuses expired code and preserves recovery controls',async({page})=>{
  const {requests,errors}=await setup(page);
  await page.getByRole('button',{name:'Use an email code instead'}).click();await page.locator('#auth-email').fill(user.email);await page.getByRole('button',{name:'Send email code'}).click();
  await expect(page.getByRole('heading',{name:'Check your inbox'})).toBeVisible();
  expect(requests.find(r=>r.path.endsWith('/otp')).body.create_user).toBe(false);
  await page.getByLabel('Email code',{exact:true}).fill('123456');await page.getByRole('button',{name:'Verify code'}).click();
  await expect(page.getByRole('alert')).toContainText('invalid or expired');await expect(page.getByRole('button',{name:'Send a new code'})).toBeVisible();expect(errors).toEqual([]);
});
test('responsive signup validates confirmation and does not expose demo credentials',async({page})=>{
  const {requests,errors}=await setup(page);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'auth-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'auth-mobile.png'),fullPage:true});
  await page.getByRole('tab',{name:'Create shop account'}).click();await page.locator('[name=shop]').fill('Test shop');await page.locator('[name=phone]').fill('09790000000');await page.locator('#auth-email').fill(user.email);await page.getByLabel('Password',{exact:true}).fill('Three quiet rivers 47!');await page.getByLabel('Confirm password').fill('A different password 84!');await page.getByRole('button',{name:'Create account',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('don’t match');expect(requests.some(r=>r.path.endsWith('/signup'))).toBe(false);await expect(page.locator('body')).not.toContainText('PIN 1234');expect(errors).toEqual([]);
});
test('valid email code opens the authorized workspace',async({page})=>{
  const {errors}=await setup(page);
  await page.getByRole('button',{name:'Use an email code instead'}).click();
  await page.locator('#auth-email').fill(user.email);await page.getByRole('button',{name:'Send email code'}).click();
  await page.getByLabel('Email code',{exact:true}).fill('654321');await page.getByRole('button',{name:'Verify code'}).click();
  await expect(page.locator('.signin')).toHaveCount(0);await expect(page.locator('[data-action="sign-out"]').first()).toBeVisible();expect(errors).toEqual([]);
});
test('recovery verifies email, saves password and requires a fresh sign-in',async({page})=>{
  const {requests,errors}=await setup(page);
  await page.getByRole('button',{name:'Forgot password?'}).click();await page.locator('#auth-email').fill(user.email);await page.getByRole('button',{name:'Send email code'}).click();
  await page.getByLabel('Email code',{exact:true}).fill('654321');await page.getByRole('button',{name:'Verify code'}).click();
  await expect(page.getByRole('heading',{name:'Choose a new password'})).toBeVisible();
  await page.getByLabel('Password',{exact:true}).fill('Four quiet mountains 82!');await page.getByLabel('Confirm password').fill('Four quiet mountains 82!');await page.getByRole('button',{name:'Save new password'}).click();
  await expect(page.getByRole('tab',{name:'Sign in',exact:true})).toBeVisible();await expect(page.getByRole('status')).toContainText('Password saved');
  expect(requests.some(r=>r.path.endsWith('/user')&&r.body?.password==='Four quiet mountains 82!')).toBe(true);expect(errors).toEqual([]);
});
test('rider login opens the existing rider screen and honors session-only storage',async({page})=>{
  const {errors}=await setup(page);
  await page.route(origin+'/api/session',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({id:user.id,name:'Test Rider',role:'Rider'})}));
  await page.locator('#auth-email').fill(user.email);await page.getByLabel('Password',{exact:true}).fill('Three quiet rivers 47!');
  await page.getByRole('checkbox',{name:'Keep me signed in on this computer'}).uncheck();
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(/#\/ride$/);
  await expect(page.getByRole('heading',{name:'Hi Test Rider'})).toBeVisible();
  await page.locator('.rider-menu summary').click();
  await expect(page.locator('[data-action="sign-out"][data-id="rider"]')).toBeVisible();
  expect(await page.evaluate(()=>!!sessionStorage.getItem('lannpya.auth')&&!localStorage.getItem('lannpya.auth'))).toBe(true);expect(errors).toEqual([]);
});
