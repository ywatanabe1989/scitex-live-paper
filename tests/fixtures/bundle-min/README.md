# bundle-min — minimal fixture

A minimal accepted-manuscript-bundle layout used by the loader tests
(`tests/bundle/`).

```
bundle-min/
  manuscript.pdf     # placeholder PDF (header only; not parsed in M1)
  claims.json        # 3 claims, mixed verification status, mirroring clew schema
  dag.mmd            # toy mermaid DAG referencing the two claims with sources
  provenance.yaml    # session/file hash graph backing the source links
  figz/              # empty (no figures in this minimal fixture)
```

**Schema note.** The `claims.json` schema is **owned by `scitex-clew`**.
This fixture's `claims.json` is a hand-rolled minimum that mirrors the
shape of `scitex_clew.Claim.to_dict()` so the loader can be exercised
without a clew install. When clew bumps its claim schema, refresh this
fixture rather than extending the loader.
