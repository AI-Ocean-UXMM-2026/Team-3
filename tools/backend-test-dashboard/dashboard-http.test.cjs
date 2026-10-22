// Executes the actual dashboard event handlers against a disposable real HTTP server.
// DOM behavior is a limited harness; this is deliberately not called a visual browser test.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const net = require('node:net');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {setTimeout: delay} = require('node:timers/promises');
const {load} = require('./harness.cjs');

async function launch() {
  const probe=net.createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
  const backend=path.resolve(__dirname,'../../backend');
  const python=require('../../scripts/python_path.cjs').pythonPath();
  const child=spawn(python,['-m','tools.backend_test_dashboard','--port',String(port)],{cwd:backend,stdio:'ignore',windowsHide:true});
  const exited=once(child,'exit');let cookie='';const origin=`http://127.0.0.1:${port}`;
  const request=async(url,body,headers={})=>{
    const response=await fetch(origin+url,{method:body===undefined?'GET':'POST',headers:{Cookie:cookie,Origin:origin,...headers,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(5000)});
    if(response.headers.get('set-cookie'))cookie=response.headers.get('set-cookie').split(';')[0];
    return response;
  };
  try {
    const deadline=Date.now()+20000;
    while(true){
      assert.equal(child.exitCode,null,'Dashboard exited during startup');
      try{assert.equal((await request('/')).status,200);break;}
      catch(e){if(Date.now()>=deadline)throw e;await delay(50);}
    }
    const boot=await (await request('/dashboard/bootstrap')).json();
    return {request,boot,async close(){
      if(child.exitCode===null){await request('/dashboard/shutdown',{confirm:'STOP LOCAL TOOL'},{'X-Dashboard-CSRF':boot.csrf});await Promise.race([exited,delay(10000,undefined,{ref:false}).then(()=>{throw Error('Graceful shutdown timed out');})]);}
    }};
  }catch(e){child.kill();throw e;}
}

test('actual dashboard controls process delivery and failure scenarios over isolated HTTP', {timeout:60000}, async t=>{
  const server=await launch();
  try {
    const ui=await load(async(url,payload,options)=>{
      const response=await server.request(url,payload??undefined,options.headers);
      return {status:response.status,data:await response.json()};
    });
    const n=id=>ui.nodes.get(id), output=()=>JSON.parse(n('output').textContent);
    const click=async(id,expected=200)=>{
      await n(id).trigger('click');
      if(!['load-order','reset'].includes(id))assert.match(n('result-status').textContent,new RegExp(`HTTP ${expected}(?:\\D|$)`),`${id}: ${output().error?.code??'unexpected status'}`);
      else assert.equal(output().error?422:200,expected);
      return output();
    };
    const status=async(value)=>{await click('load-order');n('next-status').value=value;return click('change-status');};
    const consoleCall=async(method,path,body,expected=200)=>{
      n('console-method').value=method;n('console-path').value=path;n('console-body').value=body===undefined?'':JSON.stringify(body);
      return click('console-send',expected);
    };
    const riderAction=async(riderId,orderId,body,expected=200)=>{
      const response=await server.request('/dashboard/api',{method:'PATCH',path:`/api/riders/${riderId}/deliveries/${orderId}/status`,body,actor:'rider',rider_id:riderId},{'X-Dashboard-CSRF':server.boot.csrf});
      const result=await response.json();assert.equal(response.status,expected,JSON.stringify(result));return result.data;
    };
    const reconfirm=async(orderId)=>{
      const row=await consoleCall('GET',`/api/orders/${orderId}`);
      return consoleCall('POST',`/api/orders/${orderId}/auto-assignment`,{request_id:crypto.randomUUID(),expected_version:row.version,acknowledge_unverified_location:true,receive_at_hub:true});
    };
    const dispatch=async(route)=>consoleCall('POST',`/api/routes/${route.id}/actions`,{request_id:crypto.randomUUID(),expected_version:route.version,action:'DISPATCH'});
    const verifyBuyerAndConfirm=async()=>{
      await click('generate-link',201);const verified=await click('verify');assert.equal(verified.verified,true);
      n('initial-pin').checked=true;assert.equal((await click('submit-pin')).decision,'REVIEW_REQUIRED');await approve();
      assert.equal((await click('available')).order_status,'CONFIRMED');
    };
    const approve=async()=>{
      await click('buyer-history');
      const card=n('review-list').children.find(c=>c.children[0]?.textContent.includes('REVIEW_REQUIRED'));
      assert.ok(card,'Expected pending dispatcher review');
      await card.children.find(c=>c.textContent==='APPROVE').trigger('click');
      assert.equal(output().items.filter(x=>x.decision==='REVIEW_REQUIRED'&&!x.resolution).length,0);
    };
    let identifier, rider, handle;

    await t.test('Burmese, Myanglish, mixed, missing, ambiguous and malformed parser cases',async()=>{
      const samples=[
        ['၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ COD ၂၅၀၀၀ ကျပ်၊ ညွှန်ကြားချက်: သရုပ်ပြ။','AMBER',25000],
        ['09790000000, Kamayut township, prepaid, instructions: fictional blue gate','AMBER',null],
        ['09790000000, လှိုင်မြို့နယ်, Demo Street, COD 5000 MMK, instructions: call first','AMBER',5000],
        ['လှိုင်မြို့နယ်၊ COD ၁၀၀၀ ကျပ်','RED',1000],
        ['09790000000, Unknown township, COD 0 MMK','RED',0],
        ['09790000000, 09960000000, Hlaing township, COD 100 MMK','RED',100],
      ];
      for(const [raw,confidence,cod] of samples){n('raw-text').value=raw;const data=await click('parse');assert.equal(data.confidence,confidence);assert.equal(data.address.cod_amount,cod);assert.ok(data.field_sources);assert.equal(data.original_text,raw);if(raw.includes('instructions:'))assert.equal(data.address.delivery_instructions,raw.split('instructions:')[1].trim());assert.notEqual(data.ai?.status,'available');}
      for(const raw of ['', 'x'.repeat(10001),'bad\u0000text']){n('raw-text').value=raw;await click('parse',422);}
    });

    await t.test('create, list, correct, select and lifecycle review controls',async()=>{
      n('raw-text').value='၀၉၇၉၀၀၀၀၀၀၀၊ လှိုင်မြို့နယ်၊ စမ်းသပ်လမ်း၊ COD ၂၅၀၀၀ ကျပ်';
      const row=await click('create-order',201);identifier=row.id;assert.equal(row.status,'DRAFT');
      assert.equal(n('order-list').children.length,1);
      await n('order-list').children[0].children[0].children[0].trigger('click');
      assert.equal(n('order-id').value,identifier);
      n('correction').value='{"delivery_instructions":"Synthetic private note, not a timeline entry"}';
      assert.match((await click('correct')).delivery_instructions,/Synthetic private note/);
      await status('NEEDS_REVIEW');
    });

    await t.test('buyer card, OTP verification, invalid pin and reviewed proposal',async()=>{
      const generated=await click('generate-link',201);handle=generated.buyer_handle;
      assert.equal(generated.confirmation_url,undefined);
      assert.equal((await click('buyer-card')).state,'VERIFICATION_REQUIRED');
      await click('buyer-details',401);
      const verified=await click('verify');assert.equal(verified.verified,true);assert.equal(verified.access_token,undefined);
      await click('buyer-details');
      n('latitude').value='91';n('longitude').value='0';n('initial-pin').checked=true;await click('submit-pin',422);
      n('latitude').value='0';assert.equal((await click('submit-pin')).decision,'REVIEW_REQUIRED');
      await approve();
      assert.equal(Number((await click('load-order')).latitude),0);
    });

    await t.test('rescheduling, explicit review, availability and instructions controls',async()=>{
      assert.equal((await click('reschedule')).decision,'REVIEW_REQUIRED');await approve();
      assert.equal((await click('available')).order_status,'CONFIRMED');
      n('buyer-instructions').value='Fictional buyer: ring twice';await click('instructions');
    });

    await t.test('automatic offer, acceptance, departure, COD completion and duplicate protection',async()=>{
      const prepared=await reconfirm(identifier);assert.equal(prepared.order.status,'ASSIGNED');
      assert.equal(prepared.assignment.response_status,'PENDING');rider=prepared.assignment.rider_id;
      await riderAction(rider,identifier,{expected_version:prepared.order.version,request_id:crypto.randomUUID(),action:'ACCEPT',assignment_id:prepared.assignment.id,offer_version:prepared.assignment.offer_version});
      await dispatch(prepared.route);await click('list-riders');n('active-rider').value=rider;await n('active-rider').trigger('change');
      const queue=await click('queue');assert.equal(queue.items.length,1);assert.equal(queue.items[0].order_id,identifier);assert.equal(queue.items[0].delivery_instructions,'Fictional buyer: ring twice');assert.equal(queue.items[0].coordinate_status,'BUYER_CONFIRMED');assert.equal(queue.items[0].confidence_level,'AMBER');assert.ok(queue.items[0].confirmed_window_start);
      n('cod-collected').checked=false;await click('deliver',409);
      n('cod-collected').checked=true;assert.equal((await click('deliver')).status,'DELIVERED');
      await click('deliver',404);
      const events=await click('events');assert.equal(events.items.filter(e=>e.event_type==='DELIVERY_COMPLETED').length,1);
      assert.equal((await click('load-order')).status,'DELIVERED');
    });

    await t.test('rider creation, wrong identity and failed delivery',async()=>{
      n('raw-text').value='09790000000, Kamayut township, Demo Street, COD 25000 MMK';await click('create-order',201);
      await status('NEEDS_REVIEW');const row=output();const failedId=row.id;
      await verifyBuyerAndConfirm();
      n('rider-name').value='Fictional Second Rider';const second=await click('create-rider',201);assert.equal(second.operational_status,'AVAILABLE');
      const prepared=await reconfirm(failedId);assert.equal(prepared.order.status,'ASSIGNED');
      const profiles=await consoleCall('GET','/api/riders?page_size=100');
      const wrongRider=profiles.items.find(profile=>profile.id!==prepared.assignment.rider_id);assert.ok(wrongRider);
      await riderAction(wrongRider.id,failedId,{expected_version:prepared.order.version,request_id:crypto.randomUUID(),action:'START'},404);
      rider=prepared.assignment.rider_id;await riderAction(rider,failedId,{expected_version:prepared.order.version,request_id:crypto.randomUUID(),action:'ACCEPT',assignment_id:prepared.assignment.id,offer_version:prepared.assignment.offer_version});
      await dispatch(prepared.route);await click('list-riders');n('active-rider').value=rider;await n('active-rider').trigger('change');
      const failedQueue=await click('queue');assert.ok(failedQueue.items.some(item=>item.order_id===failedId));
      n('failure-reason').value='CUSTOMER_UNAVAILABLE';assert.equal((await click('fail-delivery')).status,'FAILED');
    });

    await t.test('authorization expiry, link expiry, real three-failure lockout and activity privacy',async()=>{
      await click('create-order',201);await status('NEEDS_REVIEW');await click('generate-link',201);
      await click('verify');await click('expire-session');await click('buyer-details',401);
      await click('expire-link');await click('buyer-card',410);
      await click('generate-link',201);n('wrong-code').value='111111';await click('lock-link');
      assert.match(n('lock-note').textContent,/LOCKED/);
      await click('verify',423);
      const timeline=n('timeline').children.flatMap(row=>row.children.map(cell=>cell.textContent)).join(' ');
      assert.doesNotMatch(timeline,/09790000000|\b\d{6}\b|Synthetic private note|Fictional buyer|Bearer|X-Dev-Access-Token/);
      assert.ok(n('timeline').children.length<=100);assert.ok(timeline.includes('/api/confirm/{token}'));
    });

    await t.test('safe reset rejects wrong confirmation then removes only sandbox records',async()=>{
      n('reset-text').value='wrong';await click('reset',422);
      n('reset-text').value='RESET FICTIONAL DATA';await n('reset').trigger('click');
      assert.equal(output().reset,true);assert.equal(n('order-id').value,'');assert.equal(n('buyer-select').value,'');
      assert.match(n('page-label').textContent,/0 orders/);
      assert.notEqual(n('active-rider').value,rider);
    });
  } finally {await server.close();}
});
