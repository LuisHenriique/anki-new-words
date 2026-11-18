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
function renderImportReport(job) {
  const summary = job.summary;
  const outcome = job.summary.outcome;
  const detailed = Boolean(outcome?.available);
  const confirmed = detailed ? outcome.imported.length + outcome.imported_ai.length : null;
  $("report-description").textContent = summary.nothing_new
    ? "Essas palavras já estão no Anki. Nenhum cartão novo foi criado."
    : job.state === "failed"
      ? "O lote precisa de atenção. Confira abaixo o que foi confirmado antes de tentar novamente."
      : "Processamento concluído. Confira o resultado das suas palavras abaixo.";
  $("report-totals").replaceChildren();
  const totals = [
    { label: "Adicionadas ao Anki", value: summary.added ?? confirmed ?? "—" },
    { label: "Já estavam no Anki", value: detailed ? outcome.skipped.length : "—" },
    { label: "Completadas pela IA", value: detailed ? outcome.imported_ai.length : "—" },
  ];
  for (const total of totals) {
    const item = document.createElement("div");
    const label = document.createElement("dt");
    label.textContent = total.label;
    const value = document.createElement("dd");
    value.textContent = total.value;
    item.append(label, value);
    $("report-totals").append(item);
  }
  $("report-groups").replaceChildren();
  if (detailed) {
    const groups = [
      { title: "Importadas com dados do dicionário", items: outcome.imported, kind: "imported",
        description: "Significado e pronúncia têm referência no dicionário. A frase e a tradução foram criadas pela IA." },
      { title: "Já estavam no Anki", items: outcome.skipped, kind: "skipped",
        description: "Não foram adicionadas de novo, para evitar repetições." },
      { title: "Importadas com ajuda da IA", items: outcome.imported_ai, kind: "ai",
        description: "Conferência incompleta no dicionário (unverified). A IA completou os dados indicados abaixo; revise esses cartões." },
      { title: "Não foram importadas", items: outcome.failed, kind: "failed",
        description: "Confira o motivo antes de tentar novamente." },
      { title: "Importação não confirmada", items: outcome.unconfirmed, kind: "failed",
        description: "O processo não confirmou o resultado destas palavras. Confira o Anki antes de repetir." },
    ];
    for (const group of groups) {
      if (!group.items.length && group.kind === "failed") continue;
      const section = document.createElement("section");
      section.className = `outcome-group ${group.kind}`;
      const heading = document.createElement("div");
      heading.className = "outcome-heading";
      const title = document.createElement("h3");
      title.textContent = group.title;
      const count = document.createElement("span");
      count.className = "outcome-count";
      count.textContent = group.items.length;
      heading.append(title, count);
      const description = document.createElement("p");
      description.textContent = group.items.length ? group.description : "Nenhuma palavra nesta situação.";
      const list = document.createElement("ul");
      for (const item of group.items) {
        const li = document.createElement("li");
        li.textContent = typeof item === "string" ? item : item.word;
        if (typeof item !== "string") {
          const detail = document.createElement("small");
          detail.textContent = item.reason || `Completado pela IA: ${item.parts.map((part) => part === "meaning" ? "significado" : "pronúncia").join(" e ")}.`;
          li.append(detail);
        }
        list.append(li);
      }
      section.append(heading, description);
      if (group.items.length) section.append(list);
      $("report-groups").append(section);
    }
  }
  $("report-note").textContent = detailed
    ? "A indicação unverified fica somente neste relatório, não nos novos cartões do Anki. Os cartões com ajuda da IA já estão incluídos no total de adicionadas."
    : "Este lote não tem o resultado detalhado por palavra. Consulte os detalhes técnicos abaixo; não é possível afirmar quais dados foram conferidos no dicionário.";
  if (summary.audio != null) $("report-note").textContent += ` Áudio gerado para ${summary.audio} frases.`;
  if (summary.audio != null && Number(summary.audio) < Number(summary.audio_total)) {
    $("report-note").textContent += " Algumas frases ficaram sem áudio. Para tentar depois, use no computador: python import_to_anki.py --audio-only";
  }
}

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
  $("job-title").textContent = busy ? job.phase : "Resultado da importação";
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
  $("result").hidden = busy;
  if (!busy) renderImportReport(job);
  const sources = job.summary.dictionary?.sources || [];
  $("dictionary-sources").hidden = sources.length === 0;
  $("source-links").replaceChildren();
  for (const source of sources) {
    let url;
    try { url = new URL(source.url); } catch { continue; }
    if (url.protocol !== "https:" || url.host !== "en.wiktionary.org" || !url.pathname.startsWith("/wiki/")) continue;
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = url.href;
    link.textContent = source.word;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    li.append(link);
    $("source-links").append(li);
  }
  $("downloads").replaceChildren();
  if (job.downloads.length) {
    const note = document.createElement("p");
    note.className = "download-note";
    note.textContent = "Caso queira, baixe os arquivos abaixo.";
    $("downloads").append(note);
  }
  for (const name of job.downloads) {
    const button = document.createElement("button");
    button.textContent = name === "uploaded_words.txt" ? "Baixar palavras pendentes" : `Baixar ${name}`;
    button.addEventListener("click", () => download(job.id, name));
    $("downloads").append(button);
  }
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
