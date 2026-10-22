/* Local show/rehearsal credentials only. Never used to authenticate a Supabase account. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LannPyaDemoRiderAuth=api;})(globalThis,function(){
  'use strict';
  const INVITES=Object.freeze([
    Object.freeze({code:'LP-7Q4K',password:'LannPyaDemo!1234'}),
    Object.freeze({code:'LP-8M2R',password:'LannPyaDemo!2468'}),
    Object.freeze({code:'LP-3N9T',password:'LannPyaDemo!4826'})
  ]);
  function gmail(value){
    const email=String(value||'').trim().toLowerCase();
    if(!/^[a-z0-9][a-z0-9.+_-]{0,63}@gmail\.com$/.test(email))throw Error('Enter a valid Gmail address, such as rider@gmail.com.');
    return email;
  }
  function create(storage,mode){
    if(!['DEMO_SIMULATION','LIVE_BACKEND'].includes(mode))throw Error('These invitation codes are for the local demo only.');
    const key='lannpya.demo-rider-auth.v2.'+mode;
    let memory={};
    const accounts=()=>{try{const saved=JSON.parse(storage?.getItem(key)||'null');if(saved&&typeof saved==='object'&&!Array.isArray(saved))return saved;}catch{}return memory;};
    return {
      gmail,
      enroll(value,code,{riderId=null,verifiedInvite=false}={}){
        const email=gmail(value),normalized=String(code||'').trim().toUpperCase();
        const invitation=INVITES.find(item=>item.code===normalized);
        if(!invitation&&!verifiedInvite)throw Error('That invite code doesn’t work. Use a demo code below or ask your hub for a new one.');
        const account={email,password:invitation?.password||'LannPyaDemo!'+String(Math.floor(Math.random()*9000)+1000),riderId,delivery:'DEMO_PREVIEW'};
        memory={...accounts(),[email]:account};
        try{storage?.setItem(key,JSON.stringify(memory));}catch{/* The current rehearsal still works in memory. */}
        return {...account};
      },
      signIn(value,password){
        const email=gmail(value);
        const account=accounts()[email]||(email==='rider.demo@gmail.com'?{email,password:'LannPyaDemo!1234',riderId:null}:null);
        if(!account)throw Error('Use the invite code from your hub to register this Gmail first.');
        if(!password||password!==account.password)throw Error('That password is wrong. Check the demo email preview and try again.');
        return {...account};
      }
    };
  }
  return {create,INVITES};
});
