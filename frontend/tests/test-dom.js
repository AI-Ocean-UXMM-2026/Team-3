// Minimal DOM adapter for controller tests in Node. It does not render pages,
// execute HTML, emulate a browser, or validate CSS/accessibility layout.
const decode=s=>String(s).replace(/&(?:amp|lt|gt|quot|#39|#10);/g,x=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'",'&#10;':'\n'}[x]));
class Element {
  constructor(tag,attributes={}){this.tagName=tag;this.attributes=attributes;this.children=[];this.style={};this.parent=null;this._value=undefined;this.checked='checked'in attributes;this.disabled='disabled'in attributes;this.classList={add:(...xs)=>this.classes(xs,true),remove:(...xs)=>this.classes(xs,false),toggle:(x,on)=>{const has=(this.attributes.class||'').split(' ').includes(x);this.classes([x],on==null?!has:on);}};this.dataset=new Proxy({}, {get:(_,key)=>this.attributes['data-'+String(key).replace(/[A-Z]/g,c=>'-'+c.toLowerCase())]});}
  classes(xs,on){const set=new Set((this.attributes.class||'').split(' ').filter(Boolean));for(const x of xs)on?set.add(x):set.delete(x);this.attributes.class=[...set].join(' ');}
  append(el){el.parent=this;this.children.push(el);}
  appendChild(el){this.append(el);}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}
  set innerHTML(html){this.children=[];const stack=[this],voids=new Set(['input','br','hr','img','meta','link']);for(const token of html.match(/<[^>]*>|[^<]+/g)||[]){if(token.startsWith('</')){const tag=token.slice(2,-1).trim();for(let i=stack.length-1;i>0;i--)if(stack[i].tagName===tag){stack.length=i;break;}}else if(token.startsWith('<')){const m=token.match(/^<([a-zA-Z][\w-]*)([\s\S]*?)\/?\s*>$/);if(!m)continue;const attrs={};for(const a of m[2].matchAll(/([\w:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g))attrs[a[1]]=decode(a[2]??a[3]??a[4]??'');const el=new Element(m[1].toLowerCase(),attrs);stack.at(-1).append(el);if(!voids.has(el.tagName))stack.push(el);}else stack.at(-1).children.push(decode(token));}}
  get innerHTML(){return this.children.map(x=>typeof x==='string'?x:`<${x.tagName} ${Object.entries(x.attributes).map(([k,v])=>`${k}="${v}"`).join(' ')}>${x.innerHTML}</${x.tagName}>`).join('');}
  get textContent(){return this.children.map(x=>typeof x==='string'?x:x.textContent).join('');}
  set textContent(text){this.children=[String(text)];}
  get value(){if(this._value!==undefined)return this._value;if(this.tagName==='textarea')return this.textContent;if(this.tagName==='select'){const opts=this.querySelectorAll('option');const selected=opts.find(x=>'selected'in x.attributes)||opts[0];return selected?selected.attributes.value??selected.textContent:'';}return this.attributes.value||'';}
  set value(v){this._value=String(v);}
  matches(selector){return selector.split(',').some(s=>{s=s.trim();const parts=s.split(/\s+/);if(parts.length>1){if(!this.matches(parts.pop()))return false;for(let p=this.parent;p;p=p.parent)if(p.matches(parts.join(' ')))return true;return false;}if(s.startsWith('#'))return this.attributes.id===s.slice(1);const tag=s.match(/^[\w-]+/)?.[0];if(tag&&this.tagName!==tag)return false;for(const cls of s.matchAll(/\.([\w-]+)/g))if(!(this.attributes.class||'').split(' ').includes(cls[1]))return false;for(const a of s.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g))if(!(a[1]in this.attributes)||a[2]!==undefined&&this.attributes[a[1]]!==a[2])return false;return true;});}
  querySelectorAll(selector){const results=[];for(const el of this.children){if(typeof el==='string')continue;if(el.matches(selector))results.push(el);results.push(...el.querySelectorAll(selector));}return results;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  showModal(){this.open=true;}
  close(){this.open=false;this.onclose?.();}
  getBoundingClientRect(){return {left:0,top:0,width:360,height:360};}
  click(){return this.onclick?.({target:this,currentTarget:this,preventDefault(){}});}
}
class FormValues {
  constructor(form){this.data=new Map();for(const el of form.querySelectorAll('[name]')){if(el.disabled)continue;if(['checkbox','radio'].includes(el.attributes.type)&&!el.checked)continue;this.data.set(el.attributes.name,el.value||(['checkbox','radio'].includes(el.attributes.type)?'on':''));}}
  get(key){return this.data.get(key)??null;}
  has(key){return this.data.has(key);}
  [Symbol.iterator](){return this.data[Symbol.iterator]();}
}
function environment(storage,hash='#/dispatch'){
  const body=new Element('body');body.innerHTML='<div id="app"></div><div id="toast"></div>';
  const listeners={},timers=new Map();let elapsed=0,nextId=1,currentHash=hash;
  const location={href:'file:///prototype/index.html'+hash,get hash(){return currentHash;},set hash(value){if(value===currentHash)return;currentHash=value;location.href='file:///prototype/index.html'+value;listeners.hashchange?.();}};
    const win={LANNPYA_RUNTIME:{mode:'DEMO_SIMULATION'},LannPyaDemoRiderAuth:require('../js/demo-rider-auth.js'),localStorage:storage,addEventListener:(name,fn)=>listeners[name]=fn};
  const ctx={window:win,document:{body,querySelector:s=>body.querySelector(s),querySelectorAll:s=>body.querySelectorAll(s),createElement:tag=>new Element(tag)},location,navigator:{onLine:true,clipboard:{writeText:async text=>{ctx.clipboard=text;}}},FormData:FormValues,console,URL,Blob,setTimeout:(fn,ms)=>{const id=nextId++;timers.set(id,{fn,at:elapsed+ms});return id;},clearTimeout:id=>timers.delete(id)};
  return {ctx,body,get root(){return body.querySelector('#app');},find:s=>body.querySelector(s),all:s=>body.querySelectorAll(s),async tick(ms){elapsed+=ms;for(let n=0;n<10;n++){const due=[...timers.entries()].filter(([,v])=>v.at<=elapsed);if(!due.length){await Promise.resolve();continue;}for(const [id,v]of due){timers.delete(id);v.fn();}await Promise.resolve();}},async action(name,id){const button=body.querySelectorAll('[data-action]').find(b=>b.dataset.action===name&&(id==null||b.dataset.id===id));if(!button)throw Error(`Missing action ${name}/${id}`);await button.click();},async submit(selector,fields={}){const form=body.querySelector(selector);if(!form)throw Error('Missing form '+selector);for(const [name,value]of Object.entries(fields)){const el=form.querySelectorAll('[name]').find(x=>x.attributes.name===name);if(!el)throw Error('Missing field '+name);if(typeof value==='boolean')el.checked=value;else el.value=value;}return form.onsubmit({preventDefault(){}});}};
}
module.exports={environment};
