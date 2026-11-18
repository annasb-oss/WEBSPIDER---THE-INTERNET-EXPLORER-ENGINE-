const themeToggle = document.querySelector("#theme-toggle");
const themeIcon = themeToggle?.querySelector(".theme-icon");
const themeLabel = themeToggle?.querySelector(".theme-label");
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const dark = theme === "dark";
  if (themeIcon) themeIcon.textContent = dark ? "☾" : "☼";
  if (themeLabel) themeLabel.textContent = dark ? "Tema escuro" : "Tema claro";
  if (themeToggle) themeToggle.setAttribute("aria-label", dark ? "Ativar tema claro" : "Ativar tema escuro");
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) metaTheme.content = dark ? "#17151c" : "#ffffff";
}
applyTheme(localStorage.getItem("webspider-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
themeToggle?.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next); localStorage.setItem("webspider-theme", next);
});

const apiInput = document.querySelector("#api-url");
const apiStatus = document.querySelector("#api-status");
const crawlForm = document.querySelector("#crawl-form");
const startButton = document.querySelector("#start-button");
const log = document.querySelector("#activity-log");
const state = document.querySelector("#run-state");
const claimForm = document.querySelector("#claim-form");
const claimButton = document.querySelector("#claim-button");
const claimResults = document.querySelector("#claim-results");
const saveApiButton = document.querySelector("#save-api-url");
const metrics = {
  discovered: document.querySelector("#discovered"),
  visited: document.querySelector("#visited"),
  analyzed: document.querySelector("#analyzed"),
  elapsed: document.querySelector("#elapsed"),
};
let pollHandle = null;
let seenEvents = new Set();
let apiBase = localStorage.getItem("webspider-api-url") || "";

function normalizeApiBase(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(url.hostname)) {
    throw new Error("Use uma URL HTTPS para conectar a API.");
  }
  return url.origin;
}
function updateApiControls(connected, message) {
  apiStatus.textContent = message;
  startButton.disabled = !connected;
  if (!connected) startButton.textContent = "API não conectada";
}
async function apiFetch(path, options = {}) {
  if (!apiBase) throw new Error("Conecte primeiro a API do WEBSPIDER.");
  return fetch(apiBase + path, { ...options, headers: { ...(options.headers || {}) } });
}
async function connectApi() {
  if (!apiBase) { updateApiControls(false, "A API ainda não foi conectada. Publique a API gratuita no Cloudflare Workers e informe a URL workers.dev aqui."); return; }
  try {
    const response = await apiFetch("/api/health");
    if (!response.ok) throw new Error("A API respondeu com erro.");
    const data = await response.json();
    updateApiControls(true, "Conectado: " + data.service + " · versão " + data.version);
    startButton.textContent = "Iniciar crawler →";
    addLog("API conectada e respondendo ao teste de saúde.");
  } catch (error) {
    updateApiControls(false, "Não foi possível conectar. Confira a URL e se o serviço está ativo.");
    addLog(error.message, "error");
  }
}
apiInput.value = apiBase;
saveApiButton.addEventListener("click", async () => {
  try {
    apiBase = normalizeApiBase(apiInput.value.trim());
    apiInput.value = apiBase;
    localStorage.setItem("webspider-api-url", apiBase);
    await connectApi();
  } catch (error) { updateApiControls(false, error.message); }
});

function addLog(message, level = "info", timestamp = Date.now()) {
  const empty = log.querySelector(".empty-log"); if (empty) empty.remove();
  const key = String(timestamp) + message; if (seenEvents.has(key)) return; seenEvents.add(key);
  const entry = document.createElement("p"); entry.className = "log-entry";
  const time = document.createElement("time"); time.textContent = new Date(timestamp).toLocaleTimeString("pt-BR");
  entry.append(time, document.createTextNode(message));
  if (level === "warning" || level === "error") entry.dataset.level = level;
  log.prepend(entry);
}
function setState(label, mode = "muted") {
  state.replaceChildren(); const dot = document.createElement("span");
  dot.className = "status-dot" + (mode === "muted" ? " muted" : "");
  state.append(dot, document.createTextNode(" " + label));
}
function formatElapsed(seconds) {
  const total = Math.floor(seconds || 0);
  return String(Math.floor(total / 60)).padStart(2, "0") + ":" + String(total % 60).padStart(2, "0");
}
function renderSnapshot(data) {
  metrics.discovered.textContent = data.discovered; metrics.visited.textContent = data.visited;
  metrics.analyzed.textContent = data.analyzed; metrics.elapsed.textContent = formatElapsed(data.elapsed);
  (data.events || []).forEach(event => addLog(event.message, event.level, event.time * 1000));
  const labels = { queued: "Na fila", running: "Exploração em andamento", completed: "Concluída", failed: "Interrompida" };
  setState(labels[data.status] || data.status, data.status === "running" ? "live" : "muted");
  if (data.status === "completed" || data.status === "failed") {
    clearInterval(pollHandle); pollHandle = null; startButton.disabled = false;
    startButton.textContent = "Nova exploração →";
    if (data.status === "completed") {
      const audit = document.createElement("button"); audit.type = "button"; audit.className = "audit-button";
      audit.textContent = "Verificar configurações de segurança"; audit.addEventListener("click", () => loadAudit(data.id));
      log.prepend(audit);
      const link = document.createElement("a"); link.href = apiBase + "/api/crawls/" + data.id + "/export.csv";
      link.textContent = "Baixar relatório CSV"; link.className = "export-link"; link.target = "_blank"; link.rel = "noopener noreferrer";
      log.prepend(link);
    }
  }
}
async function pollJob(id) {
  try {
    const response = await apiFetch("/api/crawls/" + id);
    if (!response.ok) throw new Error("Não foi possível consultar a execução.");
    renderSnapshot(await response.json());
  } catch (error) {
    addLog(error.message, "error"); clearInterval(pollHandle); pollHandle = null; startButton.disabled = false;
  }
}
async function loadAudit(id) {
  try {
    const response = await apiFetch("/api/crawls/" + id + "/audit");
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Falha na auditoria.");
    const panel = document.createElement("div"); panel.className = "audit-results";
    const heading = document.createElement("h3"); heading.textContent = "Achados observados: " + data.findings_count;
    panel.append(heading);
    if (!data.findings.length) { const p = document.createElement("p"); p.textContent = "Nenhum dos indicadores verificados foi encontrado. Isso não garante que o site esteja livre de vulnerabilidades."; panel.append(p); }
    data.findings.forEach(item => {
      const row = document.createElement("article"); row.className = "finding " + item.severity;
      const title = document.createElement("strong"); title.textContent = item.title + " · " + item.severity.toUpperCase();
      const detail = document.createElement("p"); detail.textContent = item.detail;
      const url = document.createElement("small"); url.textContent = item.url;
      row.append(title, detail, url); panel.append(row);
    });
    const note = document.createElement("p"); note.className = "install-note"; note.textContent = data.scope; panel.append(note);
    log.prepend(panel);
  } catch (error) { addLog(error.message, "error"); }
}
crawlForm.addEventListener("submit", async event => {
  event.preventDefault(); if (pollHandle) clearInterval(pollHandle);
  seenEvents = new Set(); log.replaceChildren();
  Object.values(metrics).forEach((element, index) => element.textContent = index === 3 ? "00:00" : "0");
  startButton.disabled = true; startButton.textContent = "Iniciando…"; setState("Preparando exploração");
  const payload = { url: crawlForm.elements.url.value, max_pages: Number(crawlForm.elements.max_pages.value), max_depth: Number(crawlForm.elements.max_depth.value) };
  try {
    const response = await apiFetch("/api/crawls", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Não foi possível iniciar o crawler.");
    renderSnapshot(data);
    if (data.findings) {
      const panel = document.createElement("div"); panel.className = "audit-results";
      const heading = document.createElement("h3"); heading.textContent = "Achados observados: " + data.findings_count; panel.append(heading);
      if (!data.findings.length) { const p = document.createElement("p"); p.textContent = "Nenhum indicador verificado foi encontrado. Isso não garante que o site esteja livre de vulnerabilidades."; panel.append(p); }
      data.findings.forEach(item => { const row=document.createElement("article");row.className="finding "+item.severity;const title=document.createElement("strong");title.textContent=item.title+" · "+item.severity.toUpperCase();const detail=document.createElement("p");detail.textContent=item.detail;row.append(title,detail);panel.append(row); });
      const note=document.createElement("p");note.className="install-note";note.textContent=data.scope;panel.append(note);log.prepend(panel);
      startButton.disabled=false;startButton.textContent="Nova análise →";
    } else { addLog("A API não retornou os achados esperados.","error");startButton.disabled=false; }
  } catch (error) { addLog(error.message, "error"); setState("Não foi possível iniciar"); startButton.disabled = false; startButton.textContent = "Tentar novamente →"; }
});
claimForm.addEventListener("submit", async event => {
  event.preventDefault(); claimButton.disabled = true; claimButton.textContent = "Consultando…";
  claimResults.replaceChildren();
  try {
    const response = await apiFetch("/api/claims/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ claim: claimForm.elements.claim.value.trim() }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Falha na consulta.");
    const heading = document.createElement("h3"); heading.textContent = data.verdict; claimResults.append(heading);
    const message = document.createElement("p"); message.textContent = data.message; claimResults.append(message);
    if (data.reviews.length) data.reviews.forEach(review => {
      const card = document.createElement("article"); card.className = "finding";
      const title = document.createElement("strong"); title.textContent = review.title || review.claim || "Checagem publicada";
      const rating = document.createElement("p"); rating.textContent = "Avaliação: " + (review.rating || "não informada");
      const publisher = document.createElement("p"); publisher.textContent = "Publicador: " + (review.publisher || "não informado") + (review.review_date ? " · " + review.review_date : "");
      card.append(title, rating, publisher);
      if (review.url) { const link = document.createElement("a"); link.href = review.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Ler checagem original ↗"; card.append(link); }
      claimResults.append(card);
    });
    const explorer = document.createElement("a"); explorer.href = data.explorer_url; explorer.target = "_blank"; explorer.rel = "noopener noreferrer"; explorer.textContent = "Abrir Google Fact Check Explorer ↗"; claimResults.append(explorer);
  } catch (error) {
    const p = document.createElement("p"); p.textContent = error.message; claimResults.append(p);
  } finally { claimButton.disabled = false; claimButton.textContent = "Consultar checagens →"; }
});
if (apiBase) connectApi(); else updateApiControls(false, "A interface está no GitHub Pages. Conecte a API hospedada para ativar o crawler e as verificações em tempo real.");
