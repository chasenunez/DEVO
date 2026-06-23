"""DEVO — CSV to iCSV enrichment and validation.

Public API:
    from devo.enrich import ICSVEnricher
    from devo.validate import validate_icsv

Intentionally imports nothing on package load to avoid side effects
(frictionless, flask) in environments where only one function is needed.
"""

__version__ = "0.2.0"
