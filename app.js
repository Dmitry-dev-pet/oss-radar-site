"use strict";
/* Public static index. No external scripts, API keys or analytics. */
const featured=[
 {n:"CopilotKit/OpenDuet",s:1998,c:"agents",t:"Проактивный ассистент",d:"Агенты, задачи, согласование действий и журнал операций."},
 {n:"datalab-to/indra",s:1682,c:"documents",t:"Локальный OCR на CPU",d:"Сканы, PDF, таблицы и рукописи с экспортом в Markdown/JSON."},
 {n:"Roboparty/RP1",s:1167,c:"robots",t:"Открытая робототехника",d:"Гуманоидный проект с CAD, электроникой, приводами и прошивками."},
 {n:"reason-machines/reason-network",s:1674,c:"agents",t:"Связь между агентами",d:"Обмен сообщениями между разными AI coding-сессиями."},
 {n:"Pomerado/pomerado",s:1578,c:"agents",t:"MCP из веб-интерфейсов",d:"Создание повторяемых интеграций для сайтов."},
 {n:"colinhacks/reylo",s:1544,c:"data",t:"Типобезопасный SQL",d:"SQL-файлы с автоматическим выводом типов в TypeScript."},
 {n:"mistralai/timestral",s:1152,c:"data",t:"Временные ряды",d:"Компактные модели для вероятностного прогнозирования."},
 {n:"emanuele-em/kanzo",s:1116,c:"dev",t:"Kanban + MCP",d:"Локальная доска задач для людей и агентов."},
 {n:"openqodex/openqodex",s:1059,c:"security",t:"Второй AI code review",d:"Статический анализ и независимая проверка diff."},
 {n:"ManfredCh/Lyapunov",s:1030,c:"robots",t:"3D-симуляция роботов",d:"MuJoCo, роботы, сенсоры и опциональное управление через LLM."}
];
const labels={agents:"ИИ и агенты",robots:"Робототехника",documents:"Документы / OCR",data:"Данные / БД",dev:"Разработка",security:"Безопасность",design:"Дизайн / UI",other:"Другое"};
const $=id=>document.getElementById(id),starFmt=new Intl.NumberFormat("ru-RU");
const manifestFallback=[
 ["2025-11",922,4],["2025-12",967,4],["2026-01",1000,5],["2026-02",1000,5],
 ["2026-03",1000,5],["2026-04",1000,5],["2026-05",953,4],["2026-06",946,4],
 ["2026-07",938,4],["2026-08",953,4],["2026-09",939,4],["2026-10",937,4],["2026-11",633,3]
].map(x=>({month:x[0],count:x[1],partialBands:x[2]}));
let manifest=manifestFallback,currentMonth="2026-10",items=[],filtered=[],shown=36,version=0;
let favorites=new Set();
try{favorites=new Set(JSON.parse(localStorage.getItem("ossradar:favorites")||"[]"));}catch{}
function saveFavorites(){try{localStorage.setItem("ossradar:favorites",JSON.stringify([...favorites]));}catch{}}
function elem(tag,attrs={},text){
 const e=document.createElement(tag);
 for(const [k,v] of Object.entries(attrs)){if(k==="class")e.className=v;else e.setAttribute(k,String(v))}
 if(text!==undefined)e.textContent=String(text);
 return e;
}
function monthLabel(month){
 const [y,m]=month.split("-").map(Number);
 return new Intl.DateTimeFormat("ru-RU",{month:"long",year:"numeric"}).format(new Date(Date.UTC(y,m-1,1)));
}
function repoURL(name){
 return /^[-.\w]+\/[-.\w]+$/u.test(name)?"https://github.com/"+name:null;
}
function featuredCard(data,compact){
 const article=elem("article",{class:compact?"mini-feature":"feature-card"});
 if(compact){
  const wrap=elem("div");
  wrap.append(elem("a",{href:repoURL(data.n)||"#",target:"_blank",rel:"noopener noreferrer"},data.n.split("/")[1]),
   elem("div",{class:"f-desc"},data.t));
  article.append(wrap,elem("span",{class:"stars"},starFmt.format(data.s)+" ★"));
 }else{
  const top=elem("div",{class:"feature-top"});
  top.append(elem("span",{class:"tag green"},labels[data.c]),
   elem("span",{class:"stars"},starFmt.format(data.s)+" ★"));
  article.append(top,elem("h3",{},data.n.split("/")[1]),elem("p",{},data.d));
  const bottom=elem("div",{class:"bottom"});
  bottom.append(elem("a",{href:repoURL(data.n)||"#",target:"_blank",rel:"noopener noreferrer"},"Открыть GitHub ↗"));
  article.append(bottom);
 }
 return article;
}
function renderFeatured(){
 const grid=$("featuredGrid"),more=$("moreFeatures");
 grid.replaceChildren(...featured.slice(0,3).map(x=>featuredCard(x,false)));
 more.replaceChildren(...featured.slice(3).map(x=>featuredCard(x,true)));
 $("showFeatures").addEventListener("click",()=>{
  const hidden=more.classList.toggle("is-hidden");
  $("showFeatures").textContent=hidden?"Показать ещё 7 проектов":"Свернуть список";
  $("showFeatures").setAttribute("aria-expanded",String(!hidden));
 });
}
function safeRepo(item){
 const url=item.u||repoURL(item.n);
 return typeof url==="string"&&/^https:\/\/github\.com\/[-.\w]+\/[-.\w]+\/?$/u.test(url)?url:null;
}
function projectCard(item){
 const card=elem("article",{class:"project-card"}),top=elem("div",{class:"project-top"});
 const link=elem("a",{class:"repo-link",href:safeRepo(item)||"#",target:"_blank",rel:"noopener noreferrer"},item.n);
 const key=item.u||item.n;
 const save=elem("button",{class:"save",type:"button","aria-label":"В избранное: "+item.n,"aria-pressed":String(favorites.has(key))},favorites.has(key)?"★":"☆");
 save.addEventListener("click",()=>{
  if(favorites.has(key))favorites.delete(key);else favorites.add(key);
  saveFavorites();
  save.textContent=favorites.has(key)?"★":"☆";
  save.setAttribute("aria-pressed",String(favorites.has(key)));
  if($("favoritesOnly").checked)applyFilters();
 });
 top.append(link,save);
 const desc=elem("p",{class:"project-desc"},item.d||"Описание не указано.");
 const meta=elem("div",{class:"project-meta"});
 meta.append(elem("span",{class:"stars"},starFmt.format(item.s)+" ★"));
 meta.append(elem("span",{class:"tag"},labels[item.c]||labels.other));
 meta.append(elem("span",{class:"tag "+(item.l?"green":"amber")},item.l||"лицензия не указана"));
 card.append(top,desc,meta);return card;
}
function applyFilters(){
 const q=$("searchInput").value.trim().toLocaleLowerCase("ru-RU");
 const category=$("categorySelect").value,order=$("sortSelect").value;
 const licenseOnly=$("licenseOnly").checked,favOnly=$("favoritesOnly").checked;
 filtered=items.filter(r=>{
  if(category!=="all"&&r.c!==category)return false;
  if(licenseOnly&&!r.l)return false;
  if(favOnly&&!favorites.has(r.u||r.n))return false;
  return !q||(r.n+" "+(r.d||"")+" "+(r.l||"")).toLocaleLowerCase("ru-RU").includes(q);
 });
 if(order==="stars-asc")filtered.sort((a,b)=>a.s-b.s||a.n.localeCompare(b.n));
 else if(order==="name")filtered.sort((a,b)=>a.n.localeCompare(b.n));
 else filtered.sort((a,b)=>b.s-a.s||a.n.localeCompare(b.n));
 shown=36;paint();
}
function paint(){
 const grid=$("catalogGrid");
 grid.replaceChildren(...filtered.slice(0,shown).map(projectCard));
 const row=manifest.find(m=>m.month===currentMonth);
 $("resultsInfo").textContent=starFmt.format(filtered.length)+" из "+starFmt.format(items.length)+" проектов за "+monthLabel(currentMonth)+" · "+(row?.partialBands||0)+" неполных диапазонов из 5";
 $("emptyState").classList.toggle("is-hidden",filtered.length>0);
 const more=filtered.length>shown;
 $("catalogAction").classList.toggle("is-hidden",!more);
 if(more)$("loadMore").textContent="Показать ещё ("+starFmt.format(filtered.length-shown)+" осталось)";
}
async function loadMonth(month){
 currentMonth=month;const request=++version;
 $("catalogGrid").replaceChildren(elem("p",{class:"loading"},"Загружаем данные месяца…"));
 $("resultsInfo").textContent="Загружаем…";
 $("catalogAction").classList.add("is-hidden");
 $("emptyState").classList.add("is-hidden");
 try{
  const res=await fetch("./data/"+encodeURIComponent(month)+".json");
  if(!res.ok)throw new Error("HTTP "+res.status);
  const data=await res.json();
  if(request!==version)return;
  if(data.month!==month||!Array.isArray(data.projects))throw new Error("Invalid catalog");
  items=data.projects.filter(x=>Number.isInteger(x.s)&&x.s>=50&&x.s<=2000&&typeof x.n==="string"&&safeRepo(x));
  applyFilters();
 }catch{
  if(request!==version)return;
  items=[];$("resultsInfo").textContent="Не удалось загрузить данные. Проверь соединение и обнови страницу.";
  $("catalogGrid").replaceChildren(elem("p",{class:"loading"},"Каталог временно недоступен."));
 }
}
async function start(){
 renderFeatured();
 for(const id of ["searchInput","categorySelect","sortSelect","licenseOnly","favoritesOnly"])
  $(id).addEventListener(id==="searchInput"?"input":"change",applyFilters);
 $("monthSelect").addEventListener("change",e=>loadMonth(e.target.value));
 $("loadMore").addEventListener("click",()=>{shown+=36;paint()});
 try{
  const res=await fetch("./data/manifest.json");
  if(res.ok){
   const data=await res.json();
   if(Array.isArray(data.months)&&data.months.length)manifest=data.months;
   if(Number.isInteger(data.total))$("totalCount").textContent=starFmt.format(data.total);
   $("monthCount").textContent=String(manifest.length);
  }
 }catch{}
 for(const row of [...manifest].reverse()){
  $("monthSelect").append(elem("option",{value:row.month},monthLabel(row.month)+" ("+starFmt.format(row.count)+")"));
 }
 $("monthSelect").value=currentMonth;
 await loadMonth(currentMonth);
}
document.addEventListener("DOMContentLoaded",start);
