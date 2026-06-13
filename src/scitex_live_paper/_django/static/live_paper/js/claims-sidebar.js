// Claims sidebar + per-claim Re-verify wire-up. Vanilla ES module.
// Imports the shared helpers + the bulk Re-verify-all button from the
// sibling modules so this file stays focused on per-claim rendering.

import { ensureClaimsSidebar } from "./_utils.js";
import { renderReverifyAllButton } from "./reverify-all.js";

export function renderClaimsSidebar(rootEl, claimsPayload, apiBase) {
  if (!claimsPayload || !Array.isArray(claimsPayload.claims)) return;

  const sidebar = ensureClaimsSidebar(rootEl);
  sidebar.innerHTML = "";

  const header = document.createElement("div");
  header.className = "lp-claims-header";
  header.textContent =
    claimsPayload.claim_count +
    " claim" +
    (claimsPayload.claim_count === 1 ? "" : "s");
  sidebar.appendChild(header);

  const reVerifyEnabled = !!claimsPayload.re_verify_enabled;
  const pinnedCommit = claimsPayload.pinned_commit || null;

  // "Re-verify all" — same visibility gate as per-claim button.
  if (reVerifyEnabled) {
    sidebar.appendChild(renderReverifyAllButton(apiBase, pinnedCommit));
  }

  const list = document.createElement("ul");
  list.className = "lp-claims-list";

  for (const claim of claimsPayload.claims) {
    list.appendChild(renderClaimRow(claim, apiBase, reVerifyEnabled, pinnedCommit));
  }

  sidebar.appendChild(list);
}

export function renderClaimRow(claim, apiBase, reVerifyEnabled, pinnedCommit) {
  const li = document.createElement("li");
  li.className = "lp-claim";
  li.dataset.claimId = claim.claim_id;
  li.dataset.status = claim.status || "registered";

  const idSpan = document.createElement("span");
  idSpan.className = "lp-claim-id";
  idSpan.textContent = claim.claim_id;
  li.appendChild(idSpan);

  const valueSpan = document.createElement("span");
  valueSpan.className = "lp-claim-value";
  valueSpan.textContent =
    claim.claim_value || claim.file_path || "(no value)";
  li.appendChild(valueSpan);

  const statusBadge = document.createElement("span");
  statusBadge.className = "lp-claim-status";
  statusBadge.dataset.status = claim.status || "registered";
  statusBadge.textContent = claim.status || "registered";
  li.appendChild(statusBadge);

  // Re-verify button — only visible when PaperState.re_verify_enabled
  // (accepted/published + pinned_commit set). Hosts on draft/preprint
  // bundles see the claim row WITHOUT a button.
  if (reVerifyEnabled) {
    const btn = document.createElement("button");
    btn.className = "lp-claim-reverify";
    btn.type = "button";
    btn.textContent = "Re-verify";
    btn.dataset.claimId = claim.claim_id;
    btn.addEventListener("click", function () {
      void reverifyClaim(li, claim.claim_id, pinnedCommit, apiBase);
    });
    li.appendChild(btn);
  }

  return li;
}

export async function reverifyClaim(rowEl, claimId, pinnedCommit, apiBase) {
  const statusBadge = rowEl.querySelector(".lp-claim-status");
  const btn = rowEl.querySelector(".lp-claim-reverify");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Verifying…";
  }
  if (statusBadge) {
    statusBadge.dataset.status = "verifying";
    statusBadge.textContent = "verifying";
  }

  try {
    const body = { claim_id: claimId };
    if (pinnedCommit) body.pinned_commit = pinnedCommit;

    const res = await fetch(apiBase + "claim/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await res.json();

    let nextStatus;
    if (res.status === 200 && payload.ok === true) {
      nextStatus = payload.status || "verified";
    } else if (res.status === 200 && payload.fallback === true) {
      nextStatus = payload.status || "stale";
      console.info("[live-paper] re-verify fallback:", payload.reason);
    } else {
      nextStatus = "error";
      console.error("[live-paper] re-verify failed", res.status, payload);
    }

    rowEl.dataset.status = nextStatus;
    if (statusBadge) {
      statusBadge.dataset.status = nextStatus;
      statusBadge.textContent = nextStatus;
    }
  } catch (err) {
    console.error("[live-paper] re-verify network error", err);
    if (statusBadge) {
      statusBadge.dataset.status = "error";
      statusBadge.textContent = "error";
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Re-verify";
    }
  }
}
