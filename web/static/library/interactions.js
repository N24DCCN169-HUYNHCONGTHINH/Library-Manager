/* Progressive enhancement: GET suggestions; writes still require explicit form submission. */
(() => {
  'use strict';
  const endpoint = document.body.dataset.lookupUrl;
  if (!endpoint) return;
  const desk = document.getElementById('desk-workspace');
  if (desk) {
    const legacy = {'open-loans':'loans',reservations:'reservations',fines:'fines'};
    const panels = [...desk.querySelectorAll('[data-desk-panel]')];
    const activate = (name, push=false) => {
      if (!panels.some(panel => panel.dataset.deskPanel === name)) name = 'checkout';
      panels.forEach(panel => { panel.hidden = panel.dataset.deskPanel !== name; });
      document.querySelectorAll('[data-desk-tab]').forEach(link => {
        if (link.dataset.deskTab === name) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
      });
      desk.dataset.activeTab = name;
      if (push) { const url = new URL(location.href); url.searchParams.set('tab',name); url.hash=''; if(url.href!==location.href)history.pushState({},'',url); }
    };
    activate(legacy[location.hash.slice(1)] || desk.dataset.activeTab);
    document.querySelectorAll('[data-desk-tab]').forEach(link => link.addEventListener('click',event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault(); activate(link.dataset.deskTab,true);
      const fromMenu = link.closest('[data-circulation-menu]');
      document.querySelectorAll('[data-circulation-menu]').forEach(menu => {menu.open=false;});
      if(fromMenu) panels.find(panel=>!panel.hidden)?.querySelector('input:not([type=hidden]),a,button')?.focus({preventScroll:true});
    }));
    window.addEventListener('popstate',()=>activate(legacy[location.hash.slice(1)] || new URLSearchParams(location.search).get('tab') || 'checkout'));
    desk.querySelectorAll('.desk-action-form').forEach(form => {
      form.addEventListener('submit',()=>{ form.setAttribute('aria-busy','true'); form.querySelectorAll('button[type="submit"]').forEach(button=>{button.disabled=true;button.textContent='Đang xử lý…';}); });
    });
    desk.querySelectorAll('[data-async-expire]').forEach(form => form.addEventListener('submit',async event=>{
      event.preventDefault(); const button=form.querySelector('button'); if(button.disabled)return;
      const status=form.querySelector('[data-expire-status]');button.disabled=true;form.setAttribute('aria-busy','true');status.textContent='Đang kiểm tra hàng chờ…';
      try {
        const response=await fetch(form.action || location.href,{method:'POST',body:new FormData(form),credentials:'same-origin',headers:{Accept:'application/json'}});
        if(!response.ok || response.redirected)throw new Error('update');
        const data=await response.json();
        // HTML comes only from the authenticated, same-origin Django template,
        // whose record values are escaped by the server.
        document.getElementById('reservation-results').innerHTML=data.html;status.textContent=data.message;
      } catch(_){status.textContent='Chưa xác nhận được kết quả. Hãy kiểm tra kết nối hoặc tải lại mục Đặt trước; hệ thống không tự gửi lại thao tác.';}
      finally {button.disabled=false;form.removeAttribute('aria-busy');}
    }));
  }
  document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('[data-circulation-menu][open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});});
  document.addEventListener('pointerdown',event=>document.querySelectorAll('[data-circulation-menu]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
  let serial = 0;
  document.querySelectorAll('input[data-lookup]').forEach(input => {
    const wrapper = document.createElement('div');
    wrapper.className = 'entity-picker';
    input.before(wrapper); wrapper.append(input);
    const list = document.createElement('div');
    list.className = 'entity-suggestions'; list.id = `suggestions-${++serial}`;
    list.setAttribute('role', 'listbox'); list.hidden = true;
    const status = document.createElement('span');
    status.className = 'picker-status'; status.setAttribute('role', 'status');
    wrapper.append(list, status);
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', list.id); input.setAttribute('aria-expanded', 'false');
    input.setAttribute('autocomplete', 'off');
    let timer, controller, version = 0, selected = -1, rows = [];
    const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); selected = -1; };
    const choose = row => {
      clearTimeout(timer); controller?.abort(); ++version;
      if (input.dataset.lookupMode === 'navigate' && row.url) {
        const url = new URL(row.url, location.origin);
        if (url.origin === location.origin) location.assign(url.href);
      } else {
        input.value = row.value; input.dispatchEvent(new Event('change', {bubbles: true}));
        close(); input.focus({preventScroll:true}); status.textContent = `Đã chọn: ${row.label} · ${row.detail}`;
      }
    };
    input.addEventListener('input', () => {
      clearTimeout(timer); controller?.abort(); const revision = ++version; close();
      const q = input.value.trim();
      if (q.length < 2 && !(/^[0-9]+$/.test(q) && ['loans', 'fines'].includes(input.dataset.lookup))) { status.textContent = ''; return; }
      timer = setTimeout(async () => {
        controller = new AbortController(); status.textContent = 'Đang tìm…';
        try {
          const url = new URL(endpoint, location.origin);
          url.search = new URLSearchParams({kind: input.dataset.lookup, q});
          ['branch', 'status'].forEach(name => {
            const field = input.form?.elements.namedItem(name);
            if (field?.value) url.searchParams.set(name, field.value);
          });
          const response = await fetch(url, {signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'application/json'}});
          if (!response.ok) throw new Error('lookup');
          const data = await response.json();
          if (revision !== version || !input.matches(':focus')) return;
          rows = data.results; list.replaceChildren();
          rows.forEach((row, index) => {
            const button = document.createElement('button'); button.type = 'button'; button.className = 'entity-option';
            button.id = `${list.id}-${index}`; button.setAttribute('role', 'option'); button.setAttribute('aria-selected', 'false'); button.tabIndex = -1;
            const title = document.createElement('strong'); title.textContent = row.label;
            const detail = document.createElement('small'); detail.textContent = row.detail;
            button.append(title, detail); button.addEventListener('click', () => choose(row));
            list.append(button);
          });
          status.textContent = rows.length ? `${rows.length} gợi ý. Dùng phím lên/xuống hoặc chạm để chọn.` : 'Không tìm thấy kết quả phù hợp.';
          list.hidden = !rows.length; input.setAttribute('aria-expanded', String(!!rows.length));
        } catch (error) {
          if (error.name !== 'AbortError' && revision === version) status.textContent = 'Chưa tải được gợi ý. Bạn vẫn có thể nhập và dùng nút xác nhận.';
        }
      }, 250);
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') { clearTimeout(timer); controller?.abort(); ++version; close(); }
      if (list.hidden) return;
      if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault(); selected = (selected + (event.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
        [...list.children].forEach((node, i) => node.setAttribute('aria-selected', String(i === selected)));
        input.setAttribute('aria-activedescendant', list.children[selected].id); list.children[selected].scrollIntoView({block: 'nearest'});
      } else if (event.key === 'Enter' && selected >= 0) { event.preventDefault(); choose(rows[selected]); }
    });
    wrapper.addEventListener('focusout', event => { if (!wrapper.contains(event.relatedTarget)) close(); });
    document.addEventListener('pointerdown', event => { if (!wrapper.contains(event.target)) { clearTimeout(timer); controller?.abort(); ++version; close(); } });
  });
  document.querySelectorAll('[data-open-url]').forEach(row => {
    row.classList.add('entity-openable');
    row.addEventListener('dblclick', event => {
      if (event.target.closest('a,button,input,select,textarea,summary')) return;
      const url = new URL(row.dataset.openUrl, location.origin);
      if (url.origin === location.origin) location.assign(url.href);
    });
  });
  document.querySelectorAll('.book-card').forEach(card => card.addEventListener('dblclick', event => {
    if (event.target.closest('a,button,input,summary')) return;
    const details = card.querySelector('.copy-details'); if (details) details.open = true;
  }));
  const collection = document.getElementById('book-collection');
  if (collection) {
    const applyLayout = mode => {
      collection.dataset.layout = mode;
      document.querySelectorAll('[data-book-layout]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.bookLayout === mode)));
    };
    try { if (localStorage.getItem('library-book-layout') === 'table') applyLayout('table'); } catch (_) { /* storage optional */ }
    document.querySelectorAll('[data-book-layout]').forEach(button => button.addEventListener('click', () => {
      applyLayout(button.dataset.bookLayout);
      try { localStorage.setItem('library-book-layout', button.dataset.bookLayout); } catch (_) { /* storage optional */ }
    }));
  }
})();
