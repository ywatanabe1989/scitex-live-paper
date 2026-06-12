# bundle-accepted — fixture for `state.yaml` loading

Mirrors `bundle-min/` exactly (same claims.json, dag.mmd, provenance.yaml,
manuscript.pdf, figz/) but adds a `state.yaml` declaring the paper has
been accepted at *eLife* with a DOI and a pinned re-verify commit.

```
bundle-accepted/
  manuscript.pdf
  claims.json
  dag.mmd
  provenance.yaml
  figz/
  state.yaml         # NEW — render-time lifecycle metadata
```

Used by `tests/bundle/test_state_yaml.py` to lock the `state.yaml`
loader's contract. Refresh in lockstep with `bundle-min/` if claims /
DAG semantics change upstream in `scitex-clew`.
