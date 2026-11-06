/* Navigation motion is opt-in: only links in the two persistent navigation bars. */
(() => {
  'use strict';
  const root=document.documentElement;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const sceneKey='library-scene-position-v1', navKey='library-navigation-motion-v1';
  const positions=[[-5,-3],[4,2],[-2,4],[5,-4],[-4,1],[2,-2],[-1,-4],[4,4]];
  let previous=[0,0];
  try {const p=JSON.parse(sessionStorage.getItem(sceneKey));if(Array.isArray(p)&&p.length===2&&p.every(v=>Number.isFinite(v)&&Math.abs(v)<=5))previous=p;}catch(_){}
  const noMotion=()=>({axis:'none',direction:1});
  const takePending=()=>{
    try {
      const p=JSON.parse(sessionStorage.getItem(navKey));sessionStorage.removeItem(navKey);
      if(p&&['x','y'].includes(p.axis)&&[1,-1].includes(p.direction)&&Date.now()-p.time>=0&&Date.now()-p.time<15000)return p;
    }catch(_){}
    return noMotion();
  };
  const setDirection=p=>{
    root.dataset.navAxis=reduced.matches?'none':p.axis;
    root.style.setProperty('--nav-direction',String(p.direction));
  };
  const moveScene=p=>{
    let target=[...previous];
    if(p.axis!=='none'&&!reduced.matches){
      const url=new URL(location.href),key=url.pathname+'|'+(url.searchParams.get('tab')||'');
      let hash=0;for(let i=0;i<key.length;i++)hash=(Math.imul(hash,31)+key.charCodeAt(i))>>>0;
      const index=p.axis==='y'?1:0;
      target[index]=positions[hash%positions.length][index];
      if(target[index]===previous[index])target[index]=previous[index]>=0?-4:4;
    }
    root.style.setProperty('--scene-from-x',previous[0]+'%');root.style.setProperty('--scene-from-y',previous[1]+'%');
    root.style.setProperty('--scene-to-x',target[0]+'%');root.style.setProperty('--scene-to-y',target[1]+'%');
    root.dataset.sceneRun=root.dataset.sceneRun==='a'?'b':'a';
    previous=target;
    try{sessionStorage.setItem(sceneKey,JSON.stringify(target));}catch(_){}
  };
  const initial=takePending();setDirection(initial);moveScene(initial);
  const reset=()=>{setDirection(noMotion());try{sessionStorage.removeItem(navKey);}catch(_){}};
  document.addEventListener('click',event=>{
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const link=event.target.closest('a[href]');
    if(!link||link.hasAttribute('download')||(link.target&&link.target!=='_self')){reset();return;}
    const bar=link.closest('.app-sidebar,.topbar');
    const url=new URL(link.href,location.href);
    if(!bar||url.origin!==location.origin||(url.pathname===location.pathname&&url.search===location.search)){reset();return;}
    const links=[...bar.querySelectorAll('a[href]')];
    const targetIndex=links.indexOf(link);
    const currentIndex=links.findIndex(a=>{
      const candidate=new URL(a.href,location.href),current=new URL(location.href);
      return candidate.pathname===current.pathname&&(candidate.searchParams.get('tab')||'')===(current.searchParams.get('tab')||'');
    });
    const p={axis:bar.matches('.app-sidebar')?'y':'x',direction:currentIndex>=0&&targetIndex<currentIndex?-1:1,time:Date.now()};
    setDirection(p);try{sessionStorage.setItem(navKey,JSON.stringify(p));}catch(_){}
  },true);
  document.addEventListener('submit',reset,true);
  addEventListener('popstate',reset);
  reduced.addEventListener('change',reset);
  window.LibraryNavigation={
    run(change){
      const p=takePending();setDirection(p);
      const commit=()=>{change();moveScene(p);};
      if(p.axis!=='none'&&!reduced.matches&&document.startViewTransition){
        const t=document.startViewTransition(commit);t.finished.catch(()=>{});
      }else commit();
    }
  };
  const pinChrome=()=>{
    const header=document.querySelector('.topbar');if(!header)return;
    const measure=()=>root.style.setProperty('--chrome-offset',Math.ceil(header.getBoundingClientRect().bottom)+'px');
    measure();if(window.ResizeObserver)new ResizeObserver(measure).observe(header);
    addEventListener('resize',measure);
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',pinChrome);else pinChrome();
})();

// Keep the long circulation menu reachable above the viewport edge.
(() => {
  const place = menu => {
    if (!menu.open) return;
    const panel=menu.querySelector('.circulation-flyout');
    if (!panel) return;
    panel.style.maxHeight='calc(100dvh - 32px)';
    const anchor=menu.getBoundingClientRect();
    const height=Math.min(panel.scrollHeight+2,innerHeight-32);
    const top=Math.max(16,Math.min(anchor.top-24,innerHeight-height-16));
    panel.style.top=(top-anchor.top)+'px';
  };
  document.addEventListener('toggle',event=>{if(event.target.matches('[data-circulation-menu]'))requestAnimationFrame(()=>place(event.target));},true);
  addEventListener('resize',()=>document.querySelectorAll('[data-circulation-menu][open]').forEach(place));
})();
