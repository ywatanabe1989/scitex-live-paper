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

      // Per-page wrapper so the canvas + text overlay + annotation
      // overlay share the same coordinate space. PDF.js's TextLayer
      // and AnnotationLayer position absolutely relative to this
      // wrapper.
      const pageWrap = document.createElement("div");
      pageWrap.className = "pdf-page";
      pageWrap.style.position = "relative";
      pageWrap.style.width = viewport.width + "px";
      pageWrap.style.height = viewport.height + "px";
      pageWrap.dataset.pageNumber = String(pageNum);

      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.className = "pdf-page-canvas";
      pageWrap.appendChild(canvas);

      this.container.appendChild(pageWrap);
      this.canvases.push(canvas);

      await page.render({ canvasContext: ctx, viewport }).promise;

      // PR (c): text-layer for native browser Ctrl-F + text selection.
      // page.getTextContent() returns positioned glyph runs; PDF.js's
      // TextLayer class paints invisible spans aligned with the canvas
      // so the browser's built-in find / select-and-copy work.
      try {
        await this._renderTextLayer(page, viewport, pageWrap);
      } catch (err) {
        console.warn("[pdf-viewer] text-layer page %d failed", pageNum, err);
      }

      // PR (c): annotation-layer for PDF-internal links + form fields.
      try {
        await this._renderAnnotationLayer(page, viewport, pageWrap);
      } catch (err) {
        console.warn("[pdf-viewer] annotation-layer page %d failed", pageNum, err);
      }
    }
  }

  async _renderTextLayer(page, viewport, pageWrap) {
    const textContent = await page.getTextContent();
    const textLayerDiv = document.createElement("div");
    textLayerDiv.className = "textLayer";
    textLayerDiv.style.position = "absolute";
    textLayerDiv.style.top = "0";
    textLayerDiv.style.left = "0";
    textLayerDiv.style.width = viewport.width + "px";
    textLayerDiv.style.height = viewport.height + "px";
    pageWrap.appendChild(textLayerDiv);

    // PDF.js exposes a TextLayer class in modern builds; older builds
    // expose a renderTextLayer() helper. Probe and call whichever is
    // available.
    if (typeof this.pdfjs.TextLayer === "function") {
      const layer = new this.pdfjs.TextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
      });
      await layer.render();
    } else if (typeof this.pdfjs.renderTextLayer === "function") {
      const task = this.pdfjs.renderTextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
      });
      await task.promise;
    } else {
      console.warn("[pdf-viewer] no TextLayer API in PDF.js — text selection/find disabled");
    }
  }

  async _renderAnnotationLayer(page, viewport, pageWrap) {
    const annotations = await page.getAnnotations();
    if (!annotations || annotations.length === 0) return;

    const annotationLayerDiv = document.createElement("div");
    annotationLayerDiv.className = "annotationLayer";
    annotationLayerDiv.style.position = "absolute";
    annotationLayerDiv.style.top = "0";
    annotationLayerDiv.style.left = "0";
    annotationLayerDiv.style.width = viewport.width + "px";
    annotationLayerDiv.style.height = viewport.height + "px";
    pageWrap.appendChild(annotationLayerDiv);

    if (typeof this.pdfjs.AnnotationLayer === "function") {
      const layer = new this.pdfjs.AnnotationLayer({
        div: annotationLayerDiv,
        page: page,
        viewport: viewport.clone({ dontFlip: true }),
      });
      layer.render({
        annotations: annotations,
        linkService: { externalLinkTarget: 2 /* BLANK */ },
        renderForms: false,
      });
    } else {
      console.warn("[pdf-viewer] no AnnotationLayer API in PDF.js — links/forms disabled");
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
