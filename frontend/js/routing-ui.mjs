// Planning views only. Business rules, authorization and all assignments remain server-owned.
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localTime=ms=>new Date(ms+23400000).toISOString().slice(0,16);
const when=t=>new Date(t).toLocaleString('en-GB',{timeZone:'Asia/Yangon'});
const duration=n=>`${Math.ceil(n/60)} min`;
const report=(node,error)=>{node.textContent=`${error.code||'CONNECTION_ERROR'}: ${error.message}. No simulated success was substituted.`;};
export function planningRequest(form,snapshot){
  for(const [name,limit]of [['latitude',90],['longitude',180]]){
    const value=String(form.get(name)??'');if(!value.trim()||!Number.isFinite(Number(value))||Math.abs(Number(value))>limit)throw Error('Select or enter a valid hub '+name+'. No default origin is assumed.');
  }
  const orders=snapshot.orders.filter(o=>form.has('order-'+o.id)).map(o=>{const priority=Number(form.get('priority-'+o.id)||0);if(!Number.isInteger(priority)||priority<0||priority>5)throw Error('Delivery priority must be an integer from 0 to 5.');return {order_id:o.id,demand:1,service_seconds:Number(form.get('service_seconds')),...(priority?{priority}:{})};});
  const riders=snapshot.riders.filter(r=>form.has('rider-'+r.id)).map(r=>({rider_id:r.id,capacity:Number(form.get('capacity-'+r.id))}));
  return {origin:{latitude:Number(form.get('latitude')),longitude:Number(form.get('longitude'))},
    orders,riders,operating_window:{start:form.get('start')+':00+06:30',end:form.get('end')+':00+06:30'},
    mode:form.get('mode'),allow_simulation:form.has('allow_simulation'),return_to_hub:form.has('return_to_hub'),
    objective:form.get('objective'),solver_seconds:Number(form.get('solver_seconds'))};
}
function resultHTML(plan){
  const r=plan.result;
  return `<h3>Plan ${esc(plan.id)}</h3><p class="live-notice">${esc(r.quality)} | ${esc(r.provider)} | ${esc(plan.state)}${plan.stale?' | STALE: recalculate before applying':''}</p><p>${esc(r.solver)}: ${esc(r.solver_status)}; ${r.elapsed_ms} ms; ${r.matrix_size} matrix locations. Bounded heuristic, no global optimality guarantee. Static planned times, no live traffic.</p><p>${esc(r.attribution)}</p>${r.vehicles.map(v=>`<section class="plan-vehicle"><h4>Rider ${esc(v.rider_id)}</h4><p>Capacity use: ${v.load??v.stops.reduce((n,s)=>n+s.demand,0)} / ${v.capacity??"capacity not recorded"} parcels.</p><p>${(v.distance_meters/1000).toFixed(2)} km; ${duration(v.duration_seconds)} including service/wait; travel ${duration(v.travel_seconds)}.</p><ol>${v.stops.map(s=>`<li><b>Stop ${s.sequence}</b> | ${esc(s.order_id)}<br>Planned arrival ${esc(when(s.arrival))}; leave ${esc(when(s.departure))}<br>Priority ${Number(s.priority)||0}; window: ${s.delivery_window?esc(when(s.delivery_window.start))+" ? "+esc(when(s.delivery_window.end)):"Any time within operating period"}</li>`).join('')}</ol>${v.geometry?`<div class="live-map" data-plan-map="${esc(v.rider_id)}" aria-label="Planned route geometry"></div>`:''}${v.geometry_warning?`<p>${esc(v.geometry_warning)}</p>`:''}</section>`).join('')}<h4>Excluded / unassigned (${r.unassigned.length})</h4><ul>${r.unassigned.map(o=>`<li>${esc(o.order_id)}: ${esc(o.reason)}</li>`).join('')}</ul><details><summary>Routing warnings</summary><ul>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></details>`;
}
function maps(root,plan){
  for(const v of plan.result.vehicles){
    const node=root.querySelector(`[data-plan-map="${v.rider_id}"]`);
    if(node&&v.geometry)globalThis.LannPyaCustomerMap?.routeView(node,v.geometry,plan.result.provider,v.stops);
  }
}
export async function mountPlanner({container,store,afterCommit}){
  const status=await store.routingStatus();if(!container.isConnected)return;
  const snapshot=store.snapshot(),prior=snapshot.plans[0],origin=prior?.origin;
  const orders=snapshot.orders.filter(o=>!['delivered','cancelled','returned','return_pending'].includes(o.state));
  container.innerHTML=`<h2>Road routing and dispatch planning</h2><p id="routing-provider">Provider: ${esc(status.provider)}. ${status.provider==='offline'?'SIMULATED / TEST DATA; invented graph, not Yangon road measurements.':status.external_requests_enabled?'External provider enabled by server configuration.':'External requests disabled; no automatic offline fallback.'}</p><form id="routing-plan-form"><fieldset><legend>Courier origin and operating period (Yangon time)</legend><div class="form-grid"><label>Hub latitude<input name="latitude" type="number" min="-90" max="90" step="any" required value="${esc(origin?.latitude??'')}"></label><label>Hub longitude<input name="longitude" type="number" min="-180" max="180" step="any" required value="${esc(origin?.longitude??'')}"></label><label>Start<input name="start" type="datetime-local" required value="${localTime(Date.now())}"></label><label>End<input name="end" type="datetime-local" required value="${localTime(Date.now()+8*3600000)}"></label></div><p>Enter the real courier origin yourself. No hub location is invented. Map clicks change only this planning origin.</p><div class="live-map" data-pin-map data-pin-note="Planning origin only; previewing does not modify deliveries." aria-label="Select routing origin"></div><button type="button" class="btn sm" data-load-tiles>Load street tiles (OpenStreetMap)</button><p data-pin-status>No origin selected.</p></fieldset><fieldset><legend>Available riders and parcel capacities</legend>${snapshot.riders.map(r=>`<label class="inline-check"><input type="checkbox" name="rider-${esc(r.id)}" ${r.operational_status==='AVAILABLE'?'checked':'disabled'}>${esc(r.name)} (${esc(r.operational_status)})</label><label>Parcel capacity for ${esc(r.name)}<input name="capacity-${esc(r.id)}" type="number" min="1" max="200" required value="20"></label>`).join('')||'<p>Create a rider in the developer API workspace first.</p>'}</fieldset><fieldset><legend>Orders (maximum ${status.max_stops})</legend><p>Existing active rider assignments are fixed. Include every active stop for each selected rider. Missing pins/review problems will be reported as excluded.</p>${orders.map(o=>`<label class="inline-check"><input type="checkbox" name="order-${esc(o.id)}" ${o.pin&&o.received?'checked':''}>${esc(o.name||o.id)} | ${esc(o.id)} | ${esc(o.date)} | ${o.pin?'Stored pin, accuracy unverified':'Missing pin'} | ${esc(o.time)}</label><label>Priority for ${esc(o.name||o.id)} (0 normal, 5 urgent)<input name="priority-${esc(o.id)}" type="number" min="0" max="5" step="1" value="0"></label>`).join('')||'<p>No eligible orders. Create and review delivery orders first.</p>'}</fieldset><div class="form-grid"><label>Service seconds per stop<input name="service_seconds" type="number" min="0" max="3600" value="180" required></label><label>Solver budget (seconds)<input name="solver_seconds" type="number" min="1" max="10" value="2" required></label><label>Travel mode<select name="mode"><option value="DRIVE">Driving</option>${status.two_wheeler_enabled?'<option value="TWO_WHEELER">Two-wheeler (Google coverage, not locally verified)</option>':''}</select></label><label>Cost objective<select name="objective"><option value="duration">Travel time</option><option value="distance">Road distance</option></select></label></div><label class="inline-check"><input name="return_to_hub" type="checkbox" checked> Return to hub within operating period</label><label class="inline-check"><input name="allow_simulation" type="checkbox" ${status.provider==='offline'?'required':''}> I explicitly authorize SIMULATED test routing, not real road/traffic estimates</label><button class="btn primary" type="submit">Optimize preview (no assignments)</button><p id="routing-error" role="alert"></p></form><section id="routing-preview" aria-live="polite"></section><section><h3>Saved plans</h3>${snapshot.plans.map(p=>`<p><button type="button" class="btn sm" data-open-plan="${esc(p.id)}">Open ${esc(p.id)}</button> ${esc(p.state)}${p.stale?' | STALE':''}</p>`).join('')||'<p>No saved plans yet.</p>'}</section>`;
  globalThis.LannPyaCustomerMap?.mount();
  const form=container.querySelector('#routing-plan-form'),error=container.querySelector('#routing-error'),view=container.querySelector('#routing-preview');
  let pending=false,displayed=null;
  function renderPlan(plan){
    displayed=plan;view.innerHTML=resultHTML(plan)+`<p>Previewing never assigns parcels. Changes to orders, riders or their queues invalidate this plan.</p>${plan.state==='PREVIEW'&&!plan.stale&&plan.result.vehicles.length?'<form id="commit-routing-plan"><label class="inline-check"><input type="checkbox" name="ack" required> I reviewed delivery pins and acknowledge unverified geospatial accuracy.</label><label class="inline-check"><input type="checkbox" name="simulation" '+(plan.result.quality==='SIMULATED'?'required':'')+'> I acknowledge that synthetic routing is TEST DATA.</label><button type="submit" class="btn primary">Commit assignments and stop order</button><p role="alert"></p></form>':''}<button type="button" class="btn" id="replan-routing">Recalculate from current records</button>`;maps(view,plan);
    const commit=view.querySelector('#commit-routing-plan');if(commit)commit.onsubmit=async e=>{e.preventDefault();if(pending)return;pending=true;const button=commit.querySelector('button');button.disabled=true;try{const d=new FormData(commit);await store.commitPlan(plan,{acknowledge_unverified_location:d.has('ack'),allow_simulation:d.has('simulation')});await afterCommit();}catch(err){report(commit.querySelector('[role=alert]'),err);}finally{pending=false;button.disabled=false;}};
    view.querySelector('#replan-routing').onclick=()=>{view.innerHTML='<p>Recalculating requires a new preview. Review the selected current orders/riders above, then Optimize preview. Completed/failed/cancelled stops are excluded; existing assignments remain fixed.</p>';displayed=null;form.scrollIntoView({block:'start'});};
  }
  form.oninput=()=>{if(displayed?.state==='PREVIEW'){displayed=null;view.innerHTML='<p>Inputs changed. Create a new preview before committing.</p>';}};
  form.onsubmit=async e=>{
    e.preventDefault();if(pending)return;pending=true;error.textContent='';displayed=null;view.innerHTML='<p>Calculating a new preview; assignments remain unchanged.</p>';const button=form.querySelector('[type=submit]');button.disabled=true;
    try{const request=planningRequest(new FormData(form),snapshot);const plan=await store.previewPlan(request);if(container.isConnected)renderPlan(plan);}
    catch(err){view.innerHTML='<p>No new preview was produced. Saved plans can be reopened below.</p>';report(error,err);}finally{pending=false;button.disabled=false;}
  };
  container.querySelectorAll('[data-open-plan]').forEach(b=>b.onclick=async()=>{try{const plan=await store.getPlan(b.dataset.openPlan);if(container.isConnected)renderPlan(plan);}catch(err){report(error,err);}});
  await mountGoogleEstimate({container,store});
}
export async function mountRiderPlan({container,store}){
  const plan=store.snapshot().riderPlans.find(p=>p.result.vehicles.length);
  if(!plan){container.innerHTML='<p>No committed optimization plan. Follow the existing dispatcher stop order and refresh for updates.</p>';return;}
  container.innerHTML=`<h2>Assigned route plan</h2>${plan.stale?'<p class="live-notice">Plan is stale after an order/queue change. Estimates need dispatcher review; follow the current queue and navigation pin.</p>':''}`+resultHTML(plan);
  maps(container,plan);
  
}

export async function mountGoogleEstimate({container,store,side='admin'}){
  // Reads status only. Mounting/refreshing never requests a Google route.
  if(!store.googleEstimateStatus)return;
  const panel=document.createElement('section');panel.className='plan-vehicle google-road-estimate';
  panel.innerHTML='<h3>Google road estimate — single delivery</h3><p data-google-status>Checking authorization…</p>';
  container.append(panel);
  let status;
  try{status=await store.googleEstimateStatus(side);}catch(error){report(panel.querySelector('[data-google-status]'),error);return;}
  if(!panel.isConnected)return;
  let available=status.enabled&&status.remaining_requests>0;
  const orders=store.snapshot().orders.filter(o=>!['delivered','cancelled','returned','return_pending'].includes(o.state));
  panel.innerHTML=`<h3>Google road estimate — single delivery</h3><p data-google-status>${available?'Server authorization enabled':'Live Google requests disabled or budget exhausted'}. Remaining server request budget: ${Number(status.remaining_requests)||0}. No request is made until you explicitly authorize and submit.</p><p>This estimate does not change assignments or the SIMULATED OR-Tools plan. Approved delivery pins are checked on the server; accuracy remains unverified.</p><form data-google-estimate><div class="form-grid"><label>Origin latitude<input name="latitude" type="number" min="-90" max="90" step="any" required></label><label>Origin longitude<input name="longitude" type="number" min="-180" max="180" step="any" required></label><label>Delivery<select name="order_id" required><option value="">Select a delivery</option>${orders.map(o=>`<option value="${esc(o.id)}">${esc(o.name||o.id)} — ${o.pin?'Stored pin; review required by server':'Missing pin'}</option>`).join('')}</select></label></div><label class="inline-check"><input name="consent" type="checkbox" required> I authorize ONE external Google request using these coordinates under the separately approved server budget.</label><button class="btn" type="submit" ${available?'':'disabled'}>Request Google road estimate</button></form><div data-google-result aria-live="polite"></div>`;
  const form=panel.querySelector('form'),result=panel.querySelector('[data-google-result]'),button=form.querySelector('button');
  let pending=false,requestId=null;
  form.oninput=e=>{if(!pending&&e.target.name!=='consent'){requestId=null;button.disabled=!available;result.textContent='Inputs changed; explicitly authorize a new request. Previous estimates are no longer displayed.';form.elements.consent.checked=false;}};
  form.onsubmit=async e=>{
    e.preventDefault();if(pending||!available||!form.reportValidity())return;
    requestId??=crypto.randomUUID();pending=true;button.disabled=true;
    const values=new FormData(form);for(const control of form.elements)control.disabled=true;result.textContent='Requesting Google road estimate. No automatic retry or simulated fallback.';
    try{
      const data=await store.googleEstimate({request_id:requestId,order_id:values.get('order_id'),origin:{latitude:Number(values.get('latitude')),longitude:Number(values.get('longitude'))},authorize_external_request:true},side);
      if(!panel.isConnected)return;
      const route=data.route;
      if(!['GOOGLE_LIVE','GOOGLE_MOCK'].includes(data.observation)||route.provider!=='google'||route.quality!=='ROAD_STATIC')throw Error('Unexpected routing response; no live result accepted.');
      result.innerHTML=`<p class="live-notice">${esc(data.observation)}${data.observation==='GOOGLE_MOCK'?' — TEST RESPONSE, not an additional live Google call':''}</p><p><strong>${(route.distance_meters/1000).toFixed(3)} km</strong> road distance; <strong>${(route.duration_seconds/60).toFixed(2)} min</strong> estimated travel duration. Static estimate, not live traffic or a delivery appointment.</p><p>Google Maps</p><p>No assignments, optimizer costs, or delivery statuses were changed. This response is not stored for later replay.</p>`;
      if([route.origin?.latitude,route.origin?.longitude,route.destination?.latitude,route.destination?.longitude].every(Number.isFinite)){
        const nav=document.createElement('a');nav.className='btn sm';nav.textContent='Open this route in Google Maps';nav.target='_blank';nav.rel='noopener noreferrer';
        nav.href='https://www.google.com/maps/dir/?api=1&origin='+encodeURIComponent(route.origin.latitude+','+route.origin.longitude)+'&destination='+encodeURIComponent(route.destination.latitude+','+route.destination.longitude)+'&travelmode=driving';result.append(nav);
      }
      if(route.geometry&&globalThis.LannPyaCustomerMap?.googleEnabled()){
        const show=document.createElement('button');show.type='button';show.className='btn sm';show.textContent='Show route on Google map';result.append(show);
        show.onclick=()=>{show.disabled=true;const map=document.createElement('div');map.className='live-map';map.setAttribute('aria-label','Google road route');result.append(map);globalThis.LannPyaCustomerMap.routeView(map,route.geometry,'google',[{...route.destination,sequence:1}]);};
      }else{const note=document.createElement('p');note.textContent='Google map display unavailable: a separately restricted browser Maps key is required. Google route geometry is not drawn on Leaflet.';result.append(note);}
    }catch(error){if(panel.isConnected)report(result,error);}
    finally{
      try{const budget=await store.googleEstimateStatus(side);available=budget.enabled&&budget.remaining_requests>0;if(panel.isConnected)panel.querySelector('[data-google-status]').textContent=`Remaining server request budget: ${Number(budget.remaining_requests)||0}. No automatic retry; another request needs explicit consent and remaining authorization.`;}
      catch{available=false;if(panel.isConnected)panel.querySelector('[data-google-status]').textContent='Budget status unavailable. Refresh before requesting another estimate.';}
      pending=false;for(const control of form.elements)if(control!==button)control.disabled=false;/* No automatic repeat: retain nonce and require changed inputs. */
    }
  };
}
