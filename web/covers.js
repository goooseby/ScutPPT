'use strict';

/*
 * Cover extension point. Add future SVG compositions to COVER_TEMPLATES and
 * palettes to COVER_PALETTES; saved course IDs remain stable across releases.
 */
const COVER_PALETTES={
  forest:{bg:'#f1f6f1',ink:'#285846',soft:'#cfe1d5'},
  ocean:{bg:'#f0f4f8',ink:'#355875',soft:'#d5e1ea'},
  sand:{bg:'#f8f4e9',ink:'#735f36',soft:'#eadfbe'},
  plum:{bg:'#f4f1f7',ink:'#615477',soft:'#ded6e8'},
  clay:{bg:'#f8f0ec',ink:'#7b5042',soft:'#ead5cc'},
  teal:{bg:'#edf6f5',ink:'#276363',soft:'#cce3df'}
};

const COVER_TEMPLATES={
  frame:({ink,soft})=>`<path d="M455 207h110v103H455Zm-20 18v105h110" fill="none" stroke="${ink}" stroke-width="4" opacity=".11"/><rect x="478" y="229" width="64" height="58" rx="3" fill="${soft}" opacity=".55"/>`,
  orbit:({ink,soft})=>`<circle cx="510" cy="253" r="71" fill="${soft}" opacity=".42"/><circle cx="510" cy="253" r="43" fill="none" stroke="${ink}" stroke-width="3" opacity=".16"/><path d="M416 253c31-47 157-47 188 0-31 47-157 47-188 0Z" fill="none" stroke="${ink}" stroke-width="3" opacity=".12"/>`,
  steps:({ink,soft})=>`<path d="M430 302h52v-44h52v-44h52" fill="none" stroke="${ink}" stroke-width="16" opacity=".11"/><rect x="456" y="190" width="105" height="105" rx="7" fill="${soft}" opacity=".26"/>`
};

const coverHash=value=>{let hash=2166136261;for(const ch of String(value||'课页'))hash=Math.imul(hash^ch.charCodeAt(0),16777619)>>>0;return hash;};
const coverChoice=(requested,choices,index)=>requested&&choices.includes(requested)?requested:choices[index%choices.length];

function generatedCover(data){
  const templateIds=Object.keys(COVER_TEMPLATES),paletteIds=Object.keys(COVER_PALETTES);
  const hash=coverHash(data.coverKey||data.id||data.title);
  const templateId=coverChoice(data.coverStyle,templateIds,hash);
  const paletteId=coverChoice(data.coverPalette,paletteIds,hash>>>8);
  const palette=COVER_PALETTES[paletteId];
  const title=Array.from(data.title||'未命名课程'),line1=title.slice(0,15).join(''),line2=title.slice(15,29).join('')+(title.length>29?'…':'');
  const meta=[data.day||data.term||'课程资料',data.pages?`${data.pages} 页`:null].filter(Boolean).join('　·　');
  return `<svg class="slide" viewBox="0 0 640 360" role="img" aria-label="${esc(data.title||'课程')} 自动生成封面" xmlns="http://www.w3.org/2000/svg" style="font-family:'Microsoft YaHei','Segoe UI',sans-serif"><rect width="640" height="360" fill="${palette.bg}"/><rect width="640" height="6" fill="${palette.ink}" opacity=".78"/><text x="46" y="51" font-size="11" fill="${palette.ink}" letter-spacing="2">课页 / PERSONAL COURSE LIBRARY</text><text x="46" y="137" font-size="32" font-weight="650" fill="${palette.ink}">${esc(line1)}</text><text x="46" y="184" font-size="32" font-weight="650" fill="${palette.ink}">${esc(line2)}</text><rect x="46" y="217" width="40" height="3" fill="${palette.ink}" opacity=".55"/><text x="46" y="261" font-size="14" fill="${palette.ink}">${esc(meta)}</text>${COVER_TEMPLATES[templateId](palette)}<path d="M45 323h550" stroke="${palette.ink}" opacity=".15"/><text x="46" y="343" font-size="10" fill="${palette.ink}" opacity=".65">自动生成封面 · ${esc(templateId)} / ${esc(paletteId)}</text></svg>`;
}
