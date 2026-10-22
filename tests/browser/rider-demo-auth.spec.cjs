const {test,expect}=require('./fixtures.cjs');
const path=require('node:path');
const invitations=[['LP-7Q4K','LannPyaDemo!1234'],['LP-8M2R','LannPyaDemo!2468'],['LP-3N9T','LannPyaDemo!4826']];
async function loginPage(page){
  await page.route('https://fonts.googleapis.com/**',route=>route.fulfill({contentType:'text/css',body:''}));
  await page.addInitScript(()=>{if(!localStorage.getItem('rider-demo-test-initialized')){localStorage.setItem('lannpya.signedOut',JSON.stringify({rider:true}));localStorage.setItem('rider-demo-test-initialized','yes');}});
  await page.goto('/#/ride');await expect(page.locator('#signin-form')).toBeVisible();
}
test('all on-page demo invitations enroll Gmail and sign in with passwords, without PIN boxes',async({page})=>{
  await page.setViewportSize({width:390,height:844});await loginPage(page);
  await expect(page.locator('.pin-boxes')).toHaveCount(0);await expect(page.locator('#signin-form [name=email]')).toHaveAttribute('type','email');
  for(const [index,[code,password]] of invitations.entries()){
    if(index){await page.locator('.rider-menu summary').click();await page.locator('[data-action=sign-out][data-id=rider]').click();await page.locator('dialog button[type=submit]').click();await expect(page.locator('#signin-form')).toBeVisible();}
    await page.locator('[data-action=signin-mode][data-id=invite]').click();
    await expect(page.locator('#signin-form [name=phone]')).toHaveCount(0);
    for(const [sample] of invitations)await expect(page.locator(`[data-action=demo-invite-code][data-id="${sample}"]`)).toBeVisible();
    await page.locator(`[data-action=demo-invite-code][data-id="${code}"]`).click();
    await expect(page.locator('#signin-form [name=code]')).toHaveValue(code);
    await page.locator('#signin-form [name=email]').fill(`rider.stage${index}@gmail.com`);
    if(index===0&&process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'rider-gmail-invite.png'),fullPage:true,animations:'disabled'});
    await page.locator('#signin-form button[type=submit]').click();
    await expect(page.locator('#signin-form .demo-hint')).toContainText(password);await expect(page.locator('#signin-form .demo-hint')).toContainText('No email was sent');
    await expect(page.locator('#signin-form [name=email]')).toHaveValue(`rider.stage${index}@gmail.com`);
    await page.locator('#signin-form [name=password]').fill('wrong-password');await page.locator('#signin-form button[type=submit]').click();await expect(page.locator('#signin-form .form-error')).toContainText('password is wrong');
    await page.locator('#signin-form [name=password]').fill(password);
    if(index===0&&process.env.LANNPYA_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.LANNPYA_SCREENSHOT_DIR,'rider-gmail-password.png'),fullPage:true,animations:'disabled'});
    await page.locator('#signin-form button[type=submit]').click();await expect(page.locator('.rider-head')).toBeVisible();await expect(page.locator('#signin-form')).toHaveCount(0);
  }
});
test('demo enrollment rejects invalid Gmail and unknown codes',async({page})=>{
  await loginPage(page);await page.locator('[data-action=signin-mode][data-id=invite]').click();
  await page.locator('#signin-form [name=code]').fill('LP-7Q4K');await page.locator('#signin-form [name=email]').fill('rider@example.com');await page.locator('#signin-form button[type=submit]').click();await expect(page.locator('#signin-form .form-error')).toContainText('Gmail');
  await page.locator('#signin-form [name=email]').fill('rider@gmail.com');await page.locator('#signin-form [name=code]').fill('FAKE-CODE');await page.locator('#signin-form button[type=submit]').click();await expect(page.locator('#signin-form .form-error')).toContainText('code');
  await expect(page.locator('#signin-form [name=code]')).toBeVisible();
});
