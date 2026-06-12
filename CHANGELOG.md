# Changelog

All notable changes to `scitex-live-paper` are documented in this file.

## [0.1.0-alpha] — 2026-06-12

### Added
- Initial scaffold with purpose + 5-milestone roadmap.
- README rendering diagram (manuscript bundle -> viewer / claims / DAG / badge).
- Dependency direction documented: consumer of `scitex-clew` (claim model owner), receives bundle from `scitex-agentic-journal`, hosts on `scitex-hub` `/viewer-v2/`.
- `pyproject.toml` with `scitex-dev`, `scitex-ui`, `click`, `jinja2`, `pyyaml` runtime; optional `django`, `mcp`, `test` extras.
- Package skeleton at `src/scitex_live_paper/` with version export.
- Smoke test (STX-TQ compliant).
