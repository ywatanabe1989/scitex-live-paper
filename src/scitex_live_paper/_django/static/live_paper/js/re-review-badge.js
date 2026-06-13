// M4 paper-level re-review badge. Sits above the claims sidebar
// header and reflects the verdict scitex-agentic-journal pushed at
// mount time via BundleContext.re_review_badge.
//
// Absent badge ⇒ nothing renders. Hosts on draft / preprint papers
// see no badge at all (the M2 per-claim chips are the only feedback
// at that stage).

export function renderReReviewBadge(rootEl, bundleInfoPayload) {
  if (!bundleInfoPayload || !bundleInfoPayload.re_review_badge) return;
  const badge = bundleInfoPayload.re_review_badge;
  if (!badge.status) return;

  const host = ensureReReviewBadgeHost(rootEl);
  host.innerHTML = "";

  const chip = document.createElement("div");
  chip.className = "lp-re-review-badge";
  chip.dataset.status = badge.status;

  const label = document.createElement("span");
  label.className = "lp-re-review-badge-label";
  label.textContent = "Re-review: " + badge.status;
  chip.appendChild(label);

  if (badge.reviewer) {
    const reviewer = document.createElement("span");
    reviewer.className = "lp-re-review-badge-reviewer";
    reviewer.textContent = " · by " + badge.reviewer;
    chip.appendChild(reviewer);
  }

  if (badge.last_reviewed_at) {
    const ts = document.createElement("span");
    ts.className = "lp-re-review-badge-ts";
    ts.textContent = " · " + badge.last_reviewed_at;
    chip.appendChild(ts);
  }

  if (badge.notes) {
    const notes = document.createElement("p");
    notes.className = "lp-re-review-badge-notes";
    notes.textContent = badge.notes;
    chip.appendChild(notes);
  }

  if (badge.log_url) {
    const link = document.createElement("a");
    link.className = "lp-re-review-badge-log";
    link.href = badge.log_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "view re-review log →";
    chip.appendChild(link);
  }

  host.appendChild(chip);
}

function ensureReReviewBadgeHost(rootEl) {
  let host = document.getElementById("live-paper-re-review");
  if (!host) {
    host = document.createElement("section");
    host.id = "live-paper-re-review";
    host.className = "live-paper-re-review";
    // Insert above the claims sidebar — claims-sidebar.js puts the
    // sidebar after PDF; this stays above both for visibility.
    rootEl.insertBefore(host, rootEl.firstChild);
  }
  return host;
}
