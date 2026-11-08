"use strict";
/* No collector or credentials: external open feed + GitHub's public star-history REST API. */
const API_VERSION = "2026-03-10";
const NAME = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const number = new Intl.NumberFormat("ru-RU");

function repositoryName(candidate) {
  if (typeof candidate !== "string") return null;
  const value = candidate.trim();
  if (NAME.test(value) && !value.split("/").some(part => part==="." || part==="..")) return value;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;
    const parts = url.pathname.split("/").filter(Boolean);
    if (url.hostname === "githubtrending.today" && parts[0] === "repo") parts.shift();
    else if (url.hostname !== "github.com") return null;
    if (parts.length < 2) return null;
    const result = parts[0] + "/" + parts[1].replace(/\.git$/i, "");
    return NAME.test(result) && !result.split("/").some(part => part==="." || part==="..") ? result : null;
  } catch { return null; }
}
function toPlainText(input) {
  return typeof input === "string" ? input.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 230) : "";
}
function parseMirror(json) {
  if (!json || json.schema !== 1 || json.source !== "GitHub Trending Today" ||
      !json.lists || !Array.isArray(json.lists["all:daily"]) ||
      !Array.isArray(json.lists["all:weekly"]) || !Array.isArray(json.lists["all:monthly"]) ||
      !Number.isFinite(Date.parse(json.collected_at))) {
    throw new Error("Неизвестная версия импортированной подборки");
  }
  for (const period of ["daily","weekly","monthly"]) {
    for (const item of json.lists["all:"+period]) {
      if (!repositoryName(item.name) || !Number.isInteger(item.gained) || item.gained < 0)
        throw new Error("Некорректные метрики в подборке");
    }
  }
  return json;
}

function parseHistory(json) {
  if (!Array.isArray(json)) throw new Error("GitHub вернул не список недель");
  const out = json.map(row => {
    if (!Number.isSafeInteger(row.week) || !Number.isSafeInteger(row.total) ||
        row.total < 0 || !Array.isArray(row.days) || row.days.length !== 7 ||
        row.days.some(x => !Number.isSafeInteger(x) || x < 0))
      throw new Error("Неизвестный формат истории GitHub");
    if (row.days.reduce((a,b) => a + b, 0) !== row.total)
      throw new Error("Сумма дней не совпадает с недельным итогом GitHub");
    return {week: row.week, total: row.total, days: row.days};
  });
  return out.sort((a,b) => b.week - a.week);
}
function recentBins(history, nowMs) {
  const all = history.flatMap(row => row.days.map((count, i) => ({
    approximateDay: row.week * 1000 + i * 86400000, count
  })));
  // Provider's week/day boundaries may not match UTC; these are rough anchors.
  const lastCompletedUtc = Date.UTC(new Date(nowMs).getUTCFullYear(),
    new Date(nowMs).getUTCMonth(), new Date(nowMs).getUTCDate()) - 86400000;
  const eligible = all.filter(x => x.approximateDay <= lastCompletedUtc)
    .sort((a,b) => b.approximateDay - a.approximateDay);
  return {previousDay: eligible.length ? eligible[0].count : null,
          lastSeven: eligible.length >= 7 ? eligible.slice(0,7).reduce((s,x) => s + x.count,0) : null};
}
function elem(tag, css, value) {
  const e = document.createElement(tag);
  if (css) e.className = css;
  if (value !== undefined) e.textContent = String(value);
  return e;
}
function status(message) { document.getElementById("historyStatus").textContent = message; }
let mirror = null;
const PERIOD = {daily:"день",weekly:"неделю",monthly:"месяц"};
const LANG = {all:"Все языки",python:"Python",typescript:"TypeScript",javascript:"JavaScript",
              rust:"Rust",go:"Go",java:"Java",cpp:"C++"};
function updateLanguages() {
  const period = document.getElementById("trendPeriod").value;
  const select = document.getElementById("trendLanguage");
  const last = select.value;
  select.replaceChildren();
  for (const [key,label] of Object.entries(LANG)) {
    if (!Array.isArray(mirror?.lists?.[key+":"+period])) continue;
    const opt = elem("option","",label);
    opt.value = key; select.append(opt);
  }
  select.value = Array.from(select.options).some(x=>x.value===last)?last:"all";
}
function renderTrends() {
  if (!mirror) return;
  const period = document.getElementById("trendPeriod").value;
  const language = document.getElementById("trendLanguage").value;
  const records = mirror.lists[language+":"+period] || [];
  const container = document.getElementById("trendResults");
  container.replaceChildren();
  for (const row of records) {
    const name = repositoryName(row.name);
    if (!name) continue;
    const card = elem("article","project-card");
    card.append(elem("h3","",(row.rank||"–")+". "+name));
    card.append(elem("p","project-desc",row.description||"Описание отсутствует"));
    const tags = elem("div","project-meta");
    tags.append(elem("span","stars","+"+number.format(row.gained)+" ★ за "+PERIOD[period]));
    tags.append(elem("span","tag",number.format(row.stars)+" ★ всего"));
    if (row.language) tags.append(elem("span","tag",row.language));
    if (row.license_declared) tags.append(elem("span","tag",row.license_declared+" (заявлена)"));
    const links = elem("div","trend-actions");
    const dynamics = elem("a","subtle-link","История звёзд");
    dynamics.href = "./trends.html?repo="+encodeURIComponent(name)+"#history";
    const github = elem("a","subtle-link","GitHub");
    github.href = "https://github.com/"+name; github.target="_blank"; github.rel="noopener noreferrer";
    links.append(dynamics,github);
    card.append(tags,links);container.append(card);
  }
  document.getElementById("trendProvenance").textContent =
    "Данные GitHub Trending Today, CC BY 4.0; снято "+mirror.collected_at+
    ". Прирост и порядок рассчитаны источником по его методике, не OSS Radar.";
  if (!records.length) container.append(elem("p","muted","Нет данных для выбранного периода и языка."));
}
async function showTrends() {
  const state = document.getElementById("trendStatus");
  try {
    const response = await fetch("./data/external-trends.json", {cache:"no-store"});
    if (!response.ok) throw new Error("HTTP "+response.status);
    mirror = parseMirror(await response.json());
    const hours = (Date.now()-Date.parse(mirror.collected_at))/3600000;
    state.textContent = "Снимок источника: "+mirror.collected_at+
      (hours>30?" · данные устарели, проверь оригинал":" · данные провайдера, не наш рейтинг");
    document.getElementById("trendPeriod").disabled = false;
    document.getElementById("trendLanguage").disabled = false;
    updateLanguages();renderTrends();
  } catch (error) {
    state.textContent = "Не удалось загрузить публичную подборку ("+error.message+
      "). Откройте источник по ссылке ниже; устаревшие данные не выдаются за текущие.";
  }
}

function formatWeek(unix) {
  return new Intl.DateTimeFormat("ru-RU", {timeZone:"UTC", day:"2-digit",month:"short",year:"numeric"})
    .format(new Date(unix * 1000));
}
async function showHistory(name) {
  const repo = repositoryName(name);
  if (!repo) { status("Введите owner/repo или прямую ссылку на репозиторий GitHub."); return; }
  const input = document.getElementById("repoInput");
  input.value = repo;
  status("Читаю историю GitHub…");
  const output = document.getElementById("historyResults");
  output.replaceChildren();
  try {
    const url = "https://api.github.com/repos/" + repo.split("/").map(encodeURIComponent).join("/") +
      "/stargazers/history?per_page=30";
    const resp = await fetch(url, {headers: {
      "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION
    }});
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const history = parseHistory(await resp.json());
    if (!history.length) throw new Error("В GitHub ещё нет недель с данными");
    const bins = recentBins(history, Date.now());
    const summary = elem("div", "history-summary");
    summary.append(elem("p", "", "Завершённая дневная корзина: " +
      (bins.previousDay === null ? "нет данных" : "+" + number.format(bins.previousDay)) +
      " ★; последние 7 календарных корзин: " +
      (bins.lastSeven === null ? "нет данных" : "+" + number.format(bins.lastSeven)) + " ★."));
    summary.append(elem("p", "muted tiny",
      "Это количество добавленных звёзд по календарным корзинам GitHub, не строго последние 24/168 часов. " +
      "Время начала дня может отличаться от UTC; снятые звёзды не представлены как отрицательный прирост."));
    const list = elem("div", "history-weeks");
    const max = Math.max(...history.slice(0,12).map(x => x.total), 1);
    for (const week of history.slice(0,12)) {
      const row = elem("div", "week-row");
      row.append(elem("span", "", "Неделя " + formatWeek(week.week)));
      const meter = elem("meter");
      meter.min = 0; meter.max = max; meter.value = week.total;
      meter.setAttribute("aria-label", "Звёзд добавлено за неделю");
      row.append(meter, elem("strong", "stars", "+" + number.format(week.total)));
      list.append(row);
    }
    const open = elem("a", "subtle-link", "Открыть GitHub репозиторий");
    open.href = "https://github.com/" + repo; open.target="_blank"; open.rel="noopener noreferrer";
    output.append(summary, list, open);
    status("История " + repo + " · официальный GitHub API; до 12 последних недель из ответа.");
  } catch (e) {
    status("Не удалось получить историю (" + e.message + "). Возможны лимиты GitHub или ограничение доступа браузера.");
  }
}
function start() {
  document.getElementById("repoForm").addEventListener("submit", e => {
    e.preventDefault();
    const repo = document.getElementById("repoInput").value;
    history.replaceState(null,"","?repo="+encodeURIComponent(repo)+"#history");
    showHistory(repo);
  });
  const preset = new URLSearchParams(window.location.search).get("repo");
  if (preset) showHistory(preset);
  document.getElementById("trendPeriod").addEventListener("change",()=>{
    if (mirror) { updateLanguages();renderTrends(); }
  });
  document.getElementById("trendLanguage").addEventListener("change", renderTrends);
  showTrends();
}
if (typeof module !== "undefined" && module.exports)
  module.exports = {repositoryName, parseMirror, parseHistory, recentBins};
if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded",start);
