// Delivery-point maps for dispatcher, buyer and rider.
// Google Maps is used when the backend provides a browser key (LANNPYA_GOOGLE_MAPS_BROWSER_KEY in backend/.env,
// served as /maps-config.js). Without a key, vendored Leaflet is used and no tile request occurs until asked.
(()=>{
  const YANGON={lat:16.8,lng:96.15};
  const valid=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a)<=90&&Math.abs(b)<=180;
  const key=()=>globalThis.LANNPYA_MAPS?.googleKey||'';
  let googleReady=null;
  function loadGoogle(){
    if(!key())return Promise.resolve(null);
    if(globalThis.google?.maps?.Map)return Promise.resolve(globalThis.google.maps);
    googleReady??=new Promise(resolve=>{
      globalThis.__lannpyaMapsReady=()=>resolve(globalThis.google.maps);
      const s=document.createElement('script');
      s.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key())}&libraries=places&loading=async&callback=__lannpyaMapsReady`;
      s.async=true;s.onerror=()=>{googleReady=null;resolve(null);};
      document.head.append(s);
    });
    return googleReady;
  }
  const mounted=[];
  function destroy(){while(mounted.length)mounted.pop()();}

  // Editable pin bound to a form's latitude/longitude fields.
  async function picker(form,{node,search,status,note}){
    if(!node)return;
    const latitude=form.querySelector('[name=latitude]'),longitude=form.querySelector('[name=longitude]');
    const current=()=>latitude.value!==''&&longitude.value!==''&&valid(Number(latitude.value),Number(longitude.value))?{lat:Number(latitude.value),lng:Number(longitude.value)}:null;
    const say=(a,b)=>{if(status)status.textContent=`Pinned at ${a.toFixed(6)}, ${b.toFixed(6)}. ${note}`;};
    const set=(a,b)=>{latitude.value=a.toFixed(7);longitude.value=b.toFixed(7);say(a,b);};
    const g=await loadGoogle();
    if(!form.isConnected)return;
    if(g){
      const start=current();
      const map=new g.Map(node,{center:start||YANGON,zoom:start?17:12,mapTypeControl:false,streetViewControl:false,fullscreenControl:false,clickableIcons:false});
      const marker=new g.Marker({map,position:start,draggable:true,title:'Delivery point'});
      const place=(p,zoom)=>{marker.setPosition(p);map.panTo(p);if(zoom)map.setZoom(17);set(p.lat(),p.lng());};
      map.addListener('click',e=>place(e.latLng));
      marker.addListener('dragend',()=>place(marker.getPosition()));
      if(search&&g.places?.Autocomplete){
        const ac=new g.places.Autocomplete(search,{componentRestrictions:{country:'mm'},fields:['geometry','name']});
        ac.addListener('place_changed',()=>{const loc=ac.getPlace()?.geometry?.location;if(loc)place(loc,true);});
        search.addEventListener('keydown',e=>{if(e.key==='Enter')e.preventDefault();});
      }
      const sync=()=>{const p=current();if(p){marker.setPosition(p);map.panTo(p);}};
      for(const f of [latitude,longitude])f.addEventListener('change',sync);
      if(start)say(start.lat,start.lng);
      mounted.push(()=>{g.event.clearInstanceListeners(map);node.replaceChildren();});
      return;
    }
    search?.closest('label')?.setAttribute('hidden','');
    if(!globalThis.L)return;
    const start=current();
    const map=L.map(node,{worldCopyJump:true}).setView(start?[start.lat,start.lng]:[YANGON.lat,YANGON.lng],start?16:11);
    const icon=L.divIcon({className:'buyer-map-pin',html:'<span aria-hidden="true">●</span>',iconSize:[30,38],iconAnchor:[15,30]});
    let marker;
    const place=(a,b,select)=>{if(!valid(a,b))return;if(!marker){marker=L.marker([a,b],{draggable:true,icon,autoPan:true,title:'Drag delivery pin',alt:'Selected delivery point'}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng().wrap();place(p.lat,p.lng,true);});}else marker.setLatLng([a,b]);if(select)set(a,b);else say(a,b);};
    map.on('click',e=>{const p=e.latlng.wrap();place(p.lat,p.lng,true);});
    const sync=()=>{const p=current();if(p){place(p.lat,p.lng,false);map.setView([p.lat,p.lng],16);}};
    for(const f of [latitude,longitude])f.addEventListener('change',sync);
    if(start)place(start.lat,start.lng,false);
    const tilesButton=form.querySelector('[data-load-tiles],#load-street-tiles');
    if(tilesButton)tilesButton.onclick=()=>{
      const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',referrerPolicy:'origin'}).addTo(map);
      tiles.on('tileerror',()=>{if(!form.querySelector('[data-map-error]')){const p=document.createElement('p');p.className='small';p.setAttribute('data-map-error','');p.textContent='Street tiles unavailable. Coordinate selection still works; no location has been verified.';node.after(p);}});
      tilesButton.disabled=true;
    };
    map.whenReady(()=>map.invalidateSize());
    node.closest('details')?.addEventListener('toggle',()=>map.invalidateSize());
    mounted.push(()=>map.remove());
  }

  // Read-only pin for the rider and the buyer. Without a key the node keeps its fallback text and link.
  async function view(node){
    const a=Number(node.dataset.lat),b=Number(node.dataset.lng);
    if(!valid(a,b))return;
    const g=await loadGoogle();
    if(!g||!node.isConnected)return;
    node.replaceChildren();node.classList.add('is-google');
    const map=new g.Map(node,{center:{lat:a,lng:b},zoom:17,disableDefaultUI:true,gestureHandling:'cooperative',clickableIcons:false});
    new g.Marker({map,position:{lat:a,lng:b},title:'Delivery point'});
    mounted.push(()=>{g.event.clearInstanceListeners(map);node.replaceChildren();});
  }

  function mount(buyerForm){
    if(buyerForm)picker(buyerForm,{node:buyerForm.querySelector('#buyer-map'),status:buyerForm.querySelector('#map-selection-status'),note:'Submit for server validation and dispatcher review.'});
    document.querySelectorAll('form [data-pin-map]').forEach(node=>{const form=node.closest('form');picker(form,{node,search:form.querySelector('[name=pin_search]'),status:form.querySelector('[data-pin-status]'),note:'Save to send this point to the rider and buyer.'});});
    document.querySelectorAll('[data-view-map]').forEach(view);
  }
  globalThis.LannPyaCustomerMap={mount,destroy,googleEnabled:()=>!!key()};
})();
