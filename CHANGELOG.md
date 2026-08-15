# Changelog

All notable changes to `scitex-live-paper` are documented in this file.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
SemVer applies *across releases*; pre-1.0 minor bumps may include
breaking changes for consumers that pin only on `==<major>` but
will not break **the documented public surface** without a note here.

The documented public surface is everything importable from
`scitex_live_paper` (the top-level package), the CLI
(`render` / `serve` / `info` / `validate`), and the Django mount
URL patterns / `bundle-info` JSON shape. Internal modules
(`_django` internals, `_renderer` internals, `_types` internals)
may change without a changelog entry.

## [Unreleased]

### Added

- Support for clew's `unsourced` claim status (clew 0.8.1,
  `claims.json` schema 1.4 / unified 1.6). `unsourced` is accepted by
  `validate` as a resting claim status, and renders in the **amber
  `suspect` colour** — one amber "questionable" bucket rather than a
  row of its own.
  The fold is a **colour-layer alias**, not a status rewrite: the
  status string stays `unsourced` everywhere it is read or displayed,
  so the sidebar still tells you *which* of the two amber states a
  claim is in. This is deliberately unlike legacy `partial`, which
  **is** normalized to `suspect` at ingest — `partial` was a rename
  with no surviving concept, whereas `unsourced` is a distinct state.
  The live re-verify endpoint likewise passes `unsourced` through
  verbatim, so it cannot disagree with the rendered sidebar.
  Colours come from clew's **fine** per-claim `color` palette, not the
  coarse `display_color` / `display_group` fields — the coarse palette
  buckets `mismatch`+`missing` into "failed" and `registered` into
  "suspect", which would silently revert the v1.3 palette below.
  clew's per-claim `grounded` (bool | null) is absorbed by
  `Claim.extras`, so the schema bump needs no typed-field change.

### Fixed

- M2 re-verify handlers (`api/claim/verify` + `api/claims/verify`) now
  call clew's real `verify_claim(claim_id_or_location)` signature — a
  single positional arg — instead of the non-existent
  `verify_claim(claim_id=, against=, bundle_root=)` kwargs that 500'd
  against a real `scitex-clew` install. The response now reads the
  nested `result["claim"]["status"]` / `["verified_at"]` (clew's real
  shape) instead of absent top-level keys, and maps clew's flat
  `not_found` result to `ok: false`. `pinned_commit` is now metadata
  only (echoed as `verified_against`): clew is git-agnostic, so the
  host/deployment owns checking out the commit and pointing clew's DB
  via `SCITEX_CLEW_DB_PATH` before serving — these handlers never
  mutate the working tree.
- Claim-status colour palette (static `claims.css` + SPA `viewer.css`)
  aligned to clew's canonical claim vocabulary — palette v1.3
  (clew 0.7.0): `verified`→green, `suspect`→amber, `mismatch`→red,
  `missing`→its own dark red (`#a40e26`, distinct from mismatch),
  `registered`/`not_found`→grey. Previously the palettes keyed on
  statuses clew never emits (`stale`/`failed`/`contradicted` as claim
  statuses), so failed verifications rendered uncoloured. Legacy
  `partial` (pre-0.7.0 exports / older installed clews) is normalized
  to `suspect` at bundle ingest and in the re-verify envelope,
  mirroring clew's own read-time behaviour. The M4 `ReReviewBadge`
  vocabulary (`verified`/`concerns`/`contradicted`/`stale`) is
  separate and unchanged.

## [0.1.0] — 2026-06-13

The first formal release. Encompasses M1 (read-only static-site
renderer), M2 (live re-verify backend + SPA UI), M3 (Django mount
helper + multi-tenant `mount(resolver=...)`), M4 prep (`ReReviewBadge`
transport contract for `scitex-agentic-journal`), and the operator
CLI (`render` / `serve` / `info` / `validate`).

100% test coverage across every Python source file
(593 tests, no mocks per the ecosystem doctrine).

### Added — M1 (read-only static-site renderer, PRs #14-#22)

- Bundle loader (`scitex_live_paper.bundle.load(path) -> Bundle`)
  with lenient `Claim.extras` passthrough so a `scitex-clew` schema
  bump doesn't require a release here.
- Per-surface renderers under `scitex_live_paper._renderer`:
  index landing page, PDF.js viewer page, claims sidebar page,
  Mermaid DAG navigator. All assets vendored (no CDN).
- `scitex-live-paper render <bundle> --out <site>` CLI: emits a
  self-contained static site that opens from `file://`.
- M3-prep `_django/` app skeleton mirroring `scitex_writer._django`
  (SPA shell + `<path:endpoint>` `api_dispatch` + standalone
  bootstrap).
- Dispatcher loud-return contract: handlers must return a `Mapping`
  or `HttpResponse`; non-conformant returns surface a JSON 500
  with the handler name + actual type rather than a bare TypeError.

### Added — Reusable component design (PRs #23-#27)

- `BundleSource` (frozen) — three constructors
  (`from_directory`, `from_bundle`, `from_resolver`) so hosts that
  already have a bundle in memory or a DB-backed lookup don't have
  to write to disk.
- `BundleContext` (frozen) — per-render / per-request context
  the renderer reads (source + paper_state + api_base + options +
  re_review_badge).
- `PaperState` (frozen) — render-time lifecycle metadata. Five
  stages (`draft` / `preprint` / `in_review` / `accepted` /
  `published`). Drives header label + verification-badge visibility
  + re-verify enablement.
- `RendererOptions` (frozen) — display-time knobs (title,
  embed_mode, theme, extra).
- `state.yaml` bundle convention: optional file at the bundle root
  drives `Bundle.paper_state`. Absent → `PaperState(stage="preprint")`
  default. Loader coerces unquoted YAML timestamps back to ISO strings.
- `?embed=1` SPA shell variant: chrome-less iframe-friendly page
  for hub project view / writer preview / scholar mount.
- `scitex_live_paper.mount(resolver=...)` Django helper: builds URL
  patterns that inject a per-request `BundleContext` via the host's
  resolver callable. Single dispatcher works under both standalone
  (env-pinned) and hub-mounted (multi-tenant) deployments.

### Added — M2 live re-verify (PRs #31-#34)

- `POST /api/claim/verify` — per-claim re-verify endpoint. Calls
  `scitex_clew.verify_claim()` against `bundle.paper_state.pinned_commit`;
  degrades gracefully when `scitex-clew` is not installed
  (`fallback: true` per-result envelope).
- `POST /api/claims/verify` — bulk re-verify. Per-claim failures
  fold into the per-result envelope; one bad claim doesn't 500 the
  sweep. Clew probed once up-front and shared across the sweep.
- `GET /api/claims` — full claim list + `re_verify_enabled` flag
  for the SPA sidebar.
- SPA UI: claims sidebar with per-status colour palette mirroring
  scitex-clew's `VerificationStatus` (green / amber / red / grey)
  + per-claim Re-verify button gated on `re_verify_enabled` +
  sticky "Re-verify all" button.
- `viewer.js` module split: 5 focused vanilla ES modules
  (`viewer.js` orchestrator + `pdf-viewer.js` +
  `claims-sidebar.js` + `reverify-all.js` + `_utils.js`).
- `[clew]` optional dependency extra: `pip install scitex-live-paper[clew]`
  installs `scitex-clew` so the M2 path stops falling back.

### Added — Writer PDF viewer dogfood (PRs #28-#30)

- Vanilla ES-module port of `scitex_writer/_django/frontend/src/pdf-viewer.ts`
  into `scitex_live_paper/_django/static/live_paper/js/`. Same
  class surface (PDFViewer with `load` / `render` / `clear` /
  `setZoom` / `setFitWidth` / `renderPlaceholder` / `zoomPercent`),
  same vendored PDF.js bundle, same `?doc_type=` parameter. Writer
  can adopt this with zero API churn.
- Text layer + Annotation layer + native Ctrl-F find: closes the
  three features writer's pdf-viewer.ts explicitly deferred.
  Native browser Ctrl-F walks the text-layer spans automatically;
  PDF-internal links open in a new tab via
  `externalLinkTarget: 2`.
- `GET /api/pdf` — serves the bundle's manuscript PDF bytes via
  Django `FileResponse`. Adapts writer's `compile.py:handle_pdf`
  pattern.

### Added — M4 prep (PR #38)

- `ReReviewBadge` (frozen) — paper-level re-review verdict pushed
  in by `scitex-agentic-journal`. Four-status palette
  (`verified` / `concerns` / `contradicted` / `stale`). Distinct
  from M2 per-claim verification chips.
- `BundleContext.re_review_badge` optional field — hosts inject
  per request via `mount(resolver=...)`.
- `api/bundle-info` surfaces the badge as a top-level
  `re_review_badge` field; SPA `re-review-badge.js` module renders
  it above the claims sidebar with the same colour palette as the
  M2 chips. Absent → SPA hides the badge entirely.
- `docs/dev/m4-re-review-badge-contract.md` — contract document
  for the agentic-journal side.

### Added — Operator CLI (PRs #39-#40)

- `scitex-live-paper info <bundle>` — one-screen pre-flight summary
  (manuscript / schema / claim count + status palette / DAG present
  / full PaperState block). `--json` flag for machine-parseable
  output stable across runs.
- `scitex-live-paper validate <bundle>` — pre-flight audit.
  Checks for duplicate claim_ids, unknown statuses, non-hex
  source_hashes, accepted/published stages without `pinned_commit`.
  Exits 0 on clean, non-zero issue count otherwise (POSIX cap 125).

### Added — Documentation (PRs #18, #28, #35)

- `docs/dev-quickstart.md` — installable-from-scratch dev loop.
- `docs/research/writer-pdf-viewer-findings.md` — discovery doc on
  the writer PDF viewer architecture + scitex.ai deployment.
- `docs/dev/m2-reverify-runbook.md` — operator-facing trace for
  the M2 live re-verify path.
- `docs/dev/m4-re-review-badge-contract.md` — agentic-journal
  contract for the M4 paper-level re-review badge.

### Coverage — 100% (PRs #36-#37)

- Every Python source file in `src/scitex_live_paper/` at 100%
  coverage.
- Two `# pragma: no cover` lines with named justification.

### Schema ownership boundary (unchanged across the release)

This package is a **thin consumer**:

- `Claim` model + `VerificationStatus` + DAG: owned by
  [`scitex-clew`](https://github.com/ywatanabe1989/scitex-clew).
- Bundle layout / `\vclaim` macros / `figz`-`pltz` blobs: owned by
  [`scitex-writer`](https://github.com/ywatanabe1989/scitex-writer).
- Re-review verdicts: owned by `scitex-agentic-journal` (M4
  contract documented; not yet shipped on their side).
- Auth / hub mount: owned by
  [`scitex-hub`](https://github.com/ywatanabe1989/scitex-hub).

If a feature requires a new claim field, open the upstream issue
against `scitex-clew` — never invent fields here.

## [0.1.0-alpha] — 2026-06-12

Initial scaffold (README + minimum package skeleton + 5-milestone
roadmap). Detailed history of the scaffold lives in the git log;
this entry marks the pre-release that PR #1-#13 + the first round
of M1 work (PRs #14-#22) built on.
