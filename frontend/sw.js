/* Cache only this prototype's static shell. Never cache API or remote map data. */
const CACHE='lannpya-static-v8-order-flows';
const FILES=['./prototype.html','./demo-config.js','./css/signboard.css?v=0.9.2','./vendor/lannpya-order-parser.js?v=0.1.0','./js/workflow-domain.js?v=0.9.2','./js/functional-app.js?v=0.9.2'];
const allowed=new Set(FILES.map(f=>new URL(f,self.registration.scope).href));
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('lannpya-static-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin||!url.href.startsWith(self.registration.scope))return;
  // Never substitute the local prototype for a failed API/customer navigation.
  if(['/','/index.html','/api.html'].includes(url.pathname)||url.pathname.startsWith('/dashboard/')||url.pathname.startsWith('/confirm/')||url.pathname.startsWith('/api/'))return;
  if(event.request.mode==='navigate'&&url.pathname.endsWith('/prototype.html')){event.respondWith(fetch(event.request).catch(()=>caches.match(new URL('./prototype.html',self.registration.scope).href)));return;}
  if(allowed.has(url.href))event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));
});
