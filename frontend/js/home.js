/* LannPya intro page: language switch, timeline scene, road reveal. */
(()=>{
  const STR={
    my:{
      skip:'အကြောင်းအရာသို့ သွားရန်',navHow:'အလုပ်လုပ်ပုံ',navWho:'ဘယ်သူတွေအတွက်လဲ',
      h1:'Chat ထဲက အော်ဒါဝင်၊ Rider အချိန်မှန်ရောက်။',
      lede:'LannPya က Messenger ထဲက ဝယ်သူ့ အော်ဒါတွေကို ဖတ်ပြီး ရန်ကုန်လိပ်စာတိုင်းကို စစ်ပေးတယ်။ ဝယ်သူက ကိုယ့်တည်နေရာနဲ့ အချိန်ကို ကိုယ်တိုင် အတည်ပြုပြီး Rider က ကောက်ခံရမယ့် ငွေနဲ့ လမ်းကြောင်းကို ရှင်းရှင်းလင်းလင်း မြင်ရတယ်။',
      ctaOpen:'Workspace ဖွင့်ရန်',ctaHow:'အလုပ်လုပ်ပုံ ကြည့်ရန်',
      sChat:'Messenger မှ ကူးထည့်ထားသည်',sRead:'LannPya ဖတ်ထားသည်',sBuyer:'ဝယ်သူ ဖုန်းမှ အတည်ပြုသည်',sRider:'Rider ၏ နောက်တစ်နေရာ',
      fName:'ဝယ်သူ',fTown:'မြို့နယ်',fMark:'မှတ်သားစရာနေရာ',fCash:'ငွေ',tIn:'ဝန်ဆောင်မှုနယ်အတွင်း',vMark:'ဆင်မလိုက်ဈေးနား',
      tPin:'တည်နေရာနဲ့ အချိန် အတည်ပြုပြီး',tDone:'ပို့ပြီး · ၃၅,၀၀၀ ကျပ် ကောက်ခံပြီး',
      sCap:'Chat မှ အိမ်ရှေ့အထိ အော်ဒါတစ်ခု။ နမူနာ ဒေတာ။',pause:'ခဏရပ်',play:'ပြန်ဖွင့်',
      howH:'Chat တစ်ခုနဲ့ အိမ်ရှေ့ကြား မှတ်တိုင် လေးခု',
      st1h:'မနက်ခင်း Chat တွေ ကူးထည့်ပါ',st1p:'Messenger ထဲက အော်ဒါတွေကို တစ်ခါတည်း ကူးထည့်ပါ။ မြန်မာ၊ ဇော်ဂျီနဲ့ အင်္ဂလိပ်စာကို ဖတ်ပြီး မူရင်းစာကို ဘေးမှာ ထားပေးတယ်။',
      st2h:'သင့်လိုအပ်တာကို စစ်ပါ',st2p:'လိပ်စာတွေကို ရန်ကုန်မြို့နယ် ၃၃ ခုနဲ့ တိုက်စစ်တယ်။ မရှင်းတာရှိရင် ဘာမှားလဲ၊ ဘာလုပ်ရမလဲ ပြောပြတယ်။',
      st3h:'ဝယ်သူက ကိုယ့်တည်နေရာ ကိုယ်အတည်ပြု',st3p:'ဝယ်သူတိုင်း ကိုယ်ပိုင် portal link ရတယ်။ ဖုန်းနံပါတ် အပြည့်အစုံနဲ့ Dispatcher ပေးတဲ့ order ID နဲ့ စစ်ပြီး pin ချ၊ အချိန်ရွေးတယ်။ Chat ထဲ လိုက်မေးစရာ မလိုတော့ဘူး။',
      st4h:'Rider က လမ်းကြောင်းအတိုင်း သွား',st4p:'နောက်တစ်နေရာကို မှတ်သားစရာနေရာနဲ့ မြင်ပြီး ကောက်ရမယ့် ငွေအတိအကျ သိတယ်။ နေ့ဆုံးမှာ ရေတွက်ငွေနဲ့ မှတ်တမ်းကို တိုက်စစ်တယ်။',
      whoH:'လူသုံးယောက်၊ တစ်ယောက်ကို အလုပ်တစ်ခု',
      r1h:'Dispatcher',r1p:'ဆိုင်ကောင်တာမှာ Messenger ဖွင့်ထားရင်း Chat အော်ဒါတွေကို ကား မထွက်ခင် လမ်းကြောင်းအဖြစ် ပြောင်းပေးတယ်။',
      r2h:'ဝယ်သူ',r2p:'Chat app ထဲက link ကို Android ဖုန်းနဲ့ ဖွင့်ပြီး ဘယ်မှာ၊ ဘယ်အချိန် ဆိုတာကို တစ်မိနစ်လောက်နဲ့ အတည်ပြုတယ်။',
      r3h:'Rider',r3p:'ဆိုင်ကယ်ပေါ်၊ နေပူထဲ၊ တစ်ခါတလေ အင်တာနက်မရှိ။ တစ်ကြိမ်မှာ တစ်နေရာပဲ မြင်ပြီး တစ်ချက်နှိပ်ရုံနဲ့ ပို့ပြီးကြောင်း မှတ်တယ်။',
      prH:'ဘာမှ အလိုအလျောက် မရွေ့ဘူး',pr1:'ပို့တာ၊ ဆိုင်းထားတာ၊ ပေးပို့တာ အားလုံး လူတစ်ယောက်က နှိပ်မှ ဖြစ်တယ်။',pr2:'သတိပေးချက်တိုင်းက code မဟုတ်ဘဲ အကြောင်းရင်းကို ပြောတယ်။',pr3:'ဝယ်သူ့ မူရင်းစာကို အမြဲ မြင်နေရတယ်။',pr4:'အင်တာနက်မရှိချိန် အလုပ်တွေကို သိမ်းထားပြီး ပြန်ရတဲ့အခါ ပို့ပေးတယ်။',
      endH:'မနက်ဖြန် မနက် အော်ဒါတွေအတွက် အသင့်ဖြစ်ပြီလား။',note:'ရန်ကုန်အတွက် အလုပ်လုပ်နေတဲ့ prototype။ ပြထားတဲ့ နာမည်နဲ့ အော်ဒါ အားလုံး နမူနာ ဖြစ်တယ်။'
    }
  };
  const en={};
  document.querySelectorAll('[data-i18n]').forEach(el=>{en[el.dataset.i18n]=el.textContent});
  en.play='Play';STR.en=en;

  const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const sw=document.querySelector('.lang-switch');
  let lang='en';
  try{lang=localStorage.getItem('lannpya.lang')==='my'?'my':'en'}catch{}
  const toggle=document.querySelector('.scene-toggle');
  let paused=false;

  function setLang(next,animate){
    lang=next;
    try{localStorage.setItem('lannpya.lang',lang)}catch{}
    document.documentElement.lang=lang==='my'?'my':'en';
    sw.dataset.at=lang==='my'?1:0;
    sw.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.lang===lang));
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      const k=el.dataset.i18n,v=STR[lang][k]??STR.en[k];
      if(v!=null)el.textContent=k==='pause'?STR[lang][paused?'play':'pause']:v;
    });
    if(animate&&!reduce){const m=document.getElementById('main');m.classList.remove('fading');void m.offsetWidth;m.classList.add('fading')}
  }
  sw.addEventListener('click',e=>{const b=e.target.closest('button[data-lang]');if(b&&b.dataset.lang!==lang)setLang(b.dataset.lang,true)});
  setLang(lang,false);

  /* Scene: clips carry data-start/data-end in seconds, a tiny timeline in the spirit of HyperFrames. */
  const scene=document.getElementById('scene');
  const clips=[...scene.querySelectorAll('.clip')];
  const LOOP=16.8;const bars=[...scene.querySelectorAll('.scene-steps li')];
  const typer=scene.querySelector('.type');
  const full=typer.dataset.text;
  const road=scene.querySelector('.road-line');
  const sizeRoad=()=>road.style.setProperty('--road-w',road.clientWidth+'px');
  sizeRoad();addEventListener('resize',sizeRoad);

  let t=0,last=0,visible=true;
  function render(){
    clips.forEach(c=>{
      const s=+c.dataset.start,e=+c.dataset.end,on=t>=s&&t<e;
      c.classList.toggle('on',on);c.classList.toggle('off',t>=e);
    });
    bars.forEach((b,i)=>{const c=clips[i+1],s=+c.dataset.start,e=+c.dataset.end;b.style.setProperty('--p',Math.max(0,Math.min(1,(t-s)/(e-s))))});
    const n=Math.min(full.length,Math.floor((t-2.4)/1.9*full.length));
    typer.textContent=full.slice(0,n);typer.classList.toggle('done',n>=full.length);
  }
  function frame(now){
    if(!paused&&visible){t+=Math.min(.1,(now-last)/1000);if(t>=LOOP){t=0;clips.forEach(c=>c.classList.remove('off'))}render()}
    last=now;requestAnimationFrame(frame);
  }
  if(reduce){
    /* Show the finished story: the last clip, everything filled in. */
    t=13;render();typer.textContent=full;typer.classList.add('done');toggle.hidden=true;
  }else{
    new IntersectionObserver(([en])=>{visible=en.isIntersecting},{threshold:.2}).observe(scene);
    /* Logo intro first, then the page and the scene. Once per visit. */
    const intro=document.getElementById('intro');let seen=false;

    const start=()=>{intro.classList.add('done');document.body.classList.remove('pre');setTimeout(()=>requestAnimationFrame(n=>{last=n;frame(n)}),500)};
    if(seen)start();else{document.body.classList.add('pre');setTimeout(start,2300);intro.addEventListener('click',start,{once:true})}
  }
  toggle.addEventListener('click',()=>{
    paused=!paused;toggle.setAttribute('aria-pressed',paused);
    toggle.textContent=STR[lang][paused?'play':'pause'];
  });

  /* Open the workspace at the sign-in screen (sign up is offered there). */
  document.querySelectorAll('a[href="index.html"]').forEach(a=>a.addEventListener('click',()=>{
    try{const k='lannpya.signedOut',v=JSON.parse(localStorage.getItem(k)||'{}');v.admin=true;v.rider=true;localStorage.setItem(k,JSON.stringify(v))}catch{}
    /* Show the LannPya loader while the workspace opens. */
    if(!document.getElementById('lp-loader')){const t=document.getElementById('lp-tpl');if(t)document.body.appendChild(t.content.cloneNode(true))}
  }));
  /* Coming back with the browser's Back button: clear the loader. */
  addEventListener('pageshow',e=>{if(e.persisted)document.getElementById('lp-loader')?.remove()});

  /* Road under "How it works" draws once when it comes into view. */
  const stops=document.querySelector('.stops');
  if(reduce||!('IntersectionObserver' in window))stops.classList.add('seen');
  else new IntersectionObserver((es,o)=>{if(es[0].isIntersecting){stops.classList.add('seen');o.disconnect()}},{threshold:.4}).observe(stops);
})();
