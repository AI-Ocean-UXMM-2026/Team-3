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
      const timer=setTimeout(()=>resolve(null),8000);
      globalThis.__lannpyaMapsReady=()=>{clearTimeout(timer);resolve(globalThis.google?.maps||null);};
      const s=document.createElement('script');
      s.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key())}&libraries=places&loading=async&callback=__lannpyaMapsReady`;
      s.async=true;s.onerror=()=>{clearTimeout(timer);googleReady=null;resolve(null);};
      document.head.append(s);
    });
    return googleReady;
  }
  const mounted=[];
  function destroy(){while(mounted.length)mounted.pop()();}

  function attachStreetTiles(map){
    if(!map||map._tilesAttached)return;
    map._tilesAttached=true;
    const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:19,
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
      referrerPolicy:'origin'
    }).addTo(map);
    tiles.on('tileerror',()=>{
      if(!map._hotFallback){
        map._hotFallback=true;
        const hot=L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',{
          subdomains:['a','b'],
          maxZoom:19,
          attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors, Tiles by <a href="https://www.hotosm.org/" target="_blank" rel="noopener noreferrer">HOT</a>'
        }).addTo(map);
        hot.on('tileerror',()=>{
          if(!map._esriFallback){
            map._esriFallback=true;
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{
              maxZoom:19,
              attribution:'Tiles &copy; Esri'
            }).addTo(map);
          }
        });
      }
    });
    return tiles;
  }

  // Editable pin bound to a form's latitude/longitude fields.
  async function picker(form,{node,search,status,note}){
    if(!node)return;
    const latitude=form.querySelector('[name=latitude]'),longitude=form.querySelector('[name=longitude]');
    const current=()=>latitude.value!==''&&longitude.value!==''&&valid(Number(latitude.value),Number(longitude.value))?{lat:Number(latitude.value),lng:Number(longitude.value)}:null;
    const say=(a,b)=>{if(status)status.textContent=`Pinned at ${a.toFixed(6)}, ${b.toFixed(6)}. ${note}`;};
    const set=(a,b)=>{if(!valid(a,b))return;latitude.value=a.toFixed(7);longitude.value=b.toFixed(7);say(a,b);latitude.dispatchEvent(new Event('input',{bubbles:true}));};
    const g=await loadGoogle();
    if(!form.isConnected)return;
    if(g){
      const start=current();
      const map=new g.Map(node,{center:start||YANGON,zoom:start?17:12,mapTypeControl:false,streetViewControl:false,fullscreenControl:false,clickableIcons:false});
      const marker=new g.Marker({map,position:start,draggable:true,title:'Delivery point'});
      const place=(p,zoom)=>{marker.setPosition(p);map.panTo(p);if(zoom)map.setZoom(17);set(p.lat(),p.lng());};
      map.addListener('click',e=>place(e.latLng));
      marker.addListener('dragend',()=>place(marker.getPosition()));
      const off=new AbortController(),cleanup=[()=>off.abort(),()=>g.event.clearInstanceListeners(map),()=>g.event.clearInstanceListeners(marker),()=>marker.setMap(null)];
      if(search){
        if(g.places?.PlaceAutocompleteElement){
          // Current Places widget; legacy Autocomplete is unavailable to new API projects.
          const el=new g.places.PlaceAutocompleteElement({includedRegionCodes:['mm']});
          el.className='pin-autocomplete';search.hidden=true;search.after(el);
          el.addEventListener('gmp-select',async({placePrediction})=>{const p=placePrediction.toPlace();await p.fetchFields({fields:['location']});if(p.location)place(p.location,true);},{signal:off.signal});
          cleanup.push(()=>el.remove(),()=>{search.hidden=false;});
        }else if(g.places?.Autocomplete){
          const ac=new g.places.Autocomplete(search,{componentRestrictions:{country:'mm'},fields:['geometry']});
          ac.addListener('place_changed',()=>{const loc=ac.getPlace()?.geometry?.location;if(loc)place(loc,true);});
          search.addEventListener('keydown',e=>{if(e.key==='Enter')e.preventDefault();},{signal:off.signal});
          cleanup.push(()=>g.event.clearInstanceListeners(ac),()=>document.querySelectorAll('.pac-container').forEach(n=>n.remove()));
        }else search.closest('label')?.setAttribute('hidden','');
      }
      const sync=()=>{const p=current();if(p){marker.setPosition(p);map.panTo(p);}};
      for(const f of [latitude,longitude])f.addEventListener('change',sync,{signal:off.signal});
      if(start)say(start.lat,start.lng);
      // Google mode needs no OpenStreetMap button or notice.
      form.querySelectorAll('[data-load-tiles],#load-street-tiles,[data-osm-note]').forEach(n=>n.remove());
      mounted.push(()=>{cleanup.forEach(f=>f());node.replaceChildren();});
      return;
    }
    search?.closest('label')?.setAttribute('hidden','');
    if(!globalThis.L){node.textContent='Map library unavailable. Type coordinates manually or contact the shop.';return;}
    const start=current();
    const map=L.map(node,{worldCopyJump:true}).setView(start?[start.lat,start.lng]:[YANGON.lat,YANGON.lng],start?16:11);
    const icon=L.divIcon({className:'buyer-map-pin',html:'<span aria-hidden="true">●</span>',iconSize:[30,38],iconAnchor:[15,30]});
    let marker;
    const place=(a,b,select)=>{if(!valid(a,b))return;if(!marker){marker=L.marker([a,b],{draggable:true,icon,autoPan:true,title:'Drag delivery pin',alt:'Selected delivery point'}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng().wrap();place(p.lat,p.lng,true);});}else marker.setLatLng([a,b]);if(select)set(a,b);else say(a,b);};
    map.on('click',e=>{const p=e.latlng.wrap();place(p.lat,p.lng,true);});
    const off=new AbortController();
    const sync=()=>{const p=current();if(p){place(p.lat,p.lng,false);map.setView([p.lat,p.lng],16);}};
    for(const f of [latitude,longitude])f.addEventListener('change',sync,{signal:off.signal});
    if(start)place(start.lat,start.lng,false);
    attachStreetTiles(map);
    form.querySelectorAll('[data-load-tiles],#load-street-tiles,[data-osm-note]').forEach(n=>n.remove());
    map.whenReady(()=>map.invalidateSize());
    node.closest('details')?.addEventListener('toggle',()=>map.invalidateSize(),{signal:off.signal});
    mounted.push(()=>{off.abort();map.remove();});
  }

  // Read-only pin for the rider and the buyer. Without a key the node keeps its fallback text and link.
  async function view(node){
    if(!node.dataset.lat?.trim()||!node.dataset.lng?.trim())return;
    const a=Number(node.dataset.lat),b=Number(node.dataset.lng);
    if(!valid(a,b))return;
    const g=await loadGoogle();
    if(!node.isConnected)return;
    if(!g){
      if(!globalThis.L)return;
      node.replaceChildren();
      const map=L.map(node).setView([a,b],16);
      L.marker([a,b],{icon:L.divIcon({className:'buyer-map-pin',html:'<span aria-hidden="true">●</span>',iconSize:[30,38],iconAnchor:[15,30]}),title:'Saved delivery point'}).addTo(map);
      attachStreetTiles(map);
      map.whenReady(()=>map.invalidateSize());
      mounted.push(()=>{map.remove();});
      return;
    }
    node.replaceChildren();node.classList.add('is-google');
    const map=new g.Map(node,{center:{lat:a,lng:b},zoom:17,disableDefaultUI:true,gestureHandling:'cooperative',clickableIcons:false});
    const marker=new g.Marker({map,position:{lat:a,lng:b},title:'Delivery point'});
    mounted.push(()=>{marker.setMap(null);g.event.clearInstanceListeners(map);node.replaceChildren();});
  }

  function mount(buyerForm){
    if(buyerForm)picker(buyerForm,{node:buyerForm.querySelector('#buyer-map'),status:buyerForm.querySelector('#map-selection-status'),note:'Submit for server validation and dispatcher review.'});
    document.querySelectorAll('form [data-pin-map]').forEach(node=>{const form=node.closest('form');picker(form,{node,search:form.querySelector('[data-pin-search]'),status:form.querySelector('[data-pin-status]'),note:node.dataset.pinNote||'Save to send this point to the rider and buyer.'});});
    document.querySelectorAll('[data-view-map]').forEach(view);
  }
  async function routeView(node,geometry,provider,stops=[]){
    if(!node?.isConnected||!geometry)return;
    // Google road data is never drawn on an unrelated Leaflet basemap.
    if(provider==='google'){
      const g=await loadGoogle();if(!node.isConnected)return;
      if(!g){node.textContent='Google map unavailable. Route geometry is withheld; use the navigation link.';return;}
      const path=geometry.coordinates.map(([lng,lat])=>({lat,lng}));
      const map=new g.Map(node,{center:path[0],zoom:14,mapTypeControl:false,streetViewControl:false});
      const line=new g.Polyline({path,map,strokeColor:'#D23F2E'}),bounds=new g.LatLngBounds();path.forEach(p=>bounds.extend(p));stops.forEach(s=>bounds.extend({lat:s.latitude,lng:s.longitude}));map.fitBounds(bounds);
      const pins=[{position:path[0],title:'Road route start'},{position:path.at(-1),title:'Road route end'},...stops.map(s=>({position:{lat:s.latitude,lng:s.longitude},title:`Approved stop ${s.sequence}; geospatial accuracy unverified`}))].map(p=>new g.Marker({...p,map}));
      mounted.push(()=>{pins.forEach(p=>p.setMap(null));line.setMap(null);g.event.clearInstanceListeners(map);node.replaceChildren();});return;
    }
    if(!globalThis.L){node.textContent='Map library unavailable. The ordered stop list remains available.';return;}
    const map=L.map(node),line=L.geoJSON(geometry,{style:{color:'#D23F2E',weight:4}}).addTo(map);
    for(const stop of stops)L.marker([stop.latitude,stop.longitude],{title:`Stop ${stop.sequence}`,icon:L.divIcon({className:'buyer-map-pin',html:`<b>${Number(stop.sequence)}</b>`,iconSize:[28,28]})}).addTo(map);
    map.fitBounds(line.getBounds(),{padding:[20,20],maxZoom:17});
    attachStreetTiles(map);
    map.whenReady(()=>map.invalidateSize());
    mounted.push(()=>{map.remove();});
  }
  // Buyer's map while the parcel is out: their delivery point and the rider's position. Returns its own cleanup.
  async function riderView(node,{dest,rider}){
    const none=()=>{};
    if(!node?.isConnected||!valid(dest?.lat,dest?.lng)||!valid(rider?.lat,rider?.lng))return none;
    const g=await loadGoogle();
    if(!node.isConnected)return none;
    if(g){
      const map=new g.Map(node,{center:rider,zoom:14,disableDefaultUI:true,zoomControl:true,zoomControlOptions:{position:g.ControlPosition.RIGHT_TOP},clickableIcons:false,gestureHandling:'greedy'});
      const home=new g.Marker({map,position:dest,title:'Your delivery point'});
      const bike=new g.Marker({map,position:rider,title:'Your rider',icon:{path:g.SymbolPath.CIRCLE,scale:9,fillColor:'#F0A032',fillOpacity:1,strokeColor:'#16263A',strokeWeight:3}});
      const bounds=new g.LatLngBounds();bounds.extend(dest);bounds.extend(rider);map.fitBounds(bounds,72);
      return ()=>{home.setMap(null);bike.setMap(null);g.event.clearInstanceListeners(map);node.replaceChildren();};
    }
    if(!globalThis.L){node.textContent='Map unavailable. The road view still shows where your rider is.';return none;}
    node.replaceChildren();
    const map=L.map(node,{zoomControl:false});L.control.zoom({position:'topright'}).addTo(map);
    L.marker([dest.lat,dest.lng],{icon:L.divIcon({className:'buyer-map-pin',html:'<span aria-hidden="true">●</span>',iconSize:[30,38],iconAnchor:[15,30]}),title:'Your delivery point'}).addTo(map);
    L.marker([rider.lat,rider.lng],{icon:L.divIcon({className:'rider-map-dot',html:'<i></i>',iconSize:[24,24],iconAnchor:[12,12]}),title:'Your rider'}).addTo(map);
    map.fitBounds([[dest.lat,dest.lng],[rider.lat,rider.lng]],{padding:[72,72],maxZoom:16});
    attachStreetTiles(map);
    map.whenReady(()=>map.invalidateSize());
    return ()=>{map.remove();};
  }
  // Rider's way to the hub. provider 'google' needs a browser key; otherwise Leaflet. Returns {off, setMe}.
  async function hubView(node,{hub,provider,mini=false}){
    const none={off(){},setMe(){}};
    if(!node?.isConnected||!valid(hub?.lat,hub?.lng))return none;
    const g=provider==='leaflet'?null:await loadGoogle();
    if(!node.isConnected)return none;
    const h={lat:hub.lat,lng:hub.lng},hubIcon='<span class="hub-map-pin" aria-hidden="true"><img src="assets/brand/mark-dark.svg" alt=""></span>';
    if(g){
      const map=new g.Map(node,{center:h,zoom:mini?15:16,disableDefaultUI:true,zoomControl:!mini,zoomControlOptions:{position:g.ControlPosition.RIGHT_CENTER},clickableIcons:false,gestureHandling:mini?'none':'greedy',keyboardShortcuts:!mini});
      const pin=new g.Marker({map,position:h,title:hub.name,icon:{path:g.SymbolPath.CIRCLE,scale:11,fillColor:'#16263A',fillOpacity:1,strokeColor:'#F0A032',strokeWeight:3}});
      let me=null,line=null;
      return {off(){pin.setMap(null);me?.setMap(null);line?.setMap(null);g.event.clearInstanceListeners(map);node.replaceChildren();},
        setMe(p){if(!valid(p?.lat,p?.lng))return;me?.setMap(null);line?.setMap(null);me=new g.Marker({map,position:p,title:'You',icon:{path:g.SymbolPath.CIRCLE,scale:8,fillColor:'#F0A032',fillOpacity:1,strokeColor:'#16263A',strokeWeight:3}});
          line=new g.Polyline({map,path:[p,h],strokeColor:'#16263A',strokeOpacity:0,icons:[{icon:{path:'M 0,-1 0,1',strokeOpacity:1,scale:3},offset:'0',repeat:'12px'}]});const b=new g.LatLngBounds();b.extend(p);b.extend(h);map.fitBounds(b,80);}};
    }
    if(!globalThis.L){node.textContent='Map unavailable. Use the hub address above.';return none;}
    node.replaceChildren();
    const map=L.map(node,{zoomControl:false,dragging:!mini,scrollWheelZoom:!mini,doubleClickZoom:!mini,touchZoom:!mini,keyboard:!mini,attributionControl:!mini}).setView([h.lat,h.lng],mini?15:16);
    if(!mini)L.control.zoom({position:'topright'}).addTo(map);
    attachStreetTiles(map);
    L.marker([h.lat,h.lng],{icon:L.divIcon({className:'',html:hubIcon,iconSize:[40,40],iconAnchor:[20,20]}),title:hub.name}).addTo(map);
    let me=null,line=null;map.whenReady(()=>map.invalidateSize());
    return {off(){map.remove();},
      setMe(p){if(!valid(p?.lat,p?.lng))return;me?.remove();line?.remove();me=L.marker([p.lat,p.lng],{icon:L.divIcon({className:'rider-map-dot',html:'<i></i>',iconSize:[24,24],iconAnchor:[12,12]}),title:'You'}).addTo(map);
        line=L.polyline([[p.lat,p.lng],[h.lat,h.lng]],{color:'#16263A',weight:4,dashArray:'2 10',lineCap:'round'}).addTo(map);map.fitBounds(line.getBounds(),{padding:[80,80],maxZoom:17});}};
  }

  // Rider route to the selected delivery stop using OpenStreetMap.
  function riderRouteView(node,{rider,dest,order,stopIndex=1,totalStops=1}){
    const none={off(){},setRider(){},invalidate(){}};
    if(!node?.isConnected)return none;
    if(!valid(dest?.lat,dest?.lng)||!valid(rider?.lat,rider?.lng))return none;
    if(!globalThis.L){
      node.innerHTML=`<div class="route-map-fallback"><p>Map library unavailable.</p><a class="btn sm" href="https://www.google.com/maps/dir/?api=1&destination=${dest.lat},${dest.lng}&travelmode=driving" target="_blank" rel="noopener">Open navigation</a></div>`;
      return none;
    }

    node.replaceChildren();
    const mapDiv=document.createElement('div');
    mapDiv.className='rider-map-canvas';
    node.append(mapDiv);

    // Overlay controls container
    const topBar=document.createElement('div');
    topBar.className='rider-map-overlay-top';
    const stopChip=document.createElement('span');
    stopChip.className='route-chip-title';
    const stopName=order?.name||'Delivery stop';
    const landmark=order?.landmark||order?.street||'Yangon';
    stopChip.innerHTML=`<b>Stop ${stopIndex}/${totalStops}</b> · ${stopName}`;
    stopChip.title=`${stopName} · ${landmark}`;
    const btnGroup=document.createElement('div');
    btnGroup.className='route-map-btn-group';

    const locateBtn=document.createElement('button');
    locateBtn.type='button';
    locateBtn.className='btn sm quiet locate-rider-btn';
    locateBtn.title='Locate my current position';
    locateBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS';

    const expandBtn=document.createElement('button');
    expandBtn.type='button';
    expandBtn.className='btn sm quiet toggle-map-size-btn';
    expandBtn.title='Expand map to full popup';
    expandBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg> Expand';

    btnGroup.append(locateBtn, expandBtn);
    topBar.append(stopChip, btnGroup);
    node.append(topBar);

    const bottomBar=document.createElement('div');
    bottomBar.className='rider-map-overlay-bottom';
    const routeInfo=document.createElement('span');
    routeInfo.className='route-info-badge';
    routeInfo.innerHTML='<span>Calculating route…</span>';

    // Route info sits on bottom-left, leaving bottom-right Leaflet zoom buttons completely unobstructed
    bottomBar.append(routeInfo);
    node.append(bottomBar);

    // Initialize Leaflet map
    const map=L.map(mapDiv,{zoomControl:false,attributionControl:false});
    L.control.zoom({position:'bottomright'}).addTo(map);

    // OpenStreetMap Humanitarian (HOT) tiles powered by OSM data; fast, free, no API key required, no watermarks
    attachStreetTiles(map);

    // Rider Icon
    const riderIcon=L.divIcon({
      className:'rider-live-marker',
      html:'<div class="rider-marker-pin"><span class="rider-marker-pulse"></span><span class="rider-marker-icon">🛵</span></div>',
      iconSize:[36,36],
      iconAnchor:[18,18]
    });
    const isLive=Boolean(globalThis.__riderLivePos);
    let currentRiderPos=rider;
    let riderMarker=L.marker([rider.lat,rider.lng],{icon:riderIcon,title:isLive?'Your Location':'Pickup Hub (Starting Point)',zIndexOffset:1000}).addTo(map);
    riderMarker.bindPopup(isLive?'<b>Your Current Location</b><br>Live GPS active':'<b>Pickup Hub (Hledan)</b><br><small>Default start point until device GPS is read</small>');

    // Destination Icon
    const destIcon=L.divIcon({
      className:'dest-delivery-marker',
      html:`<div class="dest-marker-pin"><span class="dest-marker-number">${stopIndex}</span></div>`,
      iconSize:[32,32],
      iconAnchor:[16,32]
    });
    const destMarker=L.marker([dest.lat,dest.lng],{icon:destIcon,title:stopName,zIndexOffset:500}).addTo(map);
    destMarker.bindPopup(`<b>${stopName}</b><br>${landmark}<br>Stop ${stopIndex} of ${totalStops}`);

    let routeLayer=null;
    let lastGeometry=null;
    let activeModal=null;

    const fetchRoute=async(from,to)=>{
      currentRiderPos=from;
      if(routeLayer)map.removeLayer(routeLayer);
      routeInfo.innerHTML='<span>Finding best route…</span>';

      const rad=x=>x*Math.PI/180;
      const dLat=rad(to.lat-from.lat),dLng=rad(to.lng-from.lng);
      const a=Math.sin(dLat/2)*Math.sin(dLat/2)+Math.cos(rad(from.lat))*Math.cos(rad(to.lat))*Math.sin(dLng/2)*Math.sin(dLng/2);
      const distMeters=6371000*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));

      if(distMeters<30){
        lastGeometry=null;
        const msg='<b>You are here</b> · At delivery destination';
        routeInfo.innerHTML=msg;
        map.setView([to.lat,to.lng],17);
        if(activeModal?.infoBadge)activeModal.infoBadge.innerHTML=msg;
        return;
      }

      try{
        const controller=new AbortController();
        const timeout=setTimeout(()=>controller.abort(),4000);
        const res=await fetch(`https://router.project-osrm.org/route/v1/driving/${from.lng},${from.lat};${to.lng},${to.lat}?overview=full&geometries=geojson`,{signal:controller.signal});
        clearTimeout(timeout);
        if(!res.ok)throw Error('OSRM error');
        const data=await res.json();
        if(!data?.routes?.length)throw Error('No route found');
        const r=data.routes[0];
        lastGeometry=r.geometry;
        routeLayer=L.geoJSON(r.geometry,{
          style:{color:'#2563EB',weight:5,opacity:0.9,lineCap:'round',lineJoin:'round'}
        }).addTo(map);
        map.fitBounds(routeLayer.getBounds(),{padding:[45,45],maxZoom:16});
        const km=(r.distance/1000).toFixed(1);
        const mins=Math.ceil(r.duration/60);
        const infoHtml=`<b>${km} km</b> · ~${mins} min drive`;
        routeInfo.innerHTML=infoHtml;
        if(activeModal?.infoBadge)activeModal.infoBadge.innerHTML=infoHtml;
      }catch{
        // Graceful fallback to direct styled polyline
        lastGeometry=null;
        routeLayer=L.polyline([[from.lat,from.lng],[to.lat,to.lng]],{
          color:'#2563EB',weight:4,dashArray:'6, 8',opacity:0.8
        }).addTo(map);
        map.fitBounds(routeLayer.getBounds(),{padding:[45,45],maxZoom:16});
        const dKm=(distMeters/1000).toFixed(1);
        const infoHtml=`<b>~${dKm} km direct</b>`;
        routeInfo.innerHTML=infoHtml;
        if(activeModal?.infoBadge)activeModal.infoBadge.innerHTML=infoHtml;
      }
    };

    fetchRoute(rider,dest);

    // Open full modal popup screen for map view
    function openMapModal(){
      if(activeModal){try{activeModal.close();}catch{}}

      const modal=document.createElement('div');
      modal.className='rider-map-modal';
      modal.setAttribute('role','dialog');
      modal.setAttribute('aria-modal','true');
      modal.setAttribute('aria-label',`Route map for ${stopName}`);

      modal.innerHTML=`
        <div class="rider-modal-backdrop"></div>
        <div class="rider-modal-content">
          <header class="rider-modal-header">
            <div class="rider-modal-title">
              <span class="rider-modal-stop-badge">Stop ${stopIndex}/${totalStops}</span>
              <div>
                <h3>${stopName}</h3>
                <span class="rider-modal-landmark">${landmark}</span>
              </div>
            </div>
            <button type="button" class="rider-modal-close-btn" aria-label="Close map popup">✕</button>
          </header>
          <div class="rider-modal-map-container"></div>
          <footer class="rider-modal-footer">
            <div class="rider-modal-route-info">
              <span class="modal-route-stat">${routeInfo.innerHTML}</span>
            </div>
            <div class="rider-modal-actions">
              <button type="button" class="btn sm quiet modal-gps-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS
              </button>
              <a class="btn primary sm modal-nav-btn" href="https://www.google.com/maps/dir/?api=1&destination=${dest.lat},${dest.lng}&travelmode=driving" target="_blank" rel="noopener noreferrer">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg> Google Maps
              </a>
            </div>
          </footer>
        </div>
      `;
      document.body.append(modal);

      const modalMapContainer=modal.querySelector('.rider-modal-map-container');
      const modalMap=L.map(modalMapContainer,{zoomControl:false,attributionControl:false});
      L.control.zoom({position:'topright'}).addTo(modalMap);
      attachStreetTiles(modalMap);

      const mRider=L.marker([currentRiderPos.lat,currentRiderPos.lng],{icon:riderIcon,title:riderMarker.options.title,zIndexOffset:1000}).addTo(modalMap);
      mRider.bindPopup(riderMarker.getPopup()?.getContent()||'<b>Rider Location</b>');

      const mDest=L.marker([dest.lat,dest.lng],{icon:destIcon,title:stopName,zIndexOffset:500}).addTo(modalMap);
      mDest.bindPopup(`<b>${stopName}</b><br>${landmark}<br>Stop ${stopIndex} of ${totalStops}`);

      let mRoute=null;
      if(lastGeometry){
        mRoute=L.geoJSON(lastGeometry,{
          style:{color:'#2563EB',weight:6,opacity:0.95,lineCap:'round',lineJoin:'round'}
        }).addTo(modalMap);
        modalMap.fitBounds(mRoute.getBounds(),{padding:[50,50],maxZoom:17});
      }else{
        mRoute=L.polyline([[currentRiderPos.lat,currentRiderPos.lng],[dest.lat,dest.lng]],{
          color:'#2563EB',weight:5,dashArray:'6, 8',opacity:0.85
        }).addTo(modalMap);
        modalMap.fitBounds(mRoute.getBounds(),{padding:[50,50],maxZoom:17});
      }

      const modalGpsBtn=modal.querySelector('.modal-gps-btn');
      modalGpsBtn.onclick=()=>{
        if(!navigator.geolocation)return;
        modalGpsBtn.disabled=true;
        modalGpsBtn.textContent='GPS…';
        navigator.geolocation.getCurrentPosition(
          pos=>{
            modalGpsBtn.disabled=false;
            modalGpsBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS';
            applyLivePosition(pos);
            mRider.setLatLng([pos.coords.latitude,pos.coords.longitude]);
            if(mRoute){
              try{modalMap.removeLayer(mRoute);}catch{}
              mRoute=L.polyline([[pos.coords.latitude,pos.coords.longitude],[dest.lat,dest.lng]],{color:'#2563EB',weight:5,opacity:0.9}).addTo(modalMap);
              modalMap.fitBounds(mRoute.getBounds(),{padding:[50,50],maxZoom:17});
            }
          },
          ()=>{
            modalGpsBtn.disabled=false;
            modalGpsBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS';
          },
          {enableHighAccuracy:true,timeout:8000}
        );
      };

      const close=()=>{
        try{modalMap.remove();}catch{}
        modal.remove();
        if(activeModal?.close===close)activeModal=null;
        window.removeEventListener('keydown',onKey);
      };
      const onKey=e=>{if(e.key==='Escape')close();};
      window.addEventListener('keydown',onKey);
      modal.querySelector('.rider-modal-close-btn').onclick=close;
      modal.querySelector('.rider-modal-backdrop').onclick=close;

      activeModal={close,modal,modalMap,infoBadge:modal.querySelector('.modal-route-stat')};

      setTimeout(()=>{
        try{
          modalMap.invalidateSize();
          if(mRoute)modalMap.fitBounds(mRoute.getBounds(),{padding:[50,50],maxZoom:17});
        }catch{}
      },120);
    }

    expandBtn.onclick=()=>openMapModal();

    const applyLivePosition=(pos)=>{
      locateBtn.disabled=false;
      locateBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS';
      const newPos={lat:pos.coords.latitude,lng:pos.coords.longitude};
      globalThis.__riderLivePos=newPos;
      riderMarker.setLatLng([newPos.lat,newPos.lng]);
      riderMarker.bindPopup('<b>Your Current Location</b><br>Live GPS active');
      fetchRoute(newPos,dest);
    };

    // Auto-detect rider GPS on mount if not yet established
    if(navigator.geolocation&&!globalThis.__riderLivePos){
      navigator.geolocation.getCurrentPosition(
        applyLivePosition,
        ()=>{ /* Retain hub default if permission denied */ },
        {enableHighAccuracy:true,timeout:6000,maximumAge:15000}
      );
    }

    // Locate rider GPS button
    locateBtn.onclick=()=>{
      if(!navigator.geolocation)return;
      locateBtn.disabled=true;
      locateBtn.textContent='GPS…';
      navigator.geolocation.getCurrentPosition(
        applyLivePosition,
        ()=>{
          locateBtn.disabled=false;
          locateBtn.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg> GPS';
        },
        {enableHighAccuracy:true,timeout:8000}
      );
    };

    map.whenReady(()=>map.invalidateSize());

    const instance={
      off(){
        if(activeModal){try{activeModal.close();}catch{} activeModal=null;}
        try{map.remove();}catch{}
        node.replaceChildren();
      },
      setRider(newPos){
        if(!valid(newPos?.lat,newPos?.lng))return;
        riderMarker.setLatLng([newPos.lat,newPos.lng]);
        fetchRoute(newPos,dest);
      },
      invalidate(){
        try{map.invalidateSize();}catch{}
      }
    };
    mounted.push(()=>instance.off());
    return instance;
  }

  globalThis.LannPyaCustomerMap={mount,destroy,routeView,riderView,hubView,riderRouteView,viewOne:view,googleEnabled:()=>!!key()};
})();
