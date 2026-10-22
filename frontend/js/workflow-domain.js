(function (root) {
  'use strict';
  const KEY = 'lannpya.workflow.v4';
  const RESET_MARKER = 'lannpya.reset.three-roles.v4';
  const LEGACY_KEYS = ['lannpya.workflow.v3','lannpya.delivery.v1','lannpya.form-drafts'];
  const ANY_TIME = 'Any time';
  const WINDOWS = ['10:00–12:00', '12:00–14:00', '14:00–16:00', '16:00–18:00'];
  // Shop prep / stock timeline: sets the earliest delivery day the buyer can pick.
  const PREP = [
    { id: 'ready_now', days: 0, label: 'Ready now (same day)' },
    { id: 'in_stock', days: 1, label: 'In stock (deliver tomorrow)' },
    { id: 'pre_3', days: 3, label: 'Pre-order: 3 days prep' },
    { id: 'pre_5', days: 5, label: 'Pre-order: 5 days prep' },
    { id: 'pre_7', days: 7, label: 'Pre-order: 7 days prep' }
  ];
  // Buyer-facing time slots, a subset of WINDOWS.
  const SLOTS = [
    { time: '10:00–12:00', label: 'Morning', my: 'မနက်' },
    { time: '14:00–16:00', label: 'Afternoon', my: 'နေ့လည်' },
    { time: '16:00–18:00', label: 'Evening', my: 'ညနေ' }
  ];
  const REASONS = ['Buyer not answering', 'Not at home', 'Can’t find the place', 'Buyer refused'];
  const VEHICLES = ['Motorbike','Bicycle','Car'];
  // Demo hub until the shop enters its own in Hub policy.
  const HUB = { name: 'Hledan hub', address: 'No. 12, Hledan Road, Kamayut', landmark: 'Next to the Hledan Centre car park', lat: 16.8262, lng: 96.1286, demo: true };
  // Riders added from the Riders page join the built-in two at load time.
  const registerRiders = list => { for (const r of list || []) ACTORS[r.id] ??= { id: r.id, role: 'rider', hubId: 'H-1', name: r.name, phone: r.phone, vehicle: r.vehicle }; };
  const ACTORS = {
    admin: { id: 'admin-1', role: 'admin', hubId: 'H-1', name: 'Admin' },
    customer: { id: 'customer-preview', role: 'customer', hubId: 'H-1', name: 'Customer' },
    rider: { id: 'rider-1', role: 'rider', hubId: 'H-1', name: 'Ko Aung', phone: '09 4500 12345', vehicle: 'Motorbike' },
    rider2: { id: 'rider-2', role: 'rider', hubId: 'H-1', name: 'Ko Wai', phone: '09 7700 54321', vehicle: 'Motorbike' }
  };
  // Deliberately small fixture geography. These rectangles are NOT real township boundaries.
  const PLACES = [
    { id: 'kamayut', name: 'Kamayut', aliases: ['kamayut','ကမာရွတ်','hledan','လှည်းတန်း'], lat: 16.8254, lng: 96.1309, streets: ['Hledan Road','University Avenue','Thiri Mingalar Road'], bounds: [16.818,16.845,96.121,96.147],
      points: { 'hledan road': [16.8247,96.1293], 'university avenue': [16.8320,96.1350], 'thiri mingalar road': [16.8370,96.1290] },
      landmarks: [[/junction square/i,[16.8196,96.1306]],[/hledan cent(?:er|re)|လှည်းတန်း/i,[16.8255,96.1290]]] },
    { id: 'sanchaung', name: 'Sanchaung', aliases: ['sanchaung','စမ်းချောင်း'], lat: 16.8034, lng: 96.132, streets: ['Baho Road','Bargayar Road'], bounds: [16.789,16.817,96.117,96.146],
      points: { 'baho road': [16.8040,96.1270], 'bargayar road': [16.8010,96.1330] },
      landmarks: [[/sanchaung market|စမ်းချောင်းဈေး/i,[16.8030,96.1300]]] }
  ];
  const copy = x => JSON.parse(JSON.stringify(x));
  const uid = () => root.crypto?.randomUUID?.() || `demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  const digits = t => String(t).replace(/[၀-၉]/g, c => String(c.charCodeAt(0)-0x1040));
  const day = ms => new Date(ms + 23400000).toISOString().slice(0,10);
  const minute = ms => {const d=new Date(ms+23400000);return d.getUTCHours()*60+d.getUTCMinutes();};
  const validDay = value => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value+'T00:00:00Z')) && new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
  const startMinute = time => time===ANY_TIME?0:Number(time.slice(0,2))*60+Number(time.slice(3,5));
  const endMinute = time => time===ANY_TIME?1440:Number(time.slice(6,8))*60+Number(time.slice(9,11));
  const addDays = (d,n) => new Date(Date.parse(d+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
  const readyFrom = (prepId,today) => {const p=PREP.find(x=>x.id===prepId);return p?addDays(today,p.days):today;};
  const validWindow = time => time===ANY_TIME||WINDOWS.includes(time);
  const distance = (a,b) => {const rad=x=>x*Math.PI/180;const h=Math.sin(rad(b.lat-a.lat)/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(rad(b.lng-a.lng)/2)**2;return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));};
  // Auto pin: the closest point the address supports. Landmark beats street; a street we don't know falls back to the township centre.
  function addressPoint(areaId,street,landmark,text='',places=PLACES){
    const area=places.find(a=>a.id===areaId);if(!area)return null;
    const at=([lat,lng],precision)=>({point:{lat,lng},precision});
    const hay=[landmark,street,text].filter(Boolean).join(' ');
    const lm=(area.landmarks||[]).find(([re])=>re.test(hay));if(lm)return at(lm[1],'landmark');
    const st=area.points?.[String(street||'').trim().toLowerCase()];if(st)return at(st,'street');
    return String(street||'').trim()||String(landmark||'').trim()?at([area.lat,area.lng],'township'):null;
  }
  const inside = (p,area) => !!p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && p.lat>=area.bounds[0] && p.lat<=area.bounds[1] && p.lng>=area.bounds[2] && p.lng<=area.bounds[3];
  // Optional LannPya AI order parser (vendor/lannpya-order-parser.js): Zawgyi conversion and Burmese rules/dictionary.
  // Deterministic and local; it only fills fields the labelled rules below leave empty.
  const enhancer = () => root.LannPyaOrderParser || null;
  const split = raw => (enhancer()&&Array.from(enhancer().splitOrders(String(raw))))|| String(raw).split(/\r?\n\s*---\s*\r?\n|\r?\n\s*\r?\n/).map(s=>s.trim()).filter(Boolean);
  function parse(raw) {
    const extra=enhancer()?.parseRules(String(raw))||null, filled=new Set();
    const text=digits(extra?extra.text:raw).normalize('NFC');
    const field=key=>(text.match(new RegExp('^'+key+'\\s*[:：]\\s*(.+)$','im'))?.[1]||'').trim();
    const take=(key,value)=>{if(value)filled.add(key);return value;};
    let phones=[...new Set((text.match(/(?:\+?95|09)[\d -]{6,17}\d/g)||[]).map(p=>p.replace(/[^\d]/g,'').replace(/^95/,'0')))];
    if(!phones.length&&extra){phones=[...new Set(extra.phones.filter(p=>p.valid).map(p=>p.number))];take('phone',phones.length);}
    const townships=extra?.townships||[];
    const area=PLACES.find(p=>p.aliases.some(a=>text.toLowerCase().includes(a)))||(townships.length===1?take('areaId',PLACES.find(p=>p.id===townships[0])):undefined);
    const street=field('Street')||area?.streets.find(s=>text.toLowerCase().includes(s.toLowerCase()))||take('street',[extra?.houseNo&&`No. ${extra.houseNo}`,extra?.street].filter(Boolean).join(', '));
    const amountText=field('COD');
    const ruled=!amountText&&!field('Payment')&&extra?.codAmount!=null&&!extra.ambiguousAmount?take('expected',extra):null;
    const amount=amountText ? Number(amountText.replace(/[,\s]/g,'').replace(/MMK|Ks/ig,'')) : ruled&&!ruled.prepaid?ruled.codAmount:null;
    const prepaid=/^prepaid$/i.test(field('Payment'))||!!ruled?.prepaid;
    const encodingReview=/[\u1060-\u108f]/.test(text);
    const landmark=field('Landmark'), vague=/near|နား|အနီး|somewhere/i.test(landmark) && !/gate|building|တိုက်|အမှတ်/i.test(landmark);
    const known=!!(street && area?.streets.includes(street)), auto=addressPoint(area?.id,street,landmark,text), anchor=auto?{...auto.point}:null;
    const fields={name:field('Name')||take('name',extra?.name||''),phone:phones.length===1?phones[0]:'',areaId:area?.id||'',street,landmark,floor:field('Floor'),note:field('Note'),reference:field('Invoice'),item:field('Item')||'Parcel',payment:prepaid?'prepaid':Number.isSafeInteger(amount)&&amount>0?'cod':'unknown',expected:prepaid?0:amount,anchor,pin:anchor?{...anchor}:null,pinFrom:auto?.precision||null,location:known&&!vague?'dictionary_matched':'unresolved',encodingReview,normalized:text,time:WINDOWS.includes(field('Time'))?field('Time'):WINDOWS[0],date:field('Date')||null};
    const provenance=Object.fromEntries(['phone','expected','payment'].map(k=>[k,{source:'rule',evidence:k==='phone'?phones.join(', '):amountText||field('Payment')||(ruled?(ruled.prepaid?`Prepaid${ruled.paymentMethod?' via '+ruled.paymentMethod:''}`:String(ruled.codAmount)):'')} ]));
    for(const k of ['areaId','street','anchor'])provenance[k]={source:'dictionary',evidence:area?.name||'No supported match'};
    for(const k of ['name','item','landmark','floor','note'])provenance[k]={source:'rule',evidence:fields[k]||'Not extracted'};
    if(filled.has('street'))provenance.street={source:'rule',evidence:street};
    for(const k of [...filled,...(filled.has('expected')?['payment']:[])])provenance[k].parser='lannpya-order-parser';
    const warnings=[];if(phones.length>1)warnings.push('Multiple phone candidates — choose the recipient.');if(encodingReview)warnings.push('Encoding needs manual Unicode review; no automatic conversion provider connected.');
    if(extra?.wasZawgyi){provenance.normalized={source:'rule',evidence:'Zawgyi converted to Unicode',parser:'lannpya-order-parser'};warnings.push('Converted from Zawgyi to Unicode — check names and the address against the original.');}
    if(!area&&townships.length)warnings.push(townships.length>1?`Several townships named (${townships.join(', ')}) — choose one.`:`Township ${townships[0]} is outside the supported service areas.`);
    if(!amountText&&!field('Payment')&&extra?.ambiguousAmount)warnings.push('Several amounts found — confirm the COD amount.');
    return {...fields,raw,provenance,warnings,vague};
  }
  const SAMPLE = `Name: Ma Thandar\nPhone: 09887341602\nTownship: Kamayut\nStreet: Hledan Road\nLandmark: အဆွေတော်နား\nCOD: 28000\nItem: Floral Summer Dress\nInvoice: DEMO-112\nNote: ၄ ထပ်တိုက် ညာဘက်ခန်း\n\n---\n\nName: Ko Min\nPhone: 09794339082\nTownship: Kamayut\nStreet: Thiri Mingalar Road\nLandmark: Blue gate 12\nCOD: 35000\nItem: Phone case\nInvoice: DEMO-113\n\n---\n\nName: Needs phone correction\nTownship: Sanchaung\nLandmark: near the market\nPayment: unknown\nItem: Canvas bag\nInvoice: DEMO-114`;
  function newOrder(fields,id) {return {id,hubId:'H-1',version:1,received:false,state:'held',confirmation:null,link:null,routeId:null,attempts:[],collection:null,incident:null,...fields};}
  function riderProjection(order){const safe=copy(order);for(const k of ['phone','raw','normalized','link','legacy','corrections'])delete safe[k];if(safe.provenance)delete safe.provenance.phone;return safe;}
  function triage(o) {
    const reasons=[];
    if(!/^09\d{7,9}$/.test(o.phone))reasons.push('Missing or invalid recipient phone');
    if(!PLACES.some(p=>p.id===o.areaId))reasons.push('Unknown or unsupported township');
    if(reasons.length)return {level:'red',reasons};
    if(o.encodingReview)return {level:'amber',reasons:['Unicode encoding requires manual review']};
    if(!o.anchor || !['dictionary_matched','dispatcher_verified','buyer_confirmed'].includes(o.location))return {level:'amber',reasons:['Location needs confirmation: vague landmark or unknown anchor']};
    return {level:'green',reasons:['Valid phone, supported township and resolved location']};
  }
  function blockers(o) {
    const t=triage(o), reasons=[];
    if(t.level==='red')reasons.push(...t.reasons);
    if(o.encodingReview)reasons.push('Review Unicode encoding');
    if(!o.anchor||!['dictionary_matched','dispatcher_verified','buyer_confirmed'].includes(o.location)&&!o.confirmation)reasons.push('Confirm delivery location');
    if(o.payment==='unknown'||!Number.isSafeInteger(o.expected)||o.expected<0||(o.payment==='cod'&&o.expected===0))reasons.push('Confirm payment mode and exact amount');
    if(!o.received)reasons.push('Record physical hub receipt');
    if(o.incident)reasons.push('Resolve parcel incident');
    return [...new Set(reasons)];
  }
  // Fixtures are used only by tests. The running app starts with seed(), which is empty.
  function fixtures() {
    const orders=SAMPLE.split(/\n\s*---\s*\n/).map((r,i)=>newOrder({...parse(r),date:'2026-10-20'},`LP-${2045+i}`));
    orders[0].received=true;
    orders[0].link={token:'demo-2045',status:'active',failures:0,issued:Date.parse('2026-10-20T01:30:00Z'),expires:Date.parse('2026-10-27T01:30:00Z')};
    return {version:4,revision:0,clockMode:'fixed',nextOrderNumber:2048,clock:Date.parse('2026-10-20T01:30:00Z'),policy:{version:1,areas:['kamayut','sanchaung'],cutoff:540,enforceCutoff:true,radius:500,maxRetries:1,noteLimit:300,linkDays:7,windows:[...WINDOWS]},orders,routes:[{id:'RT-001',riderId:'rider-1',date:'2026-10-20',state:'draft',orderIds:[],active:null,handover:null}],events:[],outbox:[],operations:{},policyHistory:[],migration:null};
  }
  function seed() {return {version:4,revision:0,clockMode:'live',clock:Date.now(),nextOrderNumber:1,policy:{version:1,areas:PLACES.map(p=>p.id),cutoff:540,enforceCutoff:false,radius:500,maxRetries:1,noteLimit:300,linkDays:7,windows:[ANY_TIME,...WINDOWS]},orders:[],routes:[],events:[],outbox:[],operations:{},policyHistory:[],downloads:{},resetNotice:'Previous demo records cleared. This workspace starts empty.'};}
  function createStore(storage, options={}) {
    let state, persistent=!!storage;
    try {
      if(storage && storage.getItem(RESET_MARKER)!=='done'){
        for(const key of [...LEGACY_KEYS,KEY])storage.removeItem(key);
        storage.setItem(RESET_MARKER,'done');
      }
      state=JSON.parse(storage?.getItem(KEY)||'null');
    }catch{persistent=false;}
    if(!state||state.version!==4)state=copy(options.initialState||seed());
    registerRiders(state.riders);
    const sessions=new Map();
    const now=()=>options.now?options.now():state.clockMode==='fixed'?state.clock:Date.now();
    const get=id=>{const o=state.orders.find(x=>x.id===id);if(!o)throw Error('Order not found.');return o;};
    const route=id=>{const r=state.routes.find(x=>x.id===id);if(!r)throw Error('Route not found.');return r;};
    const write=()=>{try{storage?.setItem(KEY,JSON.stringify(state));if(!storage)persistent=false;}catch{persistent=false;}};
    write();
    const refresh=()=>{try{const other=JSON.parse(storage?.getItem(KEY)||'null');if(other?.version===4&&other.revision>state.revision){state=other;registerRiders(state.riders);}}catch{persistent=false;}};
    const event=(type,id,text,actor)=>state.events.unshift({id:uid(),at:now(),type,orderId:id,text,actor:actor.id});
    const admin=a=>{if(a?.role!=='admin'||a.hubId!=='H-1')throw Error('Admin access required.');};
    const staff=(a,o)=>{if(a?.hubId!==o.hubId||a?.role!=='admin')throw Error('You cannot access this order.');};
    const activeLink=o=>{if(!o.link)return 'not_created';if(['revoked','locked'].includes(o.link.status))return o.link.status;return o.link.expires<=now()?'expired':'active';};
    const editable=o=>!['delivered','returned','return_pending','cancelled'].includes(o.state)&&(!o.routeId||route(o.routeId).state==='draft');
    const deadline=o=>{const d=day(now());return editable(o)&&d<=o.date&&(!state.policy.enforceCutoff||d<o.date||minute(now())<state.policy.cutoff);};
    const triageFor=o=>!(state.policy.areas||PLACES.map(p=>p.id)).includes(o.areaId)?{level:'red',reasons:['Township not enabled in current hub policy']}:triage(o);
    const readiness=o=>[...new Set([...blockers(o),...(!(state.policy.areas||PLACES.map(p=>p.id)).includes(o.areaId)?['Township disabled by hub policy']:[])])];
    const recalc=o=>{if(['held','ready'].includes(o.state))o.state=readiness(o).length?'held':'ready';};
    const scope=(a,o)=>{if(a?.role==='rider'){if(!o.routeId||route(o.routeId).riderId!==a.id)throw Error('This stop is not assigned to you.');}else staff(a,o);};
    function rider(a,o,override=false){if(override){admin(a);return;}if(a?.role!=='rider')throw Error('Assigned rider access required.');scope(a,o);if(!['dispatched','in_progress'].includes(route(o.routeId).state))throw Error('Route must depart before recording an attempt.');}
    const logAttempt=(o,actor,outcome,reason,operationId)=>{const queued=state.outbox.find(x=>x.operationId===operationId);o.attempts.push({id:uid(),at:queued?.at||now(),receivedAt:now(),riderId:queued?.actor.id||actor.id,reviewedBy:queued&&actor.role==='admin'?actor.id:null,routeId:o.routeId,outcome,reason,operationId});};
    function closeoutIssues(r){
      const items=r.orderIds.map(get),issues=[];
      if(r.state!=='closing'&&r.state!=='closed')issues.push('Rider handover not submitted');
      if(r.handover?.status!=='received')issues.push('Hub cash receipt not confirmed or cash difference unresolved');
      for(const item of items){
        if(!['delivered','returned'].includes(item.state))issues.push(`${item.id}: finish delivery or receive physical return`);
        if(item.collection?.discrepancy&&!item.collection.resolution)issues.push(`${item.id}: resolve collection difference`);
        if(item.incident)issues.push(`${item.id}: resolve incident`);
      }
      if(state.outbox.some(x=>x.status!=='acknowledged'&&r.orderIds.includes(x.payload.id)))issues.push('Replay or resolve queued rider actions');
      return issues;
    }
    function closeRoute(r,actor){r.state='closed';r.closedAt=now();event('close_route',null,r.id,actor);}
    function allocate(o,actor){
      admin(actor);const riders=Object.values(ACTORS).filter(a=>a.role==='rider'&&a.availability!=='UNAVAILABLE'&&!o.declinedRiders?.includes(a.id)&&!state.routes.some(r=>r.riderId===a.id&&r.state!=='closed'&&r.orderIds.some(orderId=>{const item=state.orders.find(x=>x.id===orderId);return item&&!['delivered','returned','cancelled'].includes(item.state);}))).sort((a,b)=>a.id.localeCompare(b.id));
      if(!riders.length){o.allocationStatus='WAITING_FOR_RIDER';event('rider_allocation_waiting',o.id,'No available rider without an active assignment',actor);return null;}
      const rider=riders[0],id=`RT-${uid().slice(-8)}`,r={id,riderId:rider.id,date:o.date,state:'draft',orderIds:[o.id],active:null,handover:null};state.routes.push(r);o.routeId=id;o.state='assigned';o.responseStatus='PENDING';o.offerVersion=(o.offerVersion||0)+1;o.allocationStatus='ASSIGNED';o.accepted=null;event('rider_offer_sent',o.id,`Offer ${o.offerVersion} sent to ${rider.name}`,actor);return r;
    }
    function apply(type,p,actor,operationId,override=false) {
      let o=p.id?get(p.id):null;
      if(o && p.expectedVersion!=null && p.expectedVersion!==o.version && !override)throw Error('Conflict: order changed. Review the latest record.');
      if(type==='create_manual'){
        admin(actor);
        const f=p.fields||{}, area=PLACES.find(a=>a.id===f.areaId);
        const phone=digits(f.phone||'').replace(/[^\d]/g,'').replace(/^95/,'0');
        if(!String(f.name||'').trim()||!/^09\d{7,9}$/.test(phone))throw Error('Enter a recipient name and valid Myanmar mobile number.');
        if(!area||!state.policy.areas.includes(area.id))throw Error('Choose a supported township.');
        if(!String(f.item||'').trim())throw Error('Enter a parcel description.');
        if(!['cod','prepaid'].includes(f.payment)||!Number.isSafeInteger(f.expected)||f.expected<0||(f.payment==='cod'&&f.expected===0)||(f.payment==='prepaid'&&f.expected!==0))throw Error('COD requires a positive whole MMK amount; prepaid requires zero.');
        if(!validDay(f.date)||f.date<day(now())||!validWindow(f.time)||f.date===day(now())&&endMinute(f.time)<=minute(now()))throw Error('Choose today or a future delivery date and an unexpired window. Any time is available for same-day testing.');
        if(f.prep&&!PREP.some(x=>x.id===f.prep))throw Error('Choose a shop prep timeline.');
        if(f.prep&&f.date<readyFrom(f.prep,day(now())))throw Error(`This stock timeline is ready on ${readyFrom(f.prep,day(now()))}. Choose that day or later.`);
        if(String(f.note||'').length>state.policy.noteLimit)throw Error('Rider note exceeds 300 characters.');
        if(f.reference&&state.orders.some(x=>x.reference===String(f.reference).trim())&&!p.createSeparate)throw Error('This invoice/reference already exists. Confirm intentional separate creation.');
        let point=null;
        if(f.lat!==''&&f.lat!=null||f.lng!==''&&f.lng!=null){point={lat:Number(f.lat),lng:Number(f.lng)};if(f.lat===''||f.lng===''||!inside(point,area))throw Error('Enter both coordinates inside the selected demo township, or leave both empty for customer location submission.');}
        const id=`LP-${String(state.nextOrderNumber++).padStart(4,'0')}`;
        const fields={...parse(''),name:String(f.name).trim(),phone,item:String(f.item).trim(),sender:String(f.sender||'LannPya Delivery').trim(),reference:String(f.reference||'').trim(),areaId:area.id,street:String(f.street||'').trim(),landmark:String(f.landmark||'').trim(),floor:String(f.floor||'').trim(),note:String(f.note||''),payment:f.payment,expected:f.expected,date:f.date,time:f.time,prep:f.prep||'',readyDate:f.prep?readyFrom(f.prep,day(now())):'',encodingReview:false,raw:'Manually entered by admin',normalized:'',anchor:point&&p.locationReviewed?point:null,pin:point,proposedPin:point&&!p.locationReviewed?point:null,location:point&&p.locationReviewed?'dispatcher_verified':point?'buyer_submitted':'unresolved',received:!!p.received};
        if(!point){const auto=addressPoint(area.id,fields.street,fields.landmark);if(auto){fields.anchor={...auto.point};fields.pin={...auto.point};fields.pinFrom=auto.precision;}}
        fields.provenance=Object.fromEntries(Object.keys(fields).filter(k=>!['raw','normalized','provenance'].includes(k)).map(k=>[k,{source:'manual',evidence:'Admin manual entry',actor:actor.id,at:now()}]));
        const item=newOrder(fields,id);item.link={token:uid(),status:'active',failures:0,issued:now(),expires:now()+state.policy.linkDays*86400000,shared:false};state.orders.push(item);recalc(item);event('order_created',id,'Manual admin order created',actor);event('buyer_link_issued',id,'Customer confirmation link created',actor);return id;
      }
      if(type==='create_batch'){
        admin(actor);
        if(!Array.isArray(p.records)||!p.records.length)throw Error('Choose at least one preview record.');
        const ids=[];
        for(const row of p.records){const fields=parse(row.raw);const duplicate=state.orders.find(x=>fields.reference&&x.reference===fields.reference||fields.phone&&fields.phone===x.phone&&fields.item===x.item&&fields.street===x.street);if(duplicate&&row.duplicate!=='separate')throw Error(`Likely duplicate ${duplicate.id}. Choose skip or create separately.`);const id=`LP-${String(state.nextOrderNumber++).padStart(4,'0')}`;const item=newOrder(fields,id);item.date=p.date||fields.date||day(now());state.orders.push(item);recalc(item);ids.push(id);event('order_created',id,'Pasted order created',actor);}return ids;
      }
      if(type==='clock'){admin(actor);const n=Date.parse(p.value);if(!Number.isFinite(n))throw Error('Choose a valid demo timestamp.');state.clock=n;state.clockMode='fixed';return;}
      if(type==='clock_live'){admin(actor);state.clockMode='live';return;}
      if(type==='prepare_offline'){if(actor.role!=='rider')throw Error('Rider access required.');state.downloads=state.downloads||{};state.downloads[actor.id]={at:now(),orderIds:state.orders.filter(x=>x.routeId&&route(x.routeId).riderId===actor.id&&['dispatched','in_progress'].includes(route(x.routeId).state)).map(x=>x.id)};event('queue_prepared',null,'Assigned queue prepared on this device',actor);return;}
      if(type==='policy'){admin(actor);if(!Number.isInteger(p.cutoff)||p.cutoff<0||p.cutoff>1439||!Number.isInteger(p.maxRetries)||p.maxRetries<0||p.maxRetries>3||!Number.isInteger(p.linkDays)||p.linkDays<1||p.linkDays>30)throw Error('Invalid cutoff, retry limit or link lifetime.');if(p.areas&&(!Array.isArray(p.areas)||!p.areas.length||p.areas.some(id=>!PLACES.some(a=>a.id===id))))throw Error('Enable at least one supported demo township.');state.policyHistory.push(copy(state.policy));Object.assign(state.policy,{areas:p.areas||state.policy.areas||PLACES.map(p=>p.id),cutoff:p.cutoff,maxRetries:p.maxRetries,linkDays:p.linkDays,enforceCutoff:p.enforceCutoff??state.policy.enforceCutoff,version:state.policy.version+1});state.orders.forEach(recalc);event('policy_changed',null,`Policy version ${state.policy.version}`,actor);return;}
      if(type==='set_hub'){
        admin(actor);const lat=Number(p.lat),lng=Number(p.lng);
        if(!String(p.name||'').trim()||!String(p.address||'').trim())throw Error('Enter the hub name and address.');
        if(!Number.isFinite(lat)||!Number.isFinite(lng)||lat<16.6||lat>17.1||lng<95.9||lng>96.4)throw Error('Enter coordinates inside Yangon, for example 16.8262 and 96.1286.');
        state.hub={name:String(p.name).trim(),address:String(p.address).trim(),landmark:String(p.landmark||'').trim(),lat,lng,demo:false};event('hub_updated',null,state.hub.name,actor);return;
      }
      if(type==='pickup'){
        if(actor?.role!=='rider')throw Error('Assigned rider access required.');const r=route(p.routeId);if(r.riderId!==actor.id)throw Error('This route belongs to another rider.');
        if(!['dispatched','in_progress'].includes(r.state))throw Error('The hub hasn’t sent this route yet.');if(r.pickedUpAt)return;
        r.pickedUpAt=now();r.pickedUp=r.orderIds.slice();event('route_picked_up',null,`${r.id}: ${r.orderIds.length} parcels collected`,actor);return;
      }
      if(type==='restore'){
        admin(actor);const t=(state.trash||[]).find(x=>x.order.id===p.orderId);if(!t)throw Error('This order can no longer be restored.');state.trash=state.trash.filter(x=>x!==t);state.orders.push(t.order);event('order_restored',t.order.id,'Restored after delete',actor);return t.order.id;
      }
      if(type==='add_rider'){
        admin(actor);const name=String(p.name||'').trim(),phone=digits(p.phone||'').replace(/[^\d]/g,'').replace(/^95/,'0');
        if(!name)throw Error('Enter the rider’s name.');if(!/^09\d{7,9}$/.test(phone))throw Error('Enter a Myanmar mobile number that starts with 09.');
        if(!VEHICLES.includes(p.vehicle))throw Error('Choose what the rider rides.');
        if(Object.values(ACTORS).some(a=>a.role==='rider'&&digits(a.phone||'').replace(/[^\d]/g,'')===phone))throw Error('A rider with this phone number is already on the list.');
        state.riders??=[];const id=`rider-${Object.values(ACTORS).filter(a=>a.role==='rider').length+1}`;
        const letters='ABCDEFGHJKMNPQRSTUVWXYZ23456789',code='LP-'+Array.from({length:4},(_,i)=>letters[parseInt(uid().replace(/[^0-9a-f]/g,'').slice(i*2,i*2+2)||'0',16)%letters.length]).join('');
        const rider={id,name,phone:phone.replace(/^(09)(\d{4})(\d+)$/,'$1 $2 $3'),vehicle:p.vehicle,addedAt:now(),invite:{code,expires:now()+86400000,used:false}};
        state.riders.push(rider);registerRiders([rider]);event('rider_added',null,`${name} added; invite ${code}`,actor);return {id,code};
      }
      if(type==='use_invite'){
        const code=String(p.code||'').trim().toUpperCase(),r=(state.riders||[]).find(x=>x.invite?.code===code);
        if(!r||r.invite.used||r.invite.expires<now())throw Error('That code doesn’t work. Ask your hub for a new one.');
        r.invite.used=true;event('rider_joined',null,`${r.name} used their invite`,{id:r.id});return {id:r.id};
      }
      if(type==='new_route'){admin(actor);if(!Object.values(ACTORS).some(a=>a.role==='rider'&&a.id===p.riderId)||!validDay(p.date))throw Error('Choose rider and delivery date.');const id=`RT-${uid().slice(-8)}`;state.routes.push({id,riderId:p.riderId,date:p.date,state:'draft',orderIds:[],active:null,handover:null});return id;}
      if(type==='dispatch'){
        admin(actor);const r=route(p.routeId);if(r.state!=='draft'||!r.orderIds.length)throw Error('Choose a nonempty draft route.');
        for(const id of r.orderIds){const item=get(id);const issues=readiness(item);if(item.state!=='assigned')issues.push(`parcel status is ${item.state}, not assigned`);if(item.date!==r.date)issues.push(`parcel date ${item.date} differs from route date ${r.date}`);if(item.date!==day(now()))issues.push(`delivery day is ${item.date}; app clock is ${day(now())} (Yangon)`);if(item.date===day(now())&&minute(now())>=endMinute(item.time))issues.push(`delivery window ${item.time} has ended`);if(issues.length)throw Error(`${id}: ${issues.join('; ')}.`);}
        if(r.orderIds.some(id=>get(id).responseStatus!=='ACCEPTED'))throw Error('Rider offer must be accepted before route departure.');r.state='dispatched';r.departedAt=now();r.policyVersion=state.policy.version;for(const id of r.orderIds){get(id).state='out_for_delivery';get(id).version++;}event('route_dispatched',null,r.id,actor);return;
      }
      if(type==='ack_route'||type==='active_stop'){const r=route(p.routeId);if(actor.role!=='rider'||r.riderId!==actor.id)throw Error('Route not assigned to you.');if(!['dispatched','in_progress'].includes(r.state))throw Error('Route has not departed.');if(type==='active_stop'){if(!r.orderIds.includes(p.stopId)||!['out_for_delivery','retry_pending'].includes(get(p.stopId).state))throw Error('Stop is not available.');r.active=p.stopId;}r.state='in_progress';return;}
      if(type==='submit_cash'||type==='receive_cash'||type==='close_route'){
        const r=route(p.routeId),items=r.orderIds.map(get);
        if(type==='submit_cash'){if(actor.role!=='rider'||r.riderId!==actor.id)throw Error('Assigned rider required.');if(!['dispatched','in_progress','closing'].includes(r.state)||r.handover?.status==='received')throw Error('Route cannot enter closeout or cash receipt is already acknowledged.');if(items.some(x=>!['delivered','returned'].includes(x.state)))throw Error('Finish all stops and receive all returns before handover.');if(!Number.isSafeInteger(p.amount)||p.amount<0)throw Error('Enter a nonnegative whole MMK amount.');const total=items.reduce((sum,x)=>sum+(x.collection?.actual||0),0);if(p.recordedTotal!=null&&p.recordedTotal!==total)throw Error('Recorded cash changed. Refresh and review the handover amount.');if(p.amount!==total&&!p.reason?.trim())throw Error('Explain the difference from recorded collection.');r.handoverHistory=r.handoverHistory||[];if(r.handover)r.handoverHistory.push(copy(r.handover));r.state='closing';r.handover={declared:p.amount,recorded:total,reason:p.reason||'',status:'submitted',submittedBy:actor.id};}
        else if(type==='receive_cash'){admin(actor);if(r.state!=='closing'||r.handover?.status!=='submitted'&&r.handover?.status!=='disputed')throw Error('Rider must submit handover first.');if(p.expectedDeclared!=null&&p.expectedDeclared!==r.handover.declared)throw Error('Rider handover changed. Reopen and recount before confirming receipt.');if(!Number.isSafeInteger(p.amount)||p.amount<0)throw Error('Enter actual whole MMK received.');const differs=p.amount!==r.handover.declared||p.amount!==r.handover.recorded;if(differs&&!p.reason?.trim())throw Error('Explain the cash difference.');r.receiptHistory=r.receiptHistory||[];r.receiptHistory.push({at:now(),by:actor.id,received:p.amount,reason:p.reason||''});Object.assign(r.handover,{received:p.amount,status:differs&&!p.resolve?'disputed':'received',resolution:p.resolve?p.reason:'',receivedBy:actor.id});event(type,null,r.id,actor);if(p.closeWhenReady&&!closeoutIssues(r).length)closeRoute(r,actor);return {closed:r.state==='closed',blockers:closeoutIssues(r)};}
        else{admin(actor);const issues=closeoutIssues(r);if(r.state!=='closing'||issues.length)throw Error(`Closeout blocked: ${issues.join('; ')||'route is already closed'}.`);closeRoute(r,actor);return;}event(type,null,r.id,actor);return;
      }
      if(!o)throw Error('Unknown operation.');
      if(type==='edit'){
        staff(actor,o);if(!editable(o))throw Error('Order is frozen after departure or completion.');
        if(!p.reason?.trim())throw Error('Record why fields changed.');
        o.corrections=o.corrections||[];const edits={};const allowed=['name','sender','phone','areaId','street','landmark','floor','note','payment','expected','item','reference','date','time','prep','encodingReview','normalized'];if('prep' in p.fields&&p.fields.prep&&!PREP.some(x=>x.id===p.fields.prep))throw Error('Choose a shop prep timeline.');const changed=[];
        for(const k of allowed)if(k in p.fields&&p.fields[k]!==(k==='prep'?o[k]||'':o[k])){edits[k]={before:o[k]??null,after:p.fields[k]??null};o[k]=p.fields[k];o.provenance[k]={source:'manual',evidence:p.reason,actor:actor.id,at:now()};changed.push(k);}
        if(!['unknown','cod','prepaid'].includes(o.payment)||o.payment==='prepaid'&&o.expected!==0||o.expected!=null&&(!Number.isSafeInteger(o.expected)||o.expected<0))throw Error('Choose explicit COD/prepaid or unknown and a valid whole amount.');
        if(!validWindow(o.time)||!validDay(o.date))throw Error('Choose a valid delivery date and window.');
        if(changed.includes('prep'))o.readyDate=o.prep?readyFrom(o.prep,day(now())):'';
        if(o.readyDate&&o.date<o.readyDate)throw Error(`The stock is ready on ${o.readyDate}. Move the delivery day to then or later.`);
        if(changed.some(k=>['areaId','street','landmark'].includes(k))){const auto=addressPoint(o.areaId,o.street,o.landmark);o.location='unresolved';o.anchor=auto?{...auto.point}:null;o.pin=auto?{...auto.point}:null;o.pinFrom=auto?.precision||null;}
        if(changed.some(k=>['phone','name','sender','areaId','street','landmark','payment','expected','item'].includes(k))){o.confirmation=null;if(o.link)o.link.status='revoked';}
        if(o.routeId&&(readiness(o).length||o.date!==route(o.routeId).date))throw Error('Unassign this draft route order before introducing a hold or changing its delivery day.');
        o.corrections.push({at:now(),actor:actor.id,reason:p.reason,changes:edits});event('field_corrected',o.id,`${changed.join(', ')} · ${p.reason}`,actor);
      }else if(type==='approve_customer_location'){
        admin(actor);if(!editable(o)||!o.proposedPin)throw Error('No editable customer location is awaiting review.');const area=PLACES.find(a=>a.id===o.areaId);if(!area||!inside(o.proposedPin,area)||!p.reason?.trim())throw Error('Review the point and record location evidence.');o.anchor=copy(o.proposedPin);o.pin=copy(o.proposedPin);o.proposedPin=null;o.location='dispatcher_verified';o.provenance.anchor={source:'manual',actor:actor.id,evidence:p.reason};event('customer_location_approved',o.id,p.reason,actor);
      }else if(type==='verify_location'){
        staff(actor,o);if(!editable(o))throw Error('Location frozen after departure.');const area=PLACES.find(a=>a.id===o.areaId);if(!area||!inside(p.pin,area)||!p.reason?.trim())throw Error('Choose coordinates inside the demo township and provide location evidence.');o.anchor=copy(p.pin);o.pin=copy(p.pin);o.location='dispatcher_verified';o.confirmation=null;if(o.link)o.link.status='revoked';o.provenance.anchor={source:'manual',actor:actor.id,evidence:p.reason};event('location_verified',o.id,p.reason,actor);
      }else if(type==='receive'){admin(actor);if(!editable(o)||o.received)throw Error('Parcel already received or unavailable.');o.received=true;event('parcel_received',o.id,'Physical hub receipt recorded',actor);
      }else if(type==='issue_link'){
        staff(actor,o);if(!editable(o)||triageFor(o).level==='red')throw Error('Correct phone/area and use an editable order before issuing a link.');if(state.events.filter(e=>e.type==='buyer_link_issued'&&e.orderId===o.id&&e.at>now()-600000).length>=3)throw Error('Too many link replacements. Wait 10 demo minutes and review the recipient.');o.link={token:uid(),status:'active',failures:0,issued:now(),expires:now()+state.policy.linkDays*86400000,shared:false};event('buyer_link_issued',o.id,'New link issued; previous token no longer works',actor);
      }else if(type==='revoke_link'||type==='shared'){staff(actor,o);if(!o.link)throw Error('Create a link first.');if(type==='revoke_link')o.link.status='revoked';else{if(activeLink(o)!=='active')throw Error('Link must be active.');o.link.shared=true;}event(type,o.id,type==='shared'?'Admin marked link manually shared':'Link revoked',actor);
      }else if(type==='assign'){
        admin(actor);const r=route(p.routeId);if(r.state!=='draft'||!['ready','held'].includes(o.state)||readiness(o).length||o.routeId||o.date!==r.date)throw Error('Order needs hub receipt, resolved fields and the same delivery day on an unassigned draft route.');o.routeId=r.id;r.orderIds.push(o.id);o.state='assigned';o.responseStatus='ACCEPTED';o.accepted={at:now(),riderId:r.riderId,legacy:true};event('rider_assigned',o.id,r.id,actor);
      }else if(type==='auto_assign'){
        admin(actor);if(!['ready','held'].includes(o.state)||readiness(o).length||o.routeId)throw Error('Order needs hub receipt, resolved fields and no active assignment.');
        allocate(o,actor);
      }else if(type==='offer_response'){
        if(actor?.role!=='rider'||!o.routeId||route(o.routeId).riderId!==actor.id)throw Error('Assigned rider access required.');if(!['ACCEPT','DECLINE'].includes(p.action)||o.responseStatus!=='PENDING'||p.offerVersion!==o.offerVersion)throw Error('This rider offer is no longer current. Refresh the queue.');
        const old=route(o.routeId);if(p.action==='ACCEPT'){o.responseStatus='ACCEPTED';o.accepted={at:now(),riderId:actor.id};event('rider_offer_accepted',o.id,old.id,actor);}
        else{old.orderIds=old.orderIds.filter(id=>id!==o.id);o.routeId=null;o.responseStatus='DECLINED';o.accepted=null;o.declinedRiders=[...new Set([...(o.declinedRiders||[]),actor.id])];o.state='ready';event('rider_offer_declined',o.id,old.id,actor);allocate(o,ACTORS.admin);}
      }else if(type==='unassign'){
        admin(actor);if(!o.routeId||route(o.routeId).state!=='draft')throw Error('Only draft assignments can be removed.');const r=route(o.routeId);r.orderIds=r.orderIds.filter(id=>id!==o.id);o.routeId=null;o.state='ready';event('rider_unassigned',o.id,p.reason||'Draft assignment removed',actor);
      }else if(type==='delete'){
        admin(actor);if(o.routeId||['out_for_delivery','delivered','returned','retry_pending','return_pending'].includes(o.state))throw Error('Only orders not yet on a route can be deleted. Take it off the route first.');
        state.orders=state.orders.filter(x=>x.id!==o.id);state.trash=[{order:o,at:now()},...(state.trash||[])].slice(0,20);event('order_deleted',o.id,'Deleted from the service board',actor);return o.id;
      }else if(type==='cancel'){
        staff(actor,o);if(!p.reason?.trim()||['delivered','returned','cancelled'].includes(o.state))throw Error('Cancellation needs a reason and an open order.');if(!editable(o)){if(actor.role!=='admin')throw Error('Contact admin to coordinate a departed parcel return.');if(!p.acknowledged)throw Error('Confirm the rider has acknowledged return instructions.');o.state='return_pending';}else{if(o.routeId){const r=route(o.routeId);r.orderIds=r.orderIds.filter(id=>id!==o.id);o.routeId=null;}o.state='cancelled';}if(o.link)o.link.status='revoked';event('order_cancel_requested',o.id,p.reason,actor);
      }else if(type==='accept'){
        if(o.responseStatus==='PENDING'){if(actor?.role!=='rider'||!o.routeId||route(o.routeId).riderId!==actor.id)throw Error('Assigned rider access required.');if(p.offerVersion!==o.offerVersion)throw Error('This rider offer is no longer current. Refresh the queue.');o.responseStatus='ACCEPTED';o.accepted={at:now(),riderId:actor.id};event('rider_offer_accepted',o.id,route(o.routeId).id,actor);}
        else{rider(actor,o,override);if(!['out_for_delivery','retry_pending'].includes(o.state))throw Error('This stop is not open.');o.accepted={at:now(),riderId:actor.id};o.responseStatus='ACCEPTED';event('stop_accepted',o.id,'Rider accepted the stop',actor);}
      }else if(type==='complete'){
        rider(actor,o,override);if(!['out_for_delivery','retry_pending'].includes(o.state))throw Error('Stop is already closed or has not departed.');if(day(now())!==o.date)throw Error(`Delivery day is ${o.date}; app clock is ${day(now())} (Yangon).`);if(minute(now())<startMinute(o.time))throw Error(`This delivery window starts at ${o.time}. Current app clock is ${String(Math.floor(minute(now())/60)).padStart(2,'0')}:${String(minute(now())%60).padStart(2,'0')} (Yangon).`);if(!Number.isSafeInteger(p.amount)||p.amount<0||o.payment==='prepaid'&&p.amount!==0)throw Error('Record nonnegative whole MMK; prepaid accepts zero only.');if(p.amount!==o.expected&&!p.reason?.trim())throw Error('An amount mismatch requires a reason.');logAttempt(o,actor,'delivered',p.reason||'',operationId);o.state='delivered';o.collection={expected:o.expected,actual:p.amount,discrepancy:p.amount!==o.expected,reason:p.reason||'',resolution:null};o.deliveredAt=now();if(o.link&&activeLink(o)==='active')o.link.expires=now()+86400000;if(o.routeId&&route(o.routeId).active===o.id)route(o.routeId).active=null;event('delivery_completed',o.id,`Collected ${p.amount} MMK${o.collection.discrepancy?' · discrepancy':''}`,actor);
      }else if(type==='fail'){
        rider(actor,o,override);if(!['out_for_delivery','retry_pending'].includes(o.state)||!REASONS.includes(p.reason))throw Error('Choose a failure reason for an open dispatched stop.');if(day(now())!==o.date)throw Error(`Delivery day is ${o.date}; app clock is ${day(now())} (Yangon).`);if(minute(now())<startMinute(o.time))throw Error(`This delivery window starts at ${o.time}. Current app clock is ${String(Math.floor(minute(now())/60)).padStart(2,'0')}:${String(minute(now())%60).padStart(2,'0')} (Yangon).`);if(!['retry','return'].includes(p.resolution))throw Error('Choose retry or return.');if(p.resolution==='retry'){if(o.attempts.length>=state.policy.maxRetries)throw Error('Retry limit reached. Return/replan this parcel.');if(!WINDOWS.includes(p.time)||startMinute(p.time)<=startMinute(o.time)||day(now())!==o.date||startMinute(p.time)<=minute(now()))throw Error('Choose a later future window today, or return to hub.');o.time=p.time;o.state='retry_pending';}else o.state='return_pending';logAttempt(o,actor,'failed',p.reason,operationId);if(o.routeId&&route(o.routeId).active===o.id)route(o.routeId).active=null;event('attempt_failed',o.id,`${p.reason} · ${p.resolution}`,actor);
      }else if(type==='return_received'){admin(actor);if(o.state!=='return_pending')throw Error('Parcel is not awaiting a hub return receipt.');o.state='returned';o.returnReceipt={by:actor.id,at:now()};event('return_received',o.id,'Hub physically received the parcel',actor);
      }else if(type==='replan'){admin(actor);if(o.state!=='returned'||!validDay(p.date)||p.date<=o.date)throw Error('Receive the return and choose a later delivery day.');o.cycles=o.cycles||[];o.cycles.push({date:o.date,attempts:copy(o.attempts),routeId:o.routeId,returnReceipt:o.returnReceipt});if(o.routeId&&route(o.routeId).state!=='closed')throw Error('Close the previous route before beginning a new cycle.');o.routeId=null;o.attempts=[];o.state='held';o.date=p.date;o.time=WINDOWS[0];o.confirmation=null;o.link=null;event('delivery_replanned',o.id,p.date,actor);
      }else if(type==='resolve_discrepancy'){admin(actor);if(!o.collection?.discrepancy||!p.reason?.trim())throw Error('Choose a discrepancy and record resolution.');o.collection.resolution={reason:p.reason,by:actor.id,at:now()};event('cash_discrepancy_resolved',o.id,p.reason,actor);
      }else if(type==='incident'){admin(actor);if(!p.reason?.trim())throw Error('Describe the incident or its resolution.');o.incident=p.resolve?null:p.reason;event(p.resolve?'incident_resolved':'incident_recorded',o.id,p.reason,actor);
      }else throw Error('Unknown operation.');
      o.version++;recalc(o);return o.id;
    }
    function execute(type,p={},actor=ACTORS.admin,meta={}) {
      refresh();const operationId=meta.operationId||uid();if(state.operations[operationId])return copy(state.operations[operationId]);
      if(meta.offline){if(actor.role!=='rider'||!['complete','fail'].includes(type))throw Error('Only rider delivery/attempt actions can enter the offline queue.');const o=get(p.id);rider(actor,o);if(!state.downloads?.[actor.id]?.orderIds.includes(o.id))throw Error('Prepare the assigned queue online before recording offline work.');if(state.outbox.some(x=>x.payload.id===o.id&&x.status!=='acknowledged'))throw Error('An action for this stop is already pending.');state.outbox.push({operationId,type,payload:copy(p),actor:copy(actor),at:now(),status:'pending'});state.revision++;write();return {pending:true,operationId};}
      const before=copy(state);
      try{const value=apply(type,p,actor,operationId,meta.override);const result={operationId,value:value??null};state.operations[operationId]=result;state.revision++;write();return copy(result);}catch(err){state=before;throw err;}
    }
    // Days the buyer can choose: three days from when the stock is ready, never before today, fixed once routed.
    function buyerDates(o){const today=day(now());if(o.routeId)return [o.date];const start=[o.readyDate||today,today].sort()[1];const list=[0,1,2].map(n=>addDays(start,n));if(o.date>=start&&!list.includes(o.date))list.push(o.date);return list.sort();}
    function customer(token){const o=state.orders.find(x=>x.link?.token===token);if(!o||activeLink(o)!=='active')return {available:false,status:o?activeLink(o):'invalid'};const challenge=o.link.otp,challengeActive=challenge&&challenge.expiresAt>now();const publicData={available:true,id:o.id,sender:o.sender||'LannPya Delivery',item:o.item,reference:o.reference,payment:o.payment,expected:o.expected,state:o.state,version:o.version,verified:sessions.has(token),editable:deadline(o),remaining:Math.max(0,3-(challenge?.attempts||0)),challenge:challengeActive?{mode:'DEMO',destinationMasked:`••••••${String(o.phone||'').slice(-4)}`,expiresAt:challenge.expiresAt,resendAfter:challenge.resendAfter}:null,otpPreview:challengeActive?'123456':undefined,simulationOnly:!!challengeActive};return sessions.has(token)?{...publicData,order:copy(Object.fromEntries(['id','name','item','payment','expected','state','date','time','prep','readyDate','anchor','pin','pinFrom','areaId','proposedPin','confirmation','note','version'].map(k=>[k,o[k]??null]))),dates:buyerDates(o),collection:o.collection?{actual:o.collection.actual}:null}:publicData;}
    function requestOtp(token){refresh();const o=state.orders.find(x=>x.link?.token===token);if(!o||activeLink(o)!=='active')throw Error('This link is unavailable. Contact the delivery admin.');if(sessions.has(token))return {mode:'DEMO',verified:true};if(o.link.otp&&o.link.otp.resendAfter>now())throw Error('Wait before requesting another code.');o.link.otp={code:'123456',attempts:0,expiresAt:now()+300000,resendAfter:now()+60000};state.revision++;write();event('buyer_otp_requested',o.id,'Local simulation code issued',{id:'customer'});return {mode:'DEMO',destinationMasked:`••••••${String(o.phone||'').slice(-4)}`,expiresAt:o.link.otp.expiresAt,resendAfter:o.link.otp.resendAfter,simulationOnly:true};}
    return {
      snapshot:()=>copy(state), now, persistent:()=>persistent, refresh,
      order(id,actor=ACTORS.admin){refresh();const o=get(id);scope(actor,o);return actor.role==='rider'?riderProjection(o):copy(o);},
      canEdit:id=>editable(get(id)), linkStatus:id=>activeLink(get(id)), deadline:id=>deadline(get(id)),
      blockers:id=>readiness(get(id)), triage:id=>triageFor(get(id)),
      closeoutBlockers:id=>closeoutIssues(route(id)),
      duplicate:fields=>copy(state.orders.filter(o=>fields.reference&&fields.reference===o.reference||fields.phone&&fields.phone===o.phone&&fields.street===o.street&&fields.item===o.item)),
      execute,
      customer,
      requestOtp,
      verify(token,value){refresh();const o=state.orders.find(x=>x.link?.token===token),challenge=o?.link?.otp;if(!o||activeLink(o)!=='active')throw Error('This link is unavailable. Contact the delivery admin.');if(sessions.has(token))return customer(token);if(!/^\d{6}$/.test(String(value)))throw Error('Enter the six-digit code.');if(!challenge||challenge.expiresAt<=now())throw Error('Request a new code; this code has expired.');if(value!==challenge.code){challenge.attempts++;if(challenge.attempts>=3){o.link.status='locked';delete o.link.otp;event('buyer_link_locked',o.id,'Admin action required',{id:'customer'});}state.revision++;write();throw Error(challenge.attempts>=3?'Link locked. Contact the delivery admin.':`Incorrect code. ${3-challenge.attempts} attempts remaining.`);}delete o.link.otp;sessions.set(token,true);state.revision++;write();return customer(token);},
      confirm(token,p){
        refresh();const o=state.orders.find(x=>x.link?.token===token);
        if(!o||activeLink(o)!=='active'||!sessions.has(token))throw Error('Verify an active customer link first.');
        if(p.expectedVersion!==o.version)throw Error('Conflict: delivery changed; review the latest details.');
        if(!deadline(o))throw Error('Customer changes are closed after cutoff/departure or the delivery day. Contact the admin.');
        if(triageFor(o).level==='red')throw Error('Admin must correct the phone or supported township first.');
        const area=PLACES.find(a=>a.id===o.areaId);
        if(!area||!inside(p.pin,area)||o.anchor&&distance(o.anchor,p.pin)>state.policy.radius)throw Error('Keep the pin within 500 m of the original anchor AND inside the original demo township.');
        const date=p.date||o.date;if(!buyerDates(o).includes(date))throw Error('Choose one of the delivery days shown.');
        if(!validWindow(p.time)||date<day(now())||date===day(now())&&endMinute(p.time)<=minute(now()))throw Error('Choose an available delivery window.');
        if(!['At home','Reschedule','Leave with security'].includes(p.answer))throw Error('Choose how to receive the parcel.');
        if(p.answer==='Leave with security'&&o.payment==='cod'&&!p.securityPays)throw Error('Confirm the security recipient can pay COD, or choose another option.');
        if(String(p.note||'').length>state.policy.noteLimit)throw Error('Rider note exceeds 300 characters.');
        o.confirmation={answer:p.answer,date,time:p.time,note:p.note||'',at:now(),policyVersion:state.policy.version};
        o.pin=copy(p.pin);if(!o.anchor){o.proposedPin=copy(p.pin);o.location='buyer_submitted';}else if(o.location!=='dispatcher_verified')o.location='buyer_confirmed';
        o.date=date;o.time=p.time;o.note=p.note||'';o.version++;recalc(o);
        event('buyer_confirmed',o.id,`${p.answer} · ${p.time}${o.anchor?'':' · location awaiting admin review'}`,{id:'customer'});
        state.revision++;write();return customer(token);
      },
      queue(actor=ACTORS.rider){return copy(state.orders.filter(o=>o.routeId&&route(o.routeId).riderId===actor.id&&(['dispatched','in_progress'].includes(route(o.routeId).state)&&['out_for_delivery','retry_pending'].includes(o.state)||route(o.routeId).state==='draft'&&o.state==='assigned'&&['PENDING','ACCEPTED'].includes(o.responseStatus))).sort((a,b)=>{const ar=route(a.routeId);if(ar.active===a.id)return -1;if(route(b.routeId).active===b.id)return 1;return startMinute(a.time)-startMinute(b.time)||(a.state==='retry_pending')-(b.state==='retry_pending')||ar.orderIds.indexOf(a.id)-route(b.routeId).orderIds.indexOf(b.id);}).map(riderProjection));},
      replay(){refresh();const results=[];for(const item of state.outbox.filter(x=>x.status==='pending')){try{execute(item.type,item.payload,item.actor,{operationId:item.operationId});const current=state.outbox.find(x=>x.operationId===item.operationId);current.status='acknowledged';results.push(current.operationId);}catch(err){const current=state.outbox.find(x=>x.operationId===item.operationId);current.status='conflict';current.error=err.message;}}state.revision++;write();return results;},
      resolvePending(operationId,reason,accept,actor=ACTORS.admin){admin(actor);if(!reason?.trim())throw Error('Explain the conflict resolution.');const item=state.outbox.find(x=>x.operationId===operationId);if(!item||item.status==='acknowledged')throw Error('No unresolved action.');if(accept){execute(item.type,item.payload,actor,{operationId:item.operationId,override:true});}const current=state.outbox.find(x=>x.operationId===operationId);current.status='acknowledged';current.resolution=reason;event('offline_conflict_resolved',item.payload.id,`${accept?'Recorded observed result':'Rejected observed result'} · ${reason}`,actor);state.revision++;write();},
      export:()=>JSON.stringify(state,null,2)
    };
  }
  const api={KEY,RESET_MARKER,LEGACY_KEYS,ANY_TIME,WINDOWS,PREP,SLOTS,addDays,readyFrom,REASONS,ACTORS,VEHICLES,HUB,PLACES,SAMPLE,addressPoint,parse,split,enhanced:()=>!!enhancer(),triage,blockers,createStore,distance,day,minute,startMinute,endMinute,uid,seed,fixtures};
  if(typeof module!=='undefined')module.exports=api;else root.Workflow=api;
})(typeof window==='undefined'?globalThis:window);
