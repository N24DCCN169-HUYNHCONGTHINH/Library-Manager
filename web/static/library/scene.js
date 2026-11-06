/* Decorative route-to-route camera motion. No account data or URLs are stored. */
(() => {
  'use strict';
  const root = document.documentElement;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const positions = [[-5,-3],[4,2],[-2,4],[5,-4],[-4,1],[2,-2],[-1,-4],[4,4]];
  const storageKey = 'library-scene-position-v1';
  let previous = [0,0];
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (Array.isArray(saved) && saved.length===2 && saved.every(v=>Number.isFinite(v)&&Math.abs(v)<=5)) previous=saved;
  } catch (_) {}
  const update = () => {
    const url = new URL(location.href);
    const key = url.pathname + '|' + (url.searchParams.get('tab')||'');
    let hash=0;
    for (let i=0;i<key.length;i++) hash=(Math.imul(hash,31)+key.charCodeAt(i))>>>0;
    let index=hash%positions.length;
    if (positions[index].every((v,i)=>v===previous[i])) index=(index+3)%positions.length;
    const target=positions[index];
    const from=motion.matches?target:previous;
    root.style.setProperty('--scene-from-x',from[0]+'%');
    root.style.setProperty('--scene-from-y',from[1]+'%');
    root.style.setProperty('--scene-to-x',target[0]+'%');
    root.style.setProperty('--scene-to-y',target[1]+'%');
    // Alternate animation names so navigation within the circulation workspace restarts it.
    root.dataset.sceneRun=root.dataset.sceneRun==='a'?'b':'a';
    previous=target;
    try { sessionStorage.setItem(storageKey,JSON.stringify(target)); } catch (_) {}
  };
  update();
  addEventListener('popstate',update);
  motion.addEventListener('change',update);
  document.addEventListener('click',event=>{
    if (event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey) return;
    const link=event.target.closest('a[data-desk-tab]');
    if (link&&document.getElementById('desk-workspace')) requestAnimationFrame(update);
  },true);
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
