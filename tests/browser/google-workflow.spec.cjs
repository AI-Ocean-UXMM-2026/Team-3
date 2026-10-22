// Synthetic fixture responses only. Every Compute Routes operation is intercepted locally.
const {test,expect}=require('./fixtures.cjs');
test.beforeEach(async({page})=>{await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));});
async function order(page){
  await page.goto('/#/manual');const f=page.locator('#manual-form');await expect(f).toBeVisible();
  for(const [k,v]of Object.entries({name:'Fictional Google Test Buyer',phone:'09790000000',item:'Test shirt',street:'Synthetic street',expected:'25000'}))await f.locator(`[name=${k}]`).fill(v);
  await f.locator('[name=areaId]').selectOption('Hlaing');await f.locator('[name=received]').check();
  await f.locator('button').last().click();await expect(page.locator('#edit-form')).toBeVisible();
  return new URL(page.url()).hash.split('/').at(-1);
}
async function mockGoogle(page,fail=false,observation='GOOGLE_MOCK'){
  const posts=[];
  await page.route('**/dashboard/api',route=>{
    const q=route.request().postDataJSON();
    if(q.path==='/api/routes/google-demo/status')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:200,data:{enabled:true,maximum_requests:1,reserved_requests:posts.length,remaining_requests:1-posts.length,explicit_consent_required:true,matrix_supported:false}})});
    if(q.path!=='/api/routes/google-demo')return route.continue();
    posts.push(q);
    if(fail)return route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({error:{code:'ROUTING_RATE_LIMITED',message:'Google quota rejected this request'}})});
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:200,data:{observation,order_id:q.body.order_id,request_id:q.body.request_id,route:{provider:'google',origin:q.body.origin,destination:{latitude:16.815,longitude:96.125},mode:'DRIVE',distance_meters:1741,duration_seconds:405,geometry:{type:'LineString',coordinates:[[96.13,16.825],[96.125,16.815]]},quality:'ROAD_STATIC',traffic_aware:false,warnings:['Synthetic fixture response; not a new Google call'],attribution:'Google Maps'}}})});
  });
  return posts;
}
async function fill(page,id){
  const f=page.locator('[data-google-estimate]');await expect(f).toBeVisible();
  await f.locator('[name=latitude]').fill('16.825');await f.locator('[name=longitude]').fill('96.13');
  await f.locator('[name=order_id]').selectOption(id);return f;
}
test('dispatcher explicitly requests one Google estimate; mock identity, attribution and map boundary remain clear',async({page})=>{
  const id=await order(page),posts=await mockGoogle(page);await page.goto('/#/routes');const f=await fill(page,id);
  await f.locator('button').click();expect(posts).toHaveLength(0); // Browser requires consent.
  await f.locator('[name=consent]').check();await f.locator('button').click();
  const result=page.locator('[data-google-result]');await expect(result).toContainText('GOOGLE_MOCK');
  await expect(result).toContainText('1.741 km');await expect(result).toContainText('6.75 min');
  await expect(result).toContainText('Google Maps');await expect(result).toContainText('not drawn on Leaflet');
  const navigation=result.getByRole('link',{name:'Open this route in Google Maps'});
  await expect(navigation).toBeVisible();const nav=new URL(await navigation.getAttribute('href'));
  expect(nav.searchParams.get('origin')).toBe('16.825,96.13');expect(nav.searchParams.get('destination')).toBe('16.815,96.125');expect(nav.searchParams.has('key')).toBe(false);
  await expect(result.locator('.leaflet-container')).toHaveCount(0);await expect(f.locator('button')).toBeDisabled();
  expect(posts).toHaveLength(1);expect(posts[0].body.authorize_external_request).toBe(true);
  expect(posts[0].body.order_id).toBe(id);expect(posts[0].body).not.toHaveProperty('destination');
  await page.reload();await expect(page.locator('[data-google-estimate] button')).toBeDisabled();
  await expect(page.locator('[data-google-result]')).toBeEmpty();expect(posts).toHaveLength(1);
});
test('Google failure remains explicit with no repeated request or simulated success',async({page})=>{
  page.audit.expectedHttp.add(429);const id=await order(page),posts=await mockGoogle(page,true);
  await page.goto('/#/routes');const f=await fill(page,id);await f.locator('[name=consent]').check();await f.locator('button').click();
  await expect(page.locator('[data-google-result]')).toContainText('ROUTING_RATE_LIMITED');
  await expect(page.locator('[data-google-result]')).not.toContainText('GOOGLE_LIVE');
  await expect(f.locator('button')).toBeDisabled();expect(posts).toHaveLength(1);
});
test('default server configuration prevents live dispatcher requests',async({page})=>{
  await page.goto('/#/routes');await expect(page.locator('.google-road-estimate')).toContainText('Live Google requests disabled');
  await expect(page.locator('[data-google-estimate] button')).toBeDisabled();
});
test('recorded mocked success payload exercises GOOGLE_LIVE presentation without an external request',async({page})=>{
  const id=await order(page),posts=await mockGoogle(page,false,'GOOGLE_LIVE');
  await page.goto('/#/routes');const f=await fill(page,id);await f.locator('[name=consent]').check();await f.locator('button').click();
  await expect(page.locator('[data-google-result]')).toContainText('GOOGLE_LIVE');
  await expect(page.locator('[data-google-result]')).toContainText('Static estimate, not live traffic');
  expect(posts).toHaveLength(1);
});
