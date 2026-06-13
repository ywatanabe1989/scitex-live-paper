// "Re-verify all" button + bulk dispatcher. POSTs api/claims/verify
// (PR #N bulk endpoint), then walks the per-claim results back into
// each row in the claims sidebar. Operator gets immediate feedback
// (all rows flip to "verifying") and a final state once the response
// lands; per-claim failures inside the bulk response do NOT 500 the
// sweep — they're shown row-by-row.

import { cssEscape } from "./_utils.js";

export function renderReverifyAllButton(apiBase, pinnedCommit) {
  const wrap = document.createElement("div");
  wrap.className = "lp-claims-toolbar";

  const btn = document.createElement("button");
  btn.className = "lp-claims-reverify-all";
  btn.type = "button";
  btn.textContent = "Re-verify all";
  btn.addEventListener("click", function () {
    void reverifyAllClaims(btn, pinnedCommit, apiBase);
  });

  wrap.appendChild(btn);
  return wrap;
}

export async function reverifyAllClaims(btn, pinnedCommit, apiBase) {
  btn.disabled = true;
  const originalLabel = btn.textContent;
  btn.textContent = "Verifying…";

  // Flip every row to "verifying" up front for immediate feedback.
  document.querySelectorAll(".lp-claim").forEach(function (row) {
    row.dataset.status = "verifying";
    const badge = row.querySelector(".lp-claim-status");
    if (badge) {
      badge.dataset.status = "verifying";
      badge.textContent = "verifying";
    }
    const perBtn = row.querySelector(".lp-claim-reverify");
    if (perBtn) perBtn.disabled = true;
  });

  try {
    const body = {};
    if (pinnedCommit) body.pinned_commit = pinnedCommit;

    const res = await fetch(apiBase + "claims/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await res.json();

    if (res.status !== 200 || !payload || !Array.isArray(payload.results)) {
      console.error("[live-paper] re-verify-all unexpected response", res.status, payload);
      _markAllClaimRowsAsError();
      return;
    }

    for (const result of payload.results) {
      _applyResultToRow(result);
    }
  } catch (err) {
    console.error("[live-paper] re-verify-all network error", err);
    _markAllClaimRowsAsError();
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
    document.querySelectorAll(".lp-claim-reverify").forEach(function (b) {
      b.disabled = false;
      b.textContent = "Re-verify";
    });
  }
}

function _applyResultToRow(result) {
  if (!result || !result.claim_id) return;
  const selector =
    '.lp-claim[data-claim-id="' + cssEscape(result.claim_id) + '"]';
  const row = document.querySelector(selector);
  if (!row) return;

  let nextStatus;
  if (result.ok === true) {
    nextStatus = result.status || "verified";
  } else if (result.fallback === true) {
    nextStatus = result.status || "stale";
    console.info(
      "[live-paper] re-verify-all fallback for %s: %s",
      result.claim_id,
      result.reason,
    );
  } else {
    nextStatus = result.status || "error";
    console.warn("[live-paper] re-verify-all per-claim failure", result);
  }

  row.dataset.status = nextStatus;
  const badge = row.querySelector(".lp-claim-status");
  if (badge) {
    badge.dataset.status = nextStatus;
    badge.textContent = nextStatus;
  }
}

function _markAllClaimRowsAsError() {
  document.querySelectorAll(".lp-claim").forEach(function (row) {
    row.dataset.status = "error";
    const badge = row.querySelector(".lp-claim-status");
    if (badge) {
      badge.dataset.status = "error";
      badge.textContent = "error";
    }
  });
}
