# `build_hub_resolver` — needs map (read-only)

**Status:** living needs-map. Updated 2026-06-14 with operator's a/b
ruling (F0+F1) and the corrected factory-location attribution
(adapter lives in `scitex-agentic-journal`, NOT in hub — confirmed by
proj-scitex-hub msg `b450c456`, 2026-06-14).

This doc maps what each consumer of `mount(resolver=...)` needs.
**No code, no shape commitments on the factory side** — the factory
itself is owned by `scitex-agentic-journal`
(`_hub_app_publisher/_resolver_adapter.py`, PR #34); this doc
captures what hub / scholar / writer pass *into* a resolver and what
live-paper-side surface keeps the contract consumable.

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

`build_hub_resolver(...)` is a factory that lives in
`scitex-agentic-journal` (NOT in live-paper, NOT in hub —
live-paper owns the resolver SHAPE; the
**resolver-injection ADAPTER lives in `scitex-agentic-journal`** —
their `_hub_app_publisher/_resolver_adapter.py`, landed in
agentic-journal PR #34. Hub itself does NOT own
`build_hub_resolver` — confirmed by proj-scitex-hub msg `b450c456`,
2026-06-14).

Journal owns the adapter because it's the package with re-review-badge
knowledge — the factory needs to thread `ReReviewBadge` through the
`BundleContext`, and journal is the producer of that data. Hub
consumes the resolver but doesn't construct it.

The factory takes journal-internal helpers (paper-lookup callable,
re-review-state-from-DB, etc.) and returns a `BundleResolver` ready
to hand to `live_paper.mount(...)`.

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
- **Side-effect contract**: pinned by PR #47 (commit 26e0761).
  Per-request synchronous invocation inside the view wrapper. May do
  IO (DB lookup, bundle resolution). Errors flow through the
  documented exception hierarchy:

  | Exception | Status |
  |---|---|
  | `BundleNotFound` | 404 |
  | `BundleAccessDenied` | 403 |
  | `BundleResolverError` (base) | 500 |

  Non-`BundleResolverError` exceptions propagate (Django default 500).
  All three classes are importable top-level (`from scitex_live_paper import
  BundleNotFound, BundleAccessDenied, BundleResolverError`). Full
  contract documented in `_mount.py`'s module docstring.

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

NOT here. live-paper publishes the resolver SHAPE
(`BundleResolver = Callable[..., BundleContext]`) and the resolver
ERROR HIERARCHY (`BundleResolverError` / `BundleNotFound` /
`BundleAccessDenied`, locked by PR #47); **`scitex-agentic-journal`
publishes the factory** (`_hub_app_publisher/_resolver_adapter.py`,
PR #34). Hub consumes both: it imports live-paper's public types
for the mount surface and imports journal's adapter to construct the
resolver. Dependency edges: `hub → live-paper`, `hub → journal`,
`journal → live-paper` (all forward-only, no cycles).

A live-paper-side helper (`build_resolver(...)` or similar) is NOT
needed: every host's resolver is too host-specific (auth, project
scope, storage layout) to share code with the others. The common
shape is already captured by `BundleContext` itself. Journal's
adapter is the reusable piece because it threads `ReReviewBadge`
through — and journal owns `ReReviewBadge`.

---

## M4 path-B a/b — RESOLVED (operator picked F0+F1, 2026-06-14)

Operator picked **F0+F1** (URL routing for published apps via
`scitex_hub.apps` + `scitex_hub.app_config` entry points). Locked
implications:

- Hub registers wrapper apps via the entry-points contract that
  PR #44 already ships (`scitex_hub.apps = <module>.urls:urlpatterns`,
  `scitex_hub.app_config = <module>.apps:<AppConfig>`).
- `build_hub_resolver` lives in `scitex-agentic-journal`'s
  `_hub_app_publisher/_resolver_adapter.py` (PR #34) and consumes
  the public types live-paper already exports. **No new live-paper
  surface needed** for the factory itself.
- live-paper's contributions to F0+F1 (this workstream): the
  resolver SHAPE + error hierarchy (PR #47, locked). Done.
- Next slice for live-paper is the **types-completeness audit** —
  any gap journal's adapter or hub's dispatcher needs from the
  public surface that isn't shipped yet — and **M5 DOI-landing**
  (deferred per lead msg `6a9b46a1` until M4 lands).

---

## What this doc deliberately does NOT do

- ❌ Propose a `build_hub_resolver` signature — that's owned by
  `scitex-agentic-journal` (already shipped in their PR #34's
  `_resolver_adapter.py`).
- ❌ Propose a live-paper-side `build_resolver` helper (likely not
  warranted — see "Where the factory lives" above; journal's adapter
  is the reusable piece).
- ❌ Touch `_django/_mount.py` further (PR #47 landed the contract
  pin; future shape changes would go through their own PR).
- ❌ Pre-spec storage layout, paper-id format, auth scheme — those
  belong in hub's / journal's design docs.

What live-paper IS still on the hook for (deferred until the operator
greenlights M5, per lead msg `6a9b46a1`):

- Types-completeness audit (#2 on lead's list) — any gap journal's
  adapter or hub's dispatcher actually trips on at integration
  time.
- M5 DOI-landing (canonical `/doi/<doi>/` URL surface as the first
  slice, per lead's recommendation).

---

## Cross-references

- live-paper implementation:
  - `src/scitex_live_paper/_django/_mount.py` — `mount(resolver=...)`
    contract + view-wrapper exception translation (locked PR #47).
  - `src/scitex_live_paper/_types.py` — public types
    (`BundleContext`, `BundleSource`, `PaperState`, `RendererOptions`,
    `BundleResolverError` + subclasses).
- Factory implementation (NOT here):
  - `scitex_agentic_journal/_hub_app_publisher/_resolver_adapter.py`
    (their PR #34). This is where `build_hub_resolver` lives.
- Hub consumer:
  - `scitex_hub`'s `urls_user_apps` dispatcher (F0+F1, in flight)
    consumes the live-paper mount + journal's adapter.
- Backlog ticket: `live-paper-build-hub-resolver` (in
  `.scitex/todo/tasks.yaml`) — live-paper-side coordination + audit
  tasks for this workstream.
- Coordinating agents:
  - proj-scitex-hub (msgs `1f2606e8`, `b450c456` — non-ownership
    confirmation + exception-hierarchy spec).
  - proj-scitex-agentic-journal (PRs #34 / #35 / #37 / #38 —
    cross-package parity + factory ownership).
