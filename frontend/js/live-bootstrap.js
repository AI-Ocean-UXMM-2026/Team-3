globalThis.LannPyaLiveStore={create:async W=>{
  const options={};
  if(globalThis.LANNPYA_RUNTIME?.mode==='SUPABASE_BACKEND'){
    const {AuthenticatedWorkspaceApi}=await import('./authenticated-api.mjs');
    options.api=new AuthenticatedWorkspaceApi(globalThis.LannPyaAuth,globalThis.LANNPYA_RUNTIME.apiBase);
  }
  return (await import('./live-store.mjs')).createLiveStore(W,options);
}};
globalThis.LannPyaRouting={mount:async options=>(await import('./routing-ui.mjs')).mountPlanner(options),rider:async options=>(await import('./routing-ui.mjs')).mountRiderPlan(options)};
