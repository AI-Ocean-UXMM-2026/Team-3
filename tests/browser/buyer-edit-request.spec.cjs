const {test,expect,enter,inspect}=require('./fixtures.cjs');
const path=require('node:path');

test('fresh draft accepts the first address confirmation even after the edit cutoff',async({page})=>{
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await page.setViewportSize({width:390,height:844});
  await enter(page);await page.goto('/#/manual');
  const f=page.locator('#manual-form');
  for(const [key,value] of Object.entries({name:'Fictional first confirmation',phone:'09790000000',item:'Test parcel',street:'Test street'}))await f.locator(`[name=${key}]`).fill(value);
  await f.locator('[name=areaId]').selectOption('Hlaing');
  await f.locator('[name=payment]').selectOption('prepaid');
  await f.locator('aside button').click();await page.locator('[data-created=open]').click();
  const id=new URL(page.url()).hash.split('/').at(-1);
  expect((await inspect(page,'/api/orders/'+id)).status).toBe('DRAFT');
  const link=await page.getByRole('link',{name:'See what the buyer sees'}).getAttribute('href');
  await page.goto(link);await page.locator('[data-action=request-otp]').click();
  const code=(await page.locator('.verification .demo-hint .num').textContent()).trim();
  await page.locator('#verify-form [name=digits]').fill(code);
  await page.locator('#verify-form .customer-primary').click();
  await expect(page.locator('#customer-form')).toBeVisible();
  await page.locator('[name=latitude]').fill('16.8');await page.locator('[name=longitude]').fill('96.1');
  await page.locator('[name=initial_pin_acknowledged]').check();
  const today=new Date(Date.now()+23400000).toISOString().slice(0,10);
  await page.locator('#customer-form [name=date]').fill(today);
  await page.locator('#customer-form [name=time]').selectOption('10:00–12:00');
  await expect(page.locator('[data-edit-policy]')).toContainText('first address confirmation is not blocked');
  await page.locator('#customer-form .customer-primary').click();
  await expect(page.locator('.customer-notice,.delivery-request-confirmed')).toContainText(/Delivery request confirmed|Your delivery request is saved/);
  await expect(page.locator('.form-error')).toHaveCount(0);
  const saved=await inspect(page,'/api/orders/'+id);
  expect(['NEEDS_REVIEW','CONFIRMED']).toContain(saved.status);
  expect(saved.delivery_time_window).toBe(`${today}T03:30:00+00:00/${today}T05:30:00+00:00`);
  if(process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'buyer-first-confirmation-saved.png'),fullPage:true});
});

test('buyer requested ETA survives BFF reload and allows exactly three edits',async({page})=>{
  await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:''}));
  await enter(page);
  await page.goto('/#/create');
  await expect(page.locator('.create-options a')).toHaveCount(2);
  await page.getByRole('link',{name:'Form (enter manually)',exact:true}).click();
  const f=page.locator('#manual-form');
  await expect(f.locator('[name=lat],[name=lng],[name=locationReviewed]')).toHaveCount(0);
  for(const [key,value] of Object.entries({name:'Fictional cutoff buyer',phone:'09790000000',item:'Test parcel',street:'Test street',expected:'0'}))await f.locator(`[name=${key}]`).fill(value);
  await f.locator('[name=areaId]').selectOption('Hlaing');
  await f.locator('[name=payment]').selectOption('prepaid');
  await f.locator('aside button').click();
  await page.locator('[data-created=open]').click();
  const id=new URL(page.url()).hash.split('/').at(-1);
  const link=await page.getByRole('link',{name:'See what the buyer sees'}).getAttribute('href');
  await page.goto(link);
  async function verify(){
    await page.locator('[data-action=request-otp]').click();
    const code=await page.locator('.verification .demo-hint .num').textContent();
    await page.locator('#verify-form [name=digits]').fill(code.trim());
    await page.locator('#verify-form .customer-primary').click();
    await expect(page.locator('#customer-form')).toBeVisible();
  }
  await verify();
  const tomorrow=new Date(Date.now()+23400000+86400000).toISOString().slice(0,10);
  await page.locator('[name=latitude]').fill('16.8');
  await page.locator('[name=longitude]').fill('96.1');
  await page.locator('[name=initial_pin_acknowledged]').focus();
  await page.locator('[name=initial_pin_acknowledged]').press('Space');
  await expect(page.locator('[name=initial_pin_acknowledged]')).toBeChecked();
  await page.locator('#customer-form [name=date]').fill(tomorrow);
  await page.locator('#customer-form [name=time]').selectOption('12:00–14:00');
  await page.locator('#customer-form .customer-primary').click();
  await expect(page.locator('.delivery-request-confirmed')).toContainText('11:00');
  await expect(page.locator('.delivery-request-confirmed')).toContainText('3 edits remain');
  const row=await inspect(page,'/api/orders/'+id);
  expect(row.delivery_time_window).toBe(`${tomorrow}T05:30:00+00:00/${tomorrow}T07:30:00+00:00`);
  await page.reload();
  await verify();
  for(let i=1;i<=3;i++){
    const edit=page.locator('[data-action=edit-customer]');
    if(await edit.count())await edit.click();
    if(!await page.locator('[name=initial_pin_acknowledged]').isChecked()){
      await page.locator('[name=initial_pin_acknowledged]').focus();
      await page.locator('[name=initial_pin_acknowledged]').press('Space');
    }
    await page.locator('#customer-form [name=note]').fill('Fictional amendment '+i);
    await page.locator('#customer-form .customer-primary').click();
    if(i<3)await expect(page.locator('.delivery-request-confirmed')).toContainText(`${3-i} edits remain`);
  }
  await expect(page.locator('.customer-notice')).toContainText('view-only');
  await expect(page.locator('#customer-form')).toHaveCount(0);
  await page.goto('/#/order/'+id);
  await expect(page.locator('[data-action=approve-location]')).toBeVisible();
  await page.locator('[data-action=approve-location]').click();
  await page.locator('dialog [name=reason]').fill('Reviewed fictional buyer point');
  await page.locator('dialog button[type=submit]').click();
  await expect(page.locator('dialog')).toHaveCount(0);
  expect(Number((await inspect(page,'/api/orders/'+id)).latitude)).toBe(16.8);
});
