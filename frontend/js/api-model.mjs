import {createDevelopmentApi, createBuyerApi, ApiError} from './backend-client.mjs';

export {ApiError};
export const today = () => new Date(Date.now()+23400000).toISOString().slice(0,10);
export const townships = ['Hlaing','Kamayut','San Chaung','Bahan','Mayangon','Insein','Yankin','Tamwe','Thingangyun','South Okkalapa','North Okkalapa','North Dagon','South Dagon','East Dagon','Dagon Seikkan'];
export const context = order => order.parsing_metadata?.parcel || {};
export function mmk(value) {
  if (typeof value !== 'string' || !/^\d+$/.test(value) || BigInt(value)>1000000000n) throw Error('Enter a whole MMK amount from 0 to 1,000,000,000.');
  return value.replace(/^0+(?=\d)/,'');
}
export function tokenFrom(value) {
  const match=String(value).trim().match(/(?:track\/|confirm\/)([A-Za-z0-9_-]{43})(?:$|[?#\s])/);
  const token=match?.[1]||String(value).trim();
  if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw Error('Paste the complete customer link or its secret token.');
  return token;
}
export function manualPayload(fields) {
  fields={...fields,township:({'Kamaryut':'Kamayut','Sanchaung':'San Chaung'}[fields.township]||fields.township)};
  if(!fields.customer_name?.trim()||!fields.customer_phone?.trim()||!fields.item?.trim())throw Error('Enter recipient, phone and parcel description.');
  if(!townships.includes(fields.township))throw Error('Choose a supported township.');
  const cod=fields.payment==='prepaid'?'0':mmk(fields.cod_amount||'');
  if(fields.payment==='cod'&&cod==='0')throw Error('COD must be positive. Select prepaid for zero cash.');
  const structured={customer_name:fields.customer_name.trim(),customer_phone:fields.customer_phone.trim(),township:fields.township,cod_amount:cod,delivery_time_window:'Any time'};
  for(const key of ['street','landmark','floor','delivery_instructions'])if(fields[key]?.trim())structured[key]=fields[key].trim();
  if(fields.latitude||fields.longitude){
    if(!fields.latitude||!fields.longitude)throw Error('Enter both coordinates or leave both blank.');
    structured.latitude=fields.latitude;structured.longitude=fields.longitude;
  }
  return {structured,parcel:{item:fields.item.trim(),sender:fields.sender?.trim()||null,reference:fields.reference?.trim()||null,delivery_day:fields.delivery_day,hub_received:!!fields.hub_received}};
}

// All credentials live in closures/memory, never localStorage, URLs or source.
export class WorkspaceApi {
  constructor(){this.connections={};this.buyer=null;}
  async connect(side,baseUrl,token){
    const client=createDevelopmentApi({baseUrl,token});
    const actor=await client('/api/session');
    if(side==='admin'&&!['Admin','Dispatcher'].includes(actor.role)||side==='rider'&&actor.role!=='Rider')throw Error(`This credential belongs to ${actor.role}, not ${side}. Use the matching server and token.`);
    this.connections[side]={client,actor,baseUrl};return actor;
  }
  disconnect(side){delete this.connections[side];}
  async call(side,path,options){
    const conn=this.connections[side];if(!conn)throw Error('Connect this side to its backend first.');
    try{return await conn.client(path,options);}catch(error){if(error.status===401)this.disconnect(side);throw error;}
  }
  async all(side,path){
    const rows=[];
    for(let page=1;page<=1000;page++){
      const data=await this.call(side,`${path}${path.includes('?')?'&':'?'}page=${page}&page_size=100`);rows.push(...data.items);
      if(rows.length>=data.total)return rows;
    }
    throw Error('Result is too large for this local workspace; narrow the order search.');
  }
  create(fields){return this.call('admin','/api/orders',{method:'POST',body:manualPayload(fields)});}
  order(id){return this.call('admin',`/api/orders/${encodeURIComponent(id)}`);}
  patch(order,fields){return this.call('admin',`/api/orders/${order.id}`,{method:'PATCH',body:{expected_version:order.version,...fields}});}
  status(order,status,acknowledge=false){return this.call('admin',`/api/orders/${order.id}/status`,{method:'PATCH',body:{expected_version:order.version,status,acknowledge_unverified_location:acknowledge}});}
  async ready(order,acknowledge){
    if(!acknowledge)throw Error('Review the delivery point and explicitly acknowledge its unverified map accuracy.');
    let row=order;
    if(row.status==='DRAFT')row=await this.status(row,'NEEDS_REVIEW');
    if(['NEEDS_REVIEW','AWAITING_CONFIRMATION'].includes(row.status))row=await this.status(row,'CONFIRMED');
    if(row.status==='CONFIRMED')row=await this.status(row,'READY_FOR_DISPATCH',true);
    return row;
  }
  operation(order,action,reason){return this.call('admin',`/api/orders/${order.id}/operations`,{method:'POST',body:{expected_version:order.version,action,reason:reason||null}});}
  autoAssignment(order,{received=false,acknowledge=false}={},request_id=crypto.randomUUID()){
    return this.call('admin',`/api/orders/${order.id}/auto-assignment`,{method:'POST',body:{request_id,expected_version:order.version,acknowledge_unverified_location:!!acknowledge,receive_at_hub:!!received}});
  }
  routeAction(side,route,action,extra={},request_id=crypto.randomUUID()){
    return this.call(side,`/api/routes/${route.id}/actions`,{method:'POST',body:{request_id,expected_version:route.version,action,...extra}});
  }
  delivery(order,action,extra={},request_id=crypto.randomUUID()){
    const rider=this.connections.rider?.actor.id;
    return this.call('rider',`/api/riders/${rider}/deliveries/${order.order_id}/status`,{method:'PATCH',body:{request_id,expected_version:order.order_version,action,...extra}});
  }
  respondToOffer(order,action,request_id=crypto.randomUUID()){
    const rider=this.connections.rider?.actor.id;
    if(!rider)throw Error('Connect the assigned rider before responding to an offer.');
    if(!['ACCEPT','DECLINE'].includes(action))throw Error('Choose ACCEPT or DECLINE for a pending rider offer.');
    if(!order.assignment_id||!Number.isInteger(order.offer_version))throw Error('Refresh the rider queue; this offer is stale or unavailable.');
    return this.call('rider',`/api/riders/${rider}/deliveries/${order.order_id}/status`,{method:'PATCH',body:{request_id,expected_version:order.order_version,action,assignment_id:order.assignment_id,offer_version:order.offer_version}});
  }
  openBuyer(baseUrl,value){this.buyer?.clear();this.buyer=createBuyerApi({baseUrl,linkToken:tokenFrom(value)});return this.buyer;}
}
