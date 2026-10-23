// Public Supabase configuration only. Roles are resolved by the backend, never metadata.
export function passwordProblem(value){
  if(value.length<12)return 'Use at least 12 characters. A few unrelated words work well.';
  if(value.length>128)return 'Use no more than 128 characters.';
  if(/^(password\d*|123456.*|qwerty.*|lannpya.*)$/i.test(value))return 'Choose a less common password.';
  return '';
}
export function publicAuthConfig(config){
  const {supabaseUrl,supabaseKey,apiBase}=config||{};
  let url,api;
  try{url=new URL(supabaseUrl);api=new URL(apiBase);}catch{throw Error('Sign-in is not configured. Ask your hub to finish setup.');}
  if(url.protocol!=='https:')throw Error('Supabase requires HTTPS.');
  if(url.origin!==url.href.replace(/\/$/,'')||url.username||url.password)throw Error('Use a Supabase origin without a path.');
  if(api.protocol!=='https:'&&!(['localhost','127.0.0.1'].includes(api.hostname)&&api.protocol==='http:'))throw Error('The backend requires HTTPS.');
  if(api.origin!==api.href.replace(/\/$/,'')||api.username||api.password)throw Error('Use a backend origin without a path.');
  // Legacy anon keys are supported, but service_role keys must never enter a browser bundle.
  let anon=false;
  try{anon=JSON.parse(atob(String(supabaseKey).split('.')[1].replaceAll('-','+').replaceAll('_','/'))).role==='anon';}catch{}
  if(!String(supabaseKey).startsWith('sb_publishable_')&&!anon)throw Error('Use a Supabase publishable key, never a secret or service-role key.');
  return {supabaseUrl:url.origin,supabaseKey,apiBase:api.origin};
}
export function createAuthService(client){
  const checked=async(promise,message)=>{const result=await promise;if(result.error)throw Error(result.error.status===429?'Too many attempts. Wait a minute and try again.':message);return result.data;};
  return {
    client,
    signIn:(identifier,password)=>{
      const value=identifier.trim();
      const identity=value.includes('@')?{email:value}:{phone:value.startsWith('09')?'+95'+value.slice(1).replace(/\s/g,''):value.replace(/\s/g,'')};
      return checked(client.auth.signInWithPassword({...identity,password}),'Email or password is incorrect, or the email still needs verification.');
    },
    signUp:async(email,password,profile={})=>{const problem=passwordProblem(password);if(problem)throw Error(problem);return checked(client.auth.signUp({email,password,options:{data:{shop_name:String(profile.shop||'').trim().slice(0,200),contact_phone:String(profile.phone||'').trim().slice(0,32),role:profile.role==='Rider'?'Rider':'Dispatcher'}}}),'Could not create the account. Try again later.');},
    sendCode:email=>checked(client.auth.signInWithOtp({email,options:{shouldCreateUser:false}}),'Could not send a code. Check your email and try again later.'),
    verifyCode:(email,token)=>checked(client.auth.verifyOtp({email,token,type:'email'}),'That code is invalid or expired. Request a new one.'),
    recover:email=>checked(client.auth.resetPasswordForEmail(email),'Could not send a recovery code. Try again later.'),
    verifyRecovery:(email,token)=>checked(client.auth.verifyOtp({email,token,type:'recovery'}),'That recovery code is invalid or expired. Request a new one.'),
    updatePassword:async password=>{const problem=passwordProblem(password);if(problem)throw Error(problem);return checked(client.auth.updateUser({password}),'Could not update the password. Request a new recovery code.');},
    signOut:()=>checked(client.auth.signOut({scope:'local'}),'Could not sign out. Check your connection and try again.'),
    async accessToken(){const {data,error}=await client.auth.getSession();if(error||!data.session)throw Error('Your session ended. Sign in again.');return data.session.access_token;}
  };
}
