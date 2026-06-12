# Changelog

All notable changes to `scitex-live-paper` are documented in this file.

## [Unreleased]

### Changed
- README rewritten to lead with the **web-readable foundation** framing and the **thin-consumer** boundary with `scitex-clew`. New "Scope (read this first)" table makes explicit which concerns are owned by `scitex-clew` vs. consumed here.
- README now states the M1 MVP loop end-to-end (clew claim data → render → static site with verified-claims sidebar + PDF.js + DAG).
- Implementation reference for the Django app pattern points at [`scitex_writer._django`](https://github.com/ywatanabe1989/scitex-writer/tree/main/src/scitex_writer/_django) (SPA-shell + `<path:endpoint>` `api_dispatch` + standalone bootstrap).
- Roadmap broken out into GitHub issues for trackable M1 work.

## [0.1.0-alpha] — 2026-06-12

### Added
- Initial scaffold with purpose + 5-milestone roadmap.
- README rendering diagram (manuscript bundle -> viewer / claims / DAG / badge).
- Dependency direction documented: consumer of `scitex-clew` (claim model owner), receives bundle from `scitex-agentic-journal`, hosts on `scitex-hub` `/viewer-v2/`.
- `pyproject.toml` with `scitex-dev`, `scitex-ui`, `click`, `jinja2`, `pyyaml` runtime; optional `django`, `mcp`, `test` extras.
- Package skeleton at `src/scitex_live_paper/` with version export.
- Smoke test (STX-TQ compliant).
