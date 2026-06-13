// Live-paper SPA viewer — thin orchestrator. Loads PDF.js, runs the
// boot RPCs (ping + bundle-info + claims), mounts the PDFViewer +
// claims sidebar. The actual rendering / sidebar / re-verify logic
// lives in sibling modules so each file stays focused.
//
// Module layout (under _django/static/live_paper/js/):
//   - viewer.js          (this file — orchestrator, public global)
//   - pdf-viewer.js      (PDFViewer class)
//   - claims-sidebar.js  (sidebar + per-claim Re-verify)
//   - reverify-all.js    (bulk Re-verify-all button)
//   - _utils.js          (shared helpers)
//
// Vanilla ES modules — no Vite / TS build needed. The HTML templates
// load this file with `type="module"` so dynamic + static imports
// work without ceremony.

import {
  normalizeBase,
  fetchJson,
  fetchOrNull,
  setStatus,
  ensurePdfContainer,
  renderError,
} from "./_utils.js";
import { PDFViewer } from "./pdf-viewer.js";
import { renderClaimsSidebar } from "./claims-sidebar.js";
import { renderReReviewBadge } from "./re-review-badge.js";

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

  // Boot RPCs — prefer the merged `dashboard` endpoint (one round-trip
  // returning bundle-info + claims in one go). Falls back to the
  // 3-call path if dashboard isn't served by the backend yet (so SPA
  // bundles built after this PR keep working against develop snapshots
  // that haven't picked up `api/dashboard`).
  let bundleInfo = null;
  let claimsPayload = null;

  try {
    const ping = await fetchJson(apiBase + "ping");
    if (!ping || ping.ok !== true) {
      throw new Error("ping returned non-ok: " + JSON.stringify(ping));
    }

    const dash = await fetchOrNull(apiBase + "dashboard");
    if (dash && dash.bundle && dash.claims) {
      bundleInfo = dash.bundle;
      claimsPayload = dash.claims;
    } else {
      // Fallback: separate calls. Keeps old backends working + lets
      // the SPA boot in environments where the dashboard endpoint
      // isn't reachable (e.g. an early hub-side wrapper that hasn't
      // re-deployed).
      bundleInfo = await fetchJson(apiBase + "bundle-info");
      claimsPayload = await fetchJson(apiBase + "claims");
    }

    setStatus(bundleInfo);
    renderReReviewBadge(rootEl, bundleInfo);
  } catch (err) {
    console.error("[live-paper] boot RPCs failed", err);
    setStatus({ error: String(err) });
  }

  // Claims sidebar — best-effort; if the claims payload didn't land
  // (boot RPC raised), the PDF viewer still mounts.
  if (claimsPayload) {
    try {
      renderClaimsSidebar(rootEl, claimsPayload, apiBase);
    } catch (err) {
      console.warn("[live-paper] claims sidebar render failed", err);
    }
  }

  const pdfContainer = ensurePdfContainer(rootEl);
  const viewer = new PDFViewer({
    container: pdfContainer,
    pdfjs: pdfjs,
    apiBase: apiBase,
  });
  await viewer.load();
}

// Public global — writer / scholar / hub embed paths can hand their
// own container in and drive the viewer programmatically.
window.LivePaperPDFViewer = PDFViewer;
