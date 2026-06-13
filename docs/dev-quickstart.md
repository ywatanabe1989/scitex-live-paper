# Dev quickstart

This is the short loop for working on `scitex-live-paper` itself —
install the package in editable mode, render the in-tree fixture
bundle, open the resulting site, and you have the M1 read-only
renderer running end-to-end.

> **Before you read this, read the [README](../README.md).** The
> README pins the **boundary**: `scitex-live-paper` is a thin
> consumer of the claim model — the `Claim` / `VerificationStatus` /
> DAG schema is owned upstream by
> [`scitex-clew`](https://github.com/ywatanabe1989/scitex-clew). This
> doc deliberately does **not** re-document those schemas.

---

## 1. Install

From a fresh checkout (Python ≥ 3.10):

```bash
git clone https://github.com/ywatanabe1989/scitex-live-paper.git
cd scitex-live-paper
git switch develop
python -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
# To exercise the M2 live re-verify path end-to-end, also pull
# scitex-clew (the upstream owner of `verify_claim()`):
# pip install -e '.[test,django,clew]'
```

The `[project.scripts]` entry registers a console script, so:

```bash
scitex-live-paper --version
scitex-live-paper --help
scitex-live-paper render --help
```

…all work after the editable install.

## 2. Render the fixture bundle

A minimal accepted-manuscript bundle lives in-tree at
[`tests/fixtures/bundle-min/`](../tests/fixtures/bundle-min/). Render
it into a throwaway site directory:

```bash
scitex-live-paper render tests/fixtures/bundle-min --out /tmp/live-paper-site
```

This emits the full M1 site layout (see `_cli.render_site`):

```
/tmp/live-paper-site/
├── index.html       # landing page → links to viewer / claims / dag
├── viewer.html      # PDF.js + claim-anchor overlay
├── claims.html      # claims sidebar + per-claim panel
├── dag.html         # mermaid DAG + click-to-claim
├── claims.json      # copied from bundle (read-only)
├── manuscript.pdf   # copied from bundle
└── assets/
    ├── pdfjs/       # vendored — no CDN
    ├── mermaid/     # vendored — no CDN
    └── *.css, *.js
```

Open `index.html` straight from `file://` — every asset is vendored,
no server required:

```bash
xdg-open /tmp/live-paper-site/index.html   # Linux
open    /tmp/live-paper-site/index.html    # macOS
```

Library-mode call (same site, programmatic):

```python
from scitex_live_paper._cli import render_site

result = render_site("tests/fixtures/bundle-min", "/tmp/live-paper-site")
print(result.index_html, result.viewer_html, result.claims_html, result.dag_html)
```

## 3. Run the tests

```bash
pytest -q
```

The suite covers the loader, every renderer surface, and the CLI
end-to-end. New tests follow STX-TQ — see existing files under
`tests/` for the AAA-block convention.

---

## Bundle layout contract

The renderer accepts a directory laid out as follows. **Field-level
semantics are owned upstream** — this section only fixes the
file-level contract.

```
bundle/
├── manuscript.pdf      (or manuscript.tex — PDF preferred in M1)
├── claims.json         # claim list — schema owned by scitex-clew
├── dag.mmd             # mermaid DAG source — owned by scitex-clew
├── figz/               # figure blobs (figz / pltz)  — owned by scitex-writer
└── provenance.yaml     # hash-linked artefacts
```

### Authority — do not re-document

| File             | Schema authority      | Where to read                                                                                       |
|------------------|-----------------------|-----------------------------------------------------------------------------------------------------|
| `claims.json`    | **`scitex-clew`**     | [scitex-clew README](https://github.com/ywatanabe1989/scitex-clew#readme) — `Claim`, `VerificationStatus` |
| `dag.mmd`        | **`scitex-clew`**     | same as above — `clew.dag()` output, mermaid-formatted                                              |
| `figz/`          | **`scitex-writer`**   | [scitex-writer README](https://github.com/ywatanabe1989/scitex-writer#readme) — figure blob layout  |
| `provenance.yaml`| **`scitex-clew`**     | session / file / hash graph backing each claim's source link                                        |

The in-tree loader (`scitex_live_paper.bundle`) deserialises only the
fields the renderer needs (`claim_id`, `file_path`, `claim_type`,
`status`, source hashes, anchors, …) and stashes every other key
under `Claim.extras`. **Forward-compatible** by design: if `clew`
adds a field, it flows through untouched. If the renderer needs to
*use* a new field, open the upstream issue against `scitex-clew`
first — never invent or extend the claim shape here.

### Fixture as living spec

[`tests/fixtures/bundle-min/`](../tests/fixtures/bundle-min/) is the
canonical minimum bundle: 3 claims (`verified` / `stale` /
`registered`), a toy mermaid DAG, a placeholder PDF. Its
[README](../tests/fixtures/bundle-min/README.md) restates the
boundary: when `clew` bumps the claim schema, refresh the fixture —
do **not** extend the loader.

---

## Where the Django app pattern comes from

M3 (mount on `scitex-hub` `/viewer-v2/`) is not in M1, but the
package directory is already shaped for it. The Django pattern is
mirrored from
[`scitex_writer._django`](https://github.com/ywatanabe1989/scitex-writer/tree/main/src/scitex_writer/_django):

- single SPA-shell view (the `viewer_page` analog) + a
  `<path:endpoint>` `api_dispatch` that routes into a `HANDLERS`
  registry,
- standalone-mode bootstrap (`_server.py`, `_standalone_urls.py`) for
  local dev,
- cloud consumption via a thin wrapper that injects `working_dir`.

`scitex-writer`'s `viewer/` is the **authoring preview** (private,
editable). `scitex-live-paper` is the **published** counterpart —
post-acceptance, public, agent-re-verifiable. Same Django shape,
opposite side of the accept boundary.

When the `_django/` skeleton lands (tracked under issue #8), it
should be a near-verbatim copy of the `scitex_writer._django`
structure, with the handlers swapped for the read-only viewer /
claims / DAG endpoints.

---

## Where things are

| Path                                       | What                                              |
|--------------------------------------------|---------------------------------------------------|
| `src/scitex_live_paper/_cli.py`            | CLI entry (`render` subcommand, `render_site`)    |
| `src/scitex_live_paper/bundle.py`          | Bundle loader (`load`, `Bundle`, `Claim`, `BundleError`) |
| `src/scitex_live_paper/_renderer/`         | Per-surface renderers (viewer, claims, dag, index) + vendored assets |
| `tests/fixtures/bundle-min/`               | Minimal accepted-bundle fixture                   |
| `tests/{bundle,cli,claims,dag,viewer}/`    | Per-module pytest suites (STX-TQ)                 |
