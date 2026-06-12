# pdfjs vendored bundle

Files in this directory are an **unmodified copy** of the official
[`pdfjs-dist`](https://www.npmjs.com/package/pdfjs-dist) v4.7.76 build,
fetched from `cdn.jsdelivr.net/npm/pdfjs-dist@4.7.76/build/`.

Licence: Apache-2.0 (see [Mozilla PDF.js](https://github.com/mozilla/pdf.js)).

We vendor rather than CDN-link so that:

- the generated live-paper site has no external network dependency at
  render time or read time, and
- a frozen, immutable snapshot of PDF.js travels with the bundle.

To refresh:

```bash
VER=4.7.76  # bump as needed
cd src/scitex_live_paper/_renderer/assets/pdfjs/
for f in pdf.min.mjs pdf.worker.min.mjs; do
  curl -fsSL "https://cdn.jsdelivr.net/npm/pdfjs-dist@${VER}/build/${f}" -o "${f}"
done
```

Then bump the version reference in
``scitex_live_paper._renderer.viewer.PDFJS_VERSION``.
