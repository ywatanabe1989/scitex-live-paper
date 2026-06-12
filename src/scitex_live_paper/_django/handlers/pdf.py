"""``api/pdf`` — serve the bundle's manuscript PDF bytes.

Ported from ``scitex_writer/_django/handlers/compile.py:handle_pdf``
(see ``docs/research/writer-pdf-viewer-findings.md``). Writer's
version resolves a ``doc_type`` to a hard-coded relative path under
the project dir; our bundles ship a single flat ``manuscript.pdf``
today, so the lookup degenerates to one entry, but we keep the
parameter so writer can adopt this handler without API churn (their
PRs for supplementary / revision land later).

Boundary unchanged: handler reads the bundle via
:func:`services.get_request_bundle_state`, so the same code path works
under standalone (env-pinned) and hub-mounted
(:func:`scitex_live_paper.mount`) deployments.
"""

from __future__ import annotations

from typing import Any, Mapping

from django.http import FileResponse, HttpResponse, JsonResponse

from ..services import get_request_bundle_state

__all__ = ["handle_pdf"]


# Truthy values for the ``?download=...`` query string. Anything outside
# this set leaves the response inline (the PDF.js viewer streams it
# directly).
_DOWNLOAD_TRUTHY = frozenset({"1", "true", "yes", "on"})


def handle_pdf(request) -> HttpResponse:
    """Serve the bundle's PDF bytes.

    Query string:

    - ``doc_type`` — one of ``manuscript`` (default) /
      ``supplementary`` / ``revision``. Only ``manuscript`` is
      mapped today; the other two land when the bundle layout
      extends.
    - ``download`` — when truthy (``1`` / ``true`` / ``yes`` /
      ``on``), set ``Content-Disposition: attachment`` so browsers
      offer a download dialog instead of inline preview.

    Returns ``FileResponse`` with ``content_type="application/pdf"``,
    or a JSON 404 if the bundle's manuscript is missing.
    """
    doc_type = request.GET.get("doc_type", "manuscript")

    # Today only `manuscript` is wired. Writer's compile.py resolves
    # supplementary + revision to extra paths under the project dir;
    # those land when the bundle layout grows to match. Return a
    # clean 400 for unknown doc_type so callers know it's not a
    # transient bundle issue.
    if doc_type not in {"manuscript", "supplementary", "revision"}:
        return JsonResponse(
            {"error": f"unknown doc_type: {doc_type!r}"},
            status=400,
        )

    state = get_request_bundle_state(request)
    bundle = state.bundle

    if doc_type != "manuscript":
        return JsonResponse(
            {
                "error": (
                    f"doc_type={doc_type!r} is not yet supported by the "
                    "live-paper bundle layout (only `manuscript` ships today)"
                )
            },
            status=404,
        )

    pdf_path = bundle.manuscript_path
    if pdf_path is None or not pdf_path.exists():
        return JsonResponse(
            {"error": "manuscript.pdf not found in bundle"},
            status=404,
        )

    as_attachment = request.GET.get("download", "").strip().lower() in _DOWNLOAD_TRUTHY

    return FileResponse(
        open(pdf_path, "rb"),
        content_type="application/pdf",
        filename=pdf_path.name,
        as_attachment=as_attachment,
    )
