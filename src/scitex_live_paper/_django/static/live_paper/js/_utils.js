// Shared utility helpers for the live-paper SPA modules. Vanilla ES
// module — every other JS file under this dir imports from here.
// No DOM-shape assumptions beyond `#live-paper-root` / `#live-paper-pdf`
// / `#live-paper-bundle-info` (the IDs the SPA contract pins).

export function normalizeBase(base) {
  if (!base.endsWith("/")) base += "/";
  return base;
}

export async function fetchJson(url) {
  const res = await fetch(url);
  return res.json();
}

export function setStatus(payload) {
  const pre = document.getElementById("live-paper-bundle-info");
  if (pre) {
    pre.textContent = JSON.stringify(payload, null, 2);
  }
}

export function ensurePdfContainer(rootEl) {
  let host = document.getElementById("live-paper-pdf");
  if (!host) {
    host = document.createElement("div");
    host.id = "live-paper-pdf";
    host.className = "live-paper-pdf";
    rootEl.appendChild(host);
  }
  return host;
}

export function ensureClaimsSidebar(rootEl) {
  let host = document.getElementById("live-paper-claims");
  if (!host) {
    host = document.createElement("aside");
    host.id = "live-paper-claims";
    host.className = "live-paper-claims";
    rootEl.appendChild(host);
  }
  return host;
}

export function renderError(message) {
  const container = document.getElementById("live-paper-bundle-info");
  if (container) {
    container.textContent = JSON.stringify({ error: message }, null, 2);
  }
}

export function cssEscape(value) {
  // Minimal CSS attribute-value escape. clew claim_ids are
  // alphanumerics + _ + - in practice, but we cover the corner case
  // when the runtime exposes CSS.escape() and fall back to a manual
  // replace otherwise.
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return String(value).replace(/(["\\])/g, "\\$1");
}
