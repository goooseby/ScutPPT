'use strict';

Object.assign(view,{courseId:null,courseSelected:new Set(),courseFilter:'all',courseFrom:'',courseTo:'',scanExpanded:new Set(),sessionMenuId:null});
const reviewed=m=>m.reviewRevision===m.revision;
const courseById=id=>(state.courseLibrary||[]).find(c=>c.id===id)||{id:'unfiled',title:'未归类',term:''};
const sessions=id=>activeMaterials().filter(m=>(m.courseId||'unfiled')===id).sort((a,b)=>a.day.localeCompare(b.day)||String(a.lectureId||'').localeCompare(String(b.lectureId||''),undefined,{numeric:true})||a.id.localeCompare(b.id));
const exportBadge=m=>`<span class="badge ${m.exported?(m.exportRevision===m.revision?'exported':'changed'):'pending'}">${m.exported?(m.exportRevision===m.revision?'已导出':'修改后待导出'):'未导出'}</span>`;
const queueMaterials=()=> (state.reviewQueue||[]).map(id=>activeMaterials().find(m=>m.id===id)).filter(Boolean);

function renderLibrary(){
  if(view.filter==='trash')return renderLegacyLibrary();
  const groups=[...(state.courseLibrary||[])];
  if(sessions('unfiled').length)groups.push(courseById('unfiled'));
  const query=view.search.toLowerCase();
  let list=groups.map(c=>({...c,items:sessions(c.id)})).filter(c=>`${c.title} ${c.term}`.toLowerCase().includes(query)||c.items.some(m=>`${m.day} ${m.note||''}`.toLowerCase().includes(query)));
  if(view.filter==='pending')list=list.filter(c=>c.items.some(m=>!reviewed(m)));
  list.sort((a,b)=>view.sort==='name'?a.title.localeCompare(b.title,'zh'):Math.max(0,...b.items.map(m=>m.touched))-Math.max(0,...a.items.map(m=>m.touched)));
  const last=activeMaterials().find(m=>m.id===state.lastMaterial);
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">YOUR LEARNING LIBRARY</div><h1>资料库</h1><p class="subtitle">以课程收纳课件，按自己的节奏整理每次课堂。</p></div><div class="actions"><button data-course-action="new">新建课程</button><button data-action="import">导入文件</button><button class="primary" data-nav="acquire">获取课件</button></div></div>
  ${last?`<section class="continue-card"><div class="continue-art">${cover(last)}</div><div class="continue-copy"><div class="overline">继续上次的整理</div><h2>${esc(courseById(last.courseId).title)} · ${esc(last.day)}</h2><p>${esc(last.note||last.title)} · 上次看到第 ${last.lastPage} 页</p><p>${queueMaterials().length>1?`本次整理范围：${queueMaterials().length} 份课件`:'整理记录已自动保存'}</p></div><button class="primary" data-open="${last.id}">继续整理 ${icon('arrow')}</button></section>`:''}
  <div class="toolbar"><div class="tabs"><button data-filter="all" class="${view.filter==='all'?'active':''}">全部课程</button><button data-filter="pending" class="${view.filter==='pending'?'active':''}">有待整理课件</button><button data-filter="trash">回收站</button></div><label class="search-box">${icon('search')}<input id="library-search" value="${esc(view.search)}" placeholder="搜索课程、日期…"></label></div>
  <div class="library-tools"><span>${list.length} 门课程 · ${activeMaterials().length} 份课件</span><select id="library-sort"><option value="recent">最近整理优先</option><option value="name" ${view.sort==='name'?'selected':''}>按课程名称</option></select></div>
  ${list.length?`<div class="course-grid">${list.map(c=>{const pending=c.items.filter(m=>!reviewed(m)).length;const latest=c.items.at(-1);return `<article class="course-card"><button class="course-open" data-nav="course/${c.id}"><div class="course-cover">${cover({title:c.title,term:c.term,day:c.term||'课程资料',pages:c.items.reduce((n,m)=>n+m.pages,0),coverKey:c.id,coverStyle:c.coverStyle,coverPalette:c.coverPalette})}</div><div class="course-info"><h3>${esc(c.title)}</h3><div class="meta">${esc(c.term||'学期未设置')} · ${c.items.length} 份课件</div><div class="course-info-bottom"><span class="badge ${pending?'pending':'exported'}">${pending?pending+' 份待整理':c.items.length?'已全部整理':'等待添加课件'}</span><span>${latest?'最新 '+esc(latest.day):''}</span></div></div></button></article>`;}).join('')}</div>`:empty('这里还没有相关课程','获取课件后自动按课程收纳，也可以新建课程并归入本地资料。','<button class="primary" data-nav="acquire">获取课件</button>')}`;
}

function visibleSessions(){return sessions(view.courseId).filter(m=>(view.courseFilter!=='pending'||!reviewed(m))&&(!view.courseFrom||m.day>=view.courseFrom)&&(!view.courseTo||m.day<=view.courseTo));}
function selectedSessions(){return sessions(view.courseId).filter(m=>view.courseSelected.has(m.id));}
function renderCourse(){
  const c=courseById(view.courseId),all=sessions(view.courseId),rows=visibleSessions();
  const pending=all.filter(m=>!reviewed(m)).length;
  const selected=selectedSessions();
  main.innerHTML=`<button class="back-button" data-nav="library">${icon('left')}返回资料库</button><div class="page-heading"><div><div class="eyebrow">COURSE COLLECTION</div><h1>${esc(c.title)}</h1><p class="subtitle">${esc(c.term||'学期未设置')} · ${all.length} 份课件 · ${pending} 份待整理</p></div><div class="actions">${c.id!=='unfiled'?'<button data-course-action="edit">课程信息</button>':''}<button data-action="import">导入文件</button><button class="primary" data-course-action="pending" ${pending?'':'disabled'}>整理待整理课件</button></div></div>
  ${c.id==='unfiled'?'<p class="helper-note">这里包含本地导入或暂未确认课程归属的旧课件。选中后可归入课程；平台旧课件也可在重新扫描匹配后自动归类。</p>':''}
  <div class="course-controls"><select class="field-input" id="course-filter"><option value="all">全部课次</option><option value="pending" ${view.courseFilter==='pending'?'selected':''}>仅待整理</option></select><label>从 <input type="date" id="course-from" value="${view.courseFrom}"></label><label>至 <input type="date" id="course-to" value="${view.courseTo}"></label><button data-course-action="recent">选择最近 3 份</button><button data-course-action="visible">选择当前结果</button><button data-course-action="clear">清空选择</button></div>
  <div class="course-batch"><span>已选 ${selected.length} 份 · 保留 ${selected.reduce((n,m)=>n+m.pages-m.excluded.length,0)} 页 <small>无需先标记已整理</small></span><div class="actions"><button data-course-action="assign" ${selected.length?'':'disabled'}>归入课程</button><button data-course-action="batch" ${selected.length?'':'disabled'}>更多导出方式</button><button data-course-action="quick-batch" class="primary" ${selected.length?'':'disabled'}>${icon('export')}快速导出选中</button><button data-course-action="selected" ${selected.length?'':'disabled'}>整理选中</button></div></div>
  ${rows.length?`<div class="table-wrap session-table"><table><thead><tr><th></th><th>上课日期 / 课件</th><th>保留页面</th><th>整理状态</th><th>导出状态</th><th>课件操作</th></tr></thead><tbody>${rows.map(m=>`<tr class="session-row"><td><input type="checkbox" data-session-select="${m.id}" ${view.courseSelected.has(m.id)?'checked':''} aria-label="选择 ${esc(m.day)} 课件"></td><td class="session-entry" data-course-session="${m.id}"><button class="session-title" data-course-session="${m.id}"><span class="session-title-main"><strong>${esc(m.day)}</strong><span>${esc(m.note|| (m.source==='import'?m.title:'课堂课件'))}</span></span><small>${m.lectureId?'课次 '+esc(m.lectureId):m.source==='import'?'本地资料':'平台课件'}</small></button></td><td data-course-session="${m.id}">${m.pages-m.excluded.length} / ${m.pages}</td><td data-course-session="${m.id}">${badge(m)}</td><td data-course-session="${m.id}">${exportBadge(m)}</td><td class="session-action-cell"><div class="session-actions"><button data-quick-export="${m.id}" title="直接保存到默认导出目录">快速导出</button><button data-note="${m.id}" title="编辑内容备注">备注</button><button class="icon-button session-more ${view.sessionMenuId===m.id?'active':''}" data-session-menu="${m.id}" aria-label="更多课件操作" aria-expanded="${view.sessionMenuId===m.id}">${icon('more')}</button>${view.sessionMenuId===m.id?`<div class="session-menu" role="menu"><button data-mark-reviewed="${m.id}" ${reviewed(m)?'disabled':''}>${icon('check')}${reviewed(m)?'已标记为已整理':'标记为已整理'}</button><button class="danger" data-delete-session="${m.id}">${icon('trash')}移入回收站</button></div>`:''}</div></td></tr>`).join('')}</tbody></table></div>`:empty('没有符合条件的课件','调整日期范围，或从获取课件页面添加资料。')}`;
}

function renderEditor(){
  renderPageEditor();const m=material();if(!m)return;
  const c=courseById(m.courseId),queue=queueMaterials();
  const items=queue.some(x=>x.id===m.id)?queue:sessions(m.courseId||'unfiled');
  const index=items.findIndex(x=>x.id===m.id);
  main.querySelector('.back-button').dataset.nav='course/'+(m.courseId||'unfiled');
  main.querySelector('.back-button').innerHTML=icon('left')+'返回 '+esc(c.title);
  const completion=document.createElement('div');completion.className='review-completion';
  completion.innerHTML=`<span>${reviewed(m)?'已确认这份课件整理完成':'确认本次课的页面后，再继续下一份。'} · ${exportBadge(m)}</span><button class="primary" data-course-action="complete" ${view.saving?'disabled':''}>${index<items.length-1?'标记已整理，处理下一份':'标记已整理，返回课程'}</button>`;
  main.append(completion);
}

function renderAcquire(){
  renderFlatAcquire();const table=main.querySelector('.table-wrap');if(!table)return;
  const groups=new Map();availableCourses.forEach(c=>{const key=c.groupId||String(c.course_id);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(c);});
  const unavailable=c=>activeMaterials().some(m=>m.sourceKey===c.id)||state.tasks.some(t=>t.sourceKey===c.id&&['running','paused'].includes(t.status));
  table.innerHTML=`<div class="scan-group-tools"><label><input type="checkbox" id="scan-all"> 选择全部尚未获取课件</label><span>${groups.size} 门课程 · ${availableCourses.length} 节课</span></div>${[...groups].map(([id,items])=>{const fresh=items.filter(c=>!unavailable(c)),chosen=fresh.filter(c=>view.scanSelected.has(c.id));return `<section class="scan-course"><div class="scan-course-heading"><input type="checkbox" data-scan-group="${esc(id)}" ${fresh.length&&chosen.length===fresh.length?'checked':''} ${fresh.length?'':'disabled'} aria-label="选择 ${esc(items[0].title)} 尚未获取课件"><button data-scan-expand="${esc(id)}"><strong>${esc(items[0].title)}</strong><span>本次 ${items.length} 节 · 已获取 / 获取中 ${items.length-fresh.length} · 新增 ${fresh.length}</span></button><button data-scan-expand="${esc(id)}">${view.scanExpanded.has(id)?'收起课次':'查看课次'}</button></div>${view.scanExpanded.has(id)?`<div class="scan-lectures">${items.slice().sort((a,b)=>a.day.localeCompare(b.day)).map(c=>`<label><input type="checkbox" data-scan-select="${esc(c.id)}" ${view.scanSelected.has(c.id)?'checked':''} ${unavailable(c)?'disabled':''}><span>${esc(c.day)}</span><small>课次 ${esc(c.sub_id)}</small><span class="badge ${unavailable(c)?'exported':'pending'}">${unavailable(c)?'已获取 / 获取中':'可获取'}</span></label>`).join('')}</div>`:''}</section>`;}).join('')}`;
  table.querySelectorAll('[data-scan-group]').forEach(el=>{const items=groups.get(el.dataset.scanGroup).filter(c=>!unavailable(c));const n=items.filter(c=>view.scanSelected.has(c.id)).length;el.indeterminate=n>0&&n<items.length;});
  const eligible=availableCourses.filter(c=>!unavailable(c));const count=eligible.filter(c=>view.scanSelected.has(c.id)).length;
  const all=table.querySelector('#scan-all');all.checked=eligible.length>0&&count===eligible.length;all.indeterminate=count>0&&count<eligible.length;
}

async function startReview(items){
  if(!items.length)return toast('没有需要整理的课件。');
  await call('reviewQueue',{ids:items.map(m=>m.id)});openMaterial(items[0].id);
}
async function courseClick(b){
  if(!b)return false;
  if(b.dataset.sessionMenu){view.sessionMenuId=view.sessionMenuId===b.dataset.sessionMenu?null:b.dataset.sessionMenu;renderCourse();requestAnimationFrame(()=>main.querySelector(`[data-session-menu="${b.dataset.sessionMenu}"]`)?.focus());return true;}
  if(b.dataset.markReviewed){const m=state.materials.find(m=>m.id===b.dataset.markReviewed);view.sessionMenuId=null;await call('reviewed',{id:m.id,revision:m.revision});toast('已标记为已整理');return true;}
  if(b.dataset.deleteSession){view.sessionMenuId=null;await call('trash',{id:b.dataset.deleteSession,deleted:true});toast('已移入回收站，可随时恢复');return true;}
  if(b.dataset.scanExpand){const id=b.dataset.scanExpand;view.scanExpanded.has(id)?view.scanExpanded.delete(id):view.scanExpanded.add(id);renderAcquire();return true;}
  if(b.dataset.courseSession){await startReview([state.materials.find(m=>m.id===b.dataset.courseSession)]);return true;}
  if(b.dataset.quickExport){if(await call('quickExport',{id:b.dataset.quickExport}))toast('已快速导出到默认目录，可在任务页查看进度');return true;}
  if(b.dataset.note){const m=state.materials.find(m=>m.id===b.dataset.note);showModal('课件备注',`<p>${esc(m.day)} · ${esc(m.title)}</p><label class="field">内容备注<input id="session-note" type="text" maxlength="120" value="${esc(m.note||'')}" placeholder="例如：线性规划的图解法"></label>`,`<button data-action="close-modal">取消</button><button class="primary" data-save-note="${m.id}">保存</button>`);return true;}
  if(b.dataset.saveNote){await call('materialNote',{id:b.dataset.saveNote,note:$('#session-note').value});closeModal();return true;}
  const action=b.dataset.courseAction;if(!action)return false;
  if(view.saving){toast('正在保存，请稍候。');return true;}
  if(action==='new'||action==='edit'){
    const c=action==='edit'?courseById(view.courseId):{title:'',term:''};
    showModal(action==='new'?'新建课程':'课程信息',`<label class="field">课程名称<input id="course-title" type="text" maxlength="120" value="${esc(c.title)}"></label><label class="field">学期 / 班级（选填）<input id="course-term" type="text" maxlength="80" value="${esc(c.term)}" placeholder="例如：2026 秋季 · 1 班"></label>`,`<button data-action="close-modal">取消</button><button class="primary" data-course-action="save" ${c.id?`data-course-id="${c.id}"`:''}>保存课程</button>`);
  }else if(action==='save'){
    const c=await call('saveCourse',{id:b.dataset.courseId,title:$('#course-title').value,term:$('#course-term').value});closeModal();navigate('course/'+c.id);
  }else if(action==='pending')await startReview(sessions(view.courseId).filter(m=>!reviewed(m)));
  else if(action==='selected')await startReview(selectedSessions());
  else if(action==='complete'){
    const m=material(),q=queueMaterials(),items=q.some(x=>x.id===m.id)?q:sessions(m.courseId||'unfiled'),index=items.findIndex(x=>x.id===m.id);
    view.saving=true;renderEditor();
    try{await call('reviewed',{id:m.id,revision:m.revision});}finally{view.saving=false;render();}
    if(index<items.length-1)openMaterial(items[index+1].id);else{await call('reviewQueue',{ids:[]});navigate('course/'+(m.courseId||'unfiled'));toast('本次范围已处理完成');}
  }else if(['recent','visible','clear'].includes(action)){
    view.courseSelected=new Set((action==='clear'?[]:action==='recent'?sessions(view.courseId).slice(-3):visibleSessions()).map(m=>m.id));renderCourse();
  }else if(action==='assign'){
    showModal('归入课程',`<p>将选中的 ${selectedSessions().length} 份课件归入课程，页面整理记录保留。</p><label class="field">已有课程<select id="assign-course" class="field-input"><option value="">未归类</option>${(state.courseLibrary||[]).map(c=>`<option value="${c.id}">${esc(c.title)} · ${esc(c.term)}</option>`).join('')}</select></label><label class="field">或新建课程<input id="assign-new" type="text" maxlength="120" placeholder="填写后将新建并归入该课程"></label>`,'<button data-action="close-modal">取消</button><button class="primary" data-course-action="confirm-assign">确认归入</button>');
  }else if(action==='confirm-assign'){
    let id=$('#assign-course').value;const title=$('#assign-new').value.trim();if(title)id=(await call('saveCourse',{title})).id;
    await call('assignCourse',{ids:selectedSessions().map(m=>m.id),courseId:id||null});view.courseSelected.clear();closeModal();navigate('course/'+(id||'unfiled'));
  }else if(action==='batch'){
    const items=selectedSessions(),pages=items.reduce((n,m)=>n+m.pages-m.excluded.length,0),pending=items.filter(m=>!reviewed(m)).length;
    showModal('导出选中课件',`<p>按上课日期顺序，导出 ${items.length} 份课件，共 ${pages} 页。</p>${pending?`<div class="notice">其中 ${pending} 份尚未确认整理完成，将使用当前保留的页面。</div>`:''}<label class="field">导出方式<select id="batch-mode" class="field-input"><option value="separate">分别导出，按课程保存到文件夹</option><option value="combined">合并为一个 PDF，按课次添加书签</option></select></label><p>分别导出时，已完成的文件会保留；取消或重试不会覆盖这些文件。</p>`,'<button data-action="close-modal">取消</button><button class="primary" data-course-action="confirm-batch">选择位置并导出</button>');
  }else if(action==='confirm-batch'){
    const mode=$('#batch-mode').value,ids=selectedSessions().map(m=>m.id);closeModal();if(await call('batchExport',{ids,mode})){toast('已加入导出任务');navigate('tasks');}
  }else if(action==='quick-batch'){
    if(await call('batchExport',{ids:selectedSessions().map(m=>m.id),mode:'separate',quick:true})){toast('已快速导出到默认目录');navigate('tasks');}
  }
  return true;
}
function courseChange(el){
  if(el.dataset.sessionSelect){el.checked?view.courseSelected.add(el.dataset.sessionSelect):view.courseSelected.delete(el.dataset.sessionSelect);renderCourse();return true;}
  const fields={'course-filter':'courseFilter','course-from':'courseFrom','course-to':'courseTo'};
  if(fields[el.id]){view[fields[el.id]]=el.value;renderCourse();return true;}
  if(el.dataset.scanGroup){availableCourses.filter(c=>(c.groupId||String(c.course_id))===el.dataset.scanGroup&&!activeMaterials().some(m=>m.sourceKey===c.id)&&!state.tasks.some(t=>t.sourceKey===c.id&&['running','paused'].includes(t.status))).forEach(c=>el.checked?view.scanSelected.add(c.id):view.scanSelected.delete(c.id));renderAcquire();return true;}
  return false;
}
