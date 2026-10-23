import {test} from 'node:test';
import assert from 'node:assert/strict';
import {passwordProblem, publicAuthConfig, createAuthService} from '../js/auth.mjs';

test('new passwords require length, reject common passwords and allow passphrases',()=>{
  assert.match(passwordProblem('short'),/12/);
  assert.match(passwordProblem('password123456'),/common/);
  assert.equal(passwordProblem('Three quiet rivers 47!'),'');
  assert.match(passwordProblem('x'.repeat(129)),/128/);
});
test('configuration rejects private keys and insecure project origins',()=>{
  const base={supabaseUrl:'https://example.supabase.co',supabaseKey:'sb_publishable_test',apiBase:'https://api.example.com'};
  assert.equal(publicAuthConfig(base).supabaseUrl,base.supabaseUrl);
  assert.throws(()=>publicAuthConfig({...base,supabaseKey:'sb_secret_private'}),/publishable/);
  assert.throws(()=>publicAuthConfig({...base,supabaseUrl:'http://example.supabase.co'}),/HTTPS/);
  assert.throws(()=>publicAuthConfig({...base,supabaseUrl:'https://example.supabase.co/path'}),/origin/);
});
test('email code cannot create accounts, and logout asks Supabase to revoke the session',async()=>{
  const calls=[];
  const service=createAuthService({auth:{
    signInWithOtp:async value=>{calls.push(value);return {error:null};},
    signOut:async value=>{calls.push(value);return {error:null};}
  }});
  await service.sendCode('rider@gmail.com');
  assert.equal(calls[0].options.shouldCreateUser,false);
  await service.signOut();assert.equal(calls[1].scope,'local');
});
test('failed login uses a generic error and recovery checks passwords before sending',async()=>{
  let updated=false;
  const service=createAuthService({auth:{
    signInWithPassword:async()=>({error:{message:'private account detail',status:400}}),
    updateUser:async()=>{updated=true;return {error:null};}
  }});
  await assert.rejects(service.signIn('a@example.com','bad'),/Email or password/);
  await assert.rejects(service.updatePassword('weak'),/12/);assert.equal(updated,false);
});

test('signup sends the selected public role and never requests admin access',async()=>{
  const calls=[],service=createAuthService({auth:{signUp:async body=>{calls.push(body);return {data:{},error:null};}}});
  for(const role of ['Rider','Dispatcher','Admin'])await service.signUp('new@example.test','Three quiet rivers 47!',{role});
  assert.deepEqual(calls.map(body=>body.options.data.role),['Rider','Dispatcher','Dispatcher']);
});
