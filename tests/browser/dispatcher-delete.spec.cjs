const {test,expect,enter}=require('./fixtures.cjs');
const path=require('node:path');

for(const stage of ['with-rider','delivered'])test(`dispatcher deletes ${stage} card and keeps delivery records after reload`,async({page})=>{
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await enter(page);
  const {csrf}=await (await page.request.get('/dashboard/bootstrap')).json();
  const origin=new URL(page.url()).origin;
  async function api(method,apiPath,body=null,riderId=null){
    const response=await page.request.post('/dashboard/api',{
      headers:{Origin:origin,'X-Dashboard-CSRF':csrf},
      data:{method,path:apiPath,body,actor:riderId?'rider':'dispatcher',...(riderId?{rider_id:riderId}:{})}
    });
    const result=await response.json();expect(response.ok(),JSON.stringify(result)).toBeTruthy();return result.data;
  }
  const day=new Date(Date.now()+23400000).toISOString().slice(0,10);
  const rider=(await api('GET','/api/riders')).items[0];
  let order=await api('POST','/api/orders',{
    structured:{customer_name:'Fictional board deletion',customer_phone:'09791234567',township:'Kamaryut',street:'Hledan Road',latitude:'16.8254000',longitude:'96.1309000',cod_amount:'25000',delivery_time_window:'Any time'},
    parcel:{item:'Test envelope',delivery_day:day,hub_received:true}
  });
  const orderPath='/api/orders/'+order.id;
  for(const status of ['NEEDS_REVIEW','CONFIRMED','READY_FOR_DISPATCH'])order=await api('PATCH',orderPath+'/status',{expected_version:order.version,status,acknowledge_unverified_location:true});
  let route=await api('POST','/api/routes',{rider_id:rider.id,day});
  await api('POST',orderPath+'/assign',{expected_version:order.version,rider_id:rider.id,route_id:route.id});
  route=(await api('GET','/api/routes')).items[0];
  await api('POST','/api/routes/'+route.id+'/actions',{request_id:crypto.randomUUID(),expected_version:route.version,action:'DISPATCH'});
  if(stage==='delivered'){
    const stop=(await api('GET',`/api/riders/${rider.id}/queue`,null,rider.id)).items[0];
    await api('PATCH',`/api/riders/${rider.id}/deliveries/${order.id}/status`,{request_id:crypto.randomUUID(),expected_version:stop.order_version,action:'DELIVERED',cod_collected:true,actual_amount:25000},rider.id);
    await page.setViewportSize({width:390,height:844});
  }
  const before=await api('GET',orderPath),routesBefore=await api('GET','/api/routes');
  await page.goto('/#/dispatch');
  const button=page.locator(`[data-action=delete-order][data-id="${order.id}"]`);
  await expect(button).toBeVisible();await button.click();
  const dialog=page.getByRole('dialog');
  await expect(dialog).toContainText('dispatcher board');
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,`delete-${stage}-dialog.png`),fullPage:true});
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();await expect(button).toBeVisible();
  await button.click();await page.getByRole('dialog').getByRole('button',{name:'Delete order',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);await expect(button).toHaveCount(0);
  await page.reload();await expect(page.getByRole('heading',{name:/Service board/})).toBeVisible();await expect(button).toHaveCount(0);
  const after=await api('GET',orderPath);
  expect(after.status).toBe(before.status);expect(after.parsing_metadata.parcel.dispatcher_deleted_at).toBeTruthy();
  expect(after.parsing_metadata.parcel.collection).toEqual(before.parsing_metadata.parcel.collection);
  expect(await api('GET','/api/routes')).toEqual(routesBefore);
});
