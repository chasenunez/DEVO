"""
DEVO package: Data Enrichment and Validation Operator
"""

__version__ = "0.1.0"

from .enrichment import make_icsv_from_csv, ENRICHMENT_COMMON_MISSING
from .validation import validate_icsv, parse_icsv_metadata

__all__ = [
    "make_icsv_from_csv",
    "validate_icsv",
    "parse_icsv_metadata",
    "ENRICHMENT_COMMON_MISSING",
]
