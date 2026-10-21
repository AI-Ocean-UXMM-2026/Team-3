import test from 'node:test';
import assert from 'node:assert/strict';
import {planningRequest} from '../js/routing-ui.mjs';

function form(){
  const f=new FormData();
  for(const [k,v]of Object.entries({latitude:'16.8',longitude:'96.1',start:'2026-12-01T08:00',end:'2026-12-01T18:00',service_seconds:'180',mode:'DRIVE',objective:'duration',solver_seconds:'1','rider-r1':'on','capacity-r1':'5','order-o1':'on',allow_simulation:'on',return_to_hub:'on'}))f.set(k,v);
  return f;
}
const snapshot={orders:[{id:'o1'},{id:'o2'}],riders:[{id:'r1'},{id:'r2'}]};
test('planner maps only selected canonical IDs and explicit capacities',()=>{
  const q=planningRequest(form(),snapshot);
  assert.deepEqual(q.orders,[{order_id:'o1',demand:1,service_seconds:180}]);
  assert.deepEqual(q.riders,[{rider_id:'r1',capacity:5}]);
  assert.equal(q.operating_window.start,'2026-12-01T08:00:00+06:30');
  assert.equal(q.allow_simulation,true);assert.equal(q.return_to_hub,true);
});
test('simulation and return-to-hub are explicit request flags',()=>{
  const f=form();f.delete('allow_simulation');f.delete('return_to_hub');
  const q=planningRequest(f,snapshot);assert.equal(q.allow_simulation,false);assert.equal(q.return_to_hub,false);
});
for(const value of ['', 'NaN', '91'])test('invalid hub latitude is never invented: '+JSON.stringify(value),()=>{
  const f=form();f.set('latitude',value);assert.throws(()=>planningRequest(f,snapshot),/valid hub/);
});
