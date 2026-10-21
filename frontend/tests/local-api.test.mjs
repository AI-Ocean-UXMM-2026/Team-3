import test from 'node:test';
import assert from 'node:assert/strict';
import {LocalWorkspaceApi} from '../js/local-api.mjs';
import fs from 'node:fs';
import vm from 'node:vm';

test('local adapter keeps private headers out of browser requests and binds rider identity server-side',async t=>{
 const calls=[];
 t.mock.method(globalThis,'fetch',async(url,options={})=>{
  calls.push({url,options});
  if(url.endsWith('/dashboard/bootstrap'))return new Response(JSON.stringify({test_mode:true,csrf:'test-csrf'}));
  const request=JSON.parse(options.body);
  const data=request.path.startsWith('/api/riders')?{items:[{id:'rider-fixture'}]}:{id:'rider-fixture',role:'Rider',name:'Test'};
  return new Response(JSON.stringify({data}));
 });
 const api=new LocalWorkspaceApi();await api.connect('rider','http://127.0.0.1:8780','rider-fixture');
 assert.equal(JSON.parse(calls.at(-1).options.body).rider_id,'rider-fixture');
 assert.ok(calls.every(c=>!c.options.headers?.Authorization&&!c.options.headers?.['X-Dev-Access-Token']));
 assert.equal(api.connections.rider.actor.role,'Rider');
});

test('remote origins cannot be used as privileged proxies',async t=>{
 let called=false;t.mock.method(globalThis,'fetch',async()=>{called=true;throw Error('must not call');});
 await assert.rejects(new LocalWorkspaceApi().connect('admin','https://unapproved.example.invalid'),/local integration/);
 assert.equal(called,false);
});

test('local adapter preserves real backend rejection and never invents success',async t=>{
 t.mock.method(globalThis,'fetch',async url=>url.endsWith('/dashboard/bootstrap')?new Response(JSON.stringify({test_mode:true,csrf:'csrf'})):new Response(JSON.stringify({data:{error:{code:'DATABASE_UNAVAILABLE',message:'Unavailable'}}}),{status:503}));
 await assert.rejects(new LocalWorkspaceApi().connect('admin','http://127.0.0.1:8780'),e=>e.status===503&&e.code==='DATABASE_UNAVAILABLE');
});

test('buyer calls use a capability handle with session CSRF, never browser Bearer credentials',async t=>{
 const calls=[];t.mock.method(globalThis,'fetch',async(url,options={})=>{
  calls.push({url,options});return new Response(JSON.stringify(url.endsWith('/dashboard/bootstrap')?{test_mode:true,csrf:'csrf'}:{data:{verified:true}}));
 });
 const buyer=new LocalWorkspaceApi().openBuyer('http://127.0.0.1:8780','a'.repeat(43));
 assert.equal((await buyer.verify('0000')).verified,true);
 assert.equal(JSON.parse(calls.at(-1).options.body).path,'/api/confirm/@buyer/verify');
 assert.equal(calls.at(-1).options.headers.Authorization,undefined);
 buyer.clear();await assert.rejects(buyer.details(),/closed/);
});

test('demo service worker never intercepts live workspace or private API navigation',()=>{
 const listeners={};
 const self={location:{origin:'http://127.0.0.1:8780'},registration:{scope:'http://127.0.0.1:8780/'},addEventListener:(name,fn)=>listeners[name]=fn};
 vm.runInNewContext(fs.readFileSync(new URL('../sw.js',import.meta.url),'utf8'),{self,URL});
 for(const path of ['/','/index.html','/dashboard/bootstrap','/api/orders','/api/confirm/secret']){
  let intercepted=false;listeners.fetch({request:{method:'GET',url:self.location.origin+path,mode:'navigate'},respondWith(){intercepted=true;}});
  assert.equal(intercepted,false,path);
 }
});
