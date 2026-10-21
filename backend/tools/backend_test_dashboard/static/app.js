const $ = id => document.getElementById(id);
const state = {csrf:'', boot:null, order:null, riders:[], buyers:[], page:1, total:0, cursor:null, polling:false, busy:false};
const examples = {
  unicode:'၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ စမ်းသပ်လမ်း၊ COD ၂၅၀၀၀။ သရုပ်ပြအတုသာ။',
  myanglish:'09790000000, Kamayut township, Demo Street, prepaid. Fictional test only.',
  red:'မြို့နယ်မသိ၊ ဖုန်းမပါ။ အိမ်အနီးတစ်နေရာ၊ သရုပ်ပြအတုသာ။'
};
function textNode(tag, text, className='') { const n=document.createElement(tag); n.textContent=String(text); if(className)n.className=className; return n; }
function result(data, status='', failed=false) { $('output').textContent=JSON.stringify(data,null,2); $('result-status').textContent=status; $('result-status').classList.toggle('error',failed); }
function activity(row) {
  const tr=document.createElement('tr');
  // Never log bodies, query values, buyer handles, notes or error messages.
  [new Date().toLocaleTimeString(), row.method, row.endpoint, row.status, row.duration_ms??'—', row.ok?'Success':'Rejected / failed'].forEach(x=>tr.append(textNode('td',x)));
  $('timeline').prepend(tr); while($('timeline').children.length>100)$('timeline').lastElementChild.remove();
}
async function local(path, body) {
  const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',redirect:'error',headers:body===undefined?{}:{'Content-Type':'application/json','X-Dashboard-CSRF':state.csrf},body:body===undefined?undefined:JSON.stringify(body)});
  let data; try {data=await response.json();} catch {throw new Error(`Local server returned a non-JSON response (${response.status}). No success recorded.`);}
  return {response,data};
}
async function api(method,path,body=null,options={}) {
  const {response,data}=await local('/dashboard/api',{method,path,body,actor:options.actor??'dispatcher',rider_id:options.rider_id??null,buyer_handle:state.buyers.find(x=>x.handle===$('buyer-select').value)?.handle??null});
  if(data.endpoint)activity(data); else activity({method,endpoint:'(dashboard proxy rejection)',status:response.status,ok:false});
  if(!options.quiet || !response.ok)result(data.data??data,`${method} ${data.endpoint??path.split('?')[0]} · HTTP ${response.status}${data.duration_ms!==undefined?' · '+data.duration_ms+' ms':''}`,!response.ok);
  if(!response.ok) { const e=new Error('Backend request rejected. Inspect the response and refresh stale data before retrying.'); e.displayed=true; e.status=response.status; throw e; }
  return data.data;
}
function tab(name) { document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name)); document.querySelectorAll('section.panel').forEach(p=>p.hidden=p.id!==name); }
function selectedId() {const id=$('order-id').value.trim(); if(!/^[0-9a-f-]{36}$/i.test(id))throw new Error('Create or select an order first.'); return id;}
async function refreshOrder() {const row=await api('GET',`/api/orders/${selectedId()}`,null,{quiet:true}); selectOrder(row); return row;}
function selectOrder(row) {
  state.order=row; $('order-id').value=row.id;
  $('selected-summary').replaceChildren(textNode('strong',row.status),textNode('p',`${row.confidence_level} · version ${row.version}`),textNode('p',row.township??'Township unknown'));
  $('next-status').replaceChildren(...(state.boot.transitions[row.status]??[]).map(value=>new Option(value,value)));
}
async function listOrders() {
  const query=new URLSearchParams({page:state.page,page_size:10});
  for(const [field,id] of [['status','filter-status'],['confidence','filter-confidence'],['q','search']])if($(id).value)query.set(field,$(id).value);
  const page=await api('GET','/api/orders?'+query,null,{quiet:true}); state.total=page.total;
  $('page-label').textContent=`Page ${state.page} · ${page.total} orders`; $('order-list').replaceChildren();
  for(const row of page.items) {
    const tr=document.createElement('tr'); const cell=document.createElement('td'); const b=textNode('button',row.id.slice(0,8)); b.title=row.id; b.addEventListener('click',()=>{selectOrder(row);result(row,'Saved test order');}); cell.append(b);tr.append(cell);
    [row.township??'—',row.confidence_level,row.status,row.cod_amount??'unknown'].forEach(v=>tr.append(textNode('td',v)));$('order-list').append(tr);
  }
  if(!page.items.length){ const tr=document.createElement('tr');const td=textNode('td','No saved test orders on this page.');td.colSpan=5;tr.append(td);$('order-list').append(tr); }
}
async function riders() {
  const data=await api('GET','/api/riders?page_size=100',null,{quiet:true}); state.riders=data.items;
  for(const id of ['assign-rider','active-rider']) {const previous=$(id).value; $(id).replaceChildren(...data.items.map(r=>new Option(`${r.name} · ${r.operational_status}`,r.id)));if(data.items.some(r=>r.id===previous))$(id).value=previous;}
}
function currentRider() {const r=state.riders.find(r=>r.id===$('active-rider').value);if(!r)throw new Error('Create or select a rider first.');return r;}
async function queue(quiet=false) {
  const rider=currentRider();const params=state.cursor?'?cursor='+state.cursor:'';
  const data=await api('GET',`/api/riders/${rider.id}/queue${params}`,null,{actor:'rider',rider_id:rider.id,quiet});state.cursor=data.cursor;
  if(data.unchanged)return; $('queue-list').replaceChildren();
  for(const item of data.items){const card=textNode('div','','card');card.append(textNode('strong',`${item.status} · ${item.township??'Unknown township'}`),textNode('p',`Pin: ${item.coordinate_status} · Confidence: ${item.confidence_level}`),textNode('p',`Window: ${item.delivery_time_window??'not selected'} · COD ${item.cod_amount??'unknown'}`),textNode('p',item.delivery_instructions??'No instructions'),textNode('code',item.order_id));const b=textNode('button','Select delivery');b.addEventListener('click',()=>guard(async()=>{$('order-id').value=item.order_id;await refreshOrder();}));card.append(b);if(item.navigation_ready)card.append(textNode('p',`Navigation available; inspect navigation_url in JSON. No automatic external navigation.`));$('queue-list').append(card);}
  if(!data.items.length)$('queue-list').append(textNode('p','No active deliveries.'));
}
function requireBuyer(){if(!$('buyer-select').value)throw new Error('Generate or select a buyer link first.');}
function buyer(method,suffix='',body=null){requireBuyer();return api(method,'/api/confirm/@buyer'+suffix,body);}
async function history() {
  const id=selectedId(); const data=await api('GET',`/api/orders/${id}/buyer-requests?page_size=100`);$('review-list').replaceChildren();
  for(const request of data.items){const card=textNode('div','','card');card.append(textNode('strong',`${request.kind} · ${request.resolution??request.decision}`),textNode('p',request.reason_codes.join(', ')),textNode('pre',JSON.stringify(request.submitted_values,null,2)));
    if(request.decision==='REVIEW_REQUIRED'&&!request.resolution)for(const decision of ['APPROVE','REJECT']){const b=textNode('button',decision);b.addEventListener('click',()=>guard(async()=>{const row=await refreshOrder();await api('PATCH',`/api/orders/${id}/buyer-requests/${request.id}`,{expected_version:row.version,decision,reason:$('review-reason').value});await refreshOrder();await history();}));card.append(b);}
    $('review-list').append(card);
  }if(!data.items.length)$('review-list').append(textNode('p','No buyer requests.'));
}
async function delivery(action) {
  const row=await refreshOrder(), rider=currentRider();const body={expected_version:row.version,request_id:crypto.randomUUID(),action};
  if(action==='DELIVERED')body.cod_collected=$('cod-collected').checked;
  if(action==='FAILED')body.failure_reason=$('failure-reason').value;
  await api('PATCH',`/api/riders/${rider.id}/deliveries/${row.id}/status`,body,{actor:'rider',rider_id:rider.id});await refreshOrder();state.cursor=null;await queue(true);
}
async function guard(fn) {if(state.busy)return;state.busy=true;try{await fn();}catch(error){if(!error.displayed)result({error:{message:error.message}},'Operation failed · no simulated fallback',true);}finally{state.busy=false;}}
const on=(id,fn)=>$(id).addEventListener('click',()=>guard(fn));
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
$('example').addEventListener('change',()=>$('raw-text').value=examples[$('example').value]);$('raw-text').value=examples.unicode;
on('health',async()=>{await api('GET','/health');$('connection').textContent='Backend connected · isolated SQLite';});
on('parse',async()=>api('POST','/api/orders/parse',{raw_text:$('raw-text').value}));
on('create-order',async()=>{const row=await api('POST','/api/orders',{merchant_id:state.boot.merchant_id,raw_text:$('raw-text').value});selectOrder(row);await listOrders();tab('orders');});
on('load-order',async()=>{const row=await refreshOrder();result(row,'Saved order loaded');});
on('list-orders',async()=>{state.page=1;await listOrders();});on('prev-page',async()=>{if(state.page>1){state.page--;await listOrders();}});on('next-page',async()=>{if(state.page*10<state.total){state.page++;await listOrders();}});
on('correct',async()=>{const fields=JSON.parse($('correction').value);const row=await refreshOrder();selectOrder(await api('PATCH',`/api/orders/${row.id}`,{...fields,expected_version:row.version}));await listOrders();});
on('change-status',async()=>{const target=$('next-status').value;if(!target)throw new Error('No lifecycle transition is available for this order.');const row=await refreshOrder();selectOrder(await api('PATCH',`/api/orders/${row.id}/status`,{status:target,expected_version:row.version,acknowledge_unverified_location:$('ack-location').checked}));await listOrders();});
on('events',async()=>api('GET',`/api/orders/${selectedId()}/events?page_size=100`));
on('generate-link',async()=>{const data=await api('POST',`/api/orders/${selectedId()}/confirmation-link`);const label=`Test link ${state.buyers.length+1} · expires ${data.expires_at}`;state.buyers.push({handle:data.buyer_handle});if(state.buyers.length===1)$('buyer-select').replaceChildren();$('buyer-select').append(new Option(label,data.buyer_handle));$('buyer-select').value=data.buyer_handle;});
on('revoke-link',async()=>api('POST',`/api/orders/${selectedId()}/confirmation-link/revoke`));
on('buyer-card',async()=>buyer('GET'));on('buyer-details',async()=>buyer('GET','/details'));on('verify',async()=>buyer('POST','/verify',{last_four:$('last-four').value}));
on('submit-pin',async()=>buyer('PATCH','/location',{request_id:crypto.randomUUID(),latitude:$('latitude').value,longitude:$('longitude').value,initial_pin_acknowledged:$('initial-pin').checked}));
for(const [id,action] of [['available','AVAILABLE'],['instructions','INSTRUCTIONS'],['security','LEAVE_WITH_SECURITY']])on(id,async()=>buyer('PATCH','/response',{request_id:crypto.randomUUID(),action,...($('buyer-instructions').value?{instructions:$('buyer-instructions').value}:{})}));
const tomorrow=new Date();tomorrow.setUTCDate(tomorrow.getUTCDate()+1);tomorrow.setUTCHours(4,0,0,0);$('window-start').value=tomorrow.toISOString();$('window-end').value=new Date(+tomorrow+3600000).toISOString();
on('reschedule',async()=>buyer('PATCH','/response',{request_id:crypto.randomUUID(),action:'RESCHEDULE',time_window:{start:$('window-start').value,end:$('window-end').value}}));
for(const [id,kind] of [['expire-link','LINK'],['expire-session','SESSION']])on(id,async()=>{requireBuyer();const {response,data}=await local('/dashboard/expire',{buyer_handle:$('buyer-select').value,kind});result(data,'Fixture timestamp change · HTTP '+response.status,!response.ok);});
on('lock-link',async()=>{requireBuyer();let locked=false;
  const guess=$('wrong-four').value;if(!/^\d{4}$/.test(guess))throw new Error('Enter four deliberately incorrect numeric digits.');
  for(let i=0;i<3;i++){try{await buyer('POST','/verify',{last_four:guess});throw new Error('Those digits verified successfully. Stop: use deliberately incorrect digits.');}catch(e){if(e.status===423){locked=true;break;}if(![401,403].includes(e.status))throw e;}}
  const card=await buyer('GET');locked=card.state==='LOCKED';
  $('lock-note').textContent=locked?'Public card reports LOCKED. Further verification is rejected with 423.':'Attempts submitted. Inspect the actual API state; no lockout was fabricated.';
});
on('buyer-history',history);
on('list-riders',riders);on('create-rider',async()=>{await api('POST','/api/riders',{name:$('rider-name').value,operational_status:'AVAILABLE'});await riders();});
on('assign',async()=>{const row=await refreshOrder();const sequence=$('stop-sequence').value;await api('POST',`/api/orders/${row.id}/assign`,{expected_version:row.version,rider_id:$('assign-rider').value,...(sequence?{stop_sequence:Number(sequence)}:{})});await refreshOrder();state.cursor=null;});
on('unassign',async()=>{const row=await refreshOrder();await api('POST',`/api/orders/${row.id}/unassign`,{expected_version:row.version});await refreshOrder();state.cursor=null;});on('assignment-history',async()=>api('GET',`/api/orders/${selectedId()}/assignments`));
on('update-rider',async()=>{await riders();const rider=currentRider();await api('PATCH',`/api/riders/${rider.id}`,{expected_version:rider.version,operational_status:$('rider-availability').value});await riders();state.cursor=null;});
$('active-rider').addEventListener('change',()=>{state.cursor=null;$('queue-list').replaceChildren();});on('queue',async()=>queue());
setInterval(()=>{if($('poll-queue').checked&&!state.busy&&!document.hidden)guard(async()=>queue(true));},5000);
on('start-delivery',async()=>delivery('START'));on('deliver',async()=>delivery('DELIVERED'));on('fail-delivery',async()=>delivery('FAILED'));
on('console-send',async()=>api($('console-method').value,$('console-path').value,$('console-body').value.trim()?JSON.parse($('console-body').value):null));
on('clear-output',async()=>result({},'Response cleared'));on('clear-timeline',async()=>$('timeline').replaceChildren());
on('reset',async()=>{const {response,data}=await local('/dashboard/reset',{confirm:$('reset-text').value});if(!response.ok){result(data,'Reset rejected',true);return;}state.boot=data;state.order=null;state.buyers=[];state.cursor=null;state.page=1;$('poll-queue').checked=false;$('order-id').value='';$('buyer-select').replaceChildren(new Option('Generate a link first',''));$('selected-summary').textContent='Sandbox reset. Create a new test order.';$('next-status').replaceChildren();$('review-list').replaceChildren();$('queue-list').replaceChildren();$('timeline').replaceChildren();$('reset-text').value='';result({test_mode:true,reset:true},'New isolated sandbox initialized');await riders();await listOrders();});
on('shutdown',async()=>{const {response,data}=await local('/dashboard/shutdown',{confirm:'STOP LOCAL TOOL'});result(data,'Local tool shutdown ? HTTP '+response.status,!response.ok);if(response.ok){$('poll-queue').checked=false;$('connection').textContent='Stopped ? temporary data cleaned on shutdown';}});
await guard(async()=>{const {response,data}=await local('/dashboard/bootstrap');if(!response.ok)throw new Error('Session startup failed. Reload this local page.');state.csrf=data.csrf;state.boot=data;state.buyers=data.buyers??[];if(state.buyers.length){$('buyer-select').replaceChildren(...state.buyers.map((b,i)=>new Option('Test link '+(i+1)+' - expires '+b.expires_at,b.handle)));const wanted=new URLSearchParams(location.hash.slice(1)).get('buyer');if(state.buyers.some(b=>b.handle===wanted)){$('buyer-select').value=wanted;tab('buyer');}}Object.keys(data.transitions).forEach(x=>$('filter-status').append(new Option(x,x)));await api('GET','/health',null,{quiet:true});$('connection').textContent='Backend connected · isolated SQLite';await riders();await listOrders();result({test_mode:data.test_mode,ai:data.ai,database:data.database},'Ready · real backend, fictional data');});
