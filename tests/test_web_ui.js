"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web/index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "web/app.js"), "utf8");

class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.hidden = false;
    this.open = false;
    this._text = "";
    this.className = "";
    this.classList = { toggle() {}, add() {}, remove() {} };
    this.listeners = {};
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(" "); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ""; this.children = children; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  scrollIntoView() { throw new Error("Restoring a report must not scroll the page."); }
}

function fixture(overrides = {}) {
  return {
    id: "test-job", filename: "words.txt", count: 4, phase: "Processo concluído",
    state: "completed", log: "Original process messages", downloads: [],
    summary: { added: "2", audio: "2", audio_total: "2", nothing_new: false,
      outcome: { available: true, imported: ["bathtub"],
        imported_ai: [{ word: "messed up", parts: ["pronunciation"] }],
        skipped: ["adamant"], failed: [{ word: "enlarged", reason: "Example too short" }], unconfirmed: [] } },
    ...overrides,
  };
}

function browser(storedJob = null) {
  const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map((match) => [match[1], new Element("div")]));
  const storage = new Map(storedJob ? [["anki-access", "test-key"], ["anki-job", storedJob.id]] : []);
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById(id) { assert.ok(elements.has(id), `Missing page element: ${id}`); return elements.get(id); },
      createElement(tag) { return new Element(tag); },
    },
    location: { hash: "", pathname: "/" }, history: { replaceState() {} },
    sessionStorage: { getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    URL, URLSearchParams, setInterval() {}, setTimeout() {}, clearTimeout() {},
    fetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET" });
      assert.equal(options.method || "GET", "GET", "Refreshing must never start an import.");
      return { ok: true, json: async () => url === "/api/status"
        ? { anki: true, audio: true, opencode: true, active: null } : storedJob };
    },
  });
  vm.runInContext(script, context);
  return { elements, requests, render(job) {
    context.testJob = job;
    vm.runInContext("renderJob(testJob)", context);
  } };
}

test("the page has an inline report and no modal markup or behavior", () => {
  assert.doesNotMatch(html, /<dialog\b|aria-haspopup="dialog"|show-import-result/);
  assert.doesNotMatch(script, /showModal|showImportResult|shownResults|window\.alert/);
  assert.match(html, /id="report-groups"/);
  assert.match(html, /<details id="log-details"[^>]*>/);
  assert.doesNotMatch(html, /<details id="log-details"[^>]*\bopen\b/);
});

test("completed imports render each outcome inline with accurate totals", () => {
  const page = browser();
  page.render(fixture());
  assert.equal(page.elements.get("result").hidden, false);
  const totals = page.elements.get("report-totals").children;
  assert.equal(totals[0].children[1].textContent, "2");
  assert.equal(totals[1].children[1].textContent, "1");
  assert.equal(totals[2].children[1].textContent, "1");
  const groups = page.elements.get("report-groups").textContent;
  for (const word of ["bathtub", "messed up", "adamant", "enlarged", "pronúncia", "Example too short"]) {
    assert.ok(groups.includes(word), `Missing result: ${word}`);
  }
  assert.match(page.elements.get("report-note").textContent, /não nos novos cartões/);
  assert.equal(page.elements.get("log-details").open, false);
});

test("F5 restores a completed report without a popup, scrolling or another import", async () => {
  const page = browser(fixture());
  await new Promise(setImmediate);
  assert.equal(page.elements.get("result").hidden, false);
  assert.match(page.elements.get("report-groups").textContent, /bathtub/);
  assert.equal(page.elements.get("log-details").open, false);
  assert.deepEqual(page.requests.map((request) => request.method), ["GET", "GET"]);
});

test("older results keep their known total without inventing per-word verification", async () => {
  const job = fixture({ summary: { added: "8", audio: "8", outcome: { available: false } } });
  const page = browser(job);
  await new Promise(setImmediate);
  const totals = page.elements.get("report-totals").children;
  assert.equal(totals[0].children[1].textContent, "8");
  assert.equal(totals[2].children[1].textContent, "—");
  assert.equal(page.elements.get("report-groups").children.length, 0);
  assert.match(page.elements.get("report-note").textContent, /não tem o resultado detalhado/);
});

test("failed results show unconfirmed words and keep technical messages collapsed", () => {
  const page = browser();
  const job = fixture({ state: "failed" });
  job.summary.added = null;
  job.summary.outcome.imported = [];
  job.summary.outcome.imported_ai = [];
  job.summary.outcome.unconfirmed = ["bathtub", "messed up"];
  page.render(job);
  assert.match(page.elements.get("report-description").textContent, /atenção/);
  assert.match(page.elements.get("report-groups").textContent, /Importação não confirmada/);
  assert.equal(page.elements.get("log-details").open, false);
});

test("a new running job hides the previous inline result", () => {
  const page = browser();
  page.render(fixture());
  page.render(fixture({ state: "running", summary: {} }));
  assert.equal(page.elements.get("result").hidden, true);
});

test("vocabulary is inserted as text, never interpreted as HTML", () => {
  const page = browser();
  const job = fixture();
  job.summary.outcome.imported = ["<img src=x onerror=alert(1)>"];
  page.render(job);
  const item = page.elements.get("report-groups").children[0].children[2].children[0];
  assert.equal(item.textContent, "<img src=x onerror=alert(1)>");
  assert.equal(item.children.length, 0);
});
