const form = document.querySelector("#crawl-form");
const startButton = document.querySelector("#start-button");
const log = document.querySelector("#activity-log");
const state = document.querySelector("#run-state");
const metrics = {
  discovered: document.querySelector("#discovered"),
  visited: document.querySelector("#visited"),
  analyzed: document.querySelector("#analyzed"),
  elapsed: document.querySelector("#elapsed"),
};
let pollHandle = null;
let seenEvents = new Set();

function addLog(message, level = "info", timestamp = Date.now()) {
  const empty = log.querySelector(".empty-log");
  if (empty) empty.remove();
  const key = String(timestamp) + message;
  if (seenEvents.has(key)) return;
  seenEvents.add(key);
  const entry = document.createElement("p");
  entry.className = "log-entry";
  const time = document.createElement("time");
  time.textContent = new Date(timestamp).toLocaleTimeString("pt-BR");
  entry.append(time, document.createTextNode(message));
  if (level === "warning" || level === "error") entry.dataset.level = level;
  log.prepend(entry);
}

function setState(label, mode = "muted") {
  state.replaceChildren();
  const dot = document.createElement("span");
  dot.className = "status-dot" + (mode === "muted" ? " muted" : "");
  state.append(dot, document.createTextNode(" " + label));
}

function formatElapsed(seconds) {
  const total = Math.floor(seconds || 0);
  return String(Math.floor(total / 60)).padStart(2, "0") + ":" +
    String(total % 60).padStart(2, "0");
}

function renderSnapshot(data) {
  metrics.discovered.textContent = data.discovered;
  metrics.visited.textContent = data.visited;
  metrics.analyzed.textContent = data.analyzed;
  metrics.elapsed.textContent = formatElapsed(data.elapsed);
  (data.events || []).forEach(event => addLog(event.message, event.level, event.time * 1000));
  const labels = { queued: "Na fila", running: "Exploração em andamento", completed: "Concluída", failed: "Interrompida" };
  setState(labels[data.status] || data.status, data.status === "running" ? "live" : "muted");
  if (data.status === "completed" || data.status === "failed") {
    clearInterval(pollHandle);
    pollHandle = null;
    startButton.disabled = false;
    startButton.textContent = "Nova exploração →";
    if (data.status === "completed") {
      const link = document.createElement("a");
      link.href = `/api/crawls/${data.id}/export.csv`;
      link.textContent = "Baixar relatório CSV";
      link.className = "export-link";
      log.prepend(link);
    }
  }
}

async function pollJob(id) {
  try {
    const response = await fetch(`/api/crawls/${id}`);
    if (!response.ok) throw new Error("Não foi possível consultar a execução.");
    renderSnapshot(await response.json());
  } catch (error) {
    addLog(error.message, "error");
    clearInterval(pollHandle);
    pollHandle = null;
    startButton.disabled = false;
  }
}

async function checkApi() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("API indisponível");
    const data = await response.json();
    addLog(`Serviço conectado: ${data.service} v${data.version}.`);
  } catch {
    setState("API desconectada");
    addLog("Não foi possível conectar à API. Consulte o README para iniciar o serviço.");
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (pollHandle) clearInterval(pollHandle);
  seenEvents = new Set();
  log.replaceChildren();
  Object.values(metrics).forEach((element, index) => element.textContent = index === 3 ? "00:00" : "0");
  startButton.disabled = true;
  startButton.textContent = "Iniciando…";
  setState("Preparando exploração");
  const payload = {
    url: form.elements.url.value,
    max_pages: Number(form.elements.max_pages.value),
    max_depth: Number(form.elements.max_depth.value),
  };
  try {
    const response = await fetch("/api/crawls", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Não foi possível iniciar o crawler.");
    renderSnapshot(data);
    pollHandle = setInterval(() => pollJob(data.id), 1200);
    await pollJob(data.id);
  } catch (error) {
    addLog(error.message, "error");
    setState("Não foi possível iniciar");
    startButton.disabled = false;
    startButton.textContent = "Tentar novamente →";
  }
});

if (location.hostname.endsWith("github.io")) {
  startButton.disabled = true;
  startButton.textContent = "Backend não conectado";
  setState("Prévia estática — crawler offline");
  addLog("Interface publicada no GitHub Pages. O crawler Python ainda não está conectado nesta versão.");
  addLog("As métricas e a pesquisa em tempo real serão ativadas quando o backend for hospedado.");
} else {
  checkApi();
}
