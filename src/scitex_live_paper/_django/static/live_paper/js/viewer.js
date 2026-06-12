// Live-paper SPA viewer — ported from scitex_writer's pdf-viewer.ts.
// Reads `data-api-base` from #live-paper-root + boots: ping → bundle-info
// → fetches `manuscript.pdf` via the new `api/pdf` endpoint and renders
// every page into a scrollable canvas column with fit-width + zoom.
//
// Vanilla ES module (no Vite / TypeScript build needed) — the writer
// viewer is built with Vite + TS; this file mirrors the same shape +
// surface so writer can later swap to consume this code directly.
//
// PDF.js is loaded from the vendored copy at
// `/static/live_paper/pdfjs/pdf.min.mjs`; the URL is resolved
// relative to `data-api-base` so it works under both standalone
// (root mount) and hub-mounted (`/apps/live-paper/<id>/`) deployments.

const PDFJS_REL = "../pdfjs/pdf.min.mjs"; // relative to data-api-base
const PDFJS_WORKER_REL = "../pdfjs/pdf.worker.min.mjs";

const root = document.getElementById("live-paper-root");
if (!root) {
  console.error("[live-paper] root element missing");
} else {
  boot(root);
}

async function boot(rootEl) {
  const apiBase = normalizeBase(rootEl.getAttribute("data-api-base") || "/api/");
  const pdfjsUrl = new URL(PDFJS_REL, document.baseURI + apiBase).href;
  const workerUrl = new URL(PDFJS_WORKER_REL, document.baseURI + apiBase).href;

  let pdfjs;
  try {
    pdfjs = await import(pdfjsUrl);
    pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  } catch (err) {
    console.error("[live-paper] PDF.js failed to load", err);
    renderError("PDF.js bundle not available at " + pdfjsUrl);
    return;
  }

  // Boot calls — bundle-info populates the JSON pre block.
  try {
    const ping = await fetchJson(apiBase + "ping");
    if (!ping || ping.ok !== true) {
      throw new Error("ping returned non-ok: " + JSON.stringify(ping));
    }
    const info = await fetchJson(apiBase + "bundle-info");
    setStatus(info);
  } catch (err) {
    console.error("[live-paper] boot RPCs failed", err);
    setStatus({ error: String(err) });
  }

  const pdfContainer = ensurePdfContainer(rootEl);
  const viewer = new PDFViewer({
    container: pdfContainer,
    pdfjs: pdfjs,
    apiBase: apiBase,
  });
  await viewer.load();
}

// ──────────────────────────────────────────────────────────────────
// PDFViewer — ported from scitex_writer/_django/frontend/src/pdf-viewer.ts.
// Same surface (load / render / clear / setZoom / setFitWidth /
// renderPlaceholder / zoomPercent) so writer can later import this
// class directly with zero changes.
// ──────────────────────────────────────────────────────────────────

class PDFViewer {
  constructor(options) {
    this.container = options.container;
    this.pdfjs = options.pdfjs;
    this.apiBase = options.apiBase;
    this.pdfDoc = null;
    this.scale = 1.0;
    this.fitMode = "width";
    this.canvases = [];
    this.container.classList.add("pdf-viewer-host");
  }

  async load(docType) {
    docType = docType || "manuscript";
    const url =
      this.apiBase +
      "pdf?doc_type=" +
      encodeURIComponent(docType) +
      "&t=" +
      Date.now();
    try {
      const task = this.pdfjs.getDocument({ url });
      this.pdfDoc = await task.promise;
      await this.render();
      return true;
    } catch (err) {
      console.warn("[pdf-viewer] load failed:", err);
      this.renderPlaceholder("No PDF available.");
      return false;
    }
  }

  clear() {
    this.pdfDoc = null;
    this.canvases = [];
    this.container.innerHTML = "";
  }

  renderPlaceholder(message) {
    this.clear();
    const placeholder = document.createElement("div");
    placeholder.className = "pdf-placeholder";
    placeholder.innerHTML =
      "<p>" + (message || "No PDF available.") + "</p>" +
      "<p class=\"hint\">The bundle's manuscript.pdf could not be loaded.</p>";
    this.container.appendChild(placeholder);
  }

  async render() {
    if (!this.pdfDoc) return;
    this.container.innerHTML = "";
    this.canvases = [];
    const renderScale =
      this.fitMode === "width" ? this.computeFitWidthScale() : this.scale;

    for (let pageNum = 1; pageNum <= this.pdfDoc.numPages; pageNum++) {
      const page = await this.pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: renderScale });
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.className = "pdf-page-canvas";
      this.container.appendChild(canvas);
      this.canvases.push(canvas);
      await page.render({ canvasContext: ctx, viewport }).promise;
    }
  }

  computeFitWidthScale() {
    if (!this.pdfDoc) return 1;
    const width = this.container.clientWidth - 32; // padding
    return Math.max(0.4, width / 800); // 800px baseline (same as writer)
  }

  setZoom(delta) {
    this.fitMode = "none";
    this.scale = Math.max(0.4, Math.min(3, this.scale + delta));
    void this.render();
  }

  setFitWidth() {
    this.fitMode = "width";
    this.scale = 1;
    void this.render();
  }

  get zoomPercent() {
    const effective =
      this.fitMode === "width" ? this.computeFitWidthScale() : this.scale;
    return Math.round(effective * 100);
  }
}

window.LivePaperPDFViewer = PDFViewer;

// ──────────────────────────────────────────────────────────────────
// helpers
// ──────────────────────────────────────────────────────────────────

function normalizeBase(base) {
  if (!base.endsWith("/")) base += "/";
  return base;
}

async function fetchJson(url) {
  const res = await fetch(url);
  return res.json();
}

function setStatus(payload) {
  const pre = document.getElementById("live-paper-bundle-info");
  if (pre) {
    pre.textContent = JSON.stringify(payload, null, 2);
  }
}

function ensurePdfContainer(rootEl) {
  let host = document.getElementById("live-paper-pdf");
  if (!host) {
    host = document.createElement("div");
    host.id = "live-paper-pdf";
    host.className = "live-paper-pdf";
    rootEl.appendChild(host);
  }
  return host;
}

function renderError(message) {
  const container = document.getElementById("live-paper-bundle-info");
  if (container) {
    container.textContent = JSON.stringify({ error: message }, null, 2);
  }
}
