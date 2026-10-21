/* Cache only this prototype's static shell. Never cache API or remote map data. */
const CACHE='lannpya-static-v4-signboard-0.8.3';
const FILES=['./','./index.html','./signboard.css?v=0.8.3','./assets/brand/mark-dark.svg','./assets/brand/icon-dark.svg','./vendor/lannpya-order-parser.js?v=0.1.0','./workflow-domain.js?v=0.8.3','./functional-app.js?v=0.8.3'];
const allowed=new Set(FILES.map(f=>new URL(f,self.registration.scope).href));
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('lannpya-static-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin||!url.href.startsWith(self.registration.scope))return;
  // Never substitute the local prototype for a failed API/customer navigation.
  if(url.pathname.endsWith('/api.html')||url.pathname.startsWith('/confirm/')||url.pathname.startsWith('/api/'))return;
  if(event.request.mode==='navigate'){event.respondWith(fetch(event.request).catch(()=>caches.match(new URL('./index.html',self.registration.scope).href)));return;}
  if(allowed.has(url.href))event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));
});
