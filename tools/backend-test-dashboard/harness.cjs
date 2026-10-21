// Lightweight DOM harness only; not a visual browser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const base = path.join(__dirname, '../../backend/tools/backend_test_dashboard/static');
const source = fs.readFileSync(path.join(base, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(base, 'index.html'), 'utf8');

class Element {
  constructor(id='',tag='') { this.id=id; this.tag=tag; this.children=[]; this.events={}; this._value=''; this.checked=false; this.textContent=''; this.dataset={}; this.hidden=false; this.classList={toggle(){}}; }
  get value() { return this.tag==='select' ? (this.children.some(c=>c.value===this._value)?this._value:this.children[0]?.value??'') : this._value; }
  set value(v) { this._value=String(v); }
  set innerHTML(_) { throw new Error('Unsafe HTML insertion attempted'); }
  append(...nodes) { for(const node of nodes){ node.parent=this;this.children.push(node); } }
  prepend(node) { node.parent=this;this.children.unshift(node); }
  replaceChildren(...nodes) {this.children=[];this.append(...nodes);}
  remove() {this.parent.children=this.parent.children.filter(n=>n!==this);}
  get lastElementChild() {return this.children.at(-1);}
  addEventListener(name, handler) {(this.events[name]??=[]).push(handler);}
  async trigger(name) {for(const fn of this.events[name]??[])await fn();}
}

async function load(override) {
  const nodes=new Map();
  for(const m of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*\bid="([^"]+)"[^>]*)>/g)) {
    const element=new Element(m[3],m[1]);
    const value=m[2].match(/\bvalue="([^"]*)"/);if(value)element.value=value[1];
    if(m[1]==='textarea')element.value=html.slice(m.index+m[0].length).split('</textarea>')[0];
    if(m[1]==='select')for(const option of html.slice(m.index+m[0].length).split('</select>')[0].matchAll(/<option(?: value="([^"]*)")?>([^<]*)<\/option>/g)) {
      const child=new Element('','option');child.value=option[1]??option[2];child.textContent=option[2];element.append(child);
    }
    nodes.set(m[3],element);
  }
  const intervals=[];
  const tabs=['parser','orders','buyer','dispatcher','rider','console'].map(name=>{const e=new Element();e.dataset.tab=name;return e;});
  const calls=[];
  const response=(status,data)=>({status,ok:status>=200&&status<300,json:async()=>data});
  const fetch=async(url,options={})=>{
    const payload=options.body?JSON.parse(options.body):null; calls.push({url,options,payload});
    const customized=await override?.(url,payload,options);
    if(customized)return response(customized.status,customized.data);
    if(url==='/dashboard/bootstrap')return response(200,{csrf:'test-csrf',test_mode:true,merchant_id:'merchant-fixture',ai:'MOCK',database:'temporary',transitions:{DRAFT:['NEEDS_REVIEW']},buyers:[]});
    let data={};
    if(payload?.path==='/health')data={status:'ok'};
    else if(payload?.path.startsWith('/api/riders'))data={items:[],total:0};
    else if(payload?.path.startsWith('/api/orders?'))data={items:[],total:0};
    else if(payload?.path==='/api/orders/parse')data={original_text:payload.body.raw_text,confidence:'AMBER'};
    return response(200,{method:payload?.method,endpoint:payload?.path,status:200,ok:true,duration_ms:1,data});
  };
  const context={
    document:{hidden:false,getElementById:id=>{if(!nodes.has(id))throw Error('Missing DOM control '+id);return nodes.get(id);},createElement:tag=>new Element('',tag),querySelectorAll:q=>q==='[data-tab]'?tabs:q==='section.panel'?tabs.map(t=>nodes.get(t.dataset.tab)):[]},
    fetch,crypto:webcrypto,URLSearchParams,location:{hash:''},setInterval(fn){intervals.push(fn);},
    Option:class extends Element {constructor(text,value){super('','option');this.textContent=text;this.value=value;}},
  };
  await vm.runInNewContext(`(async()=>{${source}\n})()`,context);
  return {nodes,calls,intervals};
}


module.exports={load};
