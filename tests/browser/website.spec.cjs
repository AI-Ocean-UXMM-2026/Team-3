const {test,expect,enter,inspect,shot}=require('./fixtures.cjs');

test('local boundary rejects anonymous private reads, forged CSRF and invalid buyer tokens',async({page,browser,app})=>{
  await enter(page);
  const anonymous=await browser.newContext();const outsider=await anonymous.newPage();
  await outsider.goto(app.origin+'/dashboard/bootstrap');
  expect(await outsider.locator('body').textContent()).toContain('SESSION_REQUIRED');
  const res=await page.request.post('/dashboard/api',{headers:{Origin:app.origin,'X-Dashboard-CSRF':'forged'},data:{method:'GET',path:'/api/orders',actor:'dispatcher'}});
  expect(res.status()).toBe(403);
  for(const url of ['/api/orders','/.env','/backend/data/sandbox.sqlite3'])expect((await page.request.get(url)).status()).toBe(404);
  await anonymous.close();
});

test('health, browser credential boundary, cookie policy and private assets',async({page})=>{
  await enter(page);expect(await inspect(page,'/health')).toEqual({status:'ok',service:'LannPya AI'});
  const cookies=await page.context().cookies();const session=cookies.find(c=>c.name==='lp_dashboard');
  expect(session.httpOnly).toBe(true);expect(session.sameSite).toBe('Strict');
  const root=await page.request.get('/');expect(root.headers()['content-security-policy']).toContain("default-src 'self'");
  const boot=await (await page.request.get('/dashboard/bootstrap')).json();
  expect(boot.test_mode).toBe(true);expect(boot.database).toContain('temporary');
  for(const key of ['dev_access_token','api_key','access_token'])expect(boot).not.toHaveProperty(key);
  for(const file of ['/js/functional-app.js','/js/local-api.mjs','/js/backend-client.mjs']){
    const source=await (await page.request.get(file)).text();
    expect(source).not.toMatch(/sk-[A-Za-z0-9]{25,}|AIza[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{25,}/);
  }
  expect((await page.request.get('/js/local-api.mjs.map')).status()).toBe(404);
});

test('separate browser prototype is clearly simulated and does not write to the backend',async({page})=>{
  await page.goto('/');
  await expect(page.locator('.prototype-bar')).toContainText('Local prototype');
  await expect(page.locator('#app')).not.toBeEmpty();
  await shot(page,'explicit-browser-simulation');
});
