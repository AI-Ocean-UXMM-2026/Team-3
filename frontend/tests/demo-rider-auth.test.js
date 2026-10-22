const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create,INVITES}=require('../js/demo-rider-auth.js');
const memory=()=>{const values=new Map();return {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};};
test('each published demo invitation enrolls Gmail and provides its working password',()=>{
  const auth=create(memory(),'DEMO_SIMULATION');
  for(const [index,invite] of INVITES.entries()){
    const email=`rider${index}@gmail.com`,account=auth.enroll(email,invite.code);
    assert.ok(account.password.length>=12);assert.equal(auth.signIn(email,account.password).email,email);
    assert.throws(()=>auth.signIn(email,'wrong-password'),/password/);
  }
});
test('Gmail and invitation validation reject invalid accounts and arbitrary codes',()=>{
  const auth=create(memory(),'LIVE_BACKEND');
  for(const email of ['', 'rider', 'rider@example.com', 'x@gmail.com.attacker.test'])assert.throws(()=>auth.enroll(email,INVITES[0].code),/Gmail/);
  assert.throws(()=>auth.enroll('rider@gmail.com','FAKE-CODE'),/code/);
  assert.throws(()=>auth.signIn('unknown@gmail.com','LannPyaDemo!1234'),/invite/i);
});
test('enrollment survives reload and normalizes Gmail and invitation code',()=>{
  const storage=memory(),auth=create(storage,'LIVE_BACKEND');
  const account=auth.enroll(' Rider.One@GMAIL.COM ',' lp-8m2r ',{riderId:'rider-2'});
  assert.equal(account.email,'rider.one@gmail.com');
  assert.equal(create(storage,'LIVE_BACKEND').signIn(account.email,account.password).riderId,'rider-2');
});
test('demo codes are reusable for show rehearsals but never accepted in secure mode',()=>{
  const auth=create(memory(),'DEMO_SIMULATION');
  auth.enroll('one@gmail.com',INVITES[0].code);auth.enroll('two@gmail.com',INVITES[0].code);
  assert.throws(()=>create(memory(),'SUPABASE_BACKEND'),/demo/i);
});
test('the supplied demo Gmail works immediately without enrollment',()=>{
  const auth=create(memory(),'LIVE_BACKEND');
  assert.equal(auth.signIn('rider.demo@gmail.com','LannPyaDemo!1234').email,'rider.demo@gmail.com');
});
