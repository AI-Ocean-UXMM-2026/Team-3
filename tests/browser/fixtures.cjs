const {test:base,expect}=require('@playwright/test');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const net=require('node:net');
const fs=require('node:fs');
const path=require('node:path');
const {setTimeout:delay}=require('node:timers/promises');
const {pythonPath,root}=require('../../scripts/python_path.cjs');
const shots=path.join(root,'docs/visual-testing/screenshots');
const sanitize=s=>String(s).replace(/[A-Za-z0-9_-]{43,}/g,'[redacted]').replace(/\/confirm\/[^/?\s]+/g,'/confirm/[redacted]');
const test=base.extend({
  app:async({},use,testInfo)=>{
    const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');
    const port=probe.address().port;await new Promise(r=>probe.close(r));
    const origin=`http://127.0.0.1:${port}`;
    const child=spawn(pythonPath(),['-m','tools.integrated_workspace','--port',String(port),'--temporary'],{
      cwd:path.join(root,'backend'),stdio:['ignore','ignore','pipe'],windowsHide:true,
      env:{...process.env,LANNPYA_ENVIRONMENT:'test'},
    });
    let stderr='';child.stderr.on('data',b=>{stderr+=b.toString();});
    const exited=once(child,'exit');let cookie='',csrf;
    const deadline=Date.now()+25000;
    try{
      while(true){
        if(Date.now()>deadline)throw Error('Isolated server startup timed out');
        try{const r=await fetch(origin,{signal:AbortSignal.timeout(1000)});if(r.ok){cookie=r.headers.get('set-cookie').split(';')[0];break;}}
        catch(e){if(child.exitCode!==null||Date.now()>deadline)throw Error('Isolated server startup failed: '+sanitize(stderr||e.message));}
        await delay(50);
      }
      csrf=(await (await fetch(origin+'/dashboard/bootstrap',{headers:{Cookie:cookie}})).json()).csrf;
      await use({origin,stderr:()=>sanitize(stderr)});
    }finally{
      if(child.exitCode===null){
        try{await fetch(origin+'/dashboard/shutdown',{method:'POST',headers:{Cookie:cookie,Origin:origin,'Content-Type':'application/json','X-Dashboard-CSRF':csrf},body:JSON.stringify({confirm:'STOP LOCAL TOOL'}),signal:AbortSignal.timeout(5000)});await Promise.race([exited,delay(10000).then(()=>{throw Error('Shutdown timed out');})]);}
        catch(e){child.kill();throw e;}
      }
      if(stderr.includes('Traceback'))await testInfo.attach('server-errors',{body:sanitize(stderr),contentType:'text/plain'});
    }
  },
  page:async({browser,app},use,testInfo)=>{
    const context=await browser.newContext({baseURL:app.origin,viewport:testInfo.project.use.viewport||{width:1440,height:900},timezoneId:'Asia/Rangoon'});
    const activity=[],errors=[],network=[],starts=new WeakMap();
    context.on('page',p=>{
      p.on('pageerror',e=>errors.push(sanitize(e.message)));
      p.on('console',m=>{if(m.type()==='error')activity.push({kind:'console',message:sanitize(m.text())});});
      p.on('requestfailed',r=>activity.push({kind:'network',path:sanitize(new URL(r.url()).pathname),error:sanitize(r.failure()?.errorText)}));
      p.on('response',r=>{
        const q=r.request(),body=q.url().endsWith('/dashboard/api')?q.postDataJSON():null;
        network.push({method:q.method(),path:sanitize(body?.path||new URL(r.url()).pathname),status:r.status(),duration_ms:Date.now()-(starts.get(q)||Date.now())});
        if(r.status()>=400)activity.push({kind:'http',path:sanitize(new URL(r.url()).pathname),status:r.status()});
      });
      p.on('request',r=>{starts.set(r,Date.now());if(r.headers()['x-dev-access-token']||r.headers().authorization)errors.push('Privileged credential reached browser request');});
    });
    const page=await context.newPage();
    page.audit={activity,errors,expectedHttp:new Set()};
    try{
      await use(page);expect(errors,'Uncaught JavaScript errors or credential leak').toEqual([]);
      expect(activity.filter(e=>e.kind==='http'&&!page.audit.expectedHttp.has(e.status)&&(e.status>=500||e.path!=='/dashboard/api')),'Unexpected HTTP or static-asset error').toEqual([]);
      expect(activity.filter(e=>e.kind==='console'&&!/^Failed to load resource: (the server responded with a status of 4[0-9]{2} |net::ERR_FAILED)/.test(e.message)&&![...page.audit.expectedHttp].some(status=>e.message.includes('status of '+status+' '))),'Unexpected console errors').toEqual([]);
      if(!testInfo.title.includes('failed real order write'))expect(activity.filter(e=>e.kind==='network'),'Unexpected failed request').toEqual([]);
    }
    finally{await testInfo.attach('sanitized-browser-observations',{body:JSON.stringify({activity,errors,network},null,2),contentType:'application/json'});await context.close();}
  },
});
async function enter(page){
  await page.goto('/');
  await expect(page.locator('#app')).not.toBeEmpty();
}
async function inspect(page,apiPath){
  const response=await page.request.get('/dashboard/bootstrap');const {csrf}=await response.json();
  const r=await page.request.post('/dashboard/api',{headers:{Origin:new URL(page.url()).origin,'X-Dashboard-CSRF':csrf},data:{method:'GET',path:apiPath,body:null,actor:'dispatcher'}});
  expect(r.ok(),`Read-only inspection ${apiPath}`).toBeTruthy();return (await r.json()).data;
}
async function shot(page,name){
  fs.mkdirSync(shots,{recursive:true});
  await page.screenshot({path:path.join(shots,name+'.png'),fullPage:true,animations:'disabled'});
}
module.exports={test,expect,enter,inspect,shot};
