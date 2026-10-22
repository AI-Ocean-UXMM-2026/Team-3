const {test,expect,enter,inspect,create,link,verify,approve,assignDispatch,shot}=require('./fixtures.cjs');

test('complete browser-only order, buyer, approval, rider COD and hub closeout journey',async({page})=>{
  const sent=[];page.on('request',r=>{if(r.url().endsWith('/dashboard/api'))sent.push(r.postDataJSON());});
  await enter(page);
  for(const name of ['Fictional QA rider one','Fictional QA rider two']){
    await page.locator('#new-rider-form [name=name]').fill(name);
    await page.locator('#new-rider-form button[type=submit]').click();
    await expect(page.locator('#api-status')).toContainText('Saved in the backend database');
  }
  const available=(await inspect(page,'/api/riders')).items.filter(r=>r.operational_status==='AVAILABLE');
  expect(available.length).toBeGreaterThanOrEqual(2);
  const id=await create(page);
  let order=await inspect(page,'/api/orders/'+id);
  expect(order.original_message).toContain('၀၉၇၉၀၀၀၀၀၀၀');expect(order.cod_amount).toBe('25000');
  expect(order.latitude).toBeNull();expect(order.confidence_level).toBe('AMBER');
  const url=await link(page);const buyer=await page.context().newPage();
  await buyer.goto(url);await expect(buyer.locator('[data-action=request-buyer-otp]')).toBeVisible();
  await expect(buyer.locator('body')).not.toContainText('SIMULATION ONLY');
  await buyer.locator('[data-action=request-buyer-otp]').click();
  await expect(buyer.locator('#verify-api-form')).toBeVisible();
  await expect(buyer.locator('body')).toContainText('SIMULATION ONLY');
  const handle=String(url).match(/(?:track\/|confirm\/)([A-Za-z0-9_-]{43})/)?.[1];
  const codeResponse=await buyer.request.get('/dashboard/buyer-otp?buyer_handle='+encodeURIComponent(handle));
  expect(codeResponse.ok()).toBeTruthy();const code=(await codeResponse.json()).code;
  expect(code).toMatch(/^[0-9]{6}$/);
  await buyer.locator('#verify-api-form [name=digits]').fill(code);
  await buyer.locator('#verify-api-form button[type=submit]').click();
  await expect(buyer.locator('#buyer-location-form')).toBeVisible();
  await buyer.locator('#buyer-location-form [name=latitude]').fill('0');
  await buyer.locator('#buyer-location-form [name=longitude]').fill('0');
  await buyer.locator('[name=initial_pin_acknowledged]').check();
  await buyer.locator('#buyer-location-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('awaiting admin review');
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await buyer.locator('#buyer-response-form [name=instructions]').fill('FICTIONAL QA: အနီရောင်တံခါး၊ ဖုန်းအရင်ဆက်ပါ');
  await buyer.locator('#buyer-response-form [name=action]').selectOption('AVAILABLE');
  await buyer.locator('#buyer-response-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText(/saved|review/);
  await shot(buyer,'customer-verified-desktop');
  await buyer.setViewportSize({width:390,height:844});
  await shot(buyer,'customer-verified-mobile');
  await approve(page,id);order=await inspect(page,'/api/orders/'+id);
  expect(Number(order.latitude)).toBe(0);expect(order.confidence_level).toBe('AMBER');
  const assignmentForm=page.locator('#auto-assignment-form');await expect(assignmentForm).toBeVisible();
  await assignmentForm.locator('[name=received]').check();await assignmentForm.locator('[name=ack]').check();
  await assignmentForm.locator('button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText(/offer sent|waiting/i);
  let history=(await inspect(page,`/api/orders/${id}/assignments?page=1&page_size=100`)).items;
  const firstOffer=history.at(-1);expect(firstOffer.response_status).toBe('PENDING');
  await enter(page,'rider',firstOffer.rider_id);
  await expect(page.locator('[data-action=accept-offer]')).toBeVisible();
  await expect(page.locator('[data-action=deliver]')).toHaveCount(0);
  await page.locator('[data-action=decline-offer]').click();
  await expect(page.locator('#api-status')).not.toHaveClass(/error/);
  await enter(page,'admin');await page.goto('/api.html#/order/'+id);
  await expect(page.locator('#auto-assignment-form')).toHaveCount(0);
  history=(await inspect(page,`/api/orders/${id}/assignments?page=1&page_size=100`)).items;
  expect(history).toHaveLength(2);
  const replacement=history.at(-1);expect(replacement.response_status).toBe('PENDING');
  expect(replacement.rider_id).not.toBe(firstOffer.rider_id);
  await enter(page,'rider',replacement.rider_id);
  await expect(page.locator('[data-action=accept-offer]')).toBeVisible();
  await expect(page.locator('[data-action=deliver]')).toHaveCount(0);
  await page.locator('[data-action=accept-offer]').click();
  await expect(page.locator('[data-action=accept-offer]')).toHaveCount(0);
  await expect(page.locator('[data-action=deliver]')).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});await shot(page,'rider-accepted-mobile');
  await page.setViewportSize({width:1440,height:900});
  await enter(page,'admin');await page.goto('/api.html#/order/'+id);
  await expect(page.locator('[data-action=dispatch]')).toBeVisible();
  await page.locator('[data-action=dispatch]').click();await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('dialog')).toHaveCount(0);
  order=await inspect(page,'/api/orders/'+id);expect(order.status).toBe('OUT_FOR_DELIVERY');
  const riderId=replacement.rider_id;
  await shot(page,'admin-departed-desktop');
  await enter(page,'rider',riderId);
  await expect(page.locator('[data-action=deliver]')).toBeVisible();
  await expect(page.locator('.stop-landmark')).toBeVisible();
  const navigation=page.getByRole('link',{name:/Open Google Maps/});
  if(await navigation.count())expect(new URL(await navigation.getAttribute('href')).searchParams.get('destination').split(',').map(Number)).toEqual([0,0]);
  await shot(page,'rider-assigned-desktop');
  await page.locator('[data-action=deliver]').click();
  await expect(page.locator('dialog button[type=submit]')).toBeDisabled();
  await expect(page.locator('dialog button[type=submit]')).toBeEnabled();
  await page.locator('dialog [name=amount]').fill('24000');
  await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('dialog [role=alert]')).toContainText(/difference|different|reason/i);
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('OUT_FOR_DELIVERY');
  await page.locator('dialog [name=amount]').fill('25000');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  // Inspection uses a real dispatcher API only for assertions, never to perform user actions.
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('DELIVERED');
  await expect(page.locator('[data-action=deliver]')).toHaveCount(0);
  await page.locator('[data-action=handover]').click();
  await expect(page.locator('#api-status')).toContainText('Handover submitted');
  await enter(page,'admin');
  await page.locator('[data-action=receipt]').click();
  await page.locator('dialog [name=amount]').fill('-1');
  await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('dialog')).toBeVisible(); // native numeric validation blocks invalid cash
  await page.locator('dialog [name=amount]').fill('25000');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/routes')).items[0].state).toBe('closed');
  await shot(page,'hub-closed-desktop');
  await page.reload();await page.locator('#connect-form button[type=submit]').click();
  await expect(page.locator(`a[href="#/order/${id}"]`).first()).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('DELIVERED');
  const events=(await inspect(page,`/api/orders/${id}/events`)).items;
  expect(events.filter(e=>e.event_type==='DELIVERY_COMPLETED')).toHaveLength(1);
  expect(events.some(e=>e.event_type==='DELIVERY_STARTED')).toBeTruthy();
  expect(sent.some(r=>r.path==='/api/orders'&&r.method==='POST')).toBeTruthy();
  expect(sent.some(r=>r.path.endsWith('/auto-assignment')&&r.method==='POST')).toBeTruthy();
  expect(page.audit.activity.filter(e=>e.kind==='http'&&e.path==='/dashboard/api'&&e.status>=500)).toEqual([]);
});

const samples=[
  ['Unicode Burmese digits','၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ COD ၂၅၀၀၀ ကျပ်','AMBER','25000','09790000000'],
  ['Myanglish','09790000000, Hlaing township, COD 18000 MMK, street: Fictional Sample Road','AMBER','18000','09790000000'],
  ['Mixed English Burmese','09790000000 လှိုင်မြို့နယ် COD 5000 MMK landmark: Fictional Shop','AMBER','5000','09790000000'],
  ['Invalid phone','12345 Hlaing COD 100 MMK','RED','100',null],
  ['Missing phone','Hlaing township COD 0 MMK','RED','0',null],
  ['Unknown township','09790000000 FictionalUnknownTownship COD 7000 MMK','RED','7000','09790000000'],
  ['Missing township','09790000000 COD 12500 MMK','RED','12500','09790000000'],
  ['Ambiguous townships','09790000000 Hlaing or Insein, COD 3000 MMK','RED','3000','09790000000'],
];
for(const [name,raw,confidence,cod,phone] of samples)test('parser UI/API consistency: '+name,async({page})=>{
  await enter(page);
  await page.getByText('Parse a pasted address first (optional)',{exact:true}).click();
  await page.locator('#parse-form [name=raw]').fill(raw);
  const response=page.waitForResponse(r=>r.url().endsWith('/dashboard/api')&&r.request().postDataJSON()?.path==='/api/orders/parse');
  await page.locator('#parse-form button[type=submit]').click();
  const parsed=(await (await response).json()).data;
  await expect(page.locator('#parse-result')).toContainText(confidence);
  expect(parsed.confidence).toBe(confidence);expect(String(parsed.address.cod_amount)).toBe(cod);
  expect(parsed.address.phone_number).toBe(phone);
  await expect(page.locator('header')).toContainText('AI MOCK');
  await expect(page.locator('#parse-result')).toContainText(/AI: (mock|not_requested)/i);
  await expect(page.locator('#create-form [name=cod_amount]')).toHaveValue(cod);
  expect(parsed.address.latitude??null).toBeNull();expect(parsed.address.longitude??null).toBeNull();
  expect(await page.locator('#parse-result').textContent()).not.toMatch(/\d+\s*%/);
});

test('buyer wrong digits lock at three failures, public card privacy and reissue revocation',async({page})=>{
  const id=await create(page);const url=await link(page);const buyer=await page.context().newPage();
  await buyer.goto(url);await expect(buyer.locator('[data-action=request-buyer-otp]')).toBeVisible();
  await expect(buyer.locator('body')).not.toContainText('09790000000');
  await buyer.locator('[data-action=request-buyer-otp]').click();await expect(buyer.locator('#verify-api-form')).toBeVisible();
  for(let i=0;i<3;i++){
    await buyer.locator('[name=digits]').fill('111111');await buyer.locator('#verify-api-form button[type=submit]').click();
    await expect(buyer.locator('#api-status')).toHaveClass(/error/);
    await expect(buyer.locator('#verify-api-form button[type=submit]')).toBeEnabled();
  }
  await buyer.locator('[name=digits]').fill('000000');await buyer.locator('#verify-api-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText(/locked|attempt|unavailable/i);
  await expect(buyer.locator('#buyer-location-form')).toHaveCount(0);
  await shot(buyer,'customer-locked');
  await link(page);await buyer.goto(url);
  await expect(buyer.locator('#api-status')).toHaveClass(/error/);
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
});

test('buyer invalid coordinates, instructions, rescheduling and rejection remain review gated',async({page})=>{
  const id=await create(page);const url=await link(page);const buyer=await page.context().newPage();
  await verify(buyer,url);await expect(buyer.locator('#buyer-location-form')).toBeVisible();
  await buyer.locator('[name=latitude]').fill('91');await buyer.locator('[name=longitude]').fill('181');
  await buyer.locator('[name=initial_pin_acknowledged]').check();
  await buyer.locator('#buyer-location-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toHaveClass(/error/);
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await buyer.locator('[name=latitude]').fill('0');await buyer.locator('[name=longitude]').fill('0');
  await buyer.locator('#buyer-location-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('awaiting admin review');
  const form=buyer.locator('#buyer-response-form');
  await form.locator('[name=action]').selectOption('INSTRUCTIONS');
  await form.locator('[name=instructions]').fill('FICTIONAL: ဖုန်းအရင်ဆက်ပါ');
  await form.locator('button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText(/saved|review/);
  await form.locator('[name=action]').selectOption('RESCHEDULE');
  await form.locator('button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('Choose reschedule start and end');
  const next=new Date(Date.now()+86400000).toLocaleDateString('en-CA',{timeZone:'Asia/Rangoon'});
  await form.locator('[name=start]').fill(next+'T10:00');await form.locator('[name=end]').fill(next+'T12:00');
  await form.locator('button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('review');
  await page.locator('[data-action=refresh]').click();
  await expect(page.locator('[data-action=review]').first()).toBeVisible();
  await page.locator('[data-action=review]').first().click();
  await page.locator('dialog [name=decision]').selectOption('REJECT');
  await page.locator('dialog [name=reason]').fill('Fictional dispatcher rejection of untrusted point');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  const requests=(await inspect(page,`/api/orders/${id}/buyer-requests`)).items;
  expect(requests.some(r=>r.resolution==='REJECT')).toBeTruthy();
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
  await shot(buyer,'customer-reschedule-review');
});

test('rider failure, cancellation of modal, refresh and physical return requirement',async({page})=>{
  const id=await create(page,{pin:true});await assignDispatch(page);
  await page.locator('.role-switch a[href="#/rider"]').click();
  await page.locator('#connect-form button[type=submit]').click();
  await page.locator('[data-action=deliver]').click();await page.locator('dialog [data-cancel]').click();
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('OUT_FOR_DELIVERY');
  await page.locator('[data-action=failed]').click();
  await page.locator('dialog [name=failure_reason]').selectOption('CUSTOMER_UNAVAILABLE');
  await page.locator('dialog [name=failure_note]').fill('Fictional customer unavailable');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('FAILED');
  const events=(await inspect(page,`/api/orders/${id}/events`)).items;
  expect(events.filter(e=>e.event_type==='DELIVERY_FAILED')).toHaveLength(1);
  await page.locator('[data-action=refresh]').first().click();
  await expect(page.locator('[data-action=failed]')).toHaveCount(0);
  await shot(page,'rider-failed');
});

test('rider navigation waits for a pending dispatch refresh before connecting',async({page})=>{
  const id=await create(page,{pin:true});await assignDispatch(page);
  await page.locator('.role-switch a[href="#/rider"]').click();
  await page.locator('#connect-form button[type=submit]').click();
  await expect(page.locator('.current-stop')).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('OUT_FOR_DELIVERY');
});

test('local boundary rejects anonymous private reads, forged CSRF and invalid buyer tokens',async({page,browser,app})=>{
  await enter(page);
  const anonymous=await browser.newContext();const outsider=await anonymous.newPage();
  await outsider.goto(app.origin+'/dashboard/bootstrap');
  expect(await outsider.locator('body').textContent()).toContain('SESSION_REQUIRED');
  const res=await page.request.post('/dashboard/api',{headers:{Origin:app.origin,'X-Dashboard-CSRF':'forged'},data:{method:'GET',path:'/api/orders',actor:'dispatcher'}});
  expect(res.status()).toBe(403);
  for(const url of ['/api/orders','/.env','/backend/data/sandbox.sqlite3'])expect((await page.request.get(url)).status()).toBe(404);
  await page.goto('/api.html#/track/'+'x'.repeat(43));
  await expect(page.locator('#api-status')).toHaveClass(/error/);await expect(page.locator('#verify-api-form')).toHaveCount(0);
  await anonymous.close();
});

for(const [width,height] of [[1440,900],[1366,768],[768,1024],[390,844],[360,740]])test(`responsive screens ${width}x${height}`,async({page})=>{
  await page.setViewportSize({width,height});await enter(page);
  for(const [label,target]of [['Home',null],['Orders','order-board'],['Routes','route-planner'],['Hub closeout','hub-closeout'],['Riders','rider-profiles']]){
    const nav=target?page.locator(`.side-menu [data-section="${target}"]`):page.locator('.side-menu a').first();
    await nav.click();
    if(target)await expect(page.locator('#'+target)).toBeInViewport();
    const overflow=await page.evaluate(()=>({body:document.documentElement.scrollWidth,screen:innerWidth}));
    expect(overflow.body,`${label}: horizontal overflow`).toBeLessThanOrEqual(overflow.screen+1);
    await shot(page,`admin-${label.replaceAll(' ','-').toLowerCase()}-${width}`);
  }
  await page.locator('#new-rider-form [name=name]').fill('FICTIONAL QA Rider');
  await page.locator('#new-rider-form button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText('Saved in the backend database');
  const id=await create(page);const url=await link(page);await shot(page,`admin-order-${width}`);
  const buyer=await page.context().newPage();await buyer.setViewportSize({width,height});
  await verify(buyer,url);await expect(buyer.locator('#buyer-location-form')).toBeVisible();
  const overflow=await buyer.evaluate(()=>document.documentElement.scrollWidth-innerWidth);expect(overflow).toBeLessThanOrEqual(1);
  await shot(buyer,`customer-${width}`);
  await buyer.locator('#buyer-location-form [name=latitude]').fill('0');
  await buyer.locator('#buyer-location-form [name=longitude]').fill('0');
  await buyer.locator('[name=initial_pin_acknowledged]').check();
  await buyer.locator('#buyer-location-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toContainText('awaiting admin review');
  await approve(page,id);
  const form=page.locator('#auto-assignment-form');
  await form.locator('[name=received]').check();await form.locator('[name=ack]').check();
  await form.locator('button[type=submit]').click();
  await expect(page.locator('[data-action=dispatch]')).toBeVisible();
  await page.locator('[data-action=dispatch]').click();
  const box=await page.locator('dialog').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width+1);
  expect(box.y).toBeGreaterThanOrEqual(0);expect(box.y+box.height).toBeLessThanOrEqual(height+1);
  await shot(page,`departure-modal-${width}`);
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  await page.locator('.role-switch a[href="#/rider"]').click();await page.locator('#connect-form button[type=submit]').click();
  await expect(page.locator('#api-status')).not.toHaveClass(/error/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  await expect(page.locator('[data-action=deliver]')).toBeVisible();
  await shot(page,`rider-assigned-${width}`);
  await page.locator('[data-action=deliver]').click();
  await expect(page.locator('dialog [data-cancel]')).toBeInViewport();
  await shot(page,`delivery-modal-${width}`);
  await page.locator('dialog [data-cancel]').click();
  expect((await inspect(page,'/api/orders/'+id)).confidence_level).not.toBe('GREEN');
});

test('parsing a second address clears missing values and restores COD payment selection',async({page})=>{
  await enter(page);await page.getByText('Parse a pasted address first (optional)',{exact:true}).click();
  const input=page.locator('#parse-form [name=raw]'),submit=page.locator('#parse-form button[type=submit]');
  await input.fill('09790000000 Hlaing township COD 0 MMK');await submit.click();
  await expect(page.locator('#create-form [name=customer_phone]')).toHaveValue('09790000000');
  await input.fill('FictionalUnknownTownship COD 5000 MMK');await submit.click();
  await expect(page.locator('#parse-result')).toContainText('RED');
  await expect(page.locator('#create-form [name=customer_phone]')).toHaveValue('');
  await expect(page.locator('#create-form [name=township]')).toHaveValue('');
  await expect(page.locator('#create-form [name=payment]')).toHaveValue('cod');
});

test('expired link and expired buyer authorization use real backend checks (explicit fixture clock)',async({page})=>{
  const id=await create(page);const url=await link(page);const handle=url.split('/').at(-1);
  const buyer=await page.context().newPage();await verify(buyer,url);
  await expect(buyer.locator('#buyer-location-form')).toBeVisible();
  const {csrf}=await (await page.request.get('/dashboard/bootstrap')).json();
  const expire=async kind=>{
    const r=await page.request.post('/dashboard/expire',{headers:{Origin:new URL(page.url()).origin,'X-Dashboard-CSRF':csrf},data:{buyer_handle:handle,kind}});
    expect(r.ok()).toBeTruthy();
  };
  await expire('SESSION');
  await buyer.locator('#buyer-response-form button[type=submit]').click();
  await expect(buyer.locator('#api-status')).toHaveClass(/error/);
  await expire('LINK');await buyer.goto(url);
  await expect(buyer.locator('#api-status')).toHaveClass(/error/);
  await expect(buyer.locator('#verify-api-form')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).latitude).toBeNull();
});

test('failed real order write displays error and never falls back to demo success',async({page})=>{
  await enter(page);await page.getByText('Parse a pasted address first (optional)',{exact:true}).click();
  await page.locator('#parse-form [name=raw]').fill('09790000000 Hlaing COD 1000 MMK');
  await page.locator('#create-form [name=item]').fill('Fictional network failure parcel');
  await page.route('**/dashboard/api',async route=>{
    const q=route.request().postDataJSON();
    if(q.path==='/api/orders'&&q.method==='POST')return route.abort('failed');
    return route.continue();
  });
  await page.locator('[data-action=save-raw]').click();
  await expect(page.locator('#api-status')).toHaveClass(/error/);
  await expect(page.locator('#edit-api-form')).toHaveCount(0);
  expect((await inspect(page,'/api/orders')).items).toHaveLength(0);
  await shot(page,'order-write-connection-error');
});

test('manual order form persists actual fields and HTML-like notes render as inert text',async({page})=>{
  await enter(page);
  const form=page.locator('#create-form');
  for(const [key,value]of Object.entries({customer_name:'Fictional Manual Buyer',customer_phone:'09790000000',item:'Fictional shirt',cod_amount:'12000',street:'Fictional လမ်း',delivery_instructions:'<img src=x onerror=alert(1)> Fictional note'}))await form.locator(`[name="${key}"]`).fill(value);
  await form.locator('button[type=submit]').click();await expect(page.locator('#edit-api-form')).toBeVisible();
  const id=new URL(page.url()).hash.split('/').at(-1),record=await inspect(page,'/api/orders/'+id);
  expect(record.customer_name).toBe('Fictional Manual Buyer');expect(record.cod_amount).toBe('12000');
  expect(record.latitude).toBeNull();await expect(page.locator('img[src=x]')).toHaveCount(0);
  await page.locator('#edit-api-form [name=street]').fill('Corrected Fictional လမ်း');
  await page.locator('#edit-api-form button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText('Fields saved');
  expect((await inspect(page,'/api/orders/'+id)).street).toBe('Corrected Fictional လမ်း');
});

test('multiple rider stops can be expanded and unavailable rider selection is rejected',async({page})=>{
  const first=await create(page,{pin:true});await assignDispatch(page);
  const second=await create(page,{pin:true});await assignDispatch(page);
  await page.locator('.role-switch a[href="#/rider"]').click();
  await page.locator('#connect-form [name=actor_id]').fill('00000000-0000-0000-0000-000000000000');
  await page.locator('#connect-form button[type=submit]').click();
  await expect(page.locator('#api-status')).toHaveClass(/error/);
  await page.locator('#connect-form [name=actor_id]').fill('');await page.locator('#connect-form button[type=submit]').click();
  await expect(page.locator('.current-stop')).toBeVisible();
  await page.locator('.remaining-stops > summary').click();
  await expect(page.locator(`.remaining-stops [data-action=deliver]`)).toBeVisible();
  for(const id of [first,second])expect((await inspect(page,'/api/orders/'+id)).status).toBe('OUT_FOR_DELIVERY');
  await shot(page,'rider-multiple-stops');
});

test('health, browser credential boundary, cookie policy and private assets',async({page})=>{
  await enter(page);expect(await inspect(page,'/health')).toEqual({status:'ok',service:'LannPya AI'});
  const cookies=await page.context().cookies();const session=cookies.find(c=>c.name==='lp_dashboard');
  expect(session.httpOnly).toBe(true);expect(session.sameSite).toBe('Strict');
  const root=await page.request.get('/');expect(root.headers()['content-security-policy']).toContain("default-src 'self'");
  const boot=await (await page.request.get('/dashboard/bootstrap')).json();
  expect(boot.test_mode).toBe(true);expect(boot.database).toContain('temporary');
  for(const key of ['dev_access_token','api_key','access_token'])expect(boot).not.toHaveProperty(key);
  for(const file of ['/dev/api-workspace.mjs','/js/local-api.mjs','/js/backend-client.mjs']){
    const source=await (await page.request.get(file)).text();
    expect(source).not.toMatch(/sk-[A-Za-z0-9]{25,}|AIza[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{25,}/);
  }
  expect((await page.request.get('/dev/api-workspace.mjs.map')).status()).toBe(404);
});

test('route form rejects past dates then saves a real draft route',async({page})=>{
  await enter(page);const form=page.locator('#new-route-form');
  await form.locator('[name=day]').fill('2000-01-01');await form.locator('button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText('today or a future day');
  expect((await inspect(page,'/api/routes')).items).toHaveLength(0);
  const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Rangoon'});
  await form.locator('[name=day]').fill(today);await form.locator('button[type=submit]').click();
  await expect(page.locator('#api-status')).toContainText('Saved in the backend database');
  const routes=(await inspect(page,'/api/routes')).items;expect(routes).toHaveLength(1);expect(routes[0].state).toBe('draft');
  await expect(page.locator('[data-action=dispatch]')).toHaveCount(0);
});

test('separate browser prototype is clearly simulated and does not write to the backend',async({page})=>{
  const writes=[];page.on('request',r=>{if(r.url().endsWith('/dashboard/api')&&r.postDataJSON()?.method!=='GET')writes.push(r.postDataJSON()?.path);});
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await page.goto('/prototype.html');
  await expect(page.locator('.prototype-bar')).toContainText('DEMO_SIMULATION');
  await expect(page.locator('#app')).not.toBeEmpty();
  expect(writes).toEqual([]);
  await shot(page,'explicit-browser-simulation');
});

test('parcel incident resolution and draft unassignment use persistent workflow rules',async({page})=>{
  const id=await create(page,{pin:true});
  await page.locator('[data-action=incident]').click();
  await page.locator('dialog [name=reason]').fill('Fictional parcel packaging needs review');
  await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('[data-action=resolve-incident]')).toBeVisible();
  await expect(page.locator('#auto-assignment-form')).toHaveCount(0);
  await page.locator('[data-action=resolve-incident]').click();
  await page.locator('dialog [name=reason]').fill('Fictional packaging inspected and resolved');
  await page.locator('dialog button[type=submit]').click();
  const form=page.locator('#auto-assignment-form');await expect(form).toBeVisible();
  await form.locator('[name=received]').check();await form.locator('[name=ack]').check();
  await form.locator('button[type=submit]').click();
  await expect(page.locator('[data-action=unassign]')).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('ASSIGNED');
  await page.locator('[data-action=unassign]').click();
  await expect(page.locator('#auto-assignment-form')).toBeVisible();
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('READY_FOR_DISPATCH');
});

test('failed parcel requires physical return before zero-cash route closeout',async({page})=>{
  const id=await create(page,{pin:true});await assignDispatch(page);
  await page.locator('.role-switch a[href="#/rider"]').click();await page.locator('#connect-form button[type=submit]').click();
  await page.locator('[data-action=failed]').click();await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('[data-action=failed]')).toHaveCount(0);
  await expect(page.locator('[data-action=handover]')).toHaveCount(0);
  await page.locator('.role-switch a[href="#/admin"]').click();
  await page.locator('[data-action=return]').click();
  await expect(page.locator('[data-action=return]')).toHaveCount(0);
  expect((await inspect(page,'/api/orders/'+id)).parsing_metadata.parcel.return_received_at).toBeTruthy();
  await page.locator('.role-switch a[href="#/rider"]').click();
  await page.locator('[data-action=handover]').click();await expect(page.locator('#api-status')).toContainText('Handover submitted');
  await page.locator('.role-switch a[href="#/admin"]').click();
  await page.locator('[data-action=receipt]').click();await page.locator('dialog [name=amount]').fill('0');
  await page.locator('dialog button[type=submit]').click();await expect(page.locator('dialog')).toHaveCount(0);
  expect((await inspect(page,'/api/routes')).items[0].state).toBe('closed');
});
