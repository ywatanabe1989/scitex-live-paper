/* scitex-live-paper / M1 claims sidebar
 *
 * - Click a row → expand the per-claim panel.
 * - "Open in viewer" link uses `viewer.html#claim=<id>`; the viewer page
 *   reads that fragment on load.
 * - Subscribes to `window` 'live-paper:claim' events from the viewer
 *   (issue #4 contract) so an in-page integration auto-opens the matching
 *   panel without the user clicking the sidebar row themselves.
 */

const PANEL_ATTR = 'aria-expanded';

function setExpanded(summaryBtn, expanded) {
  summaryBtn.setAttribute(PANEL_ATTR, expanded ? 'true' : 'false');
  const panelId = summaryBtn.getAttribute('aria-controls');
  const panel = panelId ? document.getElementById(panelId) : null;
  if (panel) {
    if (expanded) {
      panel.removeAttribute('hidden');
    } else {
      panel.setAttribute('hidden', '');
    }
  }
}

function closeAll(except) {
  document
    .querySelectorAll('.lp-claim-summary[aria-expanded="true"]')
    .forEach((btn) => {
      if (btn !== except) setExpanded(btn, false);
    });
}

function bindRowToggles() {
  document.querySelectorAll('.lp-claim-summary').forEach((btn) => {
    btn.addEventListener('click', () => {
      const open = btn.getAttribute(PANEL_ATTR) === 'true';
      closeAll(btn);
      setExpanded(btn, !open);
    });
  });
}

function openByClaimId(claimId) {
  if (!claimId) return false;
  const row = document.querySelector(
    `.lp-claim-row[data-claim-id="${CSS.escape(claimId)}"]`
  );
  if (!row) return false;
  const btn = row.querySelector('.lp-claim-summary');
  if (!btn) return false;
  closeAll(btn);
  setExpanded(btn, true);
  row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  return true;
}

function consumeUrlHash() {
  // Same #claim=<id> protocol the viewer uses (issue #4 link target).
  const match = (location.hash || '').match(/claim=([^&]+)/);
  if (match) {
    openByClaimId(decodeURIComponent(match[1]));
  }
}

function listenForViewerEvents() {
  // The viewer dispatches `live-paper:claim` on the global window when
  // a user clicks an anchor overlay. Same channel both pages speak.
  window.addEventListener('live-paper:claim', (ev) => {
    const id = ev?.detail?.id;
    if (id) openByClaimId(id);
  });
}

function bootstrap() {
  bindRowToggles();
  listenForViewerEvents();
  consumeUrlHash();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}

export { bootstrap, openByClaimId };
