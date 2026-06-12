<!-- ---
!-- Timestamp: 2026-06-12
!-- Author: ywatanabe
!-- File: /home/ywatanabe/proj/scitex-live-paper/README.md
!-- --- -->

# SciTeX Live Paper (`scitex-live-paper`)

Interactive, AI-verifiable, **live** rendering of a research manuscript — claims, code, data, DAG, and figures, all hash-linked back to the executable project that produced them.

> **Status:** pre-alpha scaffold (v0.1.0-alpha). README + minimum package skeleton. M1 (read-only renderer) implementation pending.

## What problem does it solve?

A traditional PDF paper is dead: the reader cannot click a claim, see the code that produced it, re-run it, or verify the provenance hash. A Live Paper does all of that — every claim is a link into the Clew DAG, every figure traces to a `figz`/`pltz` artefact, every method statement points to a hash-pinned commit. When the underlying claims are re-verified by an agentic reviewer (see [`scitex-agentic-journal`](https://github.com/ywatanabe1989/scitex-agentic-journal)), the paper updates its verification badge.

## What it renders

```
   accepted manuscript bundle
   (LaTeX + claims.json + DAG + figz/pltz + provenance)
              |
              v
        scitex-live-paper
              |
   +----------+----------+----------+
   v          v          v          v
 viewer    claims     DAG nav    badge
 (PDF.js)  panel     (mermaid)  (verification status)
```

UI surfaces:

- **Viewer** — PDF.js overlay synced with claim anchors (`\vclaim{id}`).
- **Claims panel** — list, status colour (green/orange/red, owned by Clew `VerificationStatus`), per-claim re-verify button.
- **DAG nav** — mermaid render of the Clew DAG; click a node to jump to the claim or the producing script.
- **Badge** — overall verification status fed from `scitex-agentic-journal` re-review runs.

## Dependency direction

```
scitex-live-paper   --reads-->   scitex-clew              (claim model + DAG + verify)
scitex-live-paper   --reads-->   scitex-writer            (manuscript bundle layout, \vclaim macros)
scitex-live-paper   <--emits--   scitex-agentic-journal   (accepted bundle handed in for rendering)
scitex-live-paper   --hosts-on-> scitex-hub               (Django mount at /viewer-v2/)
```

- The **claim** data model is owned by `scitex-clew` (decision locked in). Live-paper is a **consumer** — it does not define or mutate claim types; it only reads `VerificationStatus`, the DAG, and the hash-verified provenance graph.
- `scitex-writer`'s `viewer` (PDF.js + claims + DAG) is the in-app authoring preview. `scitex-live-paper` is the **published** counterpart — the post-acceptance, public, agent-re-verifiable rendition.
- Hosting on `scitex-hub` is via a `_django` app pluggable into the existing `/viewer/` mount (target slug `/viewer-v2/`).

## First milestone (M1, "read-only renderer")

1. Accept a bundle directory: `manuscript.tex`, `claims.json`, `dag.mmd`, `figz/`, `provenance.yaml`.
2. Render to a static site (HTML + PDF.js + mermaid):
   - viewer page with PDF + claim sidebar
   - DAG page (mermaid render, click-to-claim wiring)
   - per-claim page showing status, hash, producing script
3. CLI: `scitex-live-paper render ./bundle/ --out ./site/`.
4. No live re-verify yet, no agentic re-review yet, no editing. **Read-only**.

Subsequent milestones:

- M2 — live re-verify button (calls `clew claim verify` against pinned commit)
- M3 — mount as Django app on `scitex-hub` `/viewer-v2/`
- M4 — re-review badge fed from `scitex-agentic-journal`
- M5 — public DOI landing page (sandbox → Zenodo → JaLC)

## Install (planned)

```bash
pip install scitex-live-paper           # CLI + library
pip install scitex-live-paper[django]   # + Django app for scitex-hub mount
pip install scitex-live-paper[mcp]      # + MCP server for agents
```

## Part of SciTeX

`scitex-live-paper` is part of [SciTeX](https://scitex.ai).

Upstream dependencies:

| Package | Provides | Used here for |
|---------|----------|---------------|
| `scitex-clew`   | claim model + DAG + verification         | claim status, hashes, DAG render |
| `scitex-writer` | manuscript bundle layout + `\vclaim` macros | bundle ingestion, claim anchoring |
| `scitex-hub`    | Django host, Auth, app surface           | `/viewer-v2/` mount |
| `scitex-ui`     | UI shell + components                    | viewer / claims panel / DAG nav widgets |

Producer:

| Package | Hands in | For |
|---------|----------|-----|
| `scitex-agentic-journal` | accepted manuscript bundle + verification result | render + publish |

## Status

Pre-alpha — design + scaffold only. Implementation tracked under issues.

## License

AGPL-3.0-only.

<!-- EOF -->
