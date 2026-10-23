import {existingSignInView} from './signin-template.mjs';
import {publicAuthConfig,createAuthService,passwordProblem} from './auth.mjs';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export async function startAuthentication(runtime){
  const root=document.querySelector('#app');
  let config;
  try{config=publicAuthConfig(runtime);}catch{
    root.innerHTML='<main class="auth-setup panel"><img src="assets/brand/mark-dark.svg" width="48" height="48" alt="LannPya"><h1>Sign-in is being set up</h1><p>Your hub needs to connect its account service. Please try again after setup is complete.</p><button class="btn primary" onclick="location.reload()">Try again</button></main>';
    return new Promise(()=>{});
  }
  const {createClient}=await import('../vendor/supabase.mjs');
  // Honor the existing Keep me signed in checkbox; never put credentials in URLs.
  let remember=false;try{remember=!!localStorage.getItem('lannpya.auth');}catch{}
  const memory=new Map();
  const storage={
    getItem(key){try{return sessionStorage.getItem(key)||localStorage.getItem(key);}catch{return memory.get(key)||null;}},
    setItem(key,value){memory.set(key,value);try{(remember?localStorage:sessionStorage).setItem(key,value);(remember?sessionStorage:localStorage).removeItem(key);}catch{}},
    removeItem(key){memory.delete(key);try{sessionStorage.removeItem(key);localStorage.removeItem(key);}catch{}}
  };
  const client=createClient(config.supabaseUrl,config.supabaseKey,{auth:{storage,persistSession:true,autoRefreshToken:true,detectSessionInUrl:false,storageKey:'lannpya.auth'}});
  const service=createAuthService(client);
  globalThis.LannPyaAuth=service;
  if(/^#\/(customer|track\/)/.test(location.hash))return;
  let mode='signin',email='',message='',sendAfter=0,loading=false,finished=false;
  const resolveActor=async()=>{
    const token=await service.accessToken();
    const response=await fetch(config.apiBase+'/api/session',{headers:{Authorization:'Bearer '+token},credentials:'omit',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
    if(!response.ok){if(response.status===403)throw Error('Your email is verified. Ask your hub to enable your dispatcher or rider access.');throw Error(response.status===401?'Your session ended. Sign in again.':'The workspace could not be reached. Check your connection and retry.');}
    const actor=await response.json();
    if(!['Admin','Dispatcher','Rider'].includes(actor.role))throw Error('This account does not have workspace access. Ask your hub for help.');
    service.actor=actor;
    if(actor.role==='Rider'&&!location.hash.startsWith('#/ride'))location.hash='#/ride';
    if(actor.role!=='Rider'&&location.hash.startsWith('#/ride'))location.hash='#/dispatch';
    return actor;
  };
  return new Promise((resolve,reject)=>{
    const finish=async()=>{await resolveActor();finished=true;document.body.classList.remove('signed-out');resolve();};
    const title=()=>({signin:'Welcome back',signup:'Create your account',code:'Use an email code',verify:'Check your inbox',signupVerify:'Verify your email',recover:'Reset your password',recoverVerify:'Check your inbox',password:'Choose a new password',pending:'Your account is almost ready'})[mode];
    function render(){
      document.body.classList.add('signed-out');
      const code=['verify','signupVerify','recoverVerify'].includes(mode),newPassword=['signup','password'].includes(mode),emailInput=['signin','signup','code','recover'].includes(mode);
      const isRider=location.hash.startsWith('#/ride');
      const shell=document.createElement('div');
      shell.innerHTML=existingSignInView(isRider?'rider':'admin',mode==='signup'?'create':'signin');
      const existing=shell.firstElementChild;
      const originalForm=existing.querySelector('#signin-form');
      originalForm.id='auth-form';
      originalForm.setAttribute('aria-label','Sign in');
      originalForm.querySelector('.demo-hint')?.remove();
      originalForm.querySelectorAll('[data-action="signin-mode"]').forEach(button=>{button.removeAttribute('data-action');button.dataset.authMode=button.dataset.id==='create'?'signup':'signin';});
      let pane=originalForm.querySelector('.signin-pane') || originalForm;
      const tabs=originalForm.querySelector('.signin-tabs');
      if(!['signin','signup'].includes(mode)){tabs?.remove();pane.innerHTML='<h1>'+title()+'</h1>';}
      const demoEmail=isRider?'judge.rider@lannpya.dev':'judge.dispatch@lannpya.dev',demoPass='JudgeDemo2026!';
      if(mode==='signin'){
        const identifier=pane.querySelector('[name="phone"]')||pane.querySelector('[name="email"]');
        if(identifier){identifier.name='email';identifier.id='auth-email';identifier.value=email;identifier.required=true;identifier.autocomplete='username';}
        const password=pane.querySelector('[name="password"]');if(password){password.id='auth-password';password.setAttribute('aria-label','Password');if(email===demoEmail)password.value=demoPass;}
      }else if(mode==='signup'){
        const password=pane.querySelector('[name="password"]');password.id='auth-password';password.minLength=12;password.maxLength=128;password.setAttribute('aria-label','Password');
        password.parentElement.firstChild.textContent='Password, at least 12 characters';
        pane.insertAdjacentHTML('beforeend','<label>Verification email<input id="auth-email" name="email" type="email" autocomplete="email" required maxlength="254" value="'+esc(email)+'"></label><label>Confirm password<input id="auth-confirm" name="confirm" type="password" autocomplete="new-password" required maxlength="128"></label><p class="sheet-copy">Use at least 12 characters. Your hub enables access after email verification.</p>');
      }else{
        pane.insertAdjacentHTML('beforeend','<p class="sheet-copy">'+(code?'Enter the code sent to '+esc(email)+'. Check Spam if it hasn’t arrived.':mode==='password'?'Use a password you don’t use anywhere else.':mode==='pending'?'Your email is verified. Ask your hub to enable your account.':'Enter your account email. Gmail addresses work too.')+'</p>');
        if(emailInput)pane.insertAdjacentHTML('beforeend','<label>Email address<input id="auth-email" name="email" type="email" autocomplete="username" required maxlength="254" value="'+esc(email)+'"></label>');
        if(code)pane.insertAdjacentHTML('beforeend','<label>Email code<input id="auth-code" name="code" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6,10}" minlength="6" maxlength="10" required></label>');
        if(newPassword)pane.insertAdjacentHTML('beforeend','<label>New password · at least 12 characters<input id="auth-password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required aria-label="Password"></label><label>Confirm password<input id="auth-confirm" name="confirm" type="password" autocomplete="new-password" required maxlength="128"></label>');
      }
      const alert=originalForm.querySelector('.form-error');alert.id='auth-error';
      alert.insertAdjacentHTML('afterend','<p id="auth-status" class="sheet-copy" role="status">'+esc(message)+'</p>');
      const submit=originalForm.querySelector('.signin-go');submit.classList.add('auth-submit');submit.querySelector('.btn-label').textContent=loading?'Please wait…':mode==='signin'?'Sign in':mode==='signup'?'Create account':code?'Verify code':mode==='password'?'Save new password':mode==='pending'?'Check access again':'Send email code';submit.disabled=loading;
      originalForm.insertAdjacentHTML('beforeend',mode==='signin'?'<button type="button" class="btn quiet" data-auth-mode="code">Use an email code instead</button><button type="button" class="btn quiet" data-auth-mode="recover">Forgot password?</button>':code?'<button type="button" class="btn quiet" data-resend>Send a new code</button><button type="button" class="btn quiet" data-auth-mode="signin">Back to sign in</button>':mode==='signup'?'':'<button type="button" class="btn quiet" data-auth-mode="signin">Back to sign in</button>');
      originalForm.insertAdjacentHTML('beforeend','<button type="button" class="btn quiet" data-auth-logout hidden>Sign out of this account</button>');
      if(mode==='signin'){
        originalForm.insertAdjacentHTML('beforeend','<div class="judge-demo-card"><div class="judge-demo-head"><span class="judge-demo-badge"><span class="dot"></span>Judge / Demo Access</span><button type="button" class="judge-demo-fill-btn" data-demo-fill>Fill Demo Credentials</button></div><div class="judge-demo-creds"><div>Email: <code>'+demoEmail+'</code></div><div>Password: <code>'+demoPass+'</code></div></div></div>');
      }else if(mode==='signup'){
        originalForm.insertAdjacentHTML('beforeend','<div class="judge-demo-card"><div class="judge-demo-head"><span class="judge-demo-badge"><span class="dot"></span>Judge / Demo Access</span><button type="button" class="judge-demo-fill-btn" data-demo-switch>Switch to Demo Account</button></div><p class="judge-demo-note">Judges can test sign-up with any email (auto-enabled on OTP verify) or sign in directly with <code>'+demoEmail+'</code>.</p></div>');
      }
      root.innerHTML='<div class="app-shell"><main class="main"><section class="content"></section></main></div>';
      root.querySelector('.content').append(existing);
      requestAnimationFrame(()=>root.querySelector('.signin-brand')?.classList.add('play'));
      const form=root.querySelector('form'),error=root.querySelector('#auth-error');
      root.querySelectorAll('[data-auth-mode]').forEach(button=>button.onclick=()=>{if(loading)return;email=form.elements.email?.value.trim()||email;mode=button.dataset.authMode;message='';render();root.querySelector('input')?.focus();});
      root.querySelector('[data-demo-fill]')?.addEventListener('click',()=>{
        email=demoEmail;
        const em=form.querySelector('#auth-email')||form.querySelector('[name="email"]');
        const pw=form.querySelector('#auth-password')||form.querySelector('[name="password"]');
        if(em)em.value=demoEmail;
        if(pw)pw.value=demoPass;
        const btn=root.querySelector('[data-demo-fill]');
        if(btn){btn.textContent='✓ Filled';setTimeout(()=>{if(btn.isConnected)btn.textContent='Fill Demo Credentials';},2000);}
        form.querySelector('.auth-submit')?.focus();
      });
      root.querySelector('[data-demo-switch]')?.addEventListener('click',()=>{
        email=demoEmail;
        mode='signin';
        render();
        const em=root.querySelector('#auth-email')||root.querySelector('[name="email"]');
        const pw=root.querySelector('#auth-password')||root.querySelector('[name="password"]');
        if(em)em.value=demoEmail;
        if(pw)pw.value=demoPass;
        root.querySelector('.auth-submit')?.focus();
      });
      const cooldown=()=>{if(Date.now()<sendAfter)throw Error('Wait a minute before requesting another code.');sendAfter=Date.now()+60000;};
      root.querySelector('[data-resend]')?.addEventListener('click',async()=>{if(loading)return;loading=true;render();try{cooldown();if(mode==='recoverVerify')await service.recover(email);else if(mode==='signupVerify'){const result=await client.auth.resend({type:'signup',email});if(result.error)throw Error('Could not resend. Try again later.');}else await service.sendCode(email);message='A new code has been requested. Use the newest email.';}catch(e){message=e.message;}finally{loading=false;render();}});
      const logout=root.querySelector('[data-auth-logout]');client.auth.getSession().then(({data})=>{if(logout.isConnected)logout.hidden=!data.session;});
      logout.onclick=async()=>{if(loading)return;try{await service.signOut();mode='signin';message='You’re signed out.';render();}catch(e){error.textContent=e.message;}};
      form.onsubmit=async event=>{
        event.preventDefault();if(loading||!form.reportValidity())return;
        const values=new FormData(form);email=String(values.get('email')||email).trim();const password=String(values.get('password')||'');
        if(mode==='signin')remember=values.get('keep')==='on';
        if(newPassword){const problem=passwordProblem(password);if(problem){error.textContent=problem;return;}if(password!==values.get('confirm')){error.textContent='The passwords don’t match. Enter them again.';root.querySelector('#auth-confirm').focus();return;}}
        loading=true;root.querySelector('.auth-submit').disabled=true;root.querySelector('.auth-submit').textContent='Please wait…';error.textContent='';
        try{
          if(mode==='signin'){await service.signIn(email,password);await finish();}
          else if(mode==='signup'){await service.signUp(email,password,{shop:values.get('shop'),phone:values.get('phone'),role:isRider?'Rider':'Dispatcher'});mode='signupVerify';message='If the address can be registered, a verification email is on its way.';sendAfter=Date.now()+60000;}
          else if(mode==='code'){cooldown();await service.sendCode(email);mode='verify';message='If this account exists, a code is on its way.';}
          else if(mode==='recover'){cooldown();await service.recover(email);mode='recoverVerify';message='If this account exists, a recovery code is on its way.';}
          else if(mode==='verify'){await service.verifyCode(email,String(values.get('code')));await finish();}
          else if(mode==='signupVerify'){const result=await client.auth.verifyOtp({email,token:String(values.get('code')),type:'signup'});if(result.error)throw Error('That code is invalid or expired. Request a new one.');try{await finish();}catch(err){mode='pending';message=err.message||'Your email is verified.';}}
          else if(mode==='recoverVerify'){await service.verifyRecovery(email,String(values.get('code')));mode='password';message='Email verified. Set your new password.';}
          else if(mode==='password'){await service.updatePassword(password);await service.signOut();mode='signin';message='Password saved. Sign in with your new password.';}
          else await finish();
        }catch(e){message='';loading=false;render();root.querySelector('#auth-error').textContent=e.message;return;}
        finally{loading=false;}
        if(!finished){render();root.querySelector('#auth-title')?.focus();}
      };
    }
    async function boot(){
      client.auth.onAuthStateChange(event=>{if(finished&&event==='SIGNED_OUT')location.reload();});
      try{const {data}=await client.auth.getSession();if(data.session){await finish();return;}}catch(e){message=e.message;mode='pending';}
      render();
    }
    boot().catch(reject);
  });
}
