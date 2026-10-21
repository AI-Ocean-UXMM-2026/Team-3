globalThis.LannPyaLiveStore={create:async W=>(await import('./live-store.mjs')).createLiveStore(W)};
globalThis.LannPyaRouting={mount:async options=>(await import('./routing-ui.mjs')).mountPlanner(options),rider:async options=>(await import('./routing-ui.mjs')).mountRiderPlan(options)};
