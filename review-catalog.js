"use strict";
/* Static editorial review index only: one same-origin JSON; no GitHub API, feeds or analytics. */
const REVIEW_TYPES = {
  weekly:"Обзор недели",monthly:"Аналитика месяца",
  deep:"Глубокий разбор",comparison:"Сравнение",experiment:"Эксперимент"
};
const $=id=>document.getElementById(id);
let reviews=[];
function element(tag, className, value){
  const node=document.createElement(tag);
  if(className)node.className=className;
  if(value!==undefined)node.textContent=String(value);
  return node;
}
function safeReview(item){
  return !!item && typeof item==="object" &&
    typeof item.title==="string" && typeof item.summary==="string" &&
    typeof item.date==="string" && /^\d{4}-\d{2}-\d{2}$/.test(item.date) &&
    REVIEW_TYPES[item.type] && typeof item.url==="string" &&
    /^reviews\/[a-z0-9-]+\.html$/.test(item.url) &&
    Array.isArray(item.tags) && item.tags.every(x=>typeof x==="string"&&x.length<70);
}
function loadOptions(){
  const topics=[...new Set(reviews.flatMap(r=>r.tags))].sort((a,b)=>a.localeCompare(b,"ru"));
  const select=$("topicReviews");
  for(const topic of topics){
    const option=element("option","",topic);
    option.value=topic;select.append(option);
  }
}
function displayDate(value){
  return new Intl.DateTimeFormat("ru-RU",{dateStyle:"long",timeZone:"UTC"})
    .format(new Date(value+"T12:00:00Z"));
}
function render(){
  const q=$("searchReviews").value.trim().toLocaleLowerCase("ru-RU");
  const type=$("typeReviews").value;
  const topic=$("topicReviews").value;
  const rows=reviews.filter(r=>
    (type==="all"||r.type===type) &&
    (topic==="all"||r.tags.includes(topic)) &&
    (!q||[r.title,r.subtitle||"",r.summary,...r.tags,...(r.projects||[])]
      .join(" ").toLocaleLowerCase("ru-RU").includes(q))
  ).sort((a,b)=>(b.period_end||b.date).localeCompare(a.period_end||a.date)||a.title.localeCompare(b.title,"ru"));
  const root=$("reviewCards");
  root.replaceChildren();
  for(const item of rows){
    const article=element("article","lead-review archive-review");
    const meta=element("div","issue-meta");
    meta.append(element("span","meta-item",REVIEW_TYPES[item.type]));
    meta.append(element("span","meta-item",item.period_label || displayDate(item.date)));
    if(item.period_label)meta.append(element("span","meta-item","Подготовлено "+displayDate(item.date)));
    meta.append(element("span","meta-item",item.verification==="executed"?
      "Проверено экспериментом":item.verification==="source"?
      "Изучены исходники":"Документальный разбор"));
    const heading=element("h3","",item.title);
    const summary=element("p","",item.summary);
    const tags=element("div","review-keywords");
    for(const t of item.tags) tags.append(element("span","",t));
    const link=element("a","button","Читать разбор");
    link.href="./"+item.url;
    article.append(meta,heading,summary,tags,link);root.append(article);
  }
  $("reviewCount").textContent="Найдено материалов: "+rows.length+" из "+reviews.length;
  $("reviewEmpty").hidden=rows.length>0;
}
async function start(){
  try{
    const response=await fetch("./reviews/catalog.json",{cache:"no-store"});
    if(!response.ok)throw new Error("HTTP "+response.status);
    const payload=await response.json();
    if(payload.schema_version!==1||!Array.isArray(payload.articles)||
       !payload.articles.every(safeReview))throw new Error("Некорректный каталог статей");
    reviews=payload.articles;loadOptions();render();
  }catch(error){
    $("reviewCount").textContent="Не удалось прочитать каталог публикаций.";
    $("reviewEmpty").hidden=false;
  }
  for(const id of ["searchReviews","typeReviews","topicReviews"]){
    $(id).addEventListener(id==="searchReviews"?"input":"change",render);
  }
}
document.addEventListener("DOMContentLoaded",start);
