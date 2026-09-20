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
const KEY = 'getppt-prototype-v1';
const courses = [
  {id:'operations', title:'运筹学', topic:'线性规划与单纯形法', day:'2026-09-03', pages:18, tone:'green', section:'02', kind:'math'},
  {id:'database', title:'数据库系统原理', topic:'关系模型与关系代数', day:'2026-09-02', pages:24, tone:'blue', section:'03', kind:'database'},
  {id:'probability', title:'概率论与数理统计', topic:'随机变量及其分布', day:'2026-09-01', pages:16, tone:'sand', section:'02', kind:'chart'},
  {id:'network', title:'计算机网络', topic:'应用层协议', day:'2026-08-31', pages:20, tone:'purple', section:'02', kind:'network'},
  {id:'algorithm', title:'算法设计与分析', topic:'分治策略', day:'2026-08-30', pages:15, tone:'blue', section:'04', kind:'network'},
  {id:'linear', title:'线性代数', topic:'矩阵的运算', day:'2026-08-28', pages:21, tone:'sand', section:'01', kind:'math'},
];
const availableCourses = [
  {id:'new-operations', title:'运筹学', topic:'对偶理论与灵敏度分析', day:'2026-09-05', pages:22, tone:'green', section:'03', kind:'math'},
  {id:'new-database', title:'数据库系统原理', topic:'SQL 数据查询', day:'2026-09-05', pages:26, tone:'blue', section:'04', kind:'database'},
  {id:'new-probability', title:'概率论与数理统计', topic:'多维随机变量', day:'2026-09-04', pages:19, tone:'sand', section:'03', kind:'chart'},
];
function initialState() {
  return {version:1, materials:courses.map((c,i) => ({...c, excluded:i===0?[4,5,9,13,17]:i===2?[3,7,8]:[],
    edited:i===0||i===2, exported:i===2, revision:i===0?1:0, exportRevision:i===2?0:null,
    touched:Date.now()-i*3600000, lastPage:1, deleted:false})), tasks:[], lastMaterial:'operations',
    settings:{autoSave:true, keepOriginals:true, exportMode:'review', defaultFilter:'all'}};
}
let state;
let storageOK = true;
try {
  const raw = JSON.parse(localStorage.getItem(KEY));
  state = raw?.version===1 && Array.isArray(raw.materials) && Array.isArray(raw.tasks) && raw.settings ? raw : initialState();
} catch { state = initialState(); storageOK = false; }
// A suspended prototype task resumes when the preview is reopened.
const view = {page:'library',filter:'all',search:'',sort:'recent',materialId:null,pageFilter:'all',selected:new Set(),
  currentPage:1,undo:[],scanSelected:new Set(),loggedIn:false,scanned:false,scanning:false,taskFilter:'all',
  scanStart:'2026-09-01',scanEnd:'2026-09-05',directExport:state.settings.exportMode==='direct'};
const main = document.querySelector('#main');
const modal = document.querySelector('#modal');
const $ = selector => document.querySelector(selector);
const material = () => state.materials.find(m=>m.id===view.materialId);
const activeMaterials = () => state.materials.filter(m=>!m.deleted);
const statusOf = m => m.exported ? (m.revision===m.exportRevision?'exported':'changed') : m.edited?'editing':'pending';
const statuses = {pending:'待整理',editing:'整理中',exported:'已导出',changed:'修改后未导出'};
const badge = m => `<span class="badge ${statusOf(m)}">${statuses[statusOf(m)]}</span>`;
function save(){
  try {localStorage.setItem(KEY,JSON.stringify(state));storageOK=true;}
  catch {storageOK=false;toast('浏览器未允许保存。关闭原型后，本次整理可能丢失。');}
}
function toast(message){
  $('#toast').textContent=message;$('#toast').classList.add('show');
  clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),3600);
}
function hydrate(){document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
function renderShell(){
  const running=state.tasks.filter(t=>t.status==='running'||t.status==='paused').length;
  $('#nav').innerHTML=[['library','资料库','library'],['acquire','获取课件','download'],['tasks','任务','tasks']].map(([id,label,i])=>
    `<button class="nav-item ${(view.page===id||(id==='library'&&view.page==='editor'))?'active':''}" data-nav="${id}" ${view.page===id?'aria-current="page"':''}>${icon(i)}${label}${id==='tasks'&&running?`<span class="nav-count">${running}</span>`:''}</button>`).join('');
  const settingsButton=$('[data-nav="settings"]');settingsButton.classList.toggle('active',view.page==='settings');
  $('#breadcrumb').innerHTML=`工作空间 <span>/</span> ${view.page==='editor'?`资料库 <span>/</span> ${esc(material()?.title||'课件整理')}`:({library:'资料库',acquire:'获取课件',tasks:'任务',settings:'设置'}[view.page]||'资料库')}`;
  const m=view.page==='editor'?material():null;
  $('#statusbar').innerHTML=`<span class="status-left"><i class="dot"></i>${m?`共 ${m.pages} 页 · 保留 ${m.pages-m.excluded.length} 页 · 排除 ${m.excluded.length} 页`:running?`${running} 项任务正在进行 · 切换页面不会中断`:'所有修改仅保存在本机原型中'}</span><span>${running?`<button data-nav="tasks">${running} 项任务进行中 →</button>`:'GetPPTApp · 交互原型 / 不连接学校账号'}</span>`;
}
function route(){
  const parts=location.hash.replace(/^#/,'').split('/');
  const target=parts[0]||'library';
  if(target==='editor'&&state.materials.some(m=>m.id===parts[1]&&!m.deleted)){
    if(view.materialId!==parts[1]){view.selected.clear();view.undo=[];view.pageFilter='all';}
    view.materialId=parts[1];view.currentPage=Math.min(state.materials.find(m=>m.id===parts[1]).lastPage||1,material().pages);
    state.lastMaterial=parts[1];save();view.page='editor';
  }else view.page=['library','acquire','tasks','settings'].includes(target)?target:'library';
  render();main.scrollTop=0;
}
function navigate(page){if(location.hash===`#${page}`)route();else location.hash=page;}
function render(){
  renderShell();
  ({library:renderLibrary,acquire:renderAcquire,editor:renderEditor,tasks:renderTasks,settings:renderSettings}[view.page]||renderLibrary)();
  hydrate();
}
const palettes={green:['#f8faf3','#4e6b4d','#dbe7ce'],blue:['#f5f8fb','#48617d','#dce6ee'],sand:['#fbf9f2','#8c7951','#eee6cf'],purple:['#f7f6fb','#726387','#e6dfef']};
function slide(m,page=1){
  const [bg,accent,soft]=palettes[m.tone]||palettes.green;
  const invalid=[5,9,13,17].includes(page);
  const base=`<svg class="slide" viewBox="0 0 640 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(m.title)} · 第 ${page} 页示例" style="font-family:'Microsoft YaHei','Segoe UI',sans-serif">`;
  if(invalid){
    if(page===9)return base+`<rect width="640" height="360" fill="#e9ecec"/><rect x="65" y="54" width="510" height="253" rx="3" fill="#f8f8f6"/><rect x="65" y="54" width="510" height="25" fill="#d9deda"/><circle cx="80" cy="67" r="3" fill="#9baba0"/><text x="320" y="170" text-anchor="middle" font-size="20" fill="#adb4b0">正在切换课件…</text><text x="320" y="202" text-anchor="middle" font-size="11" fill="#b4bbb6">课堂采集示例 · 过渡画面</text></svg>`;
    return base+`<rect width="640" height="360" fill="#c7cec8"/><rect x="19" y="26" width="601" height="220" fill="#67796d"/><path d="M110 104h90m-37 10 40 19m52-30 54 18m56-11h90" stroke="#afbdac" stroke-width="3" fill="none" opacity=".4"/><rect x="0" y="270" width="640" height="90" fill="#b9b5a8"/><path d="M48 327h111m109 0h111m109 0h111" stroke="#8e9187" stroke-width="25"/><text x="320" y="200" text-anchor="middle" fill="#d1d9d0" font-size="15">课堂采集示例 · 非课件画面</text></svg>`;
  }
  let art='';
  if(m.kind==='math')art=`<rect x="332" y="104" width="255" height="196" fill="${soft}" rx="3"/><path d="M367 265h182M389 282V131" stroke="${accent}" stroke-width="1.3"/><path d="m390 248 44-65 82-24-20 89Z" fill="${accent}" opacity=".13"/><path d="m385 257 140-107m-121 134 94-145M382 188h142" stroke="${accent}" stroke-width="1.5" opacity=".7"/><circle cx="434" cy="183" r="5" fill="${accent}"/><text x="451" y="180" font-size="13" fill="${accent}">最优解</text><text x="361" y="128" font-size="11" fill="${accent}">可行域与目标函数</text><text x="51" y="174" font-size="22" fill="${accent}" font-family="Georgia,serif">max z = cᵀx</text><text x="51" y="213" font-size="17" fill="${accent}" font-family="Georgia,serif">s.t. Ax ≤ b, x ≥ 0</text>`;
  if(m.kind==='database')art=`<g fill="${soft}"><rect x="45" y="145" width="162" height="98" rx="3"/><rect x="239" y="145" width="162" height="98" rx="3"/><rect x="432" y="145" width="162" height="98" rx="3"/></g><g fill="${accent}" font-size="15"><text x="98" y="181">Student</text><text x="296" y="181">Course</text><text x="479" y="181">Enroll</text></g><g stroke="${accent}" stroke-opacity=".3"><path d="M58 195h136m58 0h136m57 0h136M58 215h90m104 0h90m103 0h90M207 192h32m162 0h31"/></g><text x="45" y="287" font-size="14" fill="${accent}">σ 条件 (R)　 ·　 π 属性 (R)　 ·　 R ⋈ S</text>`;
  if(m.kind==='chart')art=`<path d="M55 278h520M88 296V126" fill="none" stroke="${accent}" stroke-width="1.5"/><path d="M89 270C168 270 184 259 238 164S322 122 366 190 410 266 560 270" fill="none" stroke="${accent}" stroke-width="3"/><path d="M89 270C168 270 184 259 238 164S322 122 366 190 410 266 560 270V277H89Z" fill="${soft}" opacity=".8"/><text x="443" y="152" font-family="Georgia,serif" font-size="24" fill="${accent}">X ~ N(μ, σ²)</text>`;
  if(m.kind==='network')art=`<g stroke="${accent}" opacity=".5" fill="none"><path d="M320 145 154 220m166-75 166 75M154 220l-70 65m70-65 80 65m252-65-70 65m70-65 70 65"/></g><g fill="${soft}" stroke="${accent}" stroke-width="1"><rect x="273" y="121" width="94" height="43" rx="4"/><rect x="108" y="208" width="94" height="43" rx="4"/><rect x="439" y="208" width="94" height="43" rx="4"/></g><g font-size="13" fill="${accent}" text-anchor="middle"><text x="320" y="147">${m.id.includes('algorithm')?'Problem':'应用层'}</text><text x="155" y="234">${m.id.includes('algorithm')?'Left':'客户端'}</text><text x="486" y="234">${m.id.includes('algorithm')?'Right':'服务端'}</text></g>`;
  if(page===1)art=`<text x="46" y="146" font-size="36" font-weight="600" fill="${accent}">${esc(m.topic.length>12?m.topic.slice(0,12):m.topic)}</text><text x="49" y="184" font-size="13" fill="${accent}" opacity=".65">${esc(m.title)}  /  COURSE NOTES</text><rect x="46" y="225" width="40" height="3" fill="${accent}" opacity=".6"/><text x="49" y="279" font-size="12" fill="${accent}" opacity=".6">CHAPTER ${esc(m.section)}　·　课堂教学课件</text><text x="481" y="311" font-size="149" fill="${accent}" opacity=".055" font-weight="700">${esc(m.section)}</text>`;
  return base+`<rect width="640" height="360" fill="${bg}"/><rect x="0" y="0" width="640" height="5" fill="${accent}" opacity=".75"/><text x="46" y="51" font-size="11" letter-spacing="2" fill="${accent}" opacity=".65">${esc(m.title)} · CHAPTER ${esc(m.section)}</text>${page!==1?`<text x="46" y="91" font-size="23" font-weight="500" fill="${accent}">${esc(m.topic)}${page>2?' · '+(page-1):''}</text>`:''}${art}<path d="M45 323h550" stroke="${accent}" opacity=".15"/><text x="46" y="343" font-size="9" fill="${accent}" opacity=".55">GETPPTAPP · 示例课件 / 非真实教学资料</text><text x="589" y="343" text-anchor="end" font-size="9" fill="${accent}" opacity=".6">${String(page).padStart(2,'0')}</text></svg>`;
}
function renderLibrary(){
  const active=activeMaterials();
  const last=active.find(m=>m.id===state.lastMaterial)||active[0];
  const filtered=state.materials.filter(m=>view.filter==='trash'?m.deleted:!m.deleted)
    .filter(m=>!['pending','exported'].includes(view.filter)||(view.filter==='pending'?statusOf(m)!=='exported':statusOf(m)==='exported'))
    .filter(m=>`${m.title} ${m.topic} ${m.day}`.toLowerCase().includes(view.search.toLowerCase()));
  filtered.sort((a,b)=>view.sort==='name'?a.title.localeCompare(b.title,'zh'):view.sort==='date'?b.day.localeCompare(a.day):b.touched-a.touched);
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">YOUR LEARNING LIBRARY</div><h1>资料库</h1><p class="subtitle">把课堂留下的每一页，整理成自己的知识。</p></div><div class="actions"><button data-action="import">${icon('plus')}导入文件</button><button class="primary" data-nav="acquire">${icon('download')}获取课件</button></div></div>
    ${last&&view.filter==='all'&&!view.search?`<section class="continue-card"><div class="continue-art">${slide(last,last.lastPage||1)}</div><div class="continue-copy"><div class="overline">继续上次的整理</div><h2>${esc(last.title)} <span style="font-weight:400;color:#8ca08e">/</span> ${esc(last.topic)}</h2><p>${esc(last.day)}　·　${last.pages} 页　·　已排除 ${last.excluded.length} 页</p><div class="tiny-progress"><span><i style="width:${Math.round((last.pages-last.excluded.length)/last.pages*100)}%"></i></span><span>保留 ${last.pages-last.excluded.length} 页</span></div></div><div class="actions"><button class="primary" data-open="${last.id}">继续整理 ${icon('arrow')}</button></div></section>`:''}
    <div class="toolbar"><div class="tabs" aria-label="资料筛选">${[['all','全部资料',active.length],['pending','待整理',active.filter(m=>statusOf(m)!=='exported').length],['exported','已导出',active.filter(m=>statusOf(m)==='exported').length]].map(([key,label,count])=>`<button data-filter="${key}" class="${view.filter===key?'active':''}">${label}<span class="count">${count}</span></button>`).join('')}<button data-filter="trash" class="${view.filter==='trash'?'active':''}" title="回收站">${icon('trash')}</button></div><label class="search-box">${icon('search')}<input id="library-search" placeholder="搜索课程、日期…" aria-label="搜索资料" value="${esc(view.search)}"></label></div>
    <div class="library-tools"><span>${view.filter==='trash'?'回收站 · 可随时恢复':'我的课件'} <span style="color:#b4bcb6">/</span> ${filtered.length} 份</span><select id="library-sort" aria-label="排序"><option value="recent" ${view.sort==='recent'?'selected':''}>最近整理优先</option><option value="date" ${view.sort==='date'?'selected':''}>上课日期优先</option><option value="name" ${view.sort==='name'?'selected':''}>按课程名称</option></select></div>
    ${filtered.length?`<div class="course-grid">${filtered.map(m=>`<article class="course-card"><button class="course-open" ${m.deleted?`data-restore="${m.id}"`:`data-open="${m.id}"`} aria-label="${m.deleted?'恢复':'整理'} ${esc(m.title)}"><div class="course-cover" style="background:${(palettes[m.tone]||palettes.green)[2]}66">${slide(m)}</div><div class="course-info"><h3>${esc(m.title)} · ${esc(m.topic)}</h3><div class="meta"><span>${esc(m.day)}</span><span>·</span><span>${m.pages} 页</span><span>·</span><span>${m.source==='import'?'本地导入':'华工视频平台'}</span></div><div class="course-info-bottom">${m.deleted?'<span class="badge pending">点击恢复课件</span>':badge(m)}<span>${m.edited?`保留 ${m.pages-m.excluded.length} 页`:'等待第一次整理'}</span></div></div></button>${!m.deleted?`<button class="icon-button card-menu" data-menu="${m.id}" aria-label="管理 ${esc(m.title)}">${icon('more')}</button>`:''}</article>`).join('')}</div>`:empty(view.filter==='trash'?'回收站是空的':view.search?'没有找到相关课件':'这里还没有课件',view.search?'试试其他课程名，或清空搜索条件。':'先去获取课件，或导入一份示例资料开始体验。',view.search?'<button data-action="clear-search">清空搜索</button>':'<button class="primary" data-nav="acquire">获取课件</button>')}
    <div class="footer-count">${view.filter==='trash'?'删除资料库课件不会影响已导出的文件':'原始页面保留在资料库中 · 排除页面后仍可恢复'}</div>`;
}
function empty(title,description,action=''){return `<div class="empty">${icon('folder')}<h2>${title}</h2><p>${description}</p>${action}</div>`;}
function renderAcquire(){
  const rows=availableCourses.filter(c=>c.day>=view.scanStart&&c.day<=view.scanEnd);
  const exists=id=>state.materials.some(m=>m.id===id&&!m.deleted);
  const scheduled=id=>state.tasks.some(t=>t.materialId===id&&['running','paused'].includes(t.status));
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">BRING YOUR MATERIALS TOGETHER</div><h1>获取课件</h1><p class="subtitle">从课堂平台获取，或把已有资料带进来。</p></div><span class="badge pending">登录与下载为演示流程</span></div>
    <div class="source-row"><section class="panel source-card"><div class="source-logo">${icon('school')}</div><div><h3>华工视频平台</h3><p class="${view.loggedIn?'connected':''}">${view.loggedIn?'已连接演示账号 · 不使用真实凭据':'连接学校平台，按上课日期查找课件'}</p></div><button data-action="login" class="${view.loggedIn?'':'secondary'}">${view.loggedIn?'断开演示连接':'连接平台'}</button></section><section class="panel source-card"><div class="source-logo" style="background:#f2f1ed;color:#979481">${icon('folder')}</div><div><h3>本地资料</h3><p>图片、PDF 或旧版下载目录</p></div><button data-action="import">导入 ${icon('plus')}</button></section></div>
    <section class="panel scan-panel"><div class="scan-bar"><label class="field">开始日期<input type="date" id="scan-start" value="${view.scanStart}"></label><label class="field">结束日期<input type="date" id="scan-end" value="${view.scanEnd}"></label><button class="primary" data-action="scan" ${!view.loggedIn||view.scanning?'disabled':''}>${icon('search')}${view.scanning?'正在扫描…':'扫描课表'}</button><span class="scan-note">示例课程：9 月 4 日至 5 日</span></div>
    ${view.scanned?rows.length?`<div class="table-wrap"><table><thead><tr><th><input type="checkbox" id="scan-all" aria-label="选择全部可下载课程" ${rows.filter(c=>!exists(c.id)&&!scheduled(c.id)).length&&rows.filter(c=>!exists(c.id)&&!scheduled(c.id)).every(c=>view.scanSelected.has(c.id))?'checked':''}></th><th>课程</th><th>上课日期</th><th>预计页数</th><th>资料状态</th></tr></thead><tbody>${rows.map(c=>`<tr><td><input type="checkbox" data-scan-select="${c.id}" aria-label="选择 ${esc(c.title)}" ${view.scanSelected.has(c.id)?'checked':''} ${exists(c.id)||scheduled(c.id)?'disabled':''}></td><td><div class="course-title">${esc(c.title)}</div><small>${esc(c.topic)}</small></td><td>${c.day}</td><td>${c.pages} 页</td><td>${exists(c.id)?'<span class="badge exported">已在资料库</span>':scheduled(c.id)?'<span class="badge editing">获取中</span>':'<span class="badge pending">可获取</span>'}</td></tr>`).join('')}</tbody></table></div>`:empty('这个日期范围内没有示例课程','将日期设为 2026-09-04 至 2026-09-05，可体验扫描结果。'):empty(view.scanning?'正在读取示例课表…':view.loggedIn?'选择日期，开始查找课件':'连接平台后查找课件',view.loggedIn?'扫描结果会显示在这里。':'原型将使用演示账号，不需要输入学校账号和密码。')}
    <div class="scan-bottom"><span>已选择 <strong>${view.scanSelected.size}</strong> 节课</span><div class="actions"><label><input type="checkbox" id="direct-export" ${view.directExport?'checked':''}>获取后直接导出</label><button class="primary" data-action="download" ${!view.scanSelected.size?'disabled':''}>${icon('download')}获取选中课件</button></div></div></section><div class="helper-note">${icon('info')}<span>默认先下载到资料库，再筛选页面并导出。需要原样保存时，可以选择直接导出。<br>后台任务不会打断整理；演示下载不会访问网络或创建真实课件文件。</span></div>`;
}
function renderEditor(){
  const m=material();if(!m)return navigate('library');
  const visible=Array.from({length:m.pages},(_,i)=>i+1).filter(p=>view.pageFilter==='all'||!m.excluded.includes(p));
  const excluded=m.excluded.includes(view.currentPage);
  main.innerHTML=`<button class="back-button" data-nav="library">${icon('left')}返回资料库</button><div class="page-heading editor-heading"><div><h1>${esc(m.title)} <span style="font-weight:350;color:#adb5ac">/</span> ${esc(m.topic)}</h1><p class="subtitle"><span>${m.day}</span><span>·</span><span>${m.pages} 页原始页面</span><span>·</span>${badge(m)}</p></div><div class="actions"><span class="saved-label">${icon('check')}${storageOK?'更改已保存':'保存不可用'}</span><button class="primary" data-action="export" ${m.pages===m.excluded.length?'disabled':''}>${icon('export')}导出 PDF</button></div></div>
    <div class="editor-toolbar"><div class="segmented"><button data-page-filter="all" class="${view.pageFilter==='all'?'active':''}">全部页面</button><button data-page-filter="kept" class="${view.pageFilter==='kept'?'active':''}">仅保留页</button></div><span class="separator"></span><button data-action="select-all-pages">${view.selected.size===visible.length&&visible.length?'取消全选':'全选'}</button><button data-action="range">选择范围</button><button data-action="exclude" ${!view.selected.size?'disabled':''}>排除</button><button data-action="restore" ${!view.selected.size?'disabled':''}>恢复</button><span class="separator"></span><button data-action="undo" ${!view.undo.length?'disabled':''} title="撤销上次排除或恢复">${icon('undo')}撤销</button><span class="selected-label">已选中 ${view.selected.size} 页</span></div>
    <div class="editor-layout"><section><div class="pages-grid">${visible.map(p=>`<article class="page-tile ${m.excluded.includes(p)?'excluded':''} ${view.selected.has(p)?'selected':''} ${view.currentPage===p?'current':''}" data-page-tile="${p}"><label class="page-check"><input type="checkbox" data-page-check="${p}" aria-label="选中第 ${p} 页" ${view.selected.has(p)?'checked':''}></label><div class="page-art" tabindex="0" role="button" aria-label="预览第 ${p} 页，双击放大" data-preview="${p}">${slide(m,p)}</div><div class="page-caption"><strong>${String(p).padStart(2,'0')}</strong><button data-toggle-page="${p}">${m.excluded.includes(p)?'恢复此页':'排除此页'}</button></div></article>`).join('')}</div>${!visible.length?empty('没有保留的页面','切换到全部页面，可以恢复之前排除的内容。','<button data-page-filter="all">查看全部页面</button>'):''}</section>
    <aside class="preview-panel"><div class="preview-title">页面预览 <span>原始页 ${view.currentPage} / ${m.pages}</span><button class="icon-button" data-action="fullscreen" title="放大页面" aria-label="放大页面">${icon('expand')}</button></div><div class="large-art" data-action="fullscreen">${slide(m,view.currentPage)}</div><div class="preview-controls"><button class="icon-button" data-action="previous" ${view.currentPage===1?'disabled':''} aria-label="上一页">${icon('left')}</button><span>第 ${view.currentPage} 页</span><button class="icon-button" data-action="next" ${view.currentPage===m.pages?'disabled':''} aria-label="下一页">${icon('right')}</button></div><div class="preview-detail"><h3>${excluded?'此页已排除':'此页将保留在 PDF 中'}</h3><p>${excluded?'原始页面依然保留。恢复后，这一页将重新进入导出结果。':'单击缩略图查看大图；勾选多页，可以批量排除无关画面。'}</p><button class="${excluded?'secondary':''}" data-toggle-page="${view.currentPage}">${excluded?icon('undo')+'恢复此页':icon('close')+'排除此页'}</button></div><div class="keyboard-note"><kbd>←</kbd> <kbd>→</kbd> 翻页　<kbd>E</kbd> 排除 / 恢复<br><kbd>Ctrl</kbd> + <kbd>Z</kbd> 撤销　双击缩略图放大</div></aside></div>
    <div class="editor-summary"><span>共 ${m.pages} 页 <span style="color:#c4cbc4">/</span> <strong>保留 ${m.pages-m.excluded.length} 页</strong> <span style="color:#c4cbc4">/</span> 排除 ${m.excluded.length} 页</span><span>排除不会删除原始图片</span></div>`;
}
function renderTasks(){
  const tasks=state.tasks.filter(t=>view.taskFilter==='all'||(view.taskFilter==='active'?['running','paused'].includes(t.status):t.status==='done'));
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">LET THE WORK CONTINUE</div><h1>任务</h1><p class="subtitle">下载和导出在这里继续，你可以放心切换页面。</p></div><button data-nav="acquire">${icon('plus')}获取课件</button></div><div class="toolbar"><div class="tabs">${[['all','全部任务'],['active','进行中'],['done','已完成']].map(([id,label])=>`<button data-task-filter="${id}" class="${view.taskFilter===id?'active':''}">${label}</button>`).join('')}</div></div>
    ${tasks.length?`<div class="task-list">${[...tasks].reverse().map(t=>`<article class="task-row"><div class="task-icon">${icon(t.type==='export'?'export':'download')}</div><div class="task-copy"><h3>${esc(t.title)}</h3><p>${t.type==='export'?'演示导出':'演示获取'} · ${{running:'正在处理',paused:'已暂停',done:'已完成',cancelled:'已取消'}[t.status]} ${t.status==='running'?`· ${t.progress}%`:''}${t.type==='export'&&t.status==='done'?` · ${t.pageCount} 页（未生成文件）`:''}</p>${['running','paused'].includes(t.status)?`<div class="task-progress"><span style="width:${t.progress}%"></span></div>`:''}</div><div class="actions">${t.status==='running'||t.status==='paused'?`<button data-task-toggle="${t.id}">${icon(t.status==='paused'?'play':'pause')}${t.status==='paused'?'继续':'暂停'}</button><button data-task-cancel="${t.id}">取消</button>`:t.status==='done'?`<button data-open="${t.materialId}" ${!activeMaterials().some(m=>m.id===t.materialId)?'disabled':''}>${t.type==='download'?'打开整理':'返回课件'} ${icon('arrow')}</button>`:'<span class="badge pending">已停止</span>'}</div></article>`).join('')}</div>`:empty('暂时没有'+(view.taskFilter==='active'?'进行中的':'')+'任务','获取课件后，进度和完成记录会出现在这里。','<button class="primary" data-nav="acquire">前往获取课件</button>')}`;
}
function renderSettings(){
  main.innerHTML=`<div class="page-heading"><div><div class="eyebrow">MAKE ROOM FOR YOUR KNOWLEDGE</div><h1>设置</h1><p class="subtitle">让资料保存有序，让日常整理更顺手。</p></div></div><div class="settings-grid"><div><section class="panel settings-section"><h2>资料库与存储</h2><div class="setting-row"><div><h3>资料库位置</h3><p>正式版将管理原始素材、页面状态和缩略图。</p></div><button data-action="storage-plan">查看方案</button></div><div class="setting-path">${icon('database')} 当前原型：当前浏览器中的本地示例记录<br>正式应用：用户选择的资料库目录 / SQLite + 原始文件</div><div class="setting-row"><div><h3>保留原始页面</h3><p>支持恢复已排除页，随时修改并重新导出。</p></div><span class="badge exported">默认保留</span></div><div class="setting-row"><div><h3>自动保存整理进度</h3><p>离开整理页后，筛选记录仍然保留。</p></div><span class="badge exported">已开启</span></div></section>
    <section class="panel settings-section"><h2>下载与导出</h2><div class="setting-row"><div><h3>获取课件后</h3><p>这个选择会成为下次获取课件时的默认选项。</p></div><select id="default-export" class="field-input"><option value="review" ${state.settings.exportMode==='review'?'selected':''}>先整理，再导出</option><option value="direct" ${state.settings.exportMode==='direct'?'selected':''}>直接导出 PDF</option></select></div><div class="setting-row"><div><h3>导出文件与资料库分开</h3><p>删除资料库课件，不会连带删除已导出的 PDF。</p></div>${icon('check')}</div></section>
    <section class="panel settings-section"><h2>原型数据</h2><div class="setting-row"><div><h3>重新开始体验</h3><p>清空演示任务和筛选记录，恢复初始示例课件。</p></div><button class="danger" data-action="reset">重置原型</button></div></section></div><aside class="guide-card">${icon('folder')}<h3 style="margin-top:16px">资料留在本机</h3><p>这是可点击交互原型。你可以整理示例页、切换页面，再回来继续。</p><hr><div class="number">${activeMaterials().length}<span style="font-size:12px;margin-left:8px">份示例课件</span></div><p>不读取真实下载目录<br>不连接学校账号<br>不修改已有 PDF</p><hr><p>正式版的目录迁移、旧文件导入和回收站清理，将在实际接入文件系统时实现。</p></aside></div>`;
}

function showModal(title,body,actions=''){
  modal.classList.remove('fullscreen-modal');
  $('#modal-content').innerHTML=`<div class="modal-header"><h2>${title}</h2><button class="icon-button" data-action="close-modal" aria-label="关闭">${icon('close')}</button></div><div class="modal-body">${body}</div>${actions?`<div class="modal-actions">${actions}</div>`:''}`;
  if(!modal.open)modal.showModal();
}
function closeModal(){modal.close();modal.classList.remove('fullscreen-modal');}
function openMaterial(id){
  const m=state.materials.find(m=>m.id===id&&!m.deleted);if(!m)return toast('这份课件已移入回收站，可恢复后打开。');
  navigate('editor/'+id);
}
function mutatePages(pages,exclude){
  const m=material();if(!m)return;
  const before=[...m.excluded];
  const set=new Set(before);pages.forEach(p=>exclude?set.add(p):set.delete(p));
  const after=[...set].sort((a,b)=>a-b);
  if(JSON.stringify(before)===JSON.stringify(after))return toast(exclude?'所选页面已排除':'所选页面都已保留');
  view.undo.push({excluded:before,edited:m.edited,revision:m.revision,touched:m.touched});
  m.excluded=after;m.edited=true;m.revision++;m.touched=Date.now();view.selected.clear();save();render();
  toast(`${exclude?'已排除':'已恢复'} ${Math.abs(after.length-before.length)} 页 · 原始页面保留`);
}
function undo(){
  const previous=view.undo.pop();if(!previous)return;
  Object.assign(material(),previous);view.selected.clear();save();render();toast('已撤销上一次页面操作');
}
function preview(page){
  const m=material();if(!m)return;
  view.currentPage=Math.max(1,Math.min(m.pages,page));m.lastPage=view.currentPage;save();
  if(modal.open&&modal.classList.contains('fullscreen-modal'))showFullscreen();else renderEditor();
}
function showFullscreen(){
  const m=material();showModal(`${esc(m.title)} · 第 ${view.currentPage} 页`,`${slide(m,view.currentPage)}<div class="full-nav"><button data-action="previous" ${view.currentPage===1?'disabled':''}>${icon('left')}上一页</button><span>${view.currentPage} / ${m.pages}</span><button data-action="next" ${view.currentPage===m.pages?'disabled':''}>下一页${icon('right')}</button><button data-action="toggle-fullscreen-page">${m.excluded.includes(view.currentPage)?'恢复此页':'排除此页'}</button></div>`);modal.classList.add('fullscreen-modal');
}
function showExport(){
  const m=material();const kept=m.pages-m.excluded.length;
  if(!kept)return toast('至少保留一页后才能导出。');
  if(state.tasks.some(t=>t.materialId===m.id&&t.type==='export'&&['running','paused'].includes(t.status)))return toast('这份课件正在演示导出，可在任务页查看。');
  showModal('导出 PDF',`<p>将按原始页序，合并当前保留的页面。</p><div class="modal-stat"><div><strong>${m.pages}</strong><span>原始页面</span></div><div><strong>${kept}</strong><span>保留并导出</span></div><div><strong>${m.excluded.length}</strong><span>已排除</span></div></div><label class="field">文件名称<input type="text" id="export-name" value="${esc(m.day+'_'+m.title+'.pdf')}" maxlength="120"></label><div class="notice">原型演示：确认后会展示导出任务及结果状态，不会生成真实 PDF，也不会写入下载目录。</div>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-export">演示导出</button>');
}
function addTask(m,type,extra={}){
  state.tasks.push({id:'task-'+Date.now()+'-'+Math.random().toString(16).slice(2),materialId:m.id,title:m.title+' · '+m.topic,
    type,status:'running',progress:0,...extra});save();
}
function startDownload(){
  if(!view.loggedIn)return toast('请先连接演示平台。');
  const direct=$('#direct-export')?.checked||false;
  const selected=availableCourses.filter(m=>view.scanSelected.has(m.id));
  selected.forEach(m=>{if(!state.tasks.some(t=>t.materialId===m.id&&['running','paused'].includes(t.status)))addTask(m,'download',{direct});});
  view.scanSelected.clear();render();toast(`已加入 ${selected.length} 项演示任务，可继续浏览或整理`);
}
function taskTick(){
  let changed=false;
  const completed=[];
  state.tasks.filter(t=>t.status==='running').forEach(t=>{
    changed=true;t.progress=Math.min(100,t.progress+(t.type==='export'?25:8));
    if(t.progress<100)return;
    t.status='done';
    if(t.type==='download'){
      const definition=availableCourses.find(m=>m.id===t.materialId);
      if(definition){
        let m=state.materials.find(m=>m.id===t.materialId);
        if(m)m.deleted=false;
        else {m={...definition,excluded:[],edited:false,exported:false,revision:0,exportRevision:null,touched:Date.now(),lastPage:1,deleted:false};state.materials.push(m);}
        if(t.direct)addTask(m,'export',{pageCount:m.pages-m.excluded.length,exportRevision:m.revision,fileName:m.day+'_'+m.title+'.pdf'});
      }
    }else{
      const m=state.materials.find(m=>m.id===t.materialId);
      if(m){m.exported=true;m.exportRevision=t.exportRevision;m.exportName=t.fileName;m.touched=Date.now();}
    }
    completed.push(t);
  });
  if(changed){save();renderShell();if(view.page==='tasks'||(completed.length&&['library','acquire','editor'].includes(view.page)))render();}
  if(completed.length)toast(completed.some(t=>t.type==='download')?'示例课件已加入资料库，可以开始整理':'演示导出完成 · 未生成真实文件');
}
function showHelp(){showModal('从获取到整理，走一遍',`<p>这是一份用于确认页面布局与交互的原型。课件图片、账号和任务都是示例。</p><ol class="help-steps"><li>资料库 → 继续整理，排除几页再撤销。</li><li>双击页面看大图，试试方向键和 E 键。</li><li>点击导出 PDF，查看演示任务。</li><li>回到资料库，再打开课件继续修改。</li><li>获取课件 → 连接平台 → 扫描 → 获取。</li></ol><div class="notice">整理记录会保存在当前浏览器。可以刷新检查；在“设置”中重置体验。真实下载程序仍使用原来的启动入口。</div>`, '<button class="primary" data-action="close-modal">开始体验</button>');}

document.addEventListener('click',event=>{
  const button=event.target.closest('button,a,[data-action]');
  if(button?.disabled)return;
  if(button?.dataset.nav)return navigate(button.dataset.nav);
  if(button?.dataset.open)return openMaterial(button.dataset.open);
  if(button?.dataset.filter){view.filter=button.dataset.filter;renderLibrary();return;}
  if(button?.dataset.pageFilter){view.pageFilter=button.dataset.pageFilter;view.selected.clear();renderEditor();return;}
  if(button?.dataset.taskFilter){view.taskFilter=button.dataset.taskFilter;renderTasks();return;}
  if(button?.dataset.restore){const m=state.materials.find(m=>m.id===button.dataset.restore);m.deleted=false;save();render();toast('课件已恢复到资料库');return;}
  if(button?.dataset.togglePage){const p=Number(button.dataset.togglePage);mutatePages([p],!material().excluded.includes(p));return;}
  if(button?.dataset.taskToggle){const t=state.tasks.find(t=>t.id===button.dataset.taskToggle);t.status=t.status==='paused'?'running':'paused';save();render();return;}
  if(button?.dataset.taskCancel){const t=state.tasks.find(t=>t.id===button.dataset.taskCancel);t.status='cancelled';save();render();toast('演示任务已取消');return;}
  if(button?.dataset.menu){
    const m=state.materials.find(m=>m.id===button.dataset.menu);
    showModal('管理课件',`<p>${esc(m.title)} · ${esc(m.topic)}</p><p>移入回收站后可恢复，筛选记录会保留；已经导出的文件不受影响。</p>`,`<button data-action="close-modal">取消</button><button class="danger" data-delete-material="${m.id}">移入回收站</button>`);return;
  }
  if(button?.dataset.deleteMaterial){const m=state.materials.find(m=>m.id===button.dataset.deleteMaterial);m.deleted=true;save();closeModal();render();toast('已移入回收站，可从资料库恢复');return;}
  // Delay a single preview click so a double click can open the large preview reliably.
  const pageElement=event.target.closest('[data-preview]');
  if(pageElement){clearTimeout(preview.timer);preview.timer=setTimeout(()=>preview(Number(pageElement.dataset.preview)),220);return;}
  const action=button?.dataset.action;if(!action)return;
  if(action==='close-modal')return closeModal();
  if(action==='clear-search'){view.search='';renderLibrary();return;}
  if(action==='login'){
    if(view.loggedIn){view.loggedIn=false;view.scanned=false;view.scanSelected.clear();renderAcquire();return;}
    return showModal('连接华工视频平台',`<div class="source-card" style="margin:12px 0 20px"><div class="source-logo">${icon('school')}</div><div><h3>学校网页登录</h3><p>正式应用会在独立窗口中打开学校登录页。</p></div></div><div class="notice">这里使用演示连接，不需要输入账号、密码或验证码。原型不会接触学校登录凭据。</div>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-login">使用演示账号</button>');
  }
  if(action==='confirm-login'){view.loggedIn=true;closeModal();render();toast('已连接演示账号，现在可以扫描课表');return;}
  if(action==='scan'){
    view.scanStart=$('#scan-start').value;view.scanEnd=$('#scan-end').value;
    if(!view.scanStart||!view.scanEnd||view.scanStart>view.scanEnd)return toast('请填写有效日期，开始日期不能晚于结束日期。');
    view.scanning=true;view.scanned=false;view.scanSelected.clear();renderAcquire();
    setTimeout(()=>{view.scanning=false;view.scanned=true;if(view.page==='acquire')renderAcquire();toast('示例课表扫描完成');},700);return;
  }
  if(action==='download')return startDownload();
  if(action==='import')return showModal('导入本地资料',`<p>正式应用将支持图片、PDF 和旧版下载目录。导入时复制到资料库，保留原文件。</p><div class="notice">当前原型不读取本地文件。你可以添加一份示例 PDF，体验导入后整理的流程。</div>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-import">添加示例 PDF</button>');
  if(action==='confirm-import'){
    const id='import-'+Date.now();state.materials.push({id,title:'我的复习资料',topic:'本地 PDF 导入示例',day:'2026-09-05',pages:12,tone:'sand',kind:'chart',section:'01',source:'import',excluded:[],edited:false,exported:false,revision:0,exportRevision:null,touched:Date.now(),lastPage:1,deleted:false});save();closeModal();openMaterial(id);toast('示例资料已加入资料库');return;
  }
  if(action==='select-all-pages'){
    const m=material(),pages=Array.from({length:m.pages},(_,i)=>i+1).filter(p=>view.pageFilter==='all'||!m.excluded.includes(p));
    view.selected=view.selected.size===pages.length?new Set():new Set(pages);renderEditor();return;
  }
  if(action==='range')return showModal('选择连续页面',`<p>使用原始页码选择一段连续页面，再进行批量排除或恢复。</p><div class="range-fields"><label class="field">从第几页<input type="number" id="range-from" min="1" max="${material().pages}" value="${view.currentPage}"></label><label class="field">到第几页<input type="number" id="range-to" min="1" max="${material().pages}" value="${Math.min(material().pages,view.currentPage+3)}"></label></div>`, '<button data-action="close-modal">取消</button><button class="primary" data-action="confirm-range">选中这些页面</button>');
  if(action==='confirm-range'){
    const from=Number($('#range-from').value),to=Number($('#range-to').value);
    if(!Number.isInteger(from)||!Number.isInteger(to)||from<1||to>material().pages||from>to)return toast('请输入有效范围，起始页不能大于结束页。');
    view.pageFilter='all';view.selected=new Set(Array.from({length:to-from+1},(_,i)=>i+from));closeModal();renderEditor();return;
  }
  if(action==='exclude')return mutatePages([...view.selected],true);
  if(action==='restore')return mutatePages([...view.selected],false);
  if(action==='undo')return undo();
  if(action==='previous')return preview(view.currentPage-1);
  if(action==='next')return preview(view.currentPage+1);
  if(action==='fullscreen')return showFullscreen();
  if(action==='toggle-fullscreen-page'){mutatePages([view.currentPage],!material().excluded.includes(view.currentPage));showFullscreen();return;}
  if(action==='export')return showExport();
  if(action==='confirm-export'){
    const m=material(),name=$('#export-name').value.trim();
    if(!name||/[\\/:*?"<>|]/.test(name))return toast('请输入有效文件名，不要包含路径或特殊字符。');
    addTask(m,'export',{pageCount:m.pages-m.excluded.length,exportRevision:m.revision,fileName:name.toLowerCase().endsWith('.pdf')?name:name+'.pdf'});closeModal();render();toast('演示导出已开始，可在任务页查看');return;
  }
  if(action==='storage-plan')return showModal('正式版的资料存储',`<p>资料库目录由你选择，可以整体备份和迁移。应用通过相对路径关联原始文件。</p><div class="export-details">library.sqlite　课件与页面记录<br>materials/　原始图片、导入文件<br>thumbnails/　可重新生成的缩略图<br>temporary/　未完成下载与临时文件</div><p>PDF 导出目录独立选择。原型仅保存示例记录，不会创建以上文件。</p>`, '<button class="primary" data-action="close-modal">知道了</button>');
  if(action==='reset')return showModal('重置原型？','<p>将清除本原型中的筛选记录、导入示例和任务，恢复最初的六份示例课件。真实项目数据不受影响。</p>','<button data-action="close-modal">取消</button><button class="danger" data-action="confirm-reset">重置示例数据</button>');
  if(action==='confirm-reset'){state=initialState();save();view.selected.clear();view.undo=[];view.materialId=null;view.filter='all';view.search='';view.loggedIn=false;view.scanned=false;view.scanSelected.clear();closeModal();navigate('library');toast('已恢复初始示例数据');return;}
});
document.addEventListener('change',event=>{
  const el=event.target;
  if(el.matches('[data-page-check]')){const p=Number(el.dataset.pageCheck);el.checked?view.selected.add(p):view.selected.delete(p);renderEditor();}
  if(el.matches('[data-scan-select]')){el.checked?view.scanSelected.add(el.dataset.scanSelect):view.scanSelected.delete(el.dataset.scanSelect);renderAcquire();}
  if(el.id==='scan-all'){
    availableCourses.filter(m=>m.day>=view.scanStart&&m.day<=view.scanEnd&&!activeMaterials().some(c=>c.id===m.id)&&!state.tasks.some(t=>t.materialId===m.id&&['running','paused'].includes(t.status))).forEach(m=>el.checked?view.scanSelected.add(m.id):view.scanSelected.delete(m.id));renderAcquire();
  }
  if(el.id==='library-sort'){view.sort=el.value;renderLibrary();}
  if(el.id==='direct-export')view.directExport=el.checked;
  if(el.id==='scan-start')view.scanStart=el.value;
  if(el.id==='scan-end')view.scanEnd=el.value;
  if(el.id==='default-export'){state.settings.exportMode=el.value;view.directExport=el.value==='direct';save();toast('默认获取方式已保存');}
});
function searchInput(event){
  if(event.target.id==='library-search'&&!event.isComposing){
    const el=event.target,start=el.selectionStart;view.search=el.value;renderLibrary();$('#library-search').focus();$('#library-search').setSelectionRange(start,start);
  }
}
document.addEventListener('input',searchInput);
document.addEventListener('compositionend',searchInput);
document.addEventListener('dblclick',event=>{const el=event.target.closest('[data-preview]');if(el){clearTimeout(preview.timer);view.currentPage=Number(el.dataset.preview);material().lastPage=view.currentPage;save();showFullscreen();}});
document.addEventListener('keydown',event=>{
  if(view.page!=='editor'||['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;
  if(event.key==='Enter'&&event.target.matches('[data-preview]')){view.currentPage=Number(event.target.dataset.preview);showFullscreen();return;}
  if(modal.open&&!modal.classList.contains('fullscreen-modal'))return;
  if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();preview(view.currentPage+(event.key==='ArrowLeft'?-1:1));}
  if(event.key.toLowerCase()==='e'&&!event.ctrlKey&&!event.metaKey){const full=modal.open;mutatePages([view.currentPage],!material().excluded.includes(view.currentPage));if(full)showFullscreen();}
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();const full=modal.open;undo();if(full)showFullscreen();}
});
$('#help-button').addEventListener('click',showHelp);
modal.addEventListener('click',event=>{if(event.target===modal){const r=modal.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeModal();}});
modal.addEventListener('close',()=>{modal.classList.remove('fullscreen-modal');if(view.page==='editor')renderEditor();});
window.addEventListener('hashchange',route);
setInterval(taskTick,600);
route();hydrate();
