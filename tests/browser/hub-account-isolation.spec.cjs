const {test,expect}=require('@playwright/test');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {pythonPath}=require('../../scripts/python_path.cjs');
let child,origin,directory;
test.beforeAll(async()=>{
  directory=fs.mkdtempSync(path.join(os.tmpdir(),'lannpya-hub-isolation-'));
  const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));origin='http://127.0.0.1:'+port;
  child=spawn(pythonPath(),[path.resolve('tests/browser/native_buyer_server.py'),String(port),path.join(directory,'hubs.sqlite3'),'hub-isolation'],{cwd:path.resolve('.'),windowsHide:true,stdio:['pipe','ignore','pipe']});
  let error='';child.stderr.on('data',chunk=>{error+=chunk.toString();});
  for(let i=0;i<250;i++){
    if(child.exitCode!==null)throw Error('Isolated hub server failed: '+error);
    try{if((await fetch(origin+'/health')).ok)return;}catch{}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw Error('Isolated hub server did not start: '+error);
});
test.afterAll(async()=>{
  if(child&&child.exitCode===null){const exited=once(child,'exit');child.stdin.end('stop\n');await exited;}
  if(directory&&path.dirname(directory)===path.resolve(os.tmpdir()))fs.rmSync(directory,{recursive:true,force:true,maxRetries:10,retryDelay:200});
});

test('signing out and into another hub changes stored board orders, including after reload',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  let account='a';
  const ids={a:'11111111-1111-4111-8111-111111111111',b:'22222222-2222-4222-8222-222222222222'};
  await page.route('https://auth.example.supabase.co/**',async route=>{
    const pathname=new URL(route.request().url()).pathname;
    const user={id:ids[account],email:account+'@example.test',email_confirmed_at:new Date().toISOString(),aud:'authenticated',role:'authenticated',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()};
    const jwt=[Buffer.from('{"alg":"HS256"}').toString('base64url'),Buffer.from(JSON.stringify({sub:user.id,exp:Math.floor(Date.now()/1000)+3600,aud:'authenticated'})).toString('base64url'),'synthetic'].join('.');
    const body=pathname.endsWith('/token')?{access_token:jwt,refresh_token:'synthetic-refresh',expires_in:3600,token_type:'bearer',user}:pathname.endsWith('/user')?user:{};
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'*'},body:JSON.stringify(body)});
  });
  await page.goto(origin+'/#/dispatch');
  for(const current of ['a','b','a']){
    account=current;
    await expect(page.locator('#auth-email')).toBeVisible();
    await page.locator('#auth-email').fill(current+'@example.test');
    await page.getByLabel('Password',{exact:true}).fill('Three quiet rivers 47!');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Service board',exact:true})).toBeVisible();
    const own=current==='a'?'NATIVE-A':'NATIVE-B',other=current==='a'?'NATIVE-B':'NATIVE-A';
    await expect(page.locator('#app')).toContainText(own);
    await expect(page.locator('#app')).not.toContainText(other);
    await page.reload();
    await expect(page.locator('#app')).toContainText(own);
    await expect(page.locator('#app')).not.toContainText(other);
    if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'hub-isolation-'+current+'.png'),fullPage:true});
    await page.locator('[data-action="sign-out"]').first().click();
  }
  expect(errors).toEqual([]);
});
