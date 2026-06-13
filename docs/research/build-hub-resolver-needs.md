# `build_hub_resolver` — needs map (read-only pre-work)

**Status:** scoping doc. **No code, no shape commitments.** Implementation
is **HELD** pending the operator's M4 path-B a/b decision (F0+F1 vs F3).
This doc maps what a future `build_hub_resolver` factory would need to
do, so the implementation PR doesn't start from a blank page once the
a/b is picked.

---

## Why a factory?

`mount(resolver=...)` already lets a host inject a per-request resolver.
The example in `_mount.py`'s docstring shows what a hub-side resolver
looks like — about 8 lines, all of which encode the SAME pattern every
host repeats:

1. Look up the paper / project from the URL kwargs + request user.
2. Build a `BundleSource` (from a callable that does the IO).
3. Pick a `PaperState` (from the DB or from the bundle).
4. Compute `api_base` from the request path.
5. Compose `RendererOptions` (`embed_mode` for iframe hosts).

`build_hub_resolver(...)` would be a factory that lives in `scitex-hub`
(NOT in live-paper — live-paper owns the resolver SHAPE; hub owns
the resolver CONTENT). The factory takes hub-internal helpers
(project-lookup, bundle-lookup, paper-state-from-DB) and returns a
`BundleResolver` ready to hand to `live_paper.mount(...)`.

The win: the wrapper app (`scitex_live_paper_hub_app`) stops carrying
boilerplate; new hub mounts get a one-liner.

---

## What `mount(resolver=...)` already pins (input/output contract)

From `src/scitex_live_paper/_django/_mount.py`:

- **Signature**: `BundleResolver = Callable[..., BundleContext]`.
  - Receives the Django `request` plus all URL kwargs captured by the
    host's `path()` mount (`**url_kwargs`).
  - For the API dispatcher path, the `endpoint` kwarg also flows
    through.
- **Return**: a `BundleContext`. Required fields (see `_types.py`):
  - `source: BundleSource` — directory / `Bundle` instance / resolver
    callable.
  - `paper_state: PaperState` — render-time lifecycle (stage, journal,
    DOI, accepted_at, pinned_commit).
  - `api_base: str` — relative URL prefix the SPA uses to call
    `api/bundle-info` etc.
  - `options: RendererOptions` — display-time knobs (title, embed_mode,
    theme).
- **Side-effect contract**: not formally pinned. Today the resolver
  runs per-request synchronously inside the view wrapper. It may do
  IO (DB lookup, bundle resolution) but should not raise generic
  exceptions — hub-side will want a clean 404 path for "paper not
  found", not a 500.

---

## What each consumer actually needs

### hub (proj-scitex-hub PR #265 + follow-ups)
- URL kwargs: `paper_id` (string slug).
- Project context: `request.user.current_project` → multi-tenant scope.
- Bundle source: hub's per-project storage layout. Today: filesystem
  path; eventually: a `BundleSource.from_resolver(callable)` so storage
  can pivot without touching the resolver.
- PaperState: hub stores stage / journal / DOI in its own model. The
  resolver pulls from there; if the bundle ALSO has a `state.yaml`,
  hub's DB wins (lead's earlier ruling — host override beats bundle
  default).
- `api_base`: `request.path.rsplit("/", 1)[0] + "/"` (matches the
  existing docstring example).
- `embed_mode`: `True` (hub project view is iframe-shaped).

### scholar (forward-looking, not yet wired)
- URL kwargs: `paper_id` (scholar's per-paper lookup, not hub's slug).
- No project context — scholar's mount is single-tenant per user.
- Bundle source: scholar-side bundle store. Same `from_resolver`
  pattern.
- PaperState: stage comes from scholar's review-workflow status
  (`"in_review"` / `"accepted"` / `"published"`).
- `embed_mode`: TBD — scholar's paper page may want chrome.

### writer (forward-looking)
- URL kwargs: writer's editor-page id.
- Bundle source: writer's in-memory bundle (`BundleSource.from_bundle(...)`).
  Critical: writer doesn't write to disk before render — the live
  preview reads the in-memory Bundle.
- PaperState: `stage="draft"` (writer's preview is editable).
- `embed_mode`: `True` (writer's viewer pane is iframe-shaped).

---

## Where the factory lives

NOT here. live-paper publishes the resolver SHAPE; hub publishes the
factory that produces a resolver. The factory imports live-paper's
public types, so the dependency edge is hub → live-paper (already true).

A live-paper-side helper (`build_resolver(...)` or similar) is NOT
needed: every host's resolver is too host-specific (auth, project
scope, storage layout) to share code with the others. The
common shape is already captured by `BundleContext` itself.

---

## Open questions waiting on operator a/b

The M4 path-B a/b decision (F0+F1 vs F3) changes:

- **F0+F1 path**: hub registers wrapper apps via the existing entry
  points contract (`scitex_hub.apps` / `scitex_hub.app_config`).
  `build_hub_resolver` would live in the wrapper module
  (`scitex_live_paper_hub_app.resolver`) and ship as wrapper code. The
  factory needs no new live-paper surface — just consumes the public
  types live-paper already exports.
- **F3 path**: hub introduces a different plugin contract (TBD shape
  per the operator's choice). `build_hub_resolver` may need to be
  re-shaped to match F3's calling convention. Could affect the
  factory's signature, but NOT `BundleResolver` itself — `mount(...)`'s
  contract is independent of how the wrapper is registered.

Either way, live-paper's `mount(resolver=...)` and the public types
(`BundleContext`, `BundleSource`, `PaperState`, `RendererOptions`) do
not need to change. The a/b only affects WHERE the factory lives and
how it's discovered.

---

## What this doc deliberately does NOT do

- ❌ Propose a `build_hub_resolver` signature (operator a/b first).
- ❌ Propose a live-paper-side `build_resolver` helper (likely not
  warranted — see "Where the factory lives" above).
- ❌ Touch `_mount.py` or any other code.
- ❌ Pre-spec storage layout, paper-id format, auth scheme — those
  belong in hub's design doc.

The deliverable here is: when the operator picks a/b and lead unblocks
the workstream, the `build_hub_resolver` PR description writes itself
from this doc + the a/b ruling.

---

## Cross-references

- Implementation: `src/scitex_live_paper/_django/_mount.py` — current
  `mount(resolver=...)` contract.
- Public types: `src/scitex_live_paper/_types.py` — `BundleContext`,
  `BundleSource`, `PaperState`, `RendererOptions`.
- Backlog ticket: `live-paper-absorb-writer-pdf-viewer-d-adopt`
  (in `.scitex/todo/tasks.yaml`) — the user-visible workstream this
  feeds into.
- Coordinated agents: proj-scitex-hub (msg `1f2606e8` —
  `build_hub_resolver` deferral noted), proj-scitex-agentic-journal
  (PR #34 / #35 / #37 cross-package parity).
