// Actual selected frontend controllers + local BFF + backend + SQL transactions; not a visual browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import net from 'node:net';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {createRequire} from 'node:module';
import {LocalWorkspaceApi,context,today,townships,mmk,tokenFrom} from '../../../../frontend/js/local-api.mjs';
import {environment} from '../../../../frontend/tests/test-dom.js';
const require=createRequire(import.meta.url),{pythonPath,root}=require('../../../../scripts/python_path.cjs');

test('selected application connects admin, native buyer verification, dispatcher and rider COD closeout', {timeout:60000}, async t=>{
 const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn(pythonPath(),['-m','tools.integrated_workspace','--port',String(port),'--temporary'],{cwd:root+'/backend',stdio:'ignore',windowsHide:true});
 const exited=once(child,'exit'),origin=`http://127.0.0.1:${port}`,nativeFetch=globalThis.fetch;let cookie='';
 const direct=async(url,options={})=>{
  const response=await nativeFetch(new URL(url,origin),{...options,headers:{...options.headers,Cookie:cookie,Origin:origin},signal:AbortSignal.timeout(5000)});
  if(response.headers.get('set-cookie'))cookie=response.headers.get('set-cookie').split(';')[0];return response;
 };
 let csrf;
 try{
  const deadline=Date.now()+20000;while(true){try{assert.equal((await direct('/')).status,200);break;}catch(e){if(Date.now()>deadline)throw e;await delay(50);}}
  csrf=(await (await direct('/dashboard/bootstrap')).json()).csrf;
  t.mock.method(globalThis,'fetch',async(url,options={})=>{
    assert.equal(options.headers?.['X-Dev-Access-Token'],undefined);assert.equal(options.headers?.Authorization,undefined);
    return direct(url,options);
  });
  const e=environment(null,'#/admin');Object.assign(e.ctx,{WorkspaceApi:LocalWorkspaceApi,context,today,townships,mmk,tokenFrom,crypto,history:{replaceState(){}}});
  Object.assign(e.ctx.location,{origin,protocol:'http:',pathname:'/api.html',href:origin+'/api.html#/admin'});
  const source=fs.readFileSync(new URL('../api-workspace.mjs',import.meta.url),'utf8').replace(/^import[^\r\n]*\r?\n/,'').replace(/\nload\(\);\s*$/,'\nglobalThis.ready=load();');
  vm.runInNewContext(source,e.ctx);await e.ctx.ready;
  const wait=async(predicate,label)=>{const end=Date.now()+10000;while(!predicate()){if(Date.now()>end)throw Error('Timed out: '+label+'; '+(e.find('#api-status')?.textContent||''));await delay(10);}};
  assert.equal(e.find('[name="token"]'),null);
  await e.submit('#connect-form',{base:origin});assert.ok(e.find('#create-form'));
  const raw='name: Fictional Buyer, ၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ COD ၂၅၀၀၀ ကျပ်၊ address: fictional red gate';
  await e.submit('#parse-form',{raw});assert.match(e.find('#parse-result').textContent,/AMBER/);
  e.find('#create-form [name="item"]').value='Fictional parcel';e.find('#create-form [name="delivery_day"]').value=today();
  await e.action('save-raw');await wait(()=>e.find('#edit-api-form'),'raw order saved');
  const id=e.ctx.location.hash.split('/').at(-1);
  const api=new LocalWorkspaceApi();await api.connect('admin',origin);
  assert.equal((await api.order(id)).original_message,raw);
  await e.action('link',id);const token=tokenFrom(e.find('[name="generated-link"]').value);
  e.ctx.location.hash='#/track/'+token;await wait(()=>e.find('#verify-api-form'),'buyer card');
  await e.submit('#verify-api-form',{digits:'0000'});assert.ok(e.find('#buyer-location-form'));
  await e.submit('#buyer-location-form',{latitude:'0',longitude:'0',initial_pin_acknowledged:true});assert.match(e.find('#api-status').textContent,/awaiting admin review/);
  await e.submit('#buyer-response-form',{action:'AVAILABLE',instructions:'Fictional: ring bell'});
  e.ctx.location.hash='#/order/'+id;await wait(()=>e.find('#edit-api-form'),'dispatcher order');
  for(const request of await api.all('admin',`/api/orders/${id}/buyer-requests`)){
   if(request.decision==='REVIEW_REQUIRED'&&!request.resolution){await e.action('review',request.id);await e.submit('dialog form',{decision:'APPROVE',reason:'Synthetic dispatcher approval only'});}
  }
  const rider=(await api.all('admin','/api/riders'))[0];
  await e.submit('#prepare-assignment-form',{selection:'rider:'+rider.id,received:true,ack:true});
  const assigned=await api.order(id);assert.equal(assigned.status,'ASSIGNED');assert.equal(assigned.confidence_level,'AMBER');
  const route=await api.all('admin','/api/routes');assert.equal(route.length,1);
  await e.action('dispatch',route[0].id);await e.submit('dialog form',{});
  assert.equal((await api.order(id)).status,'OUT_FOR_DELIVERY');
  e.ctx.location.hash='#/rider';await wait(()=>e.find('#connect-form'),'rider connection');
  await e.submit('#connect-form',{base:origin,actor_id:rider.id});
  await e.action('deliver',id);await e.tick(2000);await e.submit('dialog form',{amount:'25000',reason:''});
  assert.equal((await api.order(id)).status,'DELIVERED');
  const events=await api.all('admin',`/api/orders/${id}/events`);assert.equal(events.filter(e=>e.event_type==='DELIVERY_COMPLETED').length,1);assert.ok(events.some(e=>e.event_type==='DELIVERY_STARTED'));
  await e.action('handover',route[0].id);
  e.ctx.location.hash='#/admin';await wait(()=>e.find('#hub-closeout'),'hub closeout');
  await e.action('receipt',route[0].id);await e.submit('dialog form',{amount:'25000',reason:'',resolve:false});
  assert.equal((await api.all('admin','/api/routes'))[0].state,'closed');
  // A separate RED input is corrected explicitly before a failed delivery workflow.
  await e.submit('#parse-form',{raw:'Hlaing township, COD 0 MMK'});
  e.find('#create-form [name="item"]').value='Fictional second parcel';
  await e.action('save-raw');await wait(()=>e.find('#edit-api-form'),'second order');
  const failedId=e.ctx.location.hash.split('/').at(-1);
  assert.equal((await api.order(failedId)).confidence_level,'RED');
  await e.submit('#edit-api-form',{customer_name:'Fictional second buyer',customer_phone:'09790000000',township:'Hlaing',street:'Fictional Street',cod_amount:'0',latitude:'0',longitude:'0'});
  assert.equal((await api.order(failedId)).confidence_level,'AMBER');
  await e.submit('#prepare-assignment-form',{selection:'rider:'+rider.id,received:true,ack:true});
  const secondRoute=(await api.all('admin','/api/routes')).find(r=>r.state==='draft');
  await e.action('dispatch',secondRoute.id);await e.submit('dialog form',{});
  e.ctx.location.hash='#/rider';await wait(()=>e.all('[data-action]').some(b=>b.dataset.action==='failed'),'second rider queue');
  await e.action('failed',failedId);await e.submit('dialog form',{failure_reason:'CUSTOMER_UNAVAILABLE',failure_note:'Fictional buyer unavailable'});
  assert.equal((await api.order(failedId)).status,'FAILED');
  const history=await api.all('admin',`/api/orders/${failedId}/events`);
  assert.equal(history.filter(e=>e.event_type==='DELIVERY_FAILED').length,1);
  assert.equal((await nativeFetch(origin+'/dashboard/bootstrap')).status,401);

 }finally{
  if(child.exitCode===null&&csrf){await direct('/dashboard/shutdown',{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-CSRF':csrf},body:JSON.stringify({confirm:'STOP LOCAL TOOL'})});await Promise.race([exited,delay(10000,undefined,{ref:false}).then(()=>{throw Error('Shutdown timed out');})]);}
  else if(child.exitCode===null)child.kill();
 }
});
