# M2 re-verify — operator runbook

How to bootstrap, exercise, and embed the M2 live re-verify path
end-to-end. M1 is the read-only renderer; M2 is the *live* surface:
the SPA's Re-verify (and Re-verify-all) button calls back into
`scitex_clew.verify_claim()` against the bundle's pinned commit and
updates the verification badge.

This doc reflects the implementation as merged through PR #34.

---

## 1. Install (one command)

```bash
pip install 'scitex-live-paper[clew,django]'
```

- `[clew]` pulls `scitex-clew` so the M2 endpoints make a real verify
  call. Without it, the endpoints stay reachable but degrade
  gracefully: every per-claim response carries `"fallback": true` +
  a clear reason naming the install command.
- `[django]` is needed for the live Django mount (`serve` CLI + hub
  plugin). The read-only CLI render path works without Django.

The base install also works:

```bash
pip install scitex-live-paper
```

…and the M2 endpoints will respond with `fallback: true` (the SPA
badge stays meaningful — no 500s).

---

## 2. The four M2 surfaces

Every M2 endpoint mounts under the same prefix as the rest of
`scitex_live_paper._django.urls` — standalone mounts at `"/"`;
hub-mounted under `apps/live-paper/<paper_id>/` (or whatever your
`mount(resolver=...)` mount prefix is).

| Endpoint              | Method | Body                                  | Returns                      |
|-----------------------|--------|---------------------------------------|------------------------------|
| `api/claim/verify`    | POST   | `{"claim_id": "...", "pinned_commit"?: "..."}` | Single verify envelope        |
| `api/claims/verify`   | POST   | `{"claim_ids"?: ["..."], "pinned_commit"?: "..."}` | Bulk: `{ok, count, results[]}` |
| `api/claims`          | GET    | —                                     | Full claim list + `re_verify_enabled` |
| `api/bundle-info`     | GET    | —                                     | Bundle summary + `paper_state` |

### Single verify

```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"claim_id":"claim_a1b2c3d4e5f6"}' \
     http://localhost:8765/api/claim/verify
```

Response (clew installed, claim verified)::

```json
{
  "ok": true,
  "claim_id": "claim_a1b2c3d4e5f6",
  "verified_against": "deadbeefcafef00d12345678",
  "status": "verified",
  "verified_at": "2026-06-13T03:16:30Z",
  "details": { ...extra clew keys flow here... }
}
```

Response (no clew):

```json
{
  "ok": false,
  "claim_id": "claim_a1b2c3d4e5f6",
  "status": "stale",
  "reason": "scitex-clew not installed (install scitex-live-paper[clew])",
  "fallback": true
}
```

`pinned_commit` is optional in the body — falls back to
`bundle.paper_state.pinned_commit` (loaded from `state.yaml`).

### Bulk verify

```bash
curl -X POST -H 'Content-Type: application/json' -d '{}' \
     http://localhost:8765/api/claims/verify
```

Empty body = verify *every* claim. Or filter:

```bash
curl -X POST -H 'Content-Type: application/json' \
     -d '{"claim_ids":["claim_a","claim_b"]}' \
     http://localhost:8765/api/claims/verify
```

Response::

```json
{
  "ok": false,
  "verified_against": "deadbeef...",
  "count": 3,
  "results": [
    { "ok": true,  "claim_id": "claim_a", "status": "verified", ... },
    { "ok": false, "claim_id": "claim_b", "status": "stale", "fallback": true, ... },
    { "ok": false, "claim_id": "claim_c", "error": "<exc message>" }
  ]
}
```

Top-level `ok` is `true` iff *every* per-claim result is `ok: true`.
Per-claim failures (clew raise, unknown claim id, fallback) stay in
the array — a single bad claim never 500s the sweep.

---

## 3. SPA UI gates

The `re_verify_enabled` flag drives Re-verify button visibility. It
comes from `PaperState`:

| `paper_state.stage`           | `re_verify_enabled` | Why                                     |
|-------------------------------|--------------------|-----------------------------------------|
| `"draft"` / `"preprint"` / `"in_review"` | `false`         | No commit pinned yet to verify against  |
| `"accepted"` / `"published"`  | depends             | True iff `pinned_commit` is set         |

So a preprint bundle's SPA sidebar shows claim rows but no buttons; an
accepted bundle with a `state.yaml` carrying `pinned_commit` shows the
per-claim button + the sticky "Re-verify all" at the top.

---

## 4. Local end-to-end (standalone server)

```bash
# 1. Set up a bundle. Real ones live under tests/fixtures/.
export BUNDLE_DIR=$PWD/tests/fixtures/bundle-accepted

# 2. Boot the server.
scitex-live-paper serve "$BUNDLE_DIR" --port 8765

# 3. In another terminal, hit the endpoints.
curl -s http://localhost:8765/api/bundle-info | jq .paper_state
curl -s http://localhost:8765/api/claims      | jq '{re_verify_enabled, count: .claim_count}'
curl -s -X POST -H 'Content-Type: application/json' -d '{}' \
     http://localhost:8765/api/claims/verify | jq .

# 4. In the browser:
xdg-open http://localhost:8765/    # full page with chrome
xdg-open 'http://localhost:8765/?embed=1'  # chromeless (hub iframe variant)
```

If you didn't install `[clew]`, step 3's bulk verify returns three
`"fallback": true` entries — that's the documented contract.

---

## 5. Hub mount (multi-tenant)

Hub plugs the live-paper app under `apps/live-paper/<paper_id>/`. The
hub-side resolver translates `paper_id` + `request.user.current_project`
into a `BundleContext`; the M2 endpoints then read the right bundle
without any per-handler branching:

```python
# hub-side: apps/workspace/live_paper_app/urls.py
from django.urls import include, path
from scitex_live_paper import (
    mount, BundleContext, BundleSource, PaperState, RendererOptions,
)

def hub_resolver(request, paper_id, **url_kwargs) -> BundleContext:
    project = request.user.current_project
    return BundleContext(
        source=BundleSource.from_resolver(
            lambda: load_paper(paper_id, project.id),
        ),
        paper_state=PaperState.from_db(paper_id),
        api_base=request.path.rstrip("/").rsplit("/", 1)[0] + "/api/",
        options=RendererOptions(embed_mode=True),
    )

urlpatterns = [
    path("apps/live-paper/<paper_id>/",
         include(mount(resolver=hub_resolver))),
]
```

Hub side already targets these public names (PR #27 onwards); the
resolver flip is on hub's follow-up PR after PR #265.

---

## 6. Graceful-degradation cheatsheet

| Scenario                              | Endpoint behaviour                          | SPA badge   |
|---------------------------------------|---------------------------------------------|-------------|
| `scitex-clew` not installed           | 200 + `fallback: true` + named install hint | "stale" (grey/amber) |
| `scitex-clew` installed but no `verify_claim` (version skew) | 200 + `fallback: true` + "version skew" | "stale"     |
| Clew raises on a single claim         | 500 (single) / per-result error (bulk)      | "error" (red) |
| Bundle has no `pinned_commit`         | 400 with clear message                      | (button is hidden — `re_verify_enabled=false`) |
| Network error in the SPA              | (client-side) badge → "error", button retries | "error"   |

The badge stays meaningful in every scenario — no 500-then-???
gap for the operator to puzzle over.

---

## 7. Schema ownership boundary

This package **does not** define or extend the claim model. `scitex-clew`
owns:

- `Claim` shape (mirrored in `scitex_live_paper.bundle.Claim`)
- `VerificationStatus` palette (`verified` / `stale` / `contradicted` / ...)
- `verify_claim()` semantics

The live-paper-owned bits are render-time only:

- `PaperState` (lifecycle stage, journal, DOI, pinned commit)
- `BundleSource` / `BundleContext` / `RendererOptions` (render-time options)
- The HTTP envelope (`{ok, claim_id, status, ...}`)

If you need a new claim field, open the upstream issue against
`scitex-clew` — never invent fields here.
