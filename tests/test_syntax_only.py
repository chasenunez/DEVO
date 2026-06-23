"""Smoke tests: every module imports without syntax errors.

webui is skipped when Flask is not installed, since Flask is an optional dependency.
"""
import importlib
import importlib.util
import pytest

CORE_MODULES = [
    "devo",
    "devo.exceptions",
    "devo._infer",
    "devo._parser",
    "devo._schema",
    "devo._report",
    "devo.enrich",
    "devo.validate",
    "devo.cli",
]


def test_core_modules_importable():
    for m in CORE_MODULES:
        importlib.import_module(m)


def test_webui_importable_when_flask_present():
    if importlib.util.find_spec("flask") is None:
        pytest.skip("Flask not installed (optional dependency)")
    importlib.import_module("devo.webui")
