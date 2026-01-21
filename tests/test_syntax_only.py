"""Very small smoke test to ensure Python modules import (syntax-only).

This test intentionally avoids importing `frictionless` to keep it runnable in
CI that hasn't installed the dependency. The purpose is to catch syntax errors
in the package files.
"""
import importlib

MODULES = [
    "devo.enrich",
    "devo.validate",
    "devo.cli",
    "devo.webui",
]


def test_modules_importable():
    for m in MODULES:
        importlib.import_module(m)
