// Mapping HTTP process-restart verification (Google calls disabled). Owns one temporary SQLite directory only.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {spawn}=require('node:child_process'),{once}=require('node:events');
const {setTimeout:delay}=require('node:timers/promises');
const {pythonPath,root}=require('./python_path.cjs');
const code=`import sys
from pathlib import Path
import uvicorn
from tools.integrated_workspace import WorkspaceSandbox, application
WorkspaceSandbox.storage_directory=lambda self: Path(sys.argv[1])
app=application(sys.argv[2])
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=int(sys.argv[3]),access_log=False,proxy_headers=False,log_level='warning'))
app.state.server=server
server.run()
`;
async function main(){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'lannpya-mapping-restart-'));
 const owned=fs.realpathSync(directory),marker=path.join(owned,'owned-by-test');fs.writeFileSync(marker,'synthetic restart fixture');
 let child,exited,cookie,csrf,origin;
 async function start(){
  const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');const port=probe.address().port;await new Promise(r=>probe.close(r));origin=`http://127.0.0.1:${port}`;
  child=spawn(pythonPath(),['-c',code,owned,origin,String(port)],{cwd:path.join(root,'backend'),windowsHide:true,stdio:'ignore',env:{...process.env,LANNPYA_ENVIRONMENT:'test',LANNPYA_ROUTING_PROVIDER:'offline',LANNPYA_ROUTING_EXTERNAL_REQUESTS_ENABLED:'false',LANNPYA_GOOGLE_DEMO_ENABLED:'false',LANNPYA_GOOGLE_DEMO_MAX_REQUESTS:'0',LANNPYA_GOOGLE_MAPS_BROWSER_KEY:''}});exited=once(child,'exit');
  const until=Date.now()+20000;let r;
  while(Date.now()<until){try{r=await fetch(origin,{signal:AbortSignal.timeout(1000)});if(r.ok)break;}catch{}if(child.exitCode!==null)throw Error('Isolated test server exited during startup');await delay(50);}
  assert.ok(r?.ok,'Isolated test server startup');cookie=r.headers.get('set-cookie').split(';')[0];
  csrf=(await (await fetch(origin+'/dashboard/bootstrap',{headers:{Cookie:cookie}})).json()).csrf;
 }
 const headers=()=>({'Content-Type':'application/json',Cookie:cookie,Origin:origin,'X-Dashboard-CSRF':csrf});
 async function call(method,apiPath,body=null,extra={}){
  const r=await fetch(origin+'/dashboard/api',{method:'POST',headers:headers(),body:JSON.stringify({method,path:apiPath,body,...extra}),signal:AbortSignal.timeout(15000)});
  assert.ok(r.ok,`${method} ${apiPath} returned ${r.status}`);return (await r.json()).data;
 }
 async function buyerCode(handle){
  await call('POST','/api/confirm/@buyer/otp',{}, {buyer_handle:handle});
  const r=await fetch(origin+'/dashboard/buyer-otp?buyer_handle='+encodeURIComponent(handle),{headers:{Cookie:cookie,Origin:origin}});
  assert.ok(r.ok,'Protected local OTP preview');const result=await r.json();assert.equal(result.simulation,true);return result.code;
 }
 async function stop(){
  if(!child||child.exitCode!==null)return;
  try{await fetch(origin+'/dashboard/shutdown',{method:'POST',headers:headers(),body:JSON.stringify({confirm:'STOP LOCAL TOOL'}),signal:AbortSignal.timeout(5000)});let timer;try{await Promise.race([exited,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Isolated shutdown timed out')),10000);})]);}finally{clearTimeout(timer);}}
  finally{if(child.exitCode===null)child.kill();}
 }
 try{
  await start();
  const day=new Date(Date.now()+23400000).toISOString().slice(0,10);
  let order=await call('POST','/api/orders',{raw_text:'name: Fictional Restart Buyer, 09790000000, Hlaing, COD 25000',parcel:{item:'Synthetic restart shirt',delivery_day:day,hub_received:true}});
  const endpoint='/api/orders/'+order.id;
  order=await call('PATCH',endpoint+'/status',{expected_version:order.version,status:'NEEDS_REVIEW'});
  const link=await call('POST',endpoint+'/confirmation-link',{}),buyer={buyer_handle:link.buyer_handle};
  await call('POST','/api/confirm/@buyer/verify',{code:await buyerCode(buyer.buyer_handle)},buyer);
  await call('PATCH','/api/confirm/@buyer/location',{request_id:crypto.randomUUID(),latitude:'16.81',longitude:'96.11',initial_pin_acknowledged:true},buyer);
  const pending=(await call('GET',endpoint+'/buyer-requests')).items[0];order=await call('GET',endpoint);
  await call('PATCH',endpoint+'/buyer-requests/'+pending.id,{expected_version:order.version,decision:'APPROVE',reason:'Fictional test location; no real home or geospatial accuracy claim'});
  const rider=(await call('GET','/api/riders')).items[0];order=await call('GET',endpoint);
  const routeStart=new Date(),routeEnd=new Date(routeStart.getTime()+8*3600000);
  const preview=await call('POST','/api/routes/optimize',{origin:{latitude:16.8,longitude:96.1},orders:[{order_id:order.id,priority:5}],riders:[{rider_id:rider.id,capacity:3}],operating_window:{start:routeStart.toISOString(),end:routeEnd.toISOString()},allow_simulation:true,solver_seconds:1});
  assert.equal(preview.result.quality,'SIMULATED');assert.equal(preview.result.vehicles[0].capacity,3);assert.equal(preview.result.vehicles[0].load,1);
  const plan=await call('POST','/api/routes/plans/'+preview.id+'/commit',{expected_version:preview.version,acknowledge_unverified_location:true,allow_simulation:true});
  const route=(await call('GET','/api/routes')).items.find(r=>r.id===plan.routes[rider.id]);assert.ok(route);
  await call('POST','/api/routes/'+route.id+'/actions',{request_id:crypto.randomUUID(),expected_version:route.version,action:'DISPATCH'});
  const actor={actor:'rider',rider_id:rider.id},queue=await call('GET','/api/riders/'+rider.id+'/queue',null,actor);
  assert.equal(queue.items[0].coordinate_status,'BUYER_CONFIRMED');assert.ok(queue.items[0].navigation_ready);
  await call('PATCH','/api/riders/'+rider.id+'/deliveries/'+order.id+'/status',{request_id:crypto.randomUUID(),expected_version:queue.items[0].order_version,action:'DELIVERED',cod_collected:true,actual_amount:25000},actor);
  const before=await call('GET',endpoint+'/events');await stop();await start();
  const saved=await call('GET',endpoint),after=await call('GET',endpoint+'/events');
  assert.equal(saved.status,'DELIVERED');assert.equal(saved.confidence_level,'AMBER');assert.equal(Number(saved.latitude),16.81);assert.equal(saved.parsing_metadata.parcel.collection.actual,25000);assert.equal(after.total,before.total);
  const savedPlan=await call('GET','/api/routes/plans/'+plan.id);assert.equal(savedPlan.state,'COMMITTED');assert.equal(savedPlan.result.vehicles[0].stops[0].order_id,order.id);assert.equal(savedPlan.result.vehicles[0].stops[0].priority,5);assert.equal(savedPlan.stale,true);
  const denied=await fetch(origin+'/api/orders');assert.equal(denied.status,404);
  console.log(JSON.stringify({result:'PASS',database:'isolated temporary SQLite',process_restarts:1,orders_persisted:1,route_plans_persisted:1,ordered_stops_persisted:1,route_quality:'SIMULATED',external_routing_calls:0,status:saved.status,cod_collected:25000,events_persisted:after.total,confidence:saved.confidence_level,private_direct_reads:'rejected',external_ai_calls:0}));
 }finally{
  await stop();
  // Resolve and verify ownership before recursive cleanup, never a computed user DB path.
  assert.equal(fs.realpathSync(directory),owned);assert.equal(path.dirname(owned),fs.realpathSync(os.tmpdir()));assert.ok(path.basename(owned).startsWith('lannpya-mapping-restart-'));assert.equal(fs.readFileSync(marker,'utf8'),'synthetic restart fixture');fs.rmSync(owned,{recursive:true});
 }
}
main().catch(e=>{console.error('Mapping isolated restart verification failed:',e.message);process.exitCode=1;});
