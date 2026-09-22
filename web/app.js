'use strict';

let state={materials:[],tasks:[],settings:{exportMode:'review'},lastMaterial:null};
let availableCourses=[];
let desktop=null;
let ready=false;
const updateState={info:null,checking:false,downloading:false,ready:false,progress:0,error:''};
const storageOK=true;
const pending=new Map();
let sequence=0;
let autoScanTimer=null;
let autoScanRequested=false;
let fullscreenPreloads=[];
let fullscreenFrame=null;
let fullscreenImageRequest=0;
let editorImageRequest=0;
let lastPageTimer=null;
let pendingLastPage=null;
const today=new Date();
const dateString=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const weekAgo=new Date(today);weekAgo.setDate(today.getDate()-6);
const view={page:'library',filter:'all',search:'',sort:'recent',materialId:null,pageFilter:'all',selected:new Set(),
  currentPage:1,undo:[],scanSelected:new Set(),loggedIn:false,scanned:false,scanning:false,taskFilter:'all',
  scanStart:dateString(weekAgo),scanEnd:dateString(today),directExport:false,saving:false,
  selectionAnchor:null,pageShiftPending:false};
const main=document.querySelector('#main'),modal=document.querySelector('#modal');
const $=selector=>document.querySelector(selector);
const material=()=>state.materials.find(m=>m.id===view.materialId);
const activeMaterials=()=>state.materials.filter(m=>!m.deleted);
const statusOf=m=>m.exported?(m.revision===m.exportRevision?'exported':'changed'):m.edited?'editing':'pending';
const statuses={pending:'待整理',editing:'整理中',exported:'已导出',changed:'修改后未导出'};
const badge=m=>`<span class="badge ${m.reviewRevision===m.revision?'exported':m.edited?'editing':'pending'}">${m.reviewRevision===m.revision?'已整理':m.edited?'整理中':'待整理'}</span>`;

function call(command,data={}){
  if(!desktop)return Promise.reject(new Error('桌面服务尚未连接，请通过课页启动程序打开。'));
  return new Promise((resolve,reject)=>{const id=String(++sequence);pending.set(id,{resolve,reject});desktop.request(id,command,JSON.stringify(data));});
}
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),6500);}
function fail(error){toast(error.message||String(error));}
function applySnapshot(snapshot){
  const fullscreenOpen=modal.open&&modal.classList.contains('fullscreen-modal');
  const oldMode=state.settings.exportMode;
  const wasLoggedIn=view.loggedIn;
  const wasScanning=view.scanning;
  state=snapshot;
  state.materials.forEach(m=>{let hash=0;for(const c of m.title)hash=(hash*31+c.charCodeAt(0))>>>0;m.tone=['green','blue','sand','purple'][hash%4];});
  availableCourses=snapshot.courses;
  view.loggedIn=snapshot.loggedIn;view.scanned=snapshot.scanned;view.scanning=snapshot.scanning;
  if(!ready||oldMode!==snapshot.settings.exportMode)view.directExport=snapshot.settings.exportMode==='direct';
  ready=true;
  if(!wasLoggedIn&&view.loggedIn&&!snapshot.scanned&&!snapshot.scanning){autoScanRequested=true;setTimeout(()=>scheduleAutoScan(250),0);}
  else if(wasScanning&&!view.scanning&&autoScanRequested)setTimeout(()=>scheduleAutoScan(250),0);
  if(view.page==='editor'&&!activeMaterials().some(m=>m.id===view.materialId)){view.materialId=null;navigate('library');}
  else if(fullscreenOpen){renderShell();scheduleFullscreen();}
  else render();
}
function scheduleAutoScan(delay=650){
  clearTimeout(autoScanTimer);
  autoScanRequested=true;
  if(!view.loggedIn||view.scanning)return;
  autoScanTimer=setTimeout(async()=>{
    if(!view.loggedIn||view.scanning||!view.scanStart||!view.scanEnd||view.scanStart>view.scanEnd)return;
    autoScanRequested=false;
    try{await call('scan',{start:view.scanStart,end:view.scanEnd});}
    catch(error){fail(error);}
  },delay);
}
function hydrate(){document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
function renderShell(){
  $('#app-version').textContent='v'+(state.appVersion||'0.2.0');
  document.body.classList.toggle('editing-course',view.page==='editor');
  const running=state.tasks.filter(t=>['running','paused'].includes(t.status)).length;
  $('#nav').innerHTML=[['library','资料库','library'],['acquire','获取课件','download'],['tasks','任务','tasks'],['about','关于','about']].map(([id,label,i])=>`<button class="nav-item ${(view.page===id||(id==='library'&&['editor','course'].includes(view.page)))?'active':''}" data-nav="${id}">${icon(i)}${label}${id==='tasks'&&running?`<span class="nav-count">${running}</span>`:''}</button>`).join('');
  $('[data-nav="settings"]').classList.toggle('active',view.page==='settings');
  $('#breadcrumb').innerHTML=`工作空间 <span>/</span> ${view.page==='editor'?`资料库 <span>/</span> ${esc(material()?.title||'课件整理')}`:({course:'课程课件',library:'资料库',acquire:'获取课件',tasks:'任务',about:'关于',settings:'设置'}[view.page])}`;
  const m=view.page==='editor'?material():null;
  $('#statusbar').innerHTML=`<span class="status-left"><i class="dot"></i>${m?`共 ${m.pages} 页 · 保留 ${m.pages-m.excluded.length} 页 · 排除 ${m.excluded.length} 页`:running?`${running} 项后台任务`:'课页 · 资料与整理记录保存在本机'}</span><span>${running?`<button data-nav="tasks">查看 ${running} 项任务 →</button>`:'原始页面保留，随时重新整理'}</span>`;
}
function route(){
  if(!ready)return;
  const [target='library',id]=location.hash.replace(/^#/,'').split('/');
  if(target==='editor'&&activeMaterials().some(m=>m.id===id)){
    if(view.materialId!==id){view.selected.clear();view.selectionAnchor=null;view.undo=[];view.pageFilter='all';}
    view.materialId=id;view.currentPage=state.materials.find(m=>m.id===id).lastPage||1;view.page='editor';
    state.lastMaterial=id;call('openMaterial',{id}).catch(fail);
  }else if(target==='course'){view.page='course';if(view.courseId!==id){view.courseSelected=new Set();view.courseFilter='all';view.courseFrom='';view.courseTo='';}view.courseId=id;}else view.page=['library','acquire','tasks','about','settings'].includes(target)?target:'library';
  render();main.scrollTop=0;
}
function navigate(page){if(view.saving)return toast('正在保存，请稍候再切换。');if(location.hash===`#${page}`)route();else location.hash=page;}
function render(){renderShell();({library:renderLibrary,course:renderCourse,acquire:renderAcquire,editor:renderEditor,tasks:renderTasks,about:renderAbout,settings:renderSettings}[view.page]||renderLibrary)();hydrate();}
function cover(m){
  const course=(state.courseLibrary||[]).find(c=>c.id===m.courseId);
  return generatedCover({...m,title:course?.title||m.title,term:course?.term||m.term,
    coverKey:course?.id||m.coverKey||m.courseId||m.id,coverStyle:course?.coverStyle||m.coverStyle,
    coverPalette:course?.coverPalette||m.coverPalette});
}
function slide(m,page=1,thumb=false){
  const media=m.media?.[page-1];
  return media?`<img class="slide" ${thumb?'loading="lazy"':''} decoding="async" src="${esc(thumb?media.thumb:media.src)}" alt="${esc(m.title)} · 第 ${page} 页">`:'<div class="empty">页面预览暂不可用</div>';
}
function renderFlatAcquire(){
  const rows=availableCourses;
  const exists=id=>activeMaterials().some(m=>m.sourceKey===id);
  const scheduled=id=>state.tasks.some(t=>t.sourceKey===id&&['running','paused'].includes(t.status));
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">BRING YOUR MATERIALS TOGETHER</div><h1>获取课件</h1><p class="subtitle">从课堂平台获取，或把已有资料带进来。</p></div><span class="badge ${view.loggedIn?'exported':'pending'}">${view.loggedIn?'学校平台已连接':'尚未连接学校平台'}</span></div><div class="source-row"><section class="panel source-card"><div class="source-logo">${icon('school')}</div><div><h3>华工视频平台</h3><p class="${view.loggedIn?'connected':''}">${view.loggedIn?'登录态已导入 · 仅保存在本次运行中':'连接学校平台，按上课日期查找课件'}</p></div><button data-action="login" class="secondary">${view.loggedIn?'重新登录':'连接平台'}</button>${view.loggedIn?'<button class="quiet" data-action="logout">断开</button>':''}</section><section class="panel source-card"><div class="source-logo" style="background:#f2f1ed;color:#979481">${icon('folder')}</div><div><h3>本地资料</h3><p>图片、PDF 或旧版下载目录</p></div><button data-action="import">导入 ${icon('plus')}</button></section></div>
    <section class="panel scan-panel"><div class="scan-bar"><label class="field">开始日期<input type="date" id="scan-start" value="${view.scanStart}"></label><label class="field">结束日期<input type="date" id="scan-end" value="${view.scanEnd}"></label><button class="primary" data-action="scan" ${!view.loggedIn||view.scanning?'disabled':''}>${icon('search')}${view.scanning?'正在扫描…':'立即重新扫描'}</button><span class="scan-note">登录或修改日期后自动扫描，也可手动强制刷新</span></div>
    ${view.scanning?empty('正在读取课表…','可以切换到其他页面，扫描会继续。'):state.scanError?empty('扫描失败',esc(state.scanError)):view.scanned?rows.length?`<div class="table-wrap"><table><thead><tr><th><input type="checkbox" id="scan-all" aria-label="选择所有可获取课件"></th><th>课程</th><th>上课日期</th><th>页数</th><th>资料状态</th></tr></thead><tbody>${rows.map(c=>`<tr><td><input type="checkbox" data-scan-select="${esc(c.id)}" aria-label="选择 ${esc(c.title)}" ${view.scanSelected.has(c.id)?'checked':''} ${exists(c.id)||scheduled(c.id)?'disabled':''}></td><td><div class="course-title">${esc(c.title)}</div><small>课次 ${esc(c.sub_id)}</small></td><td>${esc(c.day)}</td><td><small>获取后统计</small></td><td>${exists(c.id)?'<span class="badge exported">已在资料库</span>':scheduled(c.id)?'<span class="badge editing">获取中</span>':'<span class="badge pending">可获取</span>'}</td></tr>`).join('')}</tbody></table></div>`:empty('这个日期范围内没有课程','请选择实际有课的日期，或重新登录后再试。'):empty(view.loggedIn?'选择日期，开始查找课件':'连接平台后查找课件',view.loggedIn?'扫描结果会显示在这里。':'在学校网页中完成登录，再点击“导入登录态”。')}
    <div class="scan-bottom"><span>已选择 <strong>${view.scanSelected.size}</strong> 节课</span><div class="actions"><label title="无需整理，下载完成后自动生成 PDF"><input type="checkbox" id="direct-export" ${view.directExport?'checked':''}>获取完成后自动导出 PDF</label><button class="primary" data-action="download" ${!view.scanSelected.size||view.scanning?'disabled':''}>${icon('download')}获取选中课件</button></div></div></section><div class="helper-note">${icon('info')}<span>整理不是导出的前置条件：可以下载后自动导出，也可以在课程页随时快速导出。<br>快速导出使用当前保留页面，保存到默认目录；原始页面始终保留。</span></div>`;
}
function renderTasks(){
  const tasks=state.tasks.filter(t=>view.taskFilter==='all'||(view.taskFilter==='active'?['running','paused'].includes(t.status):view.taskFilter==='failed'?t.status==='failed':t.status==='done'));
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">LET THE WORK CONTINUE</div><h1>任务</h1><p class="subtitle">下载和导出在这里继续，你可以放心切换页面。</p></div><button data-nav="acquire">${icon('plus')}获取课件</button></div><div class="toolbar"><div class="tabs">${[['all','全部任务'],['active','进行中'],['done','已完成'],['failed','失败']].map(([id,label])=>`<button data-task-filter="${id}" class="${view.taskFilter===id?'active':''}">${label}</button>`).join('')}</div></div>${tasks.length?`<div class="task-list">${[...tasks].reverse().map(t=>`<article class="task-row"><div class="task-icon">${icon(t.type==='export'?'export':t.type==='scan'?'search':'download')}</div><div class="task-copy"><h3>${esc(t.title)}</h3><p>${{download:'下载',export:'导出',batch:'批量导出',import:'导入',scan:'扫描'}[t.type]} · ${{running:'正在处理',paused:'已暂停',done:'已完成',cancelled:'已取消',failed:'失败'}[t.status]}${['running','paused'].includes(t.status)?` · ${t.progress}% · ${esc(t.message)}`:''}</p>${t.error?`<p class="task-error">${esc(t.error)}</p>`:''}${['running','paused'].includes(t.status)?`<div class="task-progress"><span style="width:${t.progress}%"></span></div>`:''}</div><div class="actions">${['running','paused'].includes(t.status)?`${t.type==='scan'?'':`<button data-task-toggle="${t.id}">${icon(t.status==='paused'?'play':'pause')}${t.status==='paused'?'继续':'暂停'}</button>`}<button data-task-cancel="${t.id}">取消</button>`:t.status==='done'?t.materialId?`<button data-open="${t.materialId}" ${!activeMaterials().some(m=>m.id===t.materialId)?'disabled':''}>打开课件 ${icon('arrow')}</button>${['export','batch'].includes(t.type)?`<button data-output="${t.materialId}">打开目录</button>`:''}`:'<button data-nav="acquire">查看课表</button>':t.type==='scan'?'<button data-nav="acquire">重新扫描</button>':`<button data-task-retry="${t.id}">重试</button>`}</div></article>`).join('')}</div>`:empty('暂无'+(view.taskFilter==='active'?'进行中的':'')+'任务','获取课件或导入本地文件后，任务记录会出现在这里。','<button class="primary" data-nav="acquire">前往获取课件</button>')}`;
}
function renderSettings(){
  const s=state.settings;
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">MAKE ROOM FOR YOUR KNOWLEDGE</div><h1>设置</h1><p class="subtitle">让资料保存有序，让日常整理更顺手。</p></div></div><div class="settings-grid"><div><section class="panel settings-section"><h2>资料库与存储</h2><div class="setting-row"><div><h3>资料库位置</h3><p>包含原始素材、预览和整理记录，可以整体备份。</p></div><div class="actions"><button data-action="open-library">打开目录</button><button data-action="choose-library">切换资料库</button></div></div><div class="setting-path">${esc(s.libraryDir)}</div><div class="setting-row"><div><h3>保留原始页面</h3><p>排除不删除图片；回收站中的课件可以恢复。</p></div><span class="badge exported">默认保留</span></div><div class="setting-row"><div><h3>自动保存整理进度</h3><p>页面选择写入本地资料库，重新打开可继续。</p></div><span class="badge exported">已开启</span></div></section><section class="panel settings-section"><h2>下载与导出</h2><div class="setting-row"><div><h3>获取课件后</h3><p>下一次获取课件的默认处理方式。</p></div><select id="default-export" class="field-input"><option value="review" ${s.exportMode==='review'?'selected':''}>先整理，再导出</option><option value="direct" ${s.exportMode==='direct'?'selected':''}>直接导出 PDF</option></select></div><div class="setting-row"><div><h3>默认 PDF 导出目录</h3><p>首次导出时选择并记住，也可在这里主动修改。</p></div><button data-action="choose-export-dir">选择目录</button></div><div class="setting-path ${s.exportDir?'':'unset-path'}">${s.exportDir?esc(s.exportDir):'尚未设置 · 首次导出时再选择'}</div><div class="settings-numbers">${[['maxWorkers','图片并发数',1,32],['timeout','请求超时（秒）',5,600],['retries','下载尝试次数',1,10],['sleepMs','请求间隔（毫秒）',0,5000]].map(([id,label,min,max])=>`<label class="field">${label}<input type="number" id="setting-${id}" min="${min}" max="${max}" value="${s[id]}"></label>`).join('')}</div><button class="secondary" data-action="save-settings">保存下载参数</button></section></div><aside class="guide-card">${icon('folder')}<h3 style="margin-top:16px">资料留在本机</h3><p>课页自动生成课程封面；实际页面预览来自下载的课件或导入文件。</p><hr><div class="number">${activeMaterials().length}<span style="font-size:12px;margin-left:8px">份课件</span></div><p>SQLite 保存整理记录<br>原始素材长期保留<br>PDF 单独导出</p><hr><p>切换资料库会打开另一个目录，不会移动或删除当前资料。备份时请先退出应用，再复制整个资料库目录。</p></aside></div>`;
}
function renderAbout(){
  main.innerHTML=`<section class="about-hero"><div class="about-mark"><img src="../assets/app-icon.svg" alt="课页图标"></div><div class="about-intro"><div class="eyebrow">ABOUT KEYE</div><h1>课页 <span>KEYE</span></h1><p>把课堂课件的获取、筛选和 PDF 导出，整理成一条清楚、安静的工作流。</p><div class="about-actions"><span class="about-version">当前版本 v${esc(state.appVersion||'0.2.0')}</span><button class="secondary" data-action="show-help">${icon('help')}查看使用说明</button></div></div><div class="about-decoration" aria-hidden="true"><i></i><i></i><i></i></div></section>
    <div class="about-grid"><section class="panel about-card"><div class="about-card-icon">${icon('database')}</div><h2>资料留在本机</h2><p>课程、原始页面、筛选记录和设置保存在本地资料库中。排除页面不会删除原始素材。</p></section><section class="panel about-card"><div class="about-card-icon">${icon('school')}</div><h2>服务课堂资料</h2><p>面向华南理工大学课堂课件平台，也支持导入已有图片、PDF 和旧版下载目录。</p></section><section class="panel about-card"><div class="about-card-icon">${icon('export')}</div><h2>自由整理与导出</h2><p>可以直接快速导出，也可以逐页预览、排除无关画面，再生成更干净的 PDF。</p></section></div>
    <section class="panel about-update"><div class="about-update-icon">${icon('download')}</div><div class="about-update-copy"><h2>应用更新</h2><p id="update-status" role="status"></p><div id="update-notes"></div><div class="update-meter" id="update-meter" hidden><span id="update-meter-fill"></span></div></div><div class="about-update-actions"><button data-action="check-update" ${state.packaged?'':'disabled'}>检查更新</button><button class="secondary" data-action="download-update" hidden>下载更新</button><button class="primary" data-action="install-update" hidden>重启并安装</button><button class="quiet" data-action="open-release">GitHub Releases ${icon('arrow')}</button></div></section>
    <section class="panel about-details"><div><div class="eyebrow">PROJECT INFORMATION</div><h2>项目信息</h2></div><dl><div><dt>应用名称</dt><dd>课页 · Keye</dd></div><div><dt>当前版本</dt><dd>v${esc(state.appVersion||'0.2.0')}</dd></div><div><dt>适用系统</dt><dd>Windows 10 / 11</dd></div><div><dt>项目主页</dt><dd>github.com/goooseby/ScutPPT</dd></div></dl><p class="about-note">课页是一个开源的个人课件整理工具。账号凭据仅在当前运行中使用，不会写入课件数据库。</p></section>`;
  renderUpdateStatus();
}
function renderUpdateStatus(){
  const status=$('#update-status');if(!status)return;
  const info=updateState.info;
  status.textContent=updateState.error||(!state.packaged?'源码运行中；自动更新仅适用于打包版本。':updateState.checking?'正在检查 GitHub Releases…':updateState.downloading?`正在下载并校验更新：${updateState.progress}%`:updateState.ready?'下载和校验已完成。关闭课页后会安装更新，并自动重新打开。':info?.manual?info.manualReason||'请在 GitHub 下载完整包。':info?.available?`发现 v${info.latest} · ${info.incremental?'增量':'完整'}更新 · ${(info.size/1024/1024).toFixed(1)} MB`:info?'当前已是最新正式版本。':'点击检查更新，课页会从 GitHub 获取最新正式版本。');
  const notes=$('#update-notes');
  notes.textContent=info?.available&&info.notes?info.notes:'';
  notes.hidden=!notes.textContent;
  const meter=$('#update-meter');meter.hidden=!updateState.downloading;
  $('#update-meter-fill').style.width=updateState.progress+'%';
  $('[data-action="check-update"]').disabled=!state.packaged||updateState.checking||updateState.downloading;
  $('[data-action="download-update"]').hidden=!(info?.available&&!info.manual&&!updateState.downloading&&!updateState.ready);
  $('[data-action="install-update"]').hidden=!updateState.ready;
}
function showModal(title,body,actions=''){
  modal.classList.remove('fullscreen-modal');$('#modal-content').innerHTML=`<div class="modal-header"><h2>${title}</h2><button class="icon-button" data-action="close-modal" aria-label="关闭">${icon('close')}</button></div><div class="modal-body">${body}</div>${actions?`<div class="modal-actions">${actions}</div>`:''}`;if(!modal.open)modal.showModal();
}
function closeModal(){modal.close();modal.classList.remove('fullscreen-modal');}
function openMaterial(id){if(!activeMaterials().some(m=>m.id===id))return toast('请先从回收站恢复课件。');navigate('editor/'+id);}
async function mutatePages(pages,exclude){
  if(view.saving)return toast('正在保存上次修改，请稍候。');
  const m=material(),before=[...m.excluded],set=new Set(before);
  pages.forEach(p=>exclude?set.add(p):set.delete(p));const after=[...set].sort((a,b)=>a-b);
  if(JSON.stringify(before)===JSON.stringify(after))return;
  const fullscreenOpen=modal.open&&modal.classList.contains('fullscreen-modal');
  view.saving=true;if(!fullscreenOpen)renderEditor();
  try{await call('selection',{id:m.id,excluded:after,revision:m.revision});if(view.materialId===m.id)view.undo.push(before);view.selected.clear();view.selectionAnchor=null;toast(exclude?'已排除所选页面，原始素材仍保留':'所选页面已恢复');}
  finally{view.saving=false;if(fullscreenOpen)scheduleFullscreen();else render();}
}
async function undo(){
  if(view.saving||!view.undo.length)return;
  const m=material(),before=view.undo[view.undo.length-1],fullscreenOpen=modal.open&&modal.classList.contains('fullscreen-modal');view.saving=true;
  try{await call('selection',{id:m.id,excluded:before,revision:m.revision});view.undo.pop();view.selected.clear();toast('已撤销上次页面操作');}
  finally{view.saving=false;if(fullscreenOpen)scheduleFullscreen();else render();}
}
function updateEditorPreview(){
  const m=material(),panel=document.querySelector('.preview-panel');
  if(!m||!panel)return renderEditor();
  document.querySelectorAll('[data-page-tile].current').forEach(tile=>tile.classList.remove('current'));
  document.querySelector(`[data-page-tile="${view.currentPage}"]`)?.classList.add('current');
  panel.querySelector('.preview-title span').textContent=`原始页 ${view.currentPage} / ${m.pages}`;
  const stage=panel.querySelector('.large-art'),image=stage.querySelector('img.slide'),media=m.media?.[view.currentPage-1];
  if(media&&image&&image.src!==media.src){
    const request=++editorImageRequest,page=view.currentPage,loader=new Image();
    stage.setAttribute('aria-busy','true');loader.decoding='async';loader.src=media.src;
    const commit=()=>{if(request!==editorImageRequest||view.currentPage!==page||!image.isConnected)return;image.src=media.src;image.alt=`${m.title} · 第 ${page} 页`;stage.removeAttribute('aria-busy');};
    if(loader.decode)loader.decode().then(commit).catch(commit);else loader.onload=commit;
  }else if(media&&image){++editorImageRequest;stage.removeAttribute('aria-busy');}
  else stage.innerHTML=slide(m,view.currentPage);
  const controls=panel.querySelector('.preview-controls'),buttons=controls.querySelectorAll('button');
  buttons[0].disabled=view.currentPage===1;controls.querySelector('span').textContent=`第 ${view.currentPage} 页`;buttons[1].disabled=view.currentPage===m.pages;
  const excluded=m.excluded.includes(view.currentPage),detail=panel.querySelector('.preview-detail'),toggle=detail.querySelector('button');
  detail.querySelector('h3').textContent=excluded?'此页已排除':'此页将保留在 PDF 中';
  detail.querySelector('p').textContent=excluded?'原始页面依然保留。恢复后，这一页将重新进入导出结果。':'单击缩略图查看大图；勾选多页，可以批量排除无关画面。';
  toggle.classList.toggle('secondary',excluded);toggle.dataset.togglePage=String(view.currentPage);toggle.innerHTML=excluded?icon('undo')+'恢复此页':icon('close')+'排除此页';
  fullscreenPreloads=[view.currentPage-1,view.currentPage+1].map(page=>m.media?.[page-1]?.src).filter(Boolean).map(src=>{const preload=new Image();preload.src=src;return preload;});
}
function preview(page){
  const m=material();view.currentPage=Math.max(1,Math.min(m.pages,page));m.lastPage=view.currentPage;
  pendingLastPage={id:m.id,page:view.currentPage};clearTimeout(lastPageTimer);
  lastPageTimer=setTimeout(()=>{const latest=pendingLastPage;pendingLastPage=null;if(latest)call('lastPage',latest).catch(fail);},240);
  if(modal.open&&modal.classList.contains('fullscreen-modal'))scheduleFullscreen();else updateEditorPreview();
}
function scheduleFullscreen(){
  if(fullscreenFrame!==null)return;
  fullscreenFrame=requestAnimationFrame(()=>{fullscreenFrame=null;if(modal.open&&modal.classList.contains('fullscreen-modal'))showFullscreen();});
}
function showFullscreen(){
  const m=material(),excluded=m.excluded.includes(view.currentPage),media=m.media?.[view.currentPage-1];
  const updating=modal.open&&modal.classList.contains('fullscreen-modal')&&$('#fullscreen-stage');
  if(updating){
    $('#fullscreen-title').textContent=`${m.title} · 第 ${view.currentPage} 页`;
    const stage=$('#fullscreen-stage'),image=stage.querySelector('img.slide');
    if(media&&image&&image.src!==media.src){
      const request=++fullscreenImageRequest,page=view.currentPage,loader=new Image();
      stage.setAttribute('aria-busy','true');loader.decoding='async';loader.src=media.src;
      const commit=()=>{if(request!==fullscreenImageRequest||view.currentPage!==page||!image.isConnected)return;image.src=media.src;image.alt=`${m.title} · 第 ${page} 页`;stage.removeAttribute('aria-busy');};
      if(loader.decode)loader.decode().then(commit).catch(commit);else loader.onload=commit;
    }else if(media&&image){++fullscreenImageRequest;stage.removeAttribute('aria-busy');}
    else stage.innerHTML=slide(m,view.currentPage);
    $('#fullscreen-page').textContent=`${view.currentPage} / ${m.pages}`;
    $('[data-action="previous"]').disabled=view.currentPage===1;
    $('[data-action="next"]').disabled=view.currentPage===m.pages;
    $('[data-action="toggle-fullscreen-page"]').textContent=excluded?'恢复此页':'排除此页';
  }else{
    modal.classList.add('fullscreen-modal');
    $('#modal-content').innerHTML=`<div class="modal-header"><h2 id="fullscreen-title">${esc(m.title)} · 第 ${view.currentPage} 页</h2><div class="fullscreen-shortcuts"><span><kbd>←</kbd> <kbd>→</kbd> 翻页</span><span><kbd>E</kbd> 排除 / 恢复</span></div><button class="icon-button" data-action="close-modal" aria-label="关闭">${icon('close')}</button></div><div class="modal-body"><div id="fullscreen-stage">${slide(m,view.currentPage)}</div><div class="full-nav"><button data-action="previous" ${view.currentPage===1?'disabled':''}>${icon('left')}上一页</button><span id="fullscreen-page">${view.currentPage} / ${m.pages}</span><button data-action="next" ${view.currentPage===m.pages?'disabled':''}>下一页${icon('right')}</button><button data-action="toggle-fullscreen-page">${excluded?'恢复此页':'排除此页'}</button></div></div>`;
    modal.showModal();
  }
  fullscreenPreloads=[view.currentPage-1,view.currentPage+1].map(page=>m.media?.[page-1]?.src).filter(Boolean).map(src=>{const image=new Image();image.src=src;return image;});
}
function showExport(){
  const m=material(),kept=m.pages-m.excluded.length;if(!kept||view.saving)return;
  showModal('导出 PDF',`<p>将按原始页序，合并当前保留的页面。导出期间继续修改，不会影响本次输出。</p><div class="modal-stat"><div><strong>${m.pages}</strong><span>原始页面</span></div><div><strong>${kept}</strong><span>保留并导出</span></div><div><strong>${m.excluded.length}</strong><span>已排除</span></div></div><label class="field">文件名称<input type="text" id="export-name" value="${esc(m.day+'_'+m.title+'.pdf')}" maxlength="120"></label><p>下一步选择文件保存位置，完成后可在任务页打开输出目录。</p>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-export">选择位置并导出</button>');
}
function showHelp(){showModal('欢迎使用课页',`<ol class="help-steps"><li>获取课件 → 连接平台，完成学校登录。</li><li>扫描实际有课的日期，选择课程并获取。</li><li>资料库 → 打开课件，筛选需要保留的页面。</li><li>导出 PDF，选择保存位置。</li><li>下次打开课页，继续之前的整理。</li></ol><p>也可以导入本地图片、PDF 或旧版下载目录。封面由课页自动生成，预览展示真实页面。方向键翻页，E 排除/恢复，Ctrl+Z 撤销。</p>`, '<button class="primary" data-action="close-modal">开始使用</button>');}

document.addEventListener('click',event=>{
  if(event.target.matches?.('[data-page-check]'))view.pageShiftPending=event.shiftKey;
  handleClick(event).then(()=>{
    if(view.sessionMenuId&&!event.target.closest('.session-actions')){view.sessionMenuId=null;if(view.page==='course')renderCourse();}
  }).catch(fail);
});
async function handleClick(event){
  const b=event.target.closest('button,a,[data-action],[data-course-session]');if(b?.disabled)return;
  if(await courseClick(b))return;
  if(b?.dataset.nav)return navigate(b.dataset.nav);
  if(b?.dataset.open)return openMaterial(b.dataset.open);
  if(b?.dataset.output)return call('openExport',{id:b.dataset.output});
  if(b?.dataset.filter){view.filter=b.dataset.filter;renderLibrary();return;}
  if(b?.dataset.pageFilter){view.pageFilter=b.dataset.pageFilter;view.selected.clear();view.selectionAnchor=null;renderEditor();return;}
  if(b?.dataset.taskFilter){view.taskFilter=b.dataset.taskFilter;renderTasks();return;}
  if(b?.dataset.restore){await call('trash',{id:b.dataset.restore,deleted:false});toast('课件已恢复');return;}
  if(b?.dataset.togglePage){const p=Number(b.dataset.togglePage);return mutatePages([p],!material().excluded.includes(p));}
  for(const [attr,action] of [['taskToggle','toggle'],['taskCancel','cancel'],['taskRetry','retry']])if(b?.dataset[attr])return call('task',{id:b.dataset[attr],action});
  if(b?.dataset.menu){const m=state.materials.find(m=>m.id===b.dataset.menu);return showModal('管理课件',`<p>${esc(m.title)} · ${esc(m.day)}</p><p>移入回收站后可恢复，原始素材和筛选记录都会保留。已经导出的文件不受影响。</p>`,`<button data-action="close-modal">取消</button><button class="danger" data-delete-material="${m.id}">移入回收站</button>`);}
  if(b?.dataset.deleteMaterial){await call('trash',{id:b.dataset.deleteMaterial,deleted:true});closeModal();toast('已移入回收站');return;}
  const page=event.target.closest('[data-preview]');
  if(page){clearTimeout(preview.timer);preview.timer=setTimeout(()=>preview(Number(page.dataset.preview)),220);return;}
  const action=b?.dataset.action;if(!action)return;
  if(action==='close-modal')return closeModal();
  if(action==='clear-search'){view.search='';renderLibrary();return;}
  if(action==='login'){await call('login');return;}
  if(action==='logout')return call('logout');
  if(action==='scan'){
    clearTimeout(autoScanTimer);
    autoScanRequested=false;
    const start=$('#scan-start').value,end=$('#scan-end').value;
    if(!start||!end||start>end)return toast('请填写有效日期，开始日期不能晚于结束日期。');
    view.scanStart=start;view.scanEnd=end;view.scanSelected.clear();return call('scan',{start,end});
  }
  if(action==='download'){const ids=[...view.scanSelected];if(await call('download',{ids,direct:view.directExport})){view.scanSelected.clear();toast('课件已加入后台任务');renderAcquire();}return;}
  if(action==='import'){view.importCourseId=view.page==='course'&&view.courseId!=='unfiled'?view.courseId:null;return showModal('导入本地资料',`<p>复制文件到资料库，保留源文件。多张图片合为一份课件，多个 PDF 分别导入。</p><p>选择旧版下载目录时，会按图片文件夹分组；同一课次同时有图片和 PDF 时优先导入图片。</p>`, '<button data-action="close-modal">取消</button><button data-action="import-folder">选择目录</button><button class="primary" data-action="import-files">选择 PDF / 图片</button>');}
  if(action==='import-folder'||action==='import-files'){closeModal();const added=await call('import',{kind:action==='import-folder'?'folder':'files',courseId:view.importCourseId});if(added){navigate('tasks');toast('正在导入本地资料');}return;}
  if(action==='select-all-pages'){
    const m=material(),pages=Array.from({length:m.pages},(_,i)=>i+1).filter(p=>view.pageFilter==='all'||!m.excluded.includes(p));view.selected=view.selected.size===pages.length?new Set():new Set(pages);view.selectionAnchor=null;renderEditor();return;
  }
  if(action==='range')return showModal('选择连续页面',`<p>使用原始页码选择，再批量排除或恢复。</p><div class="range-fields"><label class="field">从第几页<input type="number" id="range-from" min="1" max="${material().pages}" value="${view.currentPage}"></label><label class="field">到第几页<input type="number" id="range-to" min="1" max="${material().pages}" value="${Math.min(material().pages,view.currentPage+3)}"></label></div>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-range">选中这些页面</button>');
  if(action==='confirm-range'){const from=Number($('#range-from').value),to=Number($('#range-to').value);if(!Number.isInteger(from)||!Number.isInteger(to)||from<1||to>material().pages||from>to)return toast('请输入有效的页面范围。');view.pageFilter='all';view.selected=new Set(Array.from({length:to-from+1},(_,i)=>i+from));view.selectionAnchor=to;closeModal();renderEditor();return;}
  if(action==='exclude')return mutatePages([...view.selected],true);
  if(action==='restore')return mutatePages([...view.selected],false);
  if(action==='undo')return undo();
  if(action==='previous')return preview(view.currentPage-1);
  if(action==='next')return preview(view.currentPage+1);
  if(action==='fullscreen')return showFullscreen();
  if(action==='toggle-fullscreen-page'){await mutatePages([view.currentPage],!material().excluded.includes(view.currentPage));return;}
  if(action==='export')return showExport();
  if(action==='quick-export'){if(await call('quickExport',{id:material().id}))toast('已快速导出到默认目录，可在任务页查看进度');return;}
  if(action==='confirm-export'){const id=material().id,name=$('#export-name').value.trim();if(!name)return toast('请填写文件名。');closeModal();if(await call('export',{id,name}))toast('PDF 已加入导出任务');return;}
  if(action==='open-library')return call('openLibrary');
  if(action==='show-help')return showHelp();
  if(action==='check-update'){
    updateState.checking=true;updateState.info=null;updateState.ready=false;updateState.error='';renderUpdateStatus();
    try{updateState.info=await call('checkUpdate');}
    catch(error){updateState.error=error.message;}
    finally{updateState.checking=false;renderUpdateStatus();}
    return;
  }
  if(action==='download-update'){
    updateState.downloading=true;updateState.progress=0;updateState.error='';renderUpdateStatus();
    try{await call('downloadUpdate');updateState.ready=true;}
    catch(error){updateState.error=error.message;}
    finally{updateState.downloading=false;renderUpdateStatus();}
    return;
  }
  if(action==='install-update')return call('installUpdate');
  if(action==='open-release')return call('openRelease');
  if(action==='choose-export-dir')return call('chooseExportDir');
  if(action==='choose-library')return showModal('切换资料库', '<p>选择一个新的空目录，或打开以前的资料库。当前资料会保留在原目录，不会自动搬迁。</p><p>请等待后台任务完成后再切换。</p>', '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-library">选择资料库目录</button>');
  if(action==='confirm-library'){closeModal();if(await call('chooseLibrary')){view.materialId=null;view.undo=[];view.filter='all';view.search='';navigate('library');}return;}
  if(action==='save-settings'){const values={};for(const k of ['maxWorkers','timeout','retries','sleepMs'])values[k]=Number($('#setting-'+k).value);await call('settings',values);toast('下载参数已保存');}
}
document.addEventListener('change',event=>{handleChange(event).catch(fail);});
async function handleChange(event){
  const el=event.target;
  if(courseChange(el))return;
  if(el.matches('[data-page-check]')){
    const p=Number(el.dataset.pageCheck),checked=el.checked;
    if(view.pageShiftPending&&view.selectionAnchor!==null){
      const from=Math.min(view.selectionAnchor,p),to=Math.max(view.selectionAnchor,p),m=material();
      for(let page=from;page<=to;page++){
        if(view.pageFilter==='all'||!m.excluded.includes(page))checked?view.selected.add(page):view.selected.delete(page);
      }
    }else checked?view.selected.add(p):view.selected.delete(p);
    view.selectionAnchor=p;view.pageShiftPending=false;renderEditor();
  }
  if(el.matches('[data-scan-select]')){el.checked?view.scanSelected.add(el.dataset.scanSelect):view.scanSelected.delete(el.dataset.scanSelect);renderAcquire();}
  if(el.id==='scan-all'){availableCourses.filter(c=>!activeMaterials().some(m=>m.sourceKey===c.id)&&!state.tasks.some(t=>t.sourceKey===c.id&&['running','paused'].includes(t.status))).forEach(c=>el.checked?view.scanSelected.add(c.id):view.scanSelected.delete(c.id));renderAcquire();}
  if(el.id==='library-sort'){view.sort=el.value;renderLibrary();}
  if(el.id==='direct-export')view.directExport=el.checked;
  if(el.id==='scan-start'){view.scanStart=el.value;scheduleAutoScan();}
  if(el.id==='scan-end'){view.scanEnd=el.value;scheduleAutoScan();}
  if(el.id==='default-export'){await call('settings',{exportMode:el.value});toast('默认获取方式已保存');}
}
function searchInput(event){if(event.target.id==='library-search'&&!event.isComposing){const cursor=event.target.selectionStart;view.search=event.target.value;renderLibrary();$('#library-search').focus();$('#library-search').setSelectionRange(cursor,cursor);}}
document.addEventListener('input',searchInput);document.addEventListener('compositionend',searchInput);
document.addEventListener('dblclick',event=>{const el=event.target.closest('[data-preview]');if(el){clearTimeout(preview.timer);view.currentPage=Number(el.dataset.preview);preview(view.currentPage);showFullscreen();}});
document.addEventListener('keydown',event=>{
  if(view.page!=='editor'||['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;
  if(event.key==='Enter'&&event.target.matches('[data-preview]')){view.currentPage=Number(event.target.dataset.preview);showFullscreen();return;}
  if(modal.open&&!modal.classList.contains('fullscreen-modal'))return;
  if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();preview(view.currentPage+(event.key==='ArrowLeft'?-1:1));}
  if(event.key.toLowerCase()==='e'&&!event.ctrlKey&&!event.metaKey){mutatePages([view.currentPage],!material().excluded.includes(view.currentPage)).catch(fail);}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();undo().then(()=>{if(modal.open)scheduleFullscreen();}).catch(fail);}
});
$('#help-button').addEventListener('click',showHelp);
modal.addEventListener('close',()=>{modal.classList.remove('fullscreen-modal');if(view.page==='editor')renderEditor();});
window.addEventListener('hashchange',route);
main.innerHTML=empty('正在打开资料库…','请稍候');hydrate();
if(typeof qt==='undefined')main.innerHTML=empty('请从桌面应用打开课页','在项目目录运行 .venv/Scripts/python.exe app.py');
else new QWebChannel(qt.webChannelTransport,channel=>{
  desktop=channel.objects.desktop;
  desktop.response.connect((id,payload)=>{const p=pending.get(id);if(!p)return;pending.delete(id);const data=JSON.parse(payload);data.ok?p.resolve(data.result):p.reject(new Error(data.error));});
  desktop.changed.connect(payload=>applySnapshot(JSON.parse(payload)));
  desktop.taskChanged.connect(payload=>{const task=JSON.parse(payload),index=state.tasks.findIndex(t=>t.id===task.id);if(index>=0)state.tasks[index]=task;renderShell();if(view.page==='tasks')renderTasks();});
  desktop.notice.connect(toast);
  desktop.updateProgress.connect((done,total)=>{updateState.progress=Math.min(100,Math.round(done/total*100));renderUpdateStatus();});
  call('snapshot').then(snapshot=>{applySnapshot(snapshot);route();}).catch(error=>{main.innerHTML=empty('资料库打开失败',esc(error.message));});
});
