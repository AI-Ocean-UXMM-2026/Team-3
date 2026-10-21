// Leaflet is vendored locally. No location or tile request occurs without buyer action.
(()=>{
  let active=null;
  const valid=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a)<=90&&Math.abs(b)<=180;
  function destroy(){active?.remove();active=null;}
  function mount(form){
    destroy();const node=form?.querySelector('#buyer-map');if(!node||!globalThis.L)return;
    const latitude=form.querySelector('[name=latitude]'),longitude=form.querySelector('[name=longitude]');
    const status=form.querySelector('#map-selection-status');
    const map=L.map(node,{worldCopyJump:true}).setView([16.8,96.15],11);active=map;
    let marker;
    const icon=L.divIcon({className:'buyer-map-pin',html:'<span aria-hidden="true">●</span>',iconSize:[30,38],iconAnchor:[15,30]});
    function display(a,b,selected){
      if(!valid(a,b))return;
      if(!marker){marker=L.marker([a,b],{draggable:true,icon,autoPan:true,title:'Drag delivery pin',alt:'Selected delivery point'}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng().wrap();display(p.lat,p.lng,true);});}
      else marker.setLatLng([a,b]);
      if(selected){latitude.value=a.toFixed(7);longitude.value=b.toFixed(7);}
      status.textContent=`Selected: ${a.toFixed(7)}, ${b.toFixed(7)}. Submit for server validation and dispatcher review.`;
    }
    function sync(){if(latitude.value!==''&&longitude.value!==''&&valid(Number(latitude.value),Number(longitude.value))){display(Number(latitude.value),Number(longitude.value),false);map.setView(marker.getLatLng(),16);}}
    map.on('click',e=>{const p=e.latlng.wrap();display(p.lat,p.lng,true);});
    for(const field of [latitude,longitude])field.addEventListener('change',sync);
    sync();
    form.querySelector('#load-street-tiles').onclick=()=>{
      const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',referrerPolicy:'origin'}).addTo(map);
      tiles.on('tileerror',()=>{const notice=document.createElement('p');notice.className='small';notice.textContent='Street tiles unavailable. Coordinate selection still works; no location has been verified.';if(!form.querySelector('[data-map-error]')){notice.setAttribute('data-map-error','');node.after(notice);}});
      form.querySelector('#load-street-tiles').disabled=true;
    };
    map.whenReady(()=>map.invalidateSize());
    return map;
  }
  globalThis.LannPyaCustomerMap={mount,destroy};
})();
