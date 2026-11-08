"use strict";
/* No collector or credentials: external open feed + GitHub's public star-history REST API. */
const FEED = "https://githubtrending.today/feed.json";
const INSIGHT = "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours&language=All";
const API_VERSION = "2026-03-10";
const NAME = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const number = new Intl.NumberFormat("ru-RU");

function repositoryName(candidate) {
  if (typeof candidate !== "string") return null;
  const value = candidate.trim();
  if (NAME.test(value)) return value;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;
    const parts = url.pathname.split("/").filter(Boolean);
    if (url.hostname === "githubtrending.today" && parts[0] === "repo") parts.shift();
    else if (url.hostname !== "github.com") return null;
    if (parts.length < 2) return null;
    const result = parts[0] + "/" + parts[1].replace(/\.git$/i, "");
    return NAME.test(result) ? result : null;
  } catch { return null; }
}
function toPlainText(input) {
  return typeof input === "string" ? input.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 230) : "";
}
function parseJsonFeed(json) {
  if (!json || !Array.isArray(json.items)) throw new Error("Источник вернул не JSON Feed");
  const seen = new Set();
  return json.items.map(item => {
    const repo = repositoryName(item.external_url) ||
      repositoryName(item.url) || repositoryName(item.title);
    if (!repo || seen.has(repo.toLowerCase())) return null;
    seen.add(repo.toLowerCase());
    return {repo, description: toPlainText(item.summary || item.title || ""),
      link: "https://github.com/" + repo};
  }).filter(Boolean).slice(0, 25);
}
function parseInsight(json) {
  const rows = json && json.data && json.data.rows;
  if (!Array.isArray(rows)) throw new Error("Неизвестный формат OSS Insight");
  const seen = new Set();
  return rows.map(row => {
    const repo = repositoryName(row.repo_name) || repositoryName(row.full_name) ||
      repositoryName(row.repo) || repositoryName(row.repo_url) || repositoryName(row.url);
    if (!repo || seen.has(repo.toLowerCase())) return null;
    seen.add(repo.toLowerCase());
    return {repo, description: toPlainText(row.description || ""),
      link: "https://github.com/" + repo};
  }).filter(Boolean).slice(0, 25);
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
function renderTrendList(records, origin) {
  const container = document.getElementById("trendResults");
  container.replaceChildren();
  for (const [index, row] of records.entries()) {
    const card = elem("article", "project-card");
    const heading = elem("h3", "", (index+1) + ". " + row.repo);
    const desc = elem("p", "project-desc", row.description || "Описание в исходном каталоге");
    const group = elem("div", "trend-actions");
    const see = elem("a", "subtle-link", "Динамика звёзд");
    see.href = "./trends.html?repo=" + encodeURIComponent(row.repo) + "#history";
    const source = elem("a", "subtle-link", "GitHub");
    source.href = row.link; source.target = "_blank"; source.rel = "noopener noreferrer";
    group.append(see, source);
    card.append(heading, desc, group);
    container.append(card);
  }
  document.getElementById("trendProvenance").textContent =
    "Источник: " + origin + ". Позиции отражают выдачу провайдера, не наш рейтинг.";
}
async function showTrends() {
  const state = document.getElementById("trendStatus");
  for (const source of [
    {url: FEED, parse: parseJsonFeed, label: "GitHub Trending Today (JSON Feed, CC BY 4.0)"},
    {url: INSIGHT, parse: parseInsight, label: "OSS Insight (public API)"}
  ]) {
    try {
      const response = await fetch(source.url, {headers: {"Accept": "application/json"}});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      const rows = source.parse(payload);
      if (!rows.length) throw new Error("Нет распознанных репозиториев");
      renderTrendList(rows, source.label);
      state.textContent = "Загружено " + rows.length + " проектов через открытый API; обновляется самим источником.";
      return;
    } catch (e) { /* Try second provider; no stale or invented data. */ }
  }
  state.textContent = "Открытые API недоступны из этого браузера или изменили формат. " +
    "Ниже есть прямые ссылки на источники — рейтинг не подменяется старыми данными.";
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
    status("История " + repo + " · официальный GitHub API; 12 последних недель из ответа.");
    history.replaceChildren;
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
  showTrends();
}
if (typeof module !== "undefined" && module.exports)
  module.exports = {repositoryName, parseJsonFeed, parseInsight, parseHistory, recentBins};
if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded",start);
