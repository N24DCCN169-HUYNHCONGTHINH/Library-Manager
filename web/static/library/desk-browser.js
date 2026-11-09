/* Selecting a row fills fields only. All transactions keep their explicit confirmation. */
(() => {
  'use strict';
  const panel=document.getElementById('desk-browser'),desk=document.getElementById('desk-workspace');
  if(!panel||!desk)return;
  const form=panel.querySelector('[data-desk-browser-form]'),results=panel.querySelector('[data-desk-browser-results]'),status=panel.querySelector('[data-desk-browser-status]');
  const kind=form.elements.desk_kind,query=form.elements.desk_q,filter=panel.querySelector('.desk-browser-filter');
  let pending,timer,serial=0;
  const selection={};
  const updateFilter=()=>{filter.hidden=kind.value!=='copies';query.dataset.lookup=kind.value;};
  updateFilter();
  const load=async(page=1)=>{
    clearTimeout(timer);pending?.abort();pending=new AbortController();const current=++serial;
    const url=new URL(panel.dataset.browserUrl,location.href);
    for(const [key,value] of new FormData(form))url.searchParams.set(key,value);
    url.searchParams.set('desk_page',page);
    status.textContent='Đang tải danh sách…';results.inert=true;results.setAttribute('aria-busy','true');
    try{
      const response=await fetch(url,{signal:pending.signal,headers:{Accept:'text/html'},credentials:'same-origin'});
      if(!response.ok||response.redirected||!response.headers.get('content-type')?.includes('text/html'))throw Error();
      const html=await response.text();if(current!==serial)return;
      // Same-origin Django fragment. Reader/book fields and data attributes are escaped by the template.
      results.innerHTML=html;status.textContent='Đã cập nhật danh sách.';
    }catch(error){if(error.name!=='AbortError'&&current===serial)status.textContent='Chưa tải được danh sách. Vui lòng bấm Lọc danh sách để thử lại.';}
    finally{if(current===serial){results.inert=false;results.removeAttribute('aria-busy');}}
  };
  form.addEventListener('submit',event=>{event.preventDefault();load();});
  kind.addEventListener('change',()=>{query.value='';updateFilter();load();});
  form.elements.desk_status.addEventListener('change',()=>load());
  query.addEventListener('change',()=>load());
  query.addEventListener('input',()=>{clearTimeout(timer);pending?.abort();serial++;results.inert=true;timer=setTimeout(()=>load(),280);});
  panel.addEventListener('click',event=>{
    const page=event.target.closest('[data-desk-browser-page]');
    if(page){event.preventDefault();load(page.dataset.deskBrowserPage);return;}
    const button=event.target.closest('[data-desk-pick]');if(!button)return;
    const code=button.dataset.code,label=button.dataset.label;
    const fill=(id)=>{const input=document.getElementById(id);if(!input)return;input.value=code;input.dispatchEvent(new Event('change',{bubbles:true}));input.focus({preventScroll:true});input.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});};
    if(button.dataset.deskPick==='reader'){
      selection.reader=label+' · '+code;
      fill('checkout_reader_number');
    }else{
      const target=button.dataset.deskPick;
      if(target==='return'){
        const url=new URL(form.action);
        url.searchParams.set('tab','loans');
        url.searchParams.set('barcode',code);
        url.hash='return';
        location.assign(url);
        return;
      }
      if(target!=='checkout')return;
      fill(target+'_barcode');selection.book=label+' · '+code;
    }
    panel.querySelector('[data-desk-selected]').textContent=Object.values(selection).join(' | ')+' — Chưa ghi giao dịch.';
  });
  desk.addEventListener('desk:tab-change',()=>{form.elements.tab.value=desk.dataset.activeTab;});
})();
