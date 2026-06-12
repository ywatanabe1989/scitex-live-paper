# mermaid vendored bundle

Files in this directory are an **unmodified copy** of the official
[`mermaid`](https://www.npmjs.com/package/mermaid) v10.9.4 UMD build,
fetched from `cdn.jsdelivr.net/npm/mermaid@10.9.4/dist/mermaid.min.js`.

We use the UMD bundle (rather than the chunk-split ESM build) so the
DAG page only needs a single `<script>` tag and no second-tier fetches
to satisfy the renderer's "self-contained, no CDN" boundary.

Licence: MIT (see [mermaid-js/mermaid](https://github.com/mermaid-js/mermaid)).

We vendor rather than CDN-link so that:

- the generated live-paper site has no external network dependency at
  render time or read time, and
- a frozen, immutable snapshot of mermaid travels with the bundle.

To refresh:

```bash
VER=10.9.4  # bump as needed
cd src/scitex_live_paper/_renderer/assets/mermaid/
curl -fsSL \
  "https://cdn.jsdelivr.net/npm/mermaid@${VER}/dist/mermaid.min.js" \
  -o mermaid.min.js
```

Then bump the version reference in
``scitex_live_paper._renderer.dag.MERMAID_VERSION``.
