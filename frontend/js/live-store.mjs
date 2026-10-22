// A view adapter for the MTT Signboard. SQLAlchemy records remain authoritative.
import {LocalWorkspaceApi} from './local-api.mjs';
const copy=x=>structuredClone(x);
const point=(a,b)=>a!=null&&b!=null&&Number.isFinite(Number(a))&&Number.isFinite(Number(b))?{lat:Number(a),lng:Number(b)}:null;
const states={DRAFT:'held',NEEDS_REVIEW:'held',AWAITING_CONFIRMATION:'awaiting_customer',CONFIRMED:'ready',READY_FOR_DISPATCH:'ready',ASSIGNED:'assigned',OUT_FOR_DELIVERY:'out_for_delivery',DELIVERED:'delivered',FAILED:'return_pending',CANCELLED:'cancelled'};
export function projectOrder(row){
  const p=row.parsing_metadata?.parcel||{},pin=point(row.latitude,row.longitude);
  return {id:row.id,version:row.version,name:row.customer_name||'',phone:row.customer_phone||'',raw:row.original_message||'',normalized:row.normalized_message||'',areaId:row.township,street:row.street||'',landmark:row.landmark||'',floor:row.building_floor_unit||row.floor||'',item:p.item||'',sender:p.sender||'',reference:p.reference||'',date:p.delivery_day||'',time:row.delivery_time_window||'Any time',payment:row.cod_amount==null?'unknown':Number(row.cod_amount)===0?'prepaid':'cod',expected:row.cod_amount==null?null:Number(row.cod_amount),note:row.delivery_instructions||'',state:p.return_received_at?'returned':states[row.status]||'held',location:pin?(row.field_sources?.latitude?.method==='buyer_confirmation'?'buyer_confirmed':'manual_unverified'):'unknown',anchor:null,pin,routeId:p.route_id||null,received:!!p.hub_received_at,collection:p.collection?{...p.collection,discrepancy:p.collection.actual!==p.collection.expected}:null,incident:p.incident||null,attempts:[],encodingReview:false,confidence:row.confidence_level,reasons:(row.confidence_reasons||[]).map(x=>x.message),fieldSources:row.field_sources,ai:row.ai_availability_status};
}
export async function createLiveStore(W,{api=new LocalWorkspaceApi(),origin=location.origin,route=location.hash.slice(2)}={}){
  const links=new Map(),linkStates=new Map(),buyerStates=new Map(),native=new Map(),routeRows=new Map();
  let lastRoute=route||'dispatch',queueRows=[],requests=[],activeBuyer=null;
  let state={orders:[],routes:[],plans:[],riderPlans:[],riders:[],events:[],outbox:[],downloads:{},policy:{areas:[],cutoff:900,enforceCutoff:true,maxRetries:0,radius:500,linkDays:3,version:1,noteLimit:2000},policyHistory:[],clockMode:'live'};
  const all=(side,path)=>api.all(side,path),call=(path,method='GET',body,side='admin')=>api.call(side,path,{method,body});
  function rows(routes){routeRows.clear();return routes.map(r=>{routeRows.set(r.id,r);return {...r,riderId:r.rider_id,date:r.day,orderIds:r.items.map(o=>o.id),active:null};});}
  function remember(data){native.clear();state.orders=data.map(r=>{native.set(r.id,r);const o=projectOrder(r);if(links.has(r.id))o.link=links.get(r.id);return o;});}
  async function connect(side,id){if(!api.connections[side]||id&&api.connections[side].actor.id!==id)await api.connect(side,origin,id||'');}
  async function loadBuyer(token){
    if(activeBuyer!==token){api.openBuyer(origin,token);activeBuyer=token;}
    try{const card=await api.buyer.card();const prior=buyerStates.get(token);buyerStates.set(token,{...prior,card,status:card.state==='LOCKED'?'locked':'active',available:card.state!=='LOCKED'});}
    catch(e){buyerStates.set(token,{available:false,status:e.code||'unavailable'});throw e;}
  }
  async function sync(target=lastRoute){
    lastRoute=target;
    if(target.startsWith('track/')){state.orders=[];state.routes=[];state.plans=[];state.riderPlans=[];state.riders=[];state.events=[];await loadBuyer(decodeURIComponent(target.slice(6))).catch(()=>{});return;}
    if(target==='customer'){state.orders=[];state.routes=[];state.plans=[];state.riderPlans=[];state.riders=[];state.events=[];return;}
    if(target.startsWith('ride')){
      await connect('rider');const rider=api.connections.rider.actor;
      if(!Object.values(W.ACTORS).some(a=>a.role==='rider'&&a.id===rider.id)){
        Object.keys(W.ACTORS).filter(k=>W.ACTORS[k].role==='rider').forEach(k=>delete W.ACTORS[k]);
        W.ACTORS.rider={...rider,hubId:'local',role:'rider'};
      }
      const routes=await all('rider','/api/routes');state.routes=rows(routes);
      queueRows=(await call(`/api/riders/${rider.id}/queue`,'GET',undefined,'rider')).items;
      state.riderPlans=(await call(`/api/riders/${rider.id}/route-plans`,'GET',undefined,'rider')).items||[];
      state.plans=[];state.riders=[];
      const projected=new Map(routes.flatMap(r=>r.items.map(o=>[o.id,{id:o.id,name:o.name||'',state:o.return_received?'returned':states[o.status],collection:o.collection,routeId:r.id,attempts:[]}])));
      for(const q of queueRows){const pin=point(q.latitude,q.longitude);projected.set(q.order_id,{...(projected.get(q.order_id)||{}),id:q.order_id,version:q.order_version,name:q.customer_name||'',phone:q.customer_phone||'',street:q.street||'',landmark:q.landmark||'',note:q.delivery_instructions||'',floor:q.building_floor_unit||'',areaId:q.township,state:states[q.status],pin,anchor:null,location:q.coordinate_status,navigationUrl:q.navigation_ready?q.navigation_url:null,expected:q.cod_amount==null?null:Number(q.cod_amount),payment:Number(q.cod_amount)===0?'prepaid':'cod',time:q.delivery_time_window||W.ANY_TIME,date:'',attempts:[],confirmation:q.buyer_confirmation?.last_confirmed_at?{answer:({AVAILABLE:'At home',RESCHEDULE:'Rescheduled',LEAVE_WITH_SECURITY:'Leave with security'})[q.buyer_confirmation.availability]||'Location only; availability unconfirmed',time:q.delivery_time_window||W.ANY_TIME}:null});}
      state.orders=[...projected.values()];state.events=[];return;
    }
    await connect('admin');const [orders,routes,riders]=await Promise.all([all('admin','/api/orders'),all('admin','/api/routes'),all('admin','/api/riders')]);
    state.riders=riders;state.riderPlans=[];
    state.plans=target==='routes'?await all('admin','/api/routes/plans'):[];
    remember(orders);state.routes=rows(routes);
    Object.keys(W.ACTORS).filter(k=>W.ACTORS[k].role==='rider').forEach(k=>delete W.ACTORS[k]);
    riders.forEach((r,i)=>W.ACTORS[i?'rider'+(i+1):'rider']={id:r.id,role:'rider',name:r.name,hubId:'local'});
    state.events=[];requests=[];
    if(target.startsWith('order/')){const id=target.slice(6);const [events,updates]=await Promise.all([all('admin',`/api/orders/${id}/events`),all('admin',`/api/orders/${id}/buyer-requests`)]);requests=updates;state.events=events.map(e=>({id:e.id,orderId:id,type:e.event_type,text:`${e.previous_status||''} → ${e.new_status}`,actor:new Date(e.created_at).toISOString(),at:e.created_at})).sort((a,b)=>a.at.localeCompare(b.at));const o=state.orders.find(o=>o.id===id),pending=updates.find(r=>r.kind==='LOCATION'&&r.decision==='REVIEW_REQUIRED'&&!r.resolution);if(o&&pending)o.proposedPin=point(pending.submitted_values.latitude,pending.submitted_values.longitude);}
  }
  // Controlled names, never fixture rectangles or township-centre coordinates.
  const places=['Hlaing','Kamaryut','Sanchaung','Bahan','Mayangon','Insein','Yankin','Tamwe','Thingangyun','South Okkalapa','North Okkalapa','North Dagon','South Dagon','East Dagon','Dagon Seikkan'];
  W.PLACES.splice(0,W.PLACES.length,...places.map(name=>({id:name,name,aliases:[name]})));state.policy.areas=[...places];
  const order=id=>{const o=state.orders.find(o=>o.id===id);if(!o)throw Error('Order unavailable in this workspace. Refresh before retrying.');return copy(o);};
  const row=id=>{const o=native.get(id);if(!o)throw Error('Refresh the dispatcher order before changing it.');return o;};
  async function execute(type,p={},actor={},meta={}){
    if(meta.offline||!navigator.onLine)throw Error('CONNECTION_ERROR: live writes require the backend. No simulated save was made.');
    let value;
    if(type==='create_manual'){
      const f=p.fields;if(f.prep&&f.date<W.readyFrom(f.prep,W.day(Date.now())))throw Error('Delivery day precedes the selected shop preparation timeline.');
      const structured={customer_name:f.name,customer_phone:f.phone,township:f.areaId,street:f.street||null,landmark:f.landmark||null,floor:f.floor||null,cod_amount:f.payment==='prepaid'?'0':String(f.expected??''),delivery_instructions:f.note||null,delivery_time_window:f.time||W.ANY_TIME};
      if(f.lat!==''&&f.lat!=null||f.lng!==''&&f.lng!=null){structured.latitude=f.lat;structured.longitude=f.lng;}
      const result=await call('/api/orders','POST',{structured,parcel:{item:f.item,sender:f.sender||null,reference:f.reference||null,delivery_day:f.date,hub_received:!!p.received}});value=result.id;
    }else if(type==='edit'){
      const r=row(p.id),f=p.fields,o=order(p.id);
      if(f.item!==o.item||f.sender!==o.sender||f.reference!==o.reference||f.date!==o.date||f.prep)throw Error('Parcel/preparation changes require a reviewed backend contract extension. Address fields can be corrected here.');
      await api.patch(r,{customer_name:f.name||null,customer_phone:f.phone||null,township:f.areaId||null,street:f.street||null,landmark:f.landmark||null,floor:f.floor||null,cod_amount:f.payment==='prepaid'?'0':f.expected==null?null:String(f.expected),delivery_instructions:f.note||null,delivery_time_window:f.time});
    }else if(type==='create_batch'){
      value=[];
      for(const record of p.records){
        try{const saved=await call('/api/orders','POST',{raw_text:record.raw,parcel:{item:p.item,delivery_day:p.date,hub_received:false}});value.push(saved.id);}
        catch(e){await sync();throw Error(`${value.length} order(s) persisted before this error: ${e.message}. Review the board before retrying to avoid duplicates.`);}
      }
    }else if(type==='issue_link'){
      let r=row(p.id);if(r.status==='DRAFT')r=await api.status(r,'NEEDS_REVIEW');const l=await call(`/api/orders/${p.id}/confirmation-link`,'POST',{});links.set(p.id,{token:l.buyer_handle,expires:Date.parse(l.expires_at),shared:false});linkStates.set(p.id,'active');
    }else if(type==='revoke_link'){await call(`/api/orders/${p.id}/confirmation-link/revoke`,'POST',{});links.delete(p.id);linkStates.set(p.id,'revoked');
    }else if(type==='shared'){throw Error('Chat-sharing acknowledgements are not persisted by the backend; share the private link manually.');
    }else if(['receive','return_received','incident','resolve_discrepancy'].includes(type)){
      await api.operation(row(p.id),{receive:'RECEIVE',return_received:'RETURN_RECEIVED',incident:p.resolve?'RESOLVE_INCIDENT':'INCIDENT',resolve_discrepancy:'RESOLVE_DIFFERENCE'}[type],p.reason);
    }else if(type==='approve_customer_location'||type==='reject_customer_location'){
      const pending=requests.filter(r=>r.decision==='REVIEW_REQUIRED'&&!r.resolution&&(p.requestId?r.request_id===p.requestId:r.kind==='LOCATION'));if(!pending.length)throw Error('No pending buyer requests. Refresh this order.');
      for(const r of pending){
        const current=await api.order(p.id);
        await call(`/api/orders/${p.id}/buyer-requests/${r.id}`,'PATCH',{expected_version:current.version,decision:type==='reject_customer_location'?'REJECT':'APPROVE',reason:p.reason});
      }
    }else if(type==='verify_location'){
      await api.patch(row(p.id),{latitude:String(p.pin.lat),longitude:String(p.pin.lng)});
    }else if(type==='new_route'){value=(await call('/api/routes','POST',{rider_id:p.riderId,day:p.date})).id;
    }else if(type==='assign'){
      await api.prepareAssignment(row(p.id),'route:'+p.routeId,{acknowledge:!!p.acknowledge,received:false});
    }else if(type==='unassign'){await call(`/api/orders/${p.id}/unassign`,'POST',{expected_version:row(p.id).version});
    }else if(type==='dispatch'){await api.routeAction('admin',routeRows.get(p.routeId),'DISPATCH');
    }else if(type==='cancel'){await api.status(row(p.id),'CANCELLED');
    }else if(type==='start'||type==='complete'||type==='fail'){
      await connect('rider',actor.id);const q=queueRows.find(q=>q.order_id===p.id);if(!q)throw Error('This order is not in the selected rider queue. Refresh.');
      if(type==='fail'&&p.resolution==='retry')throw Error('Same-day retry is not supported by the persistent workflow. Choose return to hub.');
      const reason={'Buyer not answering':'CUSTOMER_UNAVAILABLE','Not at home':'CUSTOMER_UNAVAILABLE','Can’t find the place':'ADDRESS_NOT_FOUND','Buyer refused':'CUSTOMER_REFUSED'}[p.reason]||'OTHER';
      await api.delivery(q,type==='start'?'START':type==='complete'?'DELIVERED':'FAILED',type==='start'?{}:type==='complete'?{actual_amount:p.amount,cod_collected:!!p.codCollected,difference_reason:p.reason||null}:{failure_reason:reason,failure_note:p.reason||null});
    }else if(['submit_cash','receive_cash','close_route'].includes(type)){
      const r=routeRows.get(p.routeId),side=type==='submit_cash'?'rider':'admin';if(side==='rider')await connect(side,actor.id);
      const result=await api.routeAction(side,r,{submit_cash:'HANDOVER',receive_cash:'RECEIVE_CLOSE',close_route:'CLOSE'}[type],{...(type==='close_route'?{}:{amount:p.amount,recorded_total:r.recorded_total,reason:p.reason||null,resolve:!!p.resolve})});value={closed:result.state==='closed'};
    }else throw Error(`Unsupported in LIVE_BACKEND: ${type}. No simulated mutation was made.`);
    try{await sync();}catch{throw Error('The backend accepted the write, but refresh failed. Reload before retrying; no simulated success was substituted.');}
    return {value,pending:false};
  }
  const store={live:true,now:()=>Date.now(),persistent:()=>true,snapshot:()=>copy(state),refresh:()=>{},sync,loadBuyer,execute,order,
    routingStatus:()=>call('/api/routes/provider-status'),
    calculateRoute:body=>call('/api/routes/calculate','POST',body),
    googleEstimateStatus:(side='admin')=>call('/api/routes/google-demo/status','GET',undefined,side),
    googleEstimate:(body,side='admin')=>call('/api/routes/google-demo','POST',body,side),
    previewPlan:body=>call('/api/routes/optimize','POST',body),
    getPlan:id=>call(`/api/routes/plans/${id}`),
    commitPlan:(plan,body)=>call(`/api/routes/plans/${plan.id}/commit`,'POST',{expected_version:plan.version,...body}),
    riderActor:()=>({...api.connections.rider?.actor,role:'rider'}),
    requests:()=>copy(requests.filter(r=>r.decision==='REVIEW_REQUIRED'&&!r.resolution)),
    async selectRider(id){await connect('rider',id);await sync('ride');},
    async verifyRefresh(token){await loadBuyer(token);const b=buyerStates.get(token);if(b.details)b.details=await api.buyer.details();},
    async parse(raw_text){await connect('admin');const r=await call('/api/orders/parse','POST',{raw_text}),a=r.address;return {name:a.customer_name||'',phone:a.phone_number||'',areaId:a.township||'',street:a.street||'',landmark:a.landmark||'',floor:a.building_floor_unit||'',expected:a.cod_amount,payment:a.cod_amount===0?'prepaid':a.cod_amount==null?'unknown':'cod',note:a.delivery_instructions||'',warnings:[...r.validation_reasons.map(v=>v.message),`AI: ${r.ai.status}. ${r.ai.message}`],confidence:r.confidence.toLowerCase(),pin:null};},
    triage:id=>{const o=order(id);return {level:(o.confidence||'AMBER').toLowerCase(),reasons:o.reasons||['Location accuracy is not independently verified.']};},
    blockers:id=>{const o=order(id);return [...(o.confidence==='RED'?['Correct critical address validation failures']:[]),...(!o.pin?['Location needed']:[]),...(o.proposedPin?['Buyer location awaiting review']:[]),...(!o.received?['Physical hub receipt required']:[])];},
    canEdit:id=>!['assigned','out_for_delivery','delivered','return_pending','returned','cancelled'].includes(order(id).state),
    duplicate:f=>state.orders.filter(o=>f.phone&&o.phone===f.phone).map(o=>o.id),
    linkStatus:id=>links.has(id)?Date.now()<links.get(id).expires?'active':'expired':linkStates.get(id)||'not_loaded',
    queue:actor=>actor.id===api.connections.rider?.actor.id?copy(queueRows.map(q=>state.orders.find(o=>o.id===q.order_id)).filter(Boolean)):[],
    closeoutBlockers:id=>routeRows.get(id)?.blockers||[],
    customer:token=>{const b=buyerStates.get(token);if(!b)return {available:false,status:'unavailable'};const d=b.details;const o=d?{id:d.order_reference,version:1,state:states[d.status],street:d.street||'',landmark:d.landmark||'',pin:point(d.latitude,d.longitude),anchor:null,location:d.initial_pin_requires_review?'unknown':'buyer_selected',time:d.delivery_time_window||W.ANY_TIME,note:d.delivery_instructions||'',date:W.day(Date.now()),confirmation:b.confirmation||null}:{};return {...b,order:o,verified:!!d,state:states[b.card?.delivery_status],sender:b.card?.shop_display_name||'LannPya',reference:b.card?.order_reference,item:'Delivery confirmation',payment:'unknown',expected:null,remaining:'up to 3',editable:!!d&&!['DELIVERED','CANCELLED','OUT_FOR_DELIVERY','ASSIGNED'].includes(d.status),dates:[W.day(Date.now()),W.addDays(W.day(Date.now()),1),W.addDays(W.day(Date.now()),2)]};},
    async verify(token,digits){await loadBuyer(token);try{await api.buyer.verify(digits);buyerStates.get(token).details=await api.buyer.details();return store.customer(token);}catch(e){await loadBuyer(token).catch(()=>{});throw e;}},
    async confirm(token,p){
      if(!p.pin||!Number.isFinite(p.pin.lat)||!Number.isFinite(p.pin.lng))throw Error('Select a valid map pin first.');
      await api.buyer.location({request_id:crypto.randomUUID(),latitude:p.pin.lat.toFixed(7),longitude:p.pin.lng.toFixed(7),initial_pin_acknowledged:!!p.acknowledged});
      const action={'At home':'AVAILABLE','Reschedule':'RESCHEDULE','Leave with security':'LEAVE_WITH_SECURITY'}[p.answer]||'AVAILABLE';
      const body={request_id:crypto.randomUUID(),action,...(p.note?{instructions:p.note}:{})};
      if(action==='RESCHEDULE'){if(!p.date||p.time===W.ANY_TIME)throw Error('Location request saved. Rescheduling also needs a specific future time window.');const [start,end]=p.time.split('–');body.time_window={start:`${p.date}T${start}:00+06:30`,end:`${p.date}T${end}:00+06:30`};}
      try{await api.buyer.respond(body);}catch(e){throw Error(`Location request was saved; availability was not saved: ${e.message}`);}
      buyerStates.get(token).confirmation={answer:p.answer,time:p.time};return store.customer(token);
    },
    replay:()=>{throw Error('Offline replay is simulation-only. Live requests must be explicitly retried.');},
    export:()=>{throw Error('Exporting private live records is not provided by this local UI.');}
  };
  await sync(lastRoute);return store;
}
