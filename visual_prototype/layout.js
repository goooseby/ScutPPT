'use strict';

const icons = {
  library: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  tasks: '<rect x="5" y="4" width="15" height="17" rx="2"/><path d="M9 3h7v3H9zM9 11h7M9 16h5"/>',
  settings: '<path d="m10 3-.6 2.1-2 .9-2.1-.5-2 3.5 1.5 1.6v2.8l-1.5 1.6 2 3.5 2.1-.5 2 .9L10 21h4l.6-2.1 2-.9 2.1.5 2-3.5-1.5-1.6v-2.8l1.5-1.6-2-3.5-2.1.5-2-.9L14 3Z"/><circle cx="12" cy="12" r="3"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .6-1.5 1-1.5 2M12 17h.01"/>',
  search: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  left: '<path d="m14 6-6 6 6 6"/>',
  right: '<path d="m10 6 6 6-6 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  file: '<path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10ZM13 3v7h7M8 14h8M8 17h5"/>',
  folder: '<path d="M3 7V5h6l2 2h10v13H3Z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  undo: '<path d="m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M3 16v5h5M16 21h5v-5"/>',
  school: '<path d="m3 9 9-6 9 6M5 10v10h14V10M9 20v-6h6v6M3 21h18M10 9h4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  export: '<path d="M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  play: '<path d="m8 4 12 8-12 8Z"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderLegacyLibrary(){
  const active=activeMaterials();
  const last=active.find(m=>m.id===state.lastMaterial)||active[0];
  const filtered=state.materials.filter(m=>view.filter==='trash'?m.deleted:!m.deleted)
    .filter(m=>!['pending','exported'].includes(view.filter)||(view.filter==='pending'?statusOf(m)!=='exported':statusOf(m)==='exported'))
    .filter(m=>`${m.title} ${m.topic} ${m.day}`.toLowerCase().includes(view.search.toLowerCase()));
  filtered.sort((a,b)=>view.sort==='name'?a.title.localeCompare(b.title,'zh'):view.sort==='date'?b.day.localeCompare(a.day):b.touched-a.touched);
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">YOUR LEARNING LIBRARY</div><h1>资料库</h1><p class="subtitle">把课堂留下的每一页，整理成自己的知识。</p></div><div class="actions"><button data-action="import">${icon('plus')}导入文件</button><button class="primary" data-nav="acquire">${icon('download')}获取课件</button></div></div>
    ${last&&view.filter==='all'&&!view.search?`<section class="continue-card"><div class="continue-art">${cover(last)}</div><div class="continue-copy"><div class="overline">继续上次的整理</div><h2>${esc(last.title)} <span style="font-weight:400;color:#8ca08e">/</span> ${esc(last.topic)}</h2><p>${esc(last.day)}　·　${last.pages} 页　·　已排除 ${last.excluded.length} 页</p><div class="tiny-progress"><span><i style="width:${Math.round((last.pages-last.excluded.length)/last.pages*100)}%"></i></span><span>保留 ${last.pages-last.excluded.length} 页</span></div></div><div class="actions"><button class="primary" data-open="${last.id}">继续整理 ${icon('arrow')}</button></div></section>`:''}
    <div class="toolbar"><div class="tabs" aria-label="资料筛选">${[['all','全部资料',active.length],['pending','待整理',active.filter(m=>statusOf(m)!=='exported').length],['exported','已导出',active.filter(m=>statusOf(m)==='exported').length]].map(([key,label,count])=>`<button data-filter="${key}" class="${view.filter===key?'active':''}">${label}<span class="count">${count}</span></button>`).join('')}<button data-filter="trash" class="${view.filter==='trash'?'active':''}" title="回收站">${icon('trash')}</button></div><label class="search-box">${icon('search')}<input id="library-search" placeholder="搜索课程、日期…" aria-label="搜索资料" value="${esc(view.search)}"></label></div>
    <div class="library-tools"><span>${view.filter==='trash'?'回收站 · 可随时恢复':'我的课件'} <span style="color:#b4bcb6">/</span> ${filtered.length} 份</span><select id="library-sort" aria-label="排序"><option value="recent" ${view.sort==='recent'?'selected':''}>最近整理优先</option><option value="date" ${view.sort==='date'?'selected':''}>上课日期优先</option><option value="name" ${view.sort==='name'?'selected':''}>按课程名称</option></select></div>
    ${filtered.length?`<div class="course-grid">${filtered.map(m=>`<article class="course-card"><button class="course-open" ${m.deleted?`data-restore="${m.id}"`:`data-open="${m.id}"`} aria-label="${m.deleted?'恢复':'整理'} ${esc(m.title)}"><div class="course-cover" style="background:${(palettes[m.tone]||palettes.green)[2]}66">${cover(m)}</div><div class="course-info"><h3>${esc(m.title)} · ${esc(m.topic)}</h3><div class="meta"><span>${esc(m.day)}</span><span>·</span><span>${m.pages} 页</span><span>·</span><span>${m.source==='import'?'本地导入':'华工视频平台'}</span></div><div class="course-info-bottom">${m.deleted?'<span class="badge pending">点击恢复课件</span>':badge(m)}<span>${m.edited?`保留 ${m.pages-m.excluded.length} 页`:'等待第一次整理'}</span></div></div></button>${!m.deleted?`<button class="icon-button card-menu" data-menu="${m.id}" aria-label="管理 ${esc(m.title)}">${icon('more')}</button>`:''}</article>`).join('')}</div>`:empty(view.filter==='trash'?'回收站是空的':view.search?'没有找到相关课件':'这里还没有课件',view.search?'试试其他课程名，或清空搜索条件。':'先去获取课件，或导入已有图片和 PDF。',view.search?'<button data-action="clear-search">清空搜索</button>':'<button class="primary" data-nav="acquire">获取课件</button>')}
    <div class="footer-count">${view.filter==='trash'?'删除资料库课件不会影响已导出的文件':'原始页面保留在资料库中 · 排除页面后仍可恢复'}</div>`;
}
function empty(title,description,action=''){return `<div class="empty">${icon('folder')}<h2>${title}</h2><p>${description}</p>${action}</div>`;}
function renderPageEditor(){
  const m=material();if(!m)return navigate('library');
  const visible=Array.from({length:m.pages},(_,i)=>i+1).filter(p=>view.pageFilter==='all'||!m.excluded.includes(p));
  const excluded=m.excluded.includes(view.currentPage);
  main.innerHTML=`<button class="back-button" data-nav="library">${icon('left')}返回资料库</button><div class="page-heading editor-heading"><div><h1>${esc(m.title)} <span style="font-weight:350;color:#adb5ac">/</span> ${esc(m.topic)}</h1><p class="subtitle"><span>${m.day}</span><span>·</span><span>${m.pages} 页原始页面</span><span>·</span>${badge(m)}</p></div><div class="actions"><span class="saved-label">${icon('check')}${view.saving?'正在保存…':'更改已保存'}</span><button data-action="quick-export" ${view.saving||m.pages===m.excluded.length?'disabled':''}>${icon('export')}快速导出</button><button class="primary" data-action="export" ${view.saving||m.pages===m.excluded.length?'disabled':''}>另存为…</button></div></div>
    <div class="editor-toolbar"><div class="segmented"><button data-page-filter="all" class="${view.pageFilter==='all'?'active':''}">全部页面</button><button data-page-filter="kept" class="${view.pageFilter==='kept'?'active':''}">仅保留页</button></div><span class="separator"></span><button data-action="select-all-pages">${view.selected.size===visible.length&&visible.length?'取消全选':'全选'}</button><button data-action="range">选择范围</button><button data-action="exclude" ${!view.selected.size?'disabled':''}>排除</button><button data-action="restore" ${!view.selected.size?'disabled':''}>恢复</button><span class="separator"></span><button data-action="undo" ${!view.undo.length?'disabled':''} title="撤销上次排除或恢复">${icon('undo')}撤销</button><span class="selected-label">已选中 ${view.selected.size} 页</span></div>
    <div class="editor-layout"><section><div class="pages-grid">${visible.map(p=>`<article class="page-tile ${m.excluded.includes(p)?'excluded':''} ${view.selected.has(p)?'selected':''} ${view.currentPage===p?'current':''}" data-page-tile="${p}"><label class="page-check"><input type="checkbox" data-page-check="${p}" aria-label="选中第 ${p} 页" ${view.selected.has(p)?'checked':''}></label><div class="page-art" tabindex="0" role="button" aria-label="预览第 ${p} 页，双击放大" data-preview="${p}">${slide(m,p,true)}</div><div class="page-caption"><strong>${String(p).padStart(2,'0')}</strong><button data-toggle-page="${p}">${m.excluded.includes(p)?'恢复此页':'排除此页'}</button></div></article>`).join('')}</div>${!visible.length?empty('没有保留的页面','切换到全部页面，可以恢复之前排除的内容。','<button data-page-filter="all">查看全部页面</button>'):''}</section>
    <aside class="preview-panel"><div class="preview-title">页面预览 <span>原始页 ${view.currentPage} / ${m.pages}</span><button class="icon-button" data-action="fullscreen" title="放大页面" aria-label="放大页面">${icon('expand')}</button></div><div class="large-art" data-action="fullscreen">${slide(m,view.currentPage)}</div><div class="preview-controls"><button class="icon-button" data-action="previous" ${view.currentPage===1?'disabled':''} aria-label="上一页">${icon('left')}</button><span>第 ${view.currentPage} 页</span><button class="icon-button" data-action="next" ${view.currentPage===m.pages?'disabled':''} aria-label="下一页">${icon('right')}</button></div><div class="preview-detail"><h3>${excluded?'此页已排除':'此页将保留在 PDF 中'}</h3><p>${excluded?'原始页面依然保留。恢复后，这一页将重新进入导出结果。':'单击缩略图查看大图；勾选多页，可以批量排除无关画面。'}</p><button class="${excluded?'secondary':''}" data-toggle-page="${view.currentPage}">${excluded?icon('undo')+'恢复此页':icon('close')+'排除此页'}</button></div><div class="keyboard-note"><kbd>←</kbd> <kbd>→</kbd> 翻页　<kbd>E</kbd> 排除 / 恢复<br><kbd>Ctrl</kbd> + <kbd>Z</kbd> 撤销　双击缩略图放大</div></aside></div>
    <div class="editor-summary"><span>共 ${m.pages} 页 <span style="color:#c4cbc4">/</span> <strong>保留 ${m.pages-m.excluded.length} 页</strong> <span style="color:#c4cbc4">/</span> 排除 ${m.excluded.length} 页</span><span>排除不会删除原始图片</span></div>`;
}
