<!-- ---
!-- Timestamp: 2026-06-12
!-- Author: ywatanabe
!-- File: /home/ywatanabe/proj/scitex-live-paper/README.md
!-- --- -->

# SciTeX Live Paper (`scitex-live-paper`)

**The web-readable foundation for live, AI-verifiable research papers.**

A traditional PDF is dead — you cannot click a claim, see the code that produced it, re-run it, or check provenance. `scitex-live-paper` is the web rendering layer that turns an accepted manuscript bundle into a *live paper*: a page where every claim is hash-linked to the executable artefact that produced it, every figure traces to a `figz` / `pltz` blob, and the verification badge tracks a continuous re-review cycle.

> **Status:** alpha (v0.1.0-alpha). M1 (read-only renderer) shipped; M2 (live re-verify) shipped — see [`docs/dev/m2-reverify-runbook.md`](docs/dev/m2-reverify-runbook.md). M3 (hub mount) in flight on the [scitex-hub side](https://github.com/ywatanabe1989/scitex-hub). Roadmap below.

---

## Scope (read this first)

`scitex-live-paper` is **deliberately thin**. It is a **consumer / rendering layer**, not an authority on claims.

| Concern                                          | Owner               | This package's role            |
|--------------------------------------------------|---------------------|--------------------------------|
| `Claim` data model, `VerificationStatus`, DAG    | **`scitex-clew`**   | reads only — never defines, never mutates |
| Hash-linked provenance graph                     | **`scitex-clew`**   | reads `clew.dag()` / `clew.verify_claim()` outputs |
| Manuscript bundle layout (`\vclaim`, `figz`, …)  | **`scitex-writer`** | ingests the bundle as-is |
| Acceptance + re-review verdicts                  | **`scitex-agentic-journal`** | receives accepted bundle, surfaces badge |
| Auth / Django app surface                        | **`scitex-hub`**    | mounted on `/viewer-v2/` |

If a feature requires extending the claim or DAG model, **the change belongs upstream in `scitex-clew`**, not here. This package treats the claim model as a stable external contract.

---

## What it renders

```
   accepted manuscript bundle
   (LaTeX + claims.json + DAG + figz/pltz + provenance)
              │
              ▼
        scitex-live-paper          ← THIS PACKAGE (thin renderer)
              │
   ┌──────────┼──────────┬──────────┐
   ▼          ▼          ▼          ▼
 viewer    claims     DAG nav    badge
 (PDF.js)  panel     (mermaid)  (verification status,
                                fed by scitex-agentic-journal)
```

UI surfaces:

- **Viewer** — PDF.js, with overlays synced to claim anchors (`\vclaim{id}`).
- **Claims panel** — list of claims with status colour (green/orange/red — owned by `clew.VerificationStatus`), per-claim re-verify button.
- **DAG nav** — mermaid render of the Clew DAG; click a node to jump to the producing claim or script.
- **Badge** — overall verification status fed from `scitex-agentic-journal` re-review runs.

---

## MVP loop (M1)

The minimum cycle this package must deliver, end-to-end:

```
clew claim data  ─►  scitex-live-paper render  ─►  static web page
                                                   ├─ verified-claims sidebar
                                                   ├─ PDF.js viewer
                                                   └─ DAG (mermaid)
```

1. Accept a bundle directory: `manuscript.pdf` (or `.tex`), `claims.json`, `dag.mmd`, `figz/`, `provenance.yaml`.
2. Read `claims.json` (schema owned by `scitex-clew`); resolve `VerificationStatus` per claim.
3. Render a static site (HTML + PDF.js + mermaid):
   - viewer page (PDF + claims sidebar)
   - DAG page (mermaid, click-to-claim wiring)
   - per-claim page (status, hash, producing script link)
4. CLI: `scitex-live-paper render ./bundle/ --out ./site/`.

**Out of scope for M1:** live re-verify, agentic re-review, editing, auth. Read-only.

### Implementation reference

The Django app pattern for M3 (Hub mount) and the SPA-shell + API dispatch split are taken directly from [`scitex_writer._django`](https://github.com/ywatanabe1989/scitex-writer/tree/main/src/scitex_writer/_django):

- single SPA shell view (`editor_page` / `viewer_page` analog) + a `<path:endpoint>` `api_dispatch` that routes into a `HANDLERS` registry,
- standalone-mode bootstrap (`_server.py`, `_standalone_urls.py`) for local dev,
- cloud consumption via a thin wrapper that injects `working_dir`.

`scitex-writer`'s `viewer/` is the *authoring preview* (private, editable).
`scitex-live-paper` is the *published* counterpart — post-acceptance, public, agent-re-verifiable.

---

## Roadmap

| Milestone | Status         | Goal                                                                 |
|-----------|----------------|----------------------------------------------------------------------|
| **M1**    | ✅ shipped     | Read-only static-site renderer for an accepted bundle (CLI)          |
| **M2**    | ✅ shipped     | Live re-verify (`api/claim/verify` + `api/claims/verify` + SPA Re-verify button) — see [runbook](docs/dev/m2-reverify-runbook.md) |
| M3        | in flight (hub-side) | Mount as Django app on `scitex-hub` `/apps/live-paper/<paper_id>/` |
| M4        | pending        | Re-review badge fed from `scitex-agentic-journal`                    |
| M5        | future         | Public DOI landing page (sandbox → Zenodo → JaLC)                    |

Issues for M1 are filed in this repo — see [open issues](https://github.com/ywatanabe1989/scitex-live-paper/issues).

---

## Install (planned)

```bash
pip install scitex-live-paper           # CLI + library
pip install scitex-live-paper[django]   # + Django app for scitex-hub mount
pip install scitex-live-paper[clew]     # + scitex-clew for live re-verify (M2)
pip install scitex-live-paper[mcp]      # + MCP server for agents
```

Without `[clew]` the M2 `api/claim/verify` and `api/claims/verify`
endpoints stay reachable but degrade gracefully (every per-claim
response carries ``fallback: true`` + a clear reason); install
`[clew]` to get the real `verify_claim()` call.

> **Working on `scitex-live-paper` itself?** See
> [Dev quickstart](docs/dev-quickstart.md) — editable install, render
> the in-tree fixture bundle, bundle-layout contract, and where the
> Django app pattern is mirrored from.

---

## Part of SciTeX

`scitex-live-paper` is part of [SciTeX](https://scitex.ai).

Upstream dependencies (this package consumes them; it does not define their models):

| Package                  | Provides                                              | Consumed here for                          |
|--------------------------|-------------------------------------------------------|--------------------------------------------|
| `scitex-clew`            | claim model, DAG, `VerificationStatus`, verification  | claim status, hashes, DAG render           |
| `scitex-writer`          | manuscript bundle layout + `\vclaim` macros + `_django` viewer pattern | bundle ingestion, Django app pattern |
| `scitex-hub`             | Django host, auth, app surface                        | `/viewer-v2/` mount                        |
| `scitex-ui`              | UI shell + components                                 | viewer / claims panel / DAG nav widgets    |

Producer (this package is the rendering target):

| Package                  | Hands in                                              | For                                        |
|--------------------------|-------------------------------------------------------|--------------------------------------------|
| `scitex-agentic-journal` | accepted manuscript bundle + re-review verdict        | render + badge update                      |

---

## License

AGPL-3.0-only.

<!-- EOF -->
