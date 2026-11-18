const form = document.querySelector("#crawl-form");
const startButton = document.querySelector("#start-button");
const log = document.querySelector("#activity-log");
const state = document.querySelector("#run-state");

function addLog(message) {
  const empty = log.querySelector(".empty-log");
  if (empty) empty.remove();
  const entry = document.createElement("p");
  entry.className = "log-entry";
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString("pt-BR");
  entry.append(time, document.createTextNode(message));
  log.prepend(entry);
}

async function checkApi() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("API indisponível");
    const data = await response.json();
    addLog(`Serviço conectado: ${data.service} v${data.version}.`);
  } catch {
    state.innerHTML = '<span class="status-dot muted"></span> API desconectada';
    addLog("Não foi possível conectar à API. Inicie o servidor local.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  addLog("A configuração foi recebida pela interface.");
  addLog("O mecanismo de rastreamento será conectado na próxima etapa.");
  state.innerHTML = '<span class="status-dot muted"></span> Preparação pendente';
  startButton.disabled = true;
  startButton.textContent = "Em desenvolvimento";
  window.setTimeout(() => {
    startButton.disabled = false;
    startButton.innerHTML = 'Iniciar crawler <span>→</span>';
  }, 1800);
});

checkApi();
