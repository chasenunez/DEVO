"""DEVO package.

This file intentionally does not import submodules to avoid pre-import side effects
when running `python -m devo.cli`. Import modules explicitly when needed.
"""

__all__ = ["enrich", "validate", "cli", "webui"]
