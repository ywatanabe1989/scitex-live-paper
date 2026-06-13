// PDFViewer — ported from scitex_writer/_django/frontend/src/pdf-viewer.ts.
// Same surface (load / render / clear / setZoom / setFitWidth /
// renderPlaceholder / zoomPercent) plus PR (c)'s text-layer +
// annotation-layer extensions. Writer can later import this class
// directly with zero API changes.

export class PDFViewer {
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
      // overlay share the same coordinate space.
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

    // PDF.js exposes TextLayer (5.x) or renderTextLayer() (4.x). Probe.
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
