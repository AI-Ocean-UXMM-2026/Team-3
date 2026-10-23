import {WorkspaceApi} from './api-model.mjs';
import {createBuyerApi,ApiError} from './backend-client.mjs';

export class AuthenticatedWorkspaceApi extends WorkspaceApi {
  #buyerClients=new Map();
  constructor(auth,baseUrl){super();this.auth=auth;this.baseUrl=baseUrl;}
  async connect(side,_baseUrl,actorId){
    const client=async(path,{method='GET',body}={})=>{
      if(!path.startsWith('/api/')||path.includes('\\')||path.includes('..'))throw Error('Use a workspace API path.');
      const token=await this.auth.accessToken();
      const response=await fetch(this.baseUrl+path,{method,credentials:'omit',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(45000),headers:{Authorization:'Bearer '+token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
      let data;try{data=await response.json();}catch{throw Error('The workspace returned an unreadable response. Try again.');}
      if(!response.ok){
        if(response.status===401){await this.auth.client.auth.signOut({scope:'local'});location.reload();}
        throw new ApiError(response.status,data.error?.code||'HTTP_ERROR',data.error?.message||'The request failed. Try again.');
      }
      return data;
    };
    const actor=await client('/api/session');
    if(side==='admin'&&!['Admin','Dispatcher'].includes(actor.role)||side==='rider'&&actor.role!=='Rider'||actorId&&actor.id!==actorId)throw Error('This account cannot open that workspace.');
    this.connections[side]={client,actor,baseUrl:this.baseUrl};return actor;
  }
  openBuyer(_baseUrl,token,initialAuth){
    let client=this.#buyerClients.get(token);
    if(!client){client=createBuyerApi({baseUrl:this.baseUrl,linkToken:token,initialAuthorization:initialAuth});this.#buyerClients.set(token,client);}
    else if(initialAuth)client.setAuthorization(initialAuth);
    this.buyer=client;return client;
  }
  async lookupBuyer(trackingId,phone){return (await import('./backend-client.mjs')).lookupBuyerOrder({baseUrl:this.baseUrl,trackingId,phone});}
}
