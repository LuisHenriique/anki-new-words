"use strict";

const $ = (id) => document.getElementById(id);
const key = new URLSearchParams(location.hash.slice(1)).get("key");
if (key) {
  sessionStorage.setItem("anki-access", key);
  history.replaceState(null, "", location.pathname);
}
const token = key || sessionStorage.getItem("anki-access");
let upload = null;
let busy = false;
let reading = false;
let timer = null;
let currentJob = null;

function message(text) {
  $("message").textContent = text || "";
  $("message").hidden = !text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.error || "Não foi possível concluir a solicitação.");
  }
  return response;
}

function updateButton() {
  $("import").disabled = !upload || busy || reading || !token;
  $("import").textContent = busy ? "Importação em andamento…" : "Gerar e adicionar ao Anki";
  $("file").disabled = busy || reading;
}

async function selectFile(file) {
  if (!file || busy || reading) return;
  message("");
  upload = null;
  reading = true;
  updateButton();
  try {
    if (file.size > 1000000) throw new Error("O arquivo deve ter no máximo 1 MB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let start = 0; start < bytes.length; start += 8192) {
      binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
    }
    const payload = { filename: file.name, data: btoa(binary) };
    const preview = await (await api("/api/preview", { method: "POST", body: JSON.stringify(payload) })).json();
    upload = payload;
    $("file-label").textContent = preview.filename;
    $("count").textContent = `${preview.count} ${preview.count === 1 ? "palavra" : "palavras"}`;
    $("empty").hidden = true;
    $("words").hidden = false;
    $("preview-note").hidden = false;
    $("preview-note").textContent = preview.repeated
      ? `${preview.repeated} repetições no arquivo serão ignoradas. As duplicadas no Anki serão verificadas ao processar.`
      : "As palavras que já estão no Anki serão verificadas ao processar.";
    $("words").replaceChildren();
    for (const item of preview.items) {
      const li = document.createElement("li");
      const word = document.createElement("strong");
      word.textContent = item.word;
      li.append(word);
      if (item.context) {
        const context = document.createElement("p");
        context.textContent = item.context;
        li.append(context);
      }
      $("words").append(li);
    }
  } catch (error) {
    $("file-label").textContent = "Escolha seu arquivo .txt";
    $("count").textContent = "0 palavras";
    $("words").hidden = true;
    $("preview-note").hidden = true;
    $("empty").hidden = false;
    message(error.message);
  } finally {
    reading = false;
    updateButton();
  }
}

async function download(jobId, filename) {
  try {
    const response = await api(`/api/jobs/${jobId}/files/${filename}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename === "uploaded_words.txt" ? "palavras_pendentes.txt" : filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) { message(error.message); }
}

function renderJob(job) {
  busy = job.state === "running";
  $("job").hidden = false;
  $("job-title").textContent = job.phase;
  $("job-subtitle").textContent = `${job.filename} · ${job.count} palavras`;
  $("job-state").textContent = busy ? "Em andamento" : job.state === "completed" ? "Concluído" : "Atenção";
  $("job-state").className = `job-state ${busy ? "" : job.state === "completed" ? "done" : "failed"}`;
  $("progress").hidden = !busy;
  $("log").textContent = job.log;
  $("job-hint").textContent = busy
    ? "Aguarde o lote terminar antes de encerrar o servidor no computador."
    : job.state === "completed"
      ? "Confira o relatório. Você pode baixar as palavras que ficaram pendentes."
      : "Confira o erro no relatório. O arquivo original está preservado. Se houve importação parcial, não repita sem conferir o Anki.";
  $("result").hidden = busy || job.state !== "completed";
  $("result").replaceChildren();
  if (!busy && job.state === "completed") {
    const summary = job.summary;
    const lines = summary.nothing_new ? ["Todas as palavras já estão no Anki. Nenhum cartão novo foi criado."] : [
      `${summary.added ?? "Confira o relatório para saber quantos"} cartões adicionados.`,
      `Com áudio: ${summary.audio ?? "consulte o relatório"}.`,
      ...(summary.tag ? [`Lote: ${summary.tag}`] : []),
      ...(summary.audio !== null && Number(summary.audio) < Number(summary.audio_total)
        ? ["Alguns cartões ficaram sem áudio. Para tentar depois, use no computador: python import_to_anki.py --audio-only"] : []),
      "Cartões escritos pela IA de memória, sem consulta a dicionários.",
      "Confira possíveis recusas e avisos no relatório completo.",
    ];
    for (const line of lines) {
      const p = document.createElement("p");
      p.textContent = line;
      $("result").append(p);
    }
  }
  $("downloads").replaceChildren();
  for (const name of job.downloads) {
    const button = document.createElement("button");
    button.textContent = name === "uploaded_words.txt" ? "Baixar palavras pendentes" : `Baixar ${name}`;
    button.addEventListener("click", () => download(job.id, name));
    $("downloads").append(button);
  }
  if (!busy && job.state === "failed") $("log-details").open = true;
  updateButton();
}

async function poll(jobId) {
  clearTimeout(timer);
  try {
    const job = await (await api(`/api/jobs/${jobId}`)).json();
    if (currentJob !== jobId) return;
    renderJob(job);
    if (job.state === "running") timer = setTimeout(() => poll(jobId), 1500);
  } catch (error) {
    message(`${error.message} Tentando reconectar; o processamento continua no computador.`);
    timer = setTimeout(() => poll(jobId), 5000);
  }
}

$("file").addEventListener("change", (event) => selectFile(event.target.files[0]));
for (const name of ["dragenter", "dragover"]) {
  $("dropzone").addEventListener(name, (event) => {
    event.preventDefault();
    if (!busy) $("dropzone").classList.add("dragging");
  });
}
for (const name of ["dragleave", "drop"]) {
  $("dropzone").addEventListener(name, (event) => {
    event.preventDefault();
    $("dropzone").classList.remove("dragging");
    if (name === "drop") selectFile(event.dataTransfer.files[0]);
  });
}
$("import").addEventListener("click", async () => {
  if (!upload || busy) return;
  message("");
  busy = true;
  updateButton();
  try {
    const job = await (await api("/api/jobs", { method: "POST", body: JSON.stringify(upload) })).json();
    currentJob = job.id;
    sessionStorage.setItem("anki-job", job.id);
    $("log-details").open = false;
    await poll(job.id);
    $("job").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
  } catch (error) {
    busy = false;
    updateButton();
    message(error.message);
  }
});

async function status() {
  try {
    const result = await (await api("/api/status")).json();
    $("connection").textContent = result.anki ? "Anki conectado" : "Abra o Anki no computador";
    $("connection").classList.toggle("ready", result.anki);
    if (!result.audio) message("Para gerar áudio, instale no computador: python -m pip install gTTS");
    else if (!result.opencode) message("O comando opencode não foi encontrado no computador. Verifique a instalação antes de importar.");
    if (result.active && currentJob !== result.active) {
      currentJob = result.active;
      sessionStorage.setItem("anki-job", currentJob);
      busy = true;
      updateButton();
      poll(currentJob);
    }
  } catch (error) {
    $("connection").textContent = "Sem conexão com o servidor";
    $("connection").classList.remove("ready");
    message(error.message);
  }
}

if (!token) {
  $("access").hidden = false;
  $("connection").textContent = "Acesso protegido";
  $("file").disabled = true;
} else {
  status();
  currentJob = sessionStorage.getItem("anki-job");
  if (currentJob) {
    busy = true;
    updateButton();
    api(`/api/jobs/${currentJob}`).then((response) => response.json()).then((job) => {
      if (currentJob !== job.id) return;
      renderJob(job);
      if (job.state === "running") poll(job.id);
    }).catch(() => {
      currentJob = null;
      sessionStorage.removeItem("anki-job");
      busy = false;
      updateButton();
    });
  }
  setInterval(status, 15000);
}
