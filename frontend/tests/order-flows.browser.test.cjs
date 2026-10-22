// Browser regression tests exercise the real UI, live-store adapter and local API
// bridge against an isolated in-memory implementation of the API contracts.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),day=()=>new Date(Date.now()+23400000).toISOString().slice(0,10);
const id='7f18e430-7a45-4cc0-b7ca-8d62bf391e23',handle='a'.repeat(43);
let browser,server,origin,state;
function order(){return {id,version:1,customer_name:'Synthetic Buyer',customer_phone:'09790000000',township:'Hlaing',street:'Test street',landmark:'Test gate',cod_amount:'25000',latitude:'16.82',longitude:'96.13',status:'NEEDS_REVIEW',confidence_level:'AMBER',confidence_reasons:[],ai_availability_status:'mock',field_sources:{},parsing_metadata:{parcel:{item:'Cotton shirt',sender:'Test shop',reference:'INV-22',delivery_day:day(),hub_received_at:'now'}}};}
function review(kind){return {id:kind.toLowerCase()+'-row',request_id:kind.toLowerCase()+'-request',kind,decision:'REVIEW_REQUIRED',resolution:null,created_at:new Date().toISOString(),submitted_values:kind==='LOCATION'?{latitude:'16.825',longitude:'96.135'}:{action:'AVAILABLE',instructions:'Call at the gate'}};}
const pending=()=>state.reviews.filter(r=>!r.resolution&&r.decision==='REVIEW_REQUIRED');
function api(q){
 const url=new URL(q.path,origin),p=url.pathname,b=q.body||{},o=state.orders[0];state.calls.push(q);
 if(p==='/api/session')return {id:'dispatcher',role:'Admin',name:'Dispatcher'};
 if(p==='/api/riders')return {items:state.riders,total:state.riders.length};
 const queueMatch=p.match(/^\/api\/riders\/([^/]+)\/queue$/);
 if(queueMatch)return {items:state.assignments.filter(a=>a.rider_id===queueMatch[1]&&a.status==='ACTIVE').map(a=>({...a,order_id:a.order_id,order_version:o.version,status:o.status,customer_name:o.customer_name,cod_amount:o.cod_amount,street:o.street,latitude:o.latitude,longitude:o.longitude,coordinate_status:'UNCONFIRMED'})),unchanged:false,total:state.assignments.length,cursor:null};
 if(p.endsWith('/assignments'))return {items:state.assignments,total:state.assignments.length,page:1,page_size:100};
 if(p==='/api/orders/parse')return {address:{customer_name:'Synthetic Buyer',phone_number:'09790000000',township:'Hlaing',street:'Test street',landmark:'Test gate',cod_amount:25000},confidence:'AMBER',validation_reasons:[],ai:{status:'mock',message:'Synthetic contract fixture'}};
 if(p==='/api/orders'&&q.method==='POST'){
  assert.ok(b.parcel.item?.trim(),'The order description must reach the API');
  const row={...order(),...b.structured,id:state.orders.length?id.replace('7f18e430','8f18e430'):id,original_message:b.raw_text||null,parsing_metadata:{parcel:{...b.parcel,hub_received_at:b.parcel.hub_received?'now':null}}};state.orders.push(row);return row;
 }
 if(p==='/api/orders')return {items:state.orders,total:state.orders.length};
 if(p==='/api/routes'&&q.method==='POST'){const r={id:'route',rider_id:b.rider_id,day:b.day,state:'draft',version:1,items:[]};state.routes.push(r);return r;}
 if(p==='/api/routes')return {items:state.routes,total:state.routes.length};
 if(p.endsWith('/events'))return {items:[],total:0};
 if(p.endsWith('/buyer-requests'))return {items:state.reviews,total:state.reviews.length};
 if(p.includes('/buyer-requests/')&&q.method==='PATCH'){
  const r=state.reviews.find(r=>p.endsWith('/'+r.id));assert.ok(r,'Review uses the stored row id');r.resolution=b.decision;o.version++;
  if(r.kind==='LOCATION'&&b.decision==='APPROVE'){o.latitude=r.submitted_values.latitude;o.longitude=r.submitted_values.longitude;}
  return {request_id:r.request_id,resolution:b.decision,order_version:o.version};
 }
 if(p.endsWith('/auto-assignment')){
  if(pending().length)throw Error('Resolve pending buyer requests before confirming dispatch.');
  const busy=new Set(state.assignments.filter(a=>a.status==='ACTIVE').map(a=>a.rider_id));
  const rider=state.riders.find(r=>r.operational_status==='AVAILABLE'&&!busy.has(r.id));
  if(!rider)return {order:o,allocation_status:'WAITING_FOR_RIDER',reason:'No free rider.',assignment:null,route:null};
  const route={id:`route-${state.routes.length+1}`,rider_id:rider.id,day:o.parsing_metadata.parcel.delivery_day,state:'draft',version:1,items:[{id:o.id,status:'ASSIGNED'}],recorded_total:0,blockers:[]};
  const assignment={id:`assignment-${state.assignments.length+1}`,order_id:o.id,rider_id:rider.id,status:'ACTIVE',response_status:'PENDING',offer_version:1,stop_sequence:1};
  state.routes.push(route);state.assignments.push(assignment);o.status='ASSIGNED';o.version++;o.parsing_metadata.parcel.route_id=route.id;
  return {order:o,allocation_status:'ASSIGNED',reason:'Offer pending rider acceptance.',assignment,route};
 }
 if(p==='/api/confirm/@buyer')return {state:'VERIFICATION_REQUIRED',order_reference:id,delivery_status:o.status,shop_display_name:'Test shop'};
 if(p.endsWith('/otp'))return {challenge_id:'challenge',destination_masked:'••••4567',expires_at:new Date(Date.now()+300000).toISOString(),resend_after:new Date(Date.now()+60000).toISOString(),mode:'DEMO'};
 if(p.endsWith('/verify')){if(b.code!=='123456')throw Error('Buyer verification failed.');return {};}
 const offerMatch=p.match(/^\/api\/riders\/([^/]+)\/deliveries\/([^/]+)\/status$/);
 if(offerMatch&&q.method==='PATCH'){
  const assignment=state.assignments.find(a=>a.order_id===offerMatch[2]&&a.rider_id===offerMatch[1]&&a.status==='ACTIVE');
  if(!assignment||assignment.offer_version!==b.offer_version)throw Error('Stale rider offer.');
  assignment.response_status=b.action==='ACCEPT'?'ACCEPTED':'DECLINED';assignment.offer_version++;
  if(b.action==='DECLINE'){
   assignment.status='UNASSIGNED';
   const allocated=api({path:`/api/orders/${o.id}/auto-assignment`,method:'POST',body:{},actor:'dispatcher'});
   return {...allocated,assignment_id:assignment.id,action:'DECLINE'};
  }
  return {assignment_id:assignment.id,order_id:o.id,rider_id:assignment.rider_id,status:o.status};
 }
 if(p.endsWith('/details'))return {order_reference:id,status:o.status,township:o.township,street:o.street,latitude:o.latitude,longitude:o.longitude,delivery_instructions:o.delivery_instructions,initial_pin_requires_review:true};
 if(p.endsWith('/location')){state.reviews.push({...review('LOCATION'),submitted_values:b});return {decision:'REVIEW_REQUIRED'};}
 if(p.endsWith('/response')){if(state.failResponse)throw Error('Synthetic availability save failure');state.reviews.push({...review('RESPONSE'),submitted_values:b});return {decision:'REVIEW_REQUIRED'};}
 if(p==='/api/orders/'+id)return o;
 throw Error('Unexpected API fixture call: '+q.method+' '+p);
}
before(async()=>{
 server=http.createServer(async(req,res)=>{
  const p=new URL(req.url,'http://localhost').pathname;res.setHeader('Cache-Control','no-store');
  if(p==='/dashboard/bootstrap'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({test_mode:true,csrf:'synthetic-csrf'}));}
  if(p==='/dashboard/buyer-otp'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({simulation:true,code:'123456',notice:'SIMULATION ONLY'}));}
  if(p==='/dashboard/api'){let raw='';for await(const part of req)raw+=part;res.setHeader('Content-Type','application/json');try{return res.end(JSON.stringify({data:api(JSON.parse(raw))}));}catch(e){res.statusCode=503;return res.end(JSON.stringify({error:{code:'SYNTHETIC_FAILURE',message:e.message}}));}}
  if(p==='/runtime-config.js'){res.setHeader('Content-Type','text/javascript');return res.end('globalThis.LANNPYA_RUNTIME={mode:"LIVE_BACKEND"};');}
  const f=path.resolve(root,'.'+(p==='/'?'/index.html':p));if(!f.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
  try{res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.svg':'image/svg+xml'})[path.extname(f)]||'application/octet-stream');res.end(fs.readFileSync(f));}catch{res.writeHead(404);res.end();}
 });await new Promise(r=>server.listen(0,'127.0.0.1',r));origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({headless:true,...(process.env.LANNPYA_BROWSER_CHANNEL?{channel:process.env.LANNPYA_BROWSER_CHANNEL}:{})});
});
after(async()=>{await browser?.close();await new Promise(r=>server?.close(r));});
async function pageFor(t,{orders=[order()],reviews=[],width=1440}={}){
 state={orders,routes:[],reviews,calls:[],riders:[{id:'rider',name:'Ko Aung',operational_status:'AVAILABLE'},{id:'rider-2',name:'Mya Mya',operational_status:'AVAILABLE'}],assignments:[]};const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:'reduce',serviceWorkers:'block'}),page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('https://**/*',r=>r.abort());
 t.after(async()=>{try{assert.deepEqual(errors,[]);}finally{await context.close();}});return page;
}
const goto=async(page,route)=>page.goto(origin+'/#/'+route,{waitUntil:'domcontentloaded'});
async function shot(page,name){if(process.env.LANNPYA_QA_DIR){fs.mkdirSync(process.env.LANNPYA_QA_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.LANNPYA_QA_DIR,name+'.png'),fullPage:true,animations:'disabled'});}}

test('live import retains description and delivery day through parsing and imports them',async t=>{
 const page=await pageFor(t,{orders:[]});await goto(page,'new');await page.locator('#live-parcel-item').fill('Cotton shirt · navy, size M');await page.locator('#live-parcel-day').fill(day());
 await page.locator('#batch-raw').fill('Name: Synthetic Buyer\nPhone: 09790000000\nTownship: Hlaing\nCOD: 25000');await page.locator('[data-action=parse]').click();await page.locator('[data-choice]').waitFor();
 assert.equal(await page.locator('#live-parcel-item').inputValue(),'Cotton shirt · navy, size M');assert.equal(await page.locator('#live-parcel-day').inputValue(),day());
 assert.equal(await page.locator('.record-controls [data-action=edit-row]').count(),1);await shot(page,'paste-desktop');
 await page.locator('[data-action=close-pop]').last().click();assert.equal(await page.locator('#live-parcel-item').inputValue(),'Cotton shirt · navy, size M');await page.locator('[data-action=open-pop]').click();
 await page.locator('[data-action=commit-batch]').click();await page.waitForURL('**/#/dispatch');assert.equal(state.orders[0].parsing_metadata.parcel.item,'Cotton shirt · navy, size M');assert.equal(state.orders[0].parsing_metadata.parcel.delivery_day,day());
});

test('live buyer success replaces submit only after both writes succeed, with a full-row order id',async t=>{
 const page=await pageFor(t,{width:390});await goto(page,'track/'+handle);await page.locator('[data-action=request-otp]').click();await page.locator('#verify-form').waitFor();await page.locator('[name=digits]').fill('123456');await page.locator('#verify-form button').click();await page.locator('#customer-form').waitFor();
 await page.locator('[name=latitude]').fill('16.825');await page.locator('[name=longitude]').fill('96.135');await page.locator('[name=initial_pin_acknowledged]').check();await page.locator('[name=note]').fill('Call at the gate');
 const styles=await page.locator('[name=answer]').evaluate(n=>({appearance:getComputedStyle(n).appearance,height:n.getBoundingClientRect().height}));assert.equal(styles.appearance,'none');assert.ok(styles.height>=48);
 await page.locator('#customer-form .customer-primary').click();await page.locator('.delivery-request-confirmed').waitFor();assert.equal(await page.locator('#customer-form .customer-primary').count(),0);
 const cdp=await page.context().newCDPSession(page),tree=await cdp.send('Accessibility.getFullAXTree');await cdp.detach();
 assert.ok(tree.nodes.some(n=>!n.ignored&&n.name?.value==='Availability'),'Saved request fields must remain readable to assistive technology');
 assert.equal(pending().length,2);assert.equal(await page.locator('.buyer-order-reference').innerText(),`Order\n${id}`);
 assert.ok(await page.locator('.buyer-order-reference').evaluate(n=>n.getBoundingClientRect().width>=n.parentElement.getBoundingClientRect().width-2));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await shot(page,'buyer-confirmed-mobile');
 await page.locator('[data-action=edit-customer]').click();assert.equal(await page.locator('#customer-form [name=note]').inputValue(),'Call at the gate');assert.equal(await page.locator('#customer-form [name=latitude]').inputValue(),'16.825');
});

test('failed buyer response keeps the draft and never shows confirmation',async t=>{
 const page=await pageFor(t);state.failResponse=true;await goto(page,'track/'+handle);await page.locator('[data-action=request-otp]').click();await page.locator('#verify-form').waitFor();await page.locator('[name=digits]').fill('123456');await page.locator('#verify-form button').click();await page.locator('#customer-form').waitFor();
 await page.locator('[name=initial_pin_acknowledged]').check();await page.locator('[name=note]').fill('Keep this draft');await page.locator('#customer-form .customer-primary').click();await page.locator('.form-error').filter({hasText:'availability was not saved'}).waitFor();
 assert.equal(await page.locator('.delivery-request-confirmed').count(),0);assert.equal(await page.locator('[name=note]').inputValue(),'Keep this draft');
});

test('created order closes back to its form and can return to the board',async t=>{
 const page=await pageFor(t,{orders:[]});await goto(page,'manual');const form=page.locator('#manual-form');
 for(const[k,v]of Object.entries({name:'Synthetic Buyer',phone:'09790000000',item:'Envelope',expected:'25000'}))await form.locator(`[name=${k}]`).fill(v);
 await form.locator('aside button').click();await page.locator('.created-dialog').waitFor();
 assert.ok(await page.locator('[data-created=close]').evaluate(n=>{const b=n.getBoundingClientRect(),d=n.closest('dialog').getBoundingClientRect();return b.left>d.left+d.width/2&&b.top<d.top+60;}));
 await shot(page,'order-created');await page.locator('[data-created=close]').click();assert.equal(await page.locator('dialog').count(),0);assert.equal(state.orders.length,1);assert.ok(page.url().endsWith('#/manual'));
 await form.locator('[name=name]').fill('Second buyer');await form.locator('[name=phone]').fill('09790000001');await form.locator('[name=item]').fill('Second envelope');await form.locator('[name=expected]').fill('1000');
 await form.locator('aside button').click();await page.locator('[data-created=board]').click();await page.waitForURL('**/#/dispatch');assert.equal(state.orders.length,2);
});

test('reviewing location and availability separately clears the assignment blocker',async t=>{
 const page=await pageFor(t,{reviews:[review('LOCATION'),review('RESPONSE')]});await goto(page,'order/'+id);
 await page.locator('#buyer-request-reviews').waitFor();assert.equal(await page.locator('#buyer-request-reviews [data-review-request]').count(),2);assert.equal(await page.locator('[data-action=assign]').isDisabled(),true);await shot(page,'buyer-reviews');
 for(const request of ['location-request','response-request']){
  await page.locator(`[data-review-request="${request}"]`).click();await page.locator('dialog [name=reason]').fill('Checked this request with the buyer');await page.locator('dialog button[type=submit]').click();await page.locator('dialog').waitFor({state:'detached'});
  if(request==='location-request')assert.equal(await page.locator('[data-action=assign]').isDisabled(),true);
 }
 assert.equal(pending().length,0);assert.equal(await page.locator('[data-action=assign]').isDisabled(),false);await page.locator('[data-action=assign]').click();await page.locator('dialog [name=acknowledge]').check();await page.locator('dialog button[type=submit]').click();await page.locator('dialog').waitFor({state:'detached'});
 assert.equal(state.orders[0].status,'ASSIGNED');assert.equal(state.calls.filter(c=>c.path.endsWith('/auto-assignment')).length,1);
});

test('buyer requests arriving on an open order reveal reviews before assignment',async t=>{
 const page=await pageFor(t);await goto(page,'order/'+id);await page.locator('[data-action=assign]').waitFor();
 state.reviews.push(review('LOCATION'),review('RESPONSE'));
 await page.locator('[data-action=assign]').click();await page.locator('#buyer-request-reviews').waitFor({timeout:2500});
 assert.equal(await page.locator('#buyer-request-reviews [data-review-request]').count(),2);assert.equal(await page.locator('dialog').count(),0);
 assert.equal(state.calls.filter(c=>c.path==='/api/routes'&&c.method==='POST').length,0);
});
