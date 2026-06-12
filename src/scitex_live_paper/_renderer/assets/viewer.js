/* scitex-live-paper / M1 viewer
 *
 * Loads the bundled PDF via PDF.js, paints an overlay rectangle per
 * claim anchor (page + bbox from `claims.json[claim].anchor`), and
 * dispatches `live-paper:claim` CustomEvents when a region is clicked
 * (consumed by the claims sidebar — issue M1-3).
 *
 * No CDN: pdf.min.mjs / pdf.worker.min.mjs are vendored beside this
 * file. Paths are passed in as data-* attributes on #live-paper-pdf-host.
 */

const STATUS_CLASS = {
  verified: 'lp-status-verified',
  stale:    'lp-status-stale',
  failed:   'lp-status-failed',
};

function classFor(status) {
  return STATUS_CLASS[(status || '').toLowerCase()] || '';
}

function emitClaimEvent(id) {
  // The event channel is documented in README ("MVP loop"); the claims
  // sidebar (M1-3) subscribes to it.
  window.dispatchEvent(
    new CustomEvent('live-paper:claim', { detail: { id } })
  );
}

/**
 * Render a single PDF page onto a fresh canvas, sized to the page
 * viewport, and return the host element so overlays can attach.
 */
async function renderPage(pdfDoc, pageNumber, scale) {
  const page = await pdfDoc.getPage(pageNumber);
  const viewport = page.getViewport({ scale });

  const pageEl = document.createElement('div');
  pageEl.className = 'lp-page';
  pageEl.dataset.page = String(pageNumber);
  pageEl.style.width = `${viewport.width}px`;
  pageEl.style.height = `${viewport.height}px`;

  const canvas = document.createElement('canvas');
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext('2d');
  pageEl.appendChild(canvas);

  const overlay = document.createElement('div');
  overlay.className = 'lp-overlay';
  pageEl.appendChild(overlay);

  await page.render({ canvasContext: ctx, viewport }).promise;
  return { pageEl, overlay, viewport, page };
}

/**
 * Convert a PDF-space bbox `[x0, y0, x1, y1]` (origin bottom-left) to a
 * top-left CSS rect on the rendered canvas. Uses the viewport's
 * convertToViewportRectangle so the maths is correct under any zoom.
 */
function pdfBboxToCssRect(viewport, bbox) {
  const [vx0, vy0, vx1, vy1] = viewport.convertToViewportRectangle(bbox);
  const left = Math.min(vx0, vx1);
  const top  = Math.min(vy0, vy1);
  const w    = Math.abs(vx1 - vx0);
  const h    = Math.abs(vy1 - vy0);
  return { left, top, w, h };
}

function paintAnchor(overlay, viewport, claim) {
  const a = claim?.anchor;
  if (!a || !Array.isArray(a.bbox) || a.bbox.length !== 4) return;
  const rect = pdfBboxToCssRect(viewport, a.bbox);

  const el = document.createElement('button');
  el.type = 'button';
  el.className = `lp-claim-anchor ${classFor(claim.status)}`;
  el.dataset.claimId = claim.claim_id;
  el.dataset.status = claim.status || 'registered';
  el.style.left   = `${rect.left}px`;
  el.style.top    = `${rect.top}px`;
  el.style.width  = `${rect.w}px`;
  el.style.height = `${rect.h}px`;
  el.title = claim.claim_value || claim.claim_id;
  el.setAttribute('aria-label', `Claim ${claim.claim_id}`);
  el.addEventListener('click', () => emitClaimEvent(claim.claim_id));
  overlay.appendChild(el);
}

function groupClaimsByPage(claims) {
  const out = new Map();
  for (const c of claims) {
    const p = c?.anchor?.page;
    if (!Number.isInteger(p)) continue;
    if (!out.has(p)) out.set(p, []);
    out.get(p).push(c);
  }
  return out;
}

async function loadClaims(url) {
  if (!url) return [];
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`claims fetch failed: ${resp.status}`);
  const data = await resp.json();
  // Accept either a bare list or the {claims: [...]} wrapper — same
  // shape the Python loader (scitex_live_paper.bundle) handles.
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.claims)) return data.claims;
  return [];
}

async function bootstrap() {
  const host = document.getElementById('live-paper-pdf-host');
  if (!host) return;

  const pdfUrl       = host.dataset.pdfUrl;
  const claimsUrl    = host.dataset.claimsUrl;
  const pdfjsUrl     = host.dataset.pdfjsUrl;
  const workerUrl    = host.dataset.pdfjsWorkerUrl;

  let pdfjsLib;
  try {
    pdfjsLib = await import(pdfjsUrl);
  } catch (err) {
    host.innerHTML = `<div class="lp-error">PDF.js failed to load: ${err.message}</div>`;
    return;
  }
  if (workerUrl) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;
  }

  let pdfDoc, claims;
  try {
    [pdfDoc, claims] = await Promise.all([
      pdfjsLib.getDocument(pdfUrl).promise,
      loadClaims(claimsUrl),
    ]);
  } catch (err) {
    host.innerHTML = `<div class="lp-error">Bundle load failed: ${err.message}</div>`;
    return;
  }

  const byPage = groupClaimsByPage(claims);
  const scale = 1.25;

  for (let n = 1; n <= pdfDoc.numPages; n++) {
    const { pageEl, overlay, viewport } = await renderPage(pdfDoc, n, scale);
    host.appendChild(pageEl);
    for (const claim of byPage.get(n) || []) {
      paintAnchor(overlay, viewport, claim);
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}

export { bootstrap, classFor, groupClaimsByPage, pdfBboxToCssRect };
