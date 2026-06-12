# scitex-writer PDF viewer — dogfood investigation

**Filed:** 2026-06-13
**By:** proj-scitex-live-paper
**Driver:** operator directive 2026-06-13 — make scitex-live-paper the SINGLE reusable PDF / live-paper viewer; dogfood the proven scitex-writer viewer that currently runs on scitex.ai.

This document is the discovery output for the migration tickets filed under
`.scitex/todo/tasks.yaml` (`live-paper-absorb-writer-pdf-viewer-*`).

---

## 1. Where the working viewer lives

```
~/proj/scitex-writer/src/scitex_writer/_django/
├── frontend/                       ← Vite + TypeScript source
│   ├── package.json, vite.config.ts, tsconfig.json
│   ├── src/
│   │   ├── pdf-viewer.ts           ← THE actual PDF.js renderer (112 lines)
│   │   ├── pdf-theme.ts            ← Light/dark theme controller
│   │   ├── viewer.ts               ← Viewer page bootstrap
│   │   ├── index.ts                ← Editor entry (not viewer-relevant)
│   │   ├── claims-list.ts, claims-tab.ts, citations-panel.ts,
│   │   ├── cite-completion.ts, details-panel.ts, insert-panel.ts,
│   │   ├── compile.ts, sections.ts, toolbar.ts
│   │   └── api.ts                  ← `API_BASE` + `PROJECT_DIR` consts
│   └── node_modules/               ← built locally, NOT pip-installed
├── static/writer/assets/           ← Vite build output (shipped in package)
│   ├── pdf-viewer.js, pdf-viewer.js.map
│   ├── index.js, claims-list.js (+ .map files)
│   ├── viewer.js (and editor.js)
│   └── ... css + favicons
├── templates/writer/viewer.html    ← Django template, extends scitex_ui shell
├── handlers/
│   ├── compile.py                  ← `handle_pdf` serves PDF bytes
│   ├── viewer.py                   ← claims-metadata / DAG / citation sidecar
│   └── core.py, files.py, media.py, claim.py, bib.py, scholar.py
└── urls.py, views.py, services.py, settings.py, apps.py, manifest.json
```

**"Hardcoded / built-in" the operator referenced** = the Vite-built JS+CSS
bundle ships **inside the package's `static/writer/assets/`**. Not installed
via an npm dependency. Live-paper would absorb either the TypeScript source
(rebuild locally) or copy the built artefacts (faster but loses theme/feature
ownership).

## 2. How it renders

### Backend: `compile.py:handle_pdf`

```python
def handle_pdf(request, project):
    doc_type = request.GET.get("doc_type", "manuscript")
    pdf_map = {
        "manuscript":    "01_manuscript/manuscript.pdf",
        "supplementary": "02_supplementary/supplementary.pdf",
        "revision":      "03_revision/revision.pdf",
    }
    rel_path = pdf_map.get(doc_type)
    pdf_path = project.project_dir / rel_path
    return FileResponse(open(pdf_path, "rb"), content_type="application/pdf",
                        filename=f"{doc_type}.pdf",
                        as_attachment=request.GET.get("download") in ("1","true"))
```

- One URL: `GET /api/pdf?doc_type=manuscript|supplementary|revision[&download=1]`
- Resolves to a hard-coded relative path under the project directory
- Returns `FileResponse` of raw PDF bytes
- Optional `?download=1` flips to attachment disposition

### Frontend: `pdf-viewer.ts`

- Module: `pdfjs-dist` (PDF.js, the Mozilla canonical implementation)
- Worker shim: `import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";`
  then `pdfjs.GlobalWorkerOptions.workerSrc = PdfWorker;`
- Class: `PDFViewer { container, pdfDoc, scale, fitMode, canvases[] }`
- Surfaces:
  - `load(docType)` — fetches `${API_BASE}api/pdf?doc_type=${docType}&working_dir=${PROJECT_DIR}&t=${Date.now()}`,
    feeds the URL to `pdfjs.getDocument({url})`, calls `render()` on success.
  - `render()` — iterates pages 1..N, creates a `<canvas>` per page, calls
    `page.render({canvasContext, viewport})`. Pages stack in a scrollable column.
  - `setZoom(delta)` — clamps to [0.4, 3.0], switches `fitMode` to "none".
  - `setFitWidth()` — switches `fitMode` to "width", recomputes scale on render.
  - `renderPlaceholder(message)` — friendly fallback when no PDF compiled.
  - `clear()`, `zoomPercent` getter.
- Cache buster: appends `&t=${Date.now()}` so re-compile is picked up without
  browser cache fuss.

### Template: `templates/writer/viewer.html`

- `{% extends "scitex_ui/standalone_shell.html" %}` — shared scitex-ui chrome
- Root: `<div class="writer-app writer-app--viewer" data-api-base="..."
  data-project-dir="..." data-mode="viewer">`
- Toolbar: doc-type `<select>` (manuscript / supplementary / revision),
  claims badge, "Edit" button back to editor mode.
- Layout: split pane — left `viewer-claims-pane` (claims sidebar), right
  `viewer-pdf-pane` with tabs (PDF + others).
- Popup: claim details + DAG render container.

### Viewer bootstrap: `viewer.ts`

- Reads `.writer-app--viewer` root
- Initializes mermaid with `{startOnLoad: false, theme: "dark"}` (DAG render)
- Wires `#doc-type-select` `change` → `pdf.load(docType)`
- Wires `#btn-pdf-zoom-in` / `#btn-pdf-zoom-out` / `#btn-pdf-fit-width` controls
- Loads claims via `loadClaims()` (from `claims-list.ts`)
- Click-claim → popup with details + per-claim DAG

## 3. What makes it work well

1. **PDF.js is the right primitive.** Pure-canvas page rendering is fast,
   zoom-tolerant, and doesn't require a backend renderer (LaTeX → PNG pipelines
   would be much slower / heavier).
2. **Per-page canvas in a scrollable column** scales to long manuscripts
   without virtual-scroll complexity. Good UX trade-off.
3. **Fit-width default** — solves the most common operator complaint (PDF
   too small/big inside a panel) without configuration.
4. **`?t=${Date.now()}` cache buster** — recompile flows work without a hard
   refresh.
5. **Worker shim via Vite `?url` import** — clean, no global script tag, no
   CDN.
6. **Split-pane + claims sidebar** is exactly the live-paper UX target.
7. **doc-type select** lets the operator browse manuscript / supplementary /
   revision from the same viewer — applicable to live-paper if we generalize
   beyond `manuscript.pdf`.

## 4. What it explicitly LACKS

From `pdf-viewer.ts`'s own docstring:

> Minimal: no text-layer, no annotation-layer, no find. PR5/6 can add them.

- **No text-layer** — text selection / copy doesn't work; everything is
  pixel-painted onto canvas.
- **No annotation-layer** — PDF.js's interactive annotation support (link
  follow, form fields, highlight comments) is not wired in.
- **No find / search** — Ctrl-F is dead.

These are the next-tier features live-paper should add **after** the port,
since the writer team intentionally deferred them.

## 5. Gap vs live-paper's current viewer

| Aspect              | scitex-writer viewer                              | scitex-live-paper viewer (today)                   |
|---------------------|---------------------------------------------------|----------------------------------------------------|
| PDF render          | PDF.js + canvas-per-page, real `class PDFViewer` | Vendored PDF.js assets + stub HTML; no JS class    |
| Backend PDF route   | `GET /api/pdf?doc_type=...` → `FileResponse`     | Static site copies `manuscript.pdf` next to HTML   |
| Zoom / fit-width    | Yes                                               | No                                                 |
| Per-page canvas col | Yes                                               | No                                                 |
| Claims sidebar      | `claims-list.ts` + `loadClaims()` + popup details | Static-site `claims.html` (separate page)          |
| DAG popup           | mermaid `theme: dark` + render-on-click          | Static-site `dag.html` (separate page)             |
| Frontend build      | Vite + TypeScript                                 | None (vanilla static HTML)                         |
| Theme               | `pdf-theme.ts` light/dark controller             | Vendored `viewer.css` only (auto/light/dark hinted) |
| Text-layer / find   | NOT present (deferred)                            | NOT present                                        |

**Net:** live-paper has the *boundaries* right (renderer separation, no claim
schema invention, BundleContext for multi-tenant) but lacks the **actual
working PDF rendering implementation**. The writer code is a near-drop-in
template for the missing piece.

## 6. Deployment trail to scitex.ai

(Tentative — needs confirmation from proj-scitex-hub when they're off the
rate-limit cooldown.)

- scitex-writer's `_django` app is registered as a scitex-hub plugin app
  (`apps/workspace/writer_app/` analog of the agentic_journal_app /
  live_paper_app wrapper hub is building).
- Hub serves `static/writer/assets/*.js` directly via Django's
  `staticfiles` (AppDirectoriesFinder discovers `_django/static/writer/`).
- scitex.ai is the production scitex-hub deployment; same wiring just under
  TLS + auth.
- The operator's "running well on scitex.ai" = the hub-mounted writer viewer,
  not a separate deployment.

## 7. Migration approach (proposed)

**Phase A — port (tickets b + c below):** copy `frontend/src/pdf-viewer.ts`
and `pdf-theme.ts` into `live-paper/_django/frontend/src/`, adapt `api.ts`
constants to live-paper's `BundleContext.api_base` (PR #27 surface).
Build with Vite, ship the bundle under `_django/static/live_paper/assets/`.
Wire `viewer_page` to include the new bundle.

**Phase B — backend PDF route:** add `handle_pdf` to live-paper's HANDLERS
(`api/pdf`), serving the bundle's `manuscript.pdf` via `FileResponse`.
Generalize the `doc_type` map for the bundle layout (live-paper currently
ships only `manuscript.pdf`; supplementary / revision come later).

**Phase C — features writer deferred (text-layer / annotations / find):**
add them in live-paper FIRST (since live-paper is the canonical viewer
now), so when writer/scholar/hub adopt, they inherit the upgrades.

**Phase D — adoption (cross-repo):**
- writer: replace `_django/static/writer/assets/pdf-viewer.js` with an
  iframe pointing at live-paper's `/apps/live-paper/<paper_id>/?embed=1` or
  a direct `include(scitex_live_paper.mount(resolver=writer_resolver))`
  under `/writer/<project>/preview/`. PaperState.stage = `"draft"`.
- scholar: same `mount(resolver=scholar_resolver)` under
  `/scholar/<paper_id>/`. PaperState driven by paper's review stage.
- hub: already targets live-paper via PR #265; their resolver flip
  (PR #265 follow-up) consumes the multi-tenant path.

## 8. Open questions for the operator / hub agent

1. Is `pdfjs-dist` an acceptable runtime dep for live-paper? (We currently
   vendor its assets without the dist package; the port needs the actual
   library.)
2. Is the `01_manuscript/02_supplementary/03_revision` directory layout a
   writer-only convention or part of the broader bundle layout? Live-paper
   currently expects a flat `manuscript.pdf` at the bundle root.
3. Does scitex.ai use a CDN for the viewer JS, or does it serve from
   `staticfiles` direct? (Affects whether live-paper's bundle should ship
   pre-built artefacts or build on the host.)
4. When writer agent comes online: who owns the writer-side switch? Live-paper
   landing the viewer doesn't auto-migrate writer.

---

See `.scitex/todo/tasks.yaml` for the discrete migration tickets:

- `live-paper-absorb-writer-pdf-viewer-a-docs`
- `live-paper-absorb-writer-pdf-viewer-b-port`
- `live-paper-absorb-writer-pdf-viewer-c-features`
- `live-paper-absorb-writer-pdf-viewer-d-adopt`
