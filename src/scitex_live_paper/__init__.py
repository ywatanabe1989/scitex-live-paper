"""SciTeX Live Paper — interactive, AI-verifiable live rendering of research manuscripts.

Consumes the accepted manuscript bundle handed in by `scitex-agentic-journal`
(or directly by `scitex-writer`) and renders it as a viewer + claims panel +
DAG nav + verification badge.

Status: pre-alpha scaffold. M1 (read-only renderer) implementation pending.

See README.md for the dependency graph and roadmap.
"""

from . import bundle
from .bundle import Bundle, BundleError, Claim

__version__ = "0.1.0-alpha"

__all__ = ["__version__", "Bundle", "BundleError", "Claim", "bundle"]
