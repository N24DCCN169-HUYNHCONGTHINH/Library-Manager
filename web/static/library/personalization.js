(() => {
const root=document.documentElement, system=matchMedia('(prefers-color-scheme: dark)');
let choice=root.dataset.themeChoice||'system';
const apply=()=>{root.dataset.bsTheme=choice==='system'?(system.matches?'dark':'light'):choice;root.dataset.themeChoice=choice;document.querySelectorAll('.theme-switch button[name=theme]').forEach(b=>b.setAttribute('aria-pressed',String(b.value===choice)));};
apply();system.addEventListener('change',apply);
document.querySelectorAll('.theme-switch').forEach(form=>form.addEventListener('submit',async event=>{
event.preventDefault();if(!event.submitter||form.dataset.busy)return;form.dataset.busy='true';const old=choice;choice=event.submitter.value;apply();const status=form.querySelector('[role=status]'),data=new FormData(form);data.set('theme',choice);
try{const response=await fetch(form.action,{method:'POST',body:data,headers:{'Accept':'application/json'},credentials:'same-origin'});if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))throw Error();await response.json();status.textContent='Đã lưu chế độ hiển thị.';}catch(_){choice=old;apply();status.textContent='Chưa lưu được. Vui lòng thử lại.';}finally{delete form.dataset.busy;}
}));})();
