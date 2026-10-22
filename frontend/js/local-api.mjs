// Local integration boundary. Privileged and buyer API credentials stay on the server.
import {WorkspaceApi} from './api-model.mjs';
export {context, today, townships, mmk, tokenFrom} from './api-model.mjs';
import {ApiError} from './backend-client.mjs';

async function bridge(baseUrl) {
  const base=new URL(baseUrl);
  if(base.hostname!=='127.0.0.1'||base.protocol!=='http:'||base.username||base.password||base.search||base.hash||!['','/'].includes(base.pathname))throw Error('Use this local integration origin only.');
  if(globalThis.location?.origin && globalThis.location.origin!==base.origin)throw Error('Cross-origin privileged integration is disabled.');
  const request=async(path,body,csrf)=>{
    const response=await fetch(base.origin+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(body?.path?.startsWith('/api/routes/')?45000:15000),headers:body===undefined?{}:{'Content-Type':'application/json','X-Dashboard-CSRF':csrf},...(body===undefined?{}:{body:JSON.stringify(body)})});
    let result;try{result=await response.json();}catch{throw new ApiError(response.status,'INVALID_RESPONSE','Local API returned invalid JSON; refresh before retrying.');}
    if(!response.ok){const e=result.data?.error||result.error;throw new ApiError(response.status,e?.code||'HTTP_ERROR',e?.message||'Local API failed',e?.details||[],response.headers.get('Retry-After'));}
    return result;
  };
  const boot=await request('/dashboard/bootstrap');
  if(!boot.test_mode)throw Error('The local test boundary is required.');
  const call=async(path,options={},actor='dispatcher',rider_id=null,buyer_handle=null)=>{
    const result=await request('/dashboard/api',{method:options.method||'GET',path,body:options.body??null,actor,rider_id,buyer_handle},boot.csrf);
    const value=result.data;
    if(value?.buyer_handle)return {...value,confirmation_url:'/confirm/'+value.buyer_handle};
    return value;
  };
  const demoOtp=buyer_handle=>request('/dashboard/buyer-otp?buyer_handle='+encodeURIComponent(buyer_handle));
  return {call,demoOtp};
}

export class LocalWorkspaceApi extends WorkspaceApi {
  async connect(side,baseUrl,actorId){
    const local=await bridge(baseUrl);
    let riderId=null;
    if(side==='rider'){
      const riders=await local.call('/api/riders?page_size=100');
      const rider=riders.items.find(r=>r.id===actorId)||(!actorId?riders.items[0]:null);
      if(!rider)throw Error('Select an available local rider profile.');
      riderId=rider.id;
    }
    const client=(path,options)=>local.call(path,options,side==='rider'?'rider':'dispatcher',riderId);
    const actor=await client('/api/session');
    if(side==='admin'&&!['Admin','Dispatcher'].includes(actor.role)||side==='rider'&&actor.role!=='Rider')throw Error('Server identity does not match the selected workspace.');
    this.connections[side]={client,actor,baseUrl};return actor;
  }
  openBuyer(baseUrl,value){
    const handle=String(value).trim().match(/(?:track\/|confirm\/)([A-Za-z0-9_-]{43})(?:$|[?#\s])/)?.[1]||String(value).trim();
    if(!/^[A-Za-z0-9_-]{43}$/.test(handle))throw Error('Use a local customer link generated in this browser session.');
    let active=true;const local=bridge(baseUrl);
    const call=async(suffix,method='GET',body)=>{
      if(!active)throw Error('This buyer view was closed.');
      return (await local).call('/api/confirm/@buyer'+suffix,{method,body},'dispatcher',null,handle);
    };
    this.buyer?.clear();
    this.buyer={card:()=>call(''),requestOtp:()=>call('/otp','POST',{}),demoCode:async()=>{if(!active)throw Error('This buyer view was closed.');return (await local).demoOtp(handle);},verify:code=>call('/verify','POST',{code}),details:()=>call('/details'),location:body=>call('/location','PATCH',body),respond:body=>call('/response','PATCH',body),request:body=>call('/request','PATCH',body),clear:()=>{active=false;}};
    return this.buyer;
  }
}
