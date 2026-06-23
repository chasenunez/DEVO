"""Pure type-inference functions — no I/O, no side effects.

All functions in this module are deterministic and dependency-free.
They are shared by the enricher (CSV → type) and the validator (data re-inference).
"""
from __future__ import annotations

import re
from datetime import datetime

# --- Constants ---

INT_RE = re.compile(r"^-?\d+$")
# Optional decimal: matches "5" and "5.0" — needed so mixed int/float columns
# resolve to 'number' rather than falling through to 'string'.
FLOAT_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")

# Tried after fromisoformat fails; restored from DEVO_enricher.py (was dropped in refactor).
STRPTIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%Y%m%dT%H%M%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
)

# iCSV spec EBNF: field_delimiter ::= [,|\/:;] — tab is not in the allowed set.
VALID_ICSV_DELIMITERS: frozenset[str] = frozenset({",", "|", "\\", "/", ":", ";"})

# Common missing-value sentinels. Single source of truth shared by enricher and validator.
# EnviDat has no standardised sentinel, so we cast a wide net.
COMMON_MISSING: frozenset[str] = frozenset({
    "", "NA", "N/A", "na", "n/a", "NULL", "null", "nan", "NaN",
    "-999", "-999.0", "-999.000000",
})

# Type subtype lattice: inferred → set of declared types it is valid under.
# integer ⊂ number ⊂ string; datetime ⊂ string.
# Used by the validator for Option-A cross-check (declared type is authoritative).
_SUBTYPES: dict[str, frozenset[str]] = {
    "integer":  frozenset({"integer", "number", "string"}),
    "number":   frozenset({"number", "string"}),
    "datetime": frozenset({"datetime", "string"}),
    "string":   frozenset({"string"}),
}


# --- Type checkers ---

def _is_integer(s: str) -> bool:
    return bool(INT_RE.match(s))


def _is_number(s: str) -> bool:
    return bool(INT_RE.match(s) or FLOAT_RE.match(s))


def _is_datetime(s: str) -> bool:
    """Try fromisoformat first, then a fixed list of strptime formats."""
    s = s.strip()
    if not s:
        return False
    try:
        datetime.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        pass
    for fmt in STRPTIME_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except (ValueError, TypeError):
            continue
    return False


# --- Public API ---

def infer_type(values: list[str], missing: frozenset[str] = COMMON_MISSING) -> str:
    """
    Infer a Frictionless field type from a list of string values.
    Cascade: integer → number → datetime → string.
    Missing-value sentinels are excluded before testing.
    An all-missing or empty column returns 'string'.
    """
    pruned = [v.strip() for v in values if v.strip() not in missing]
    if not pruned:
        return "string"
    if all(_is_integer(v) for v in pruned):
        return "integer"
    if all(_is_number(v) for v in pruned):
        return "number"
    if all(_is_datetime(v) for v in pruned):
        return "datetime"
    return "string"


def is_subtype_or_equal(inferred: str, declared: str) -> bool:
    """
    True when the inferred type is at least as specific as (or equal to) the declared type.
    This means existing data satisfies the declared schema:
      - inferred=integer, declared=number  → True  (integers pass number validation)
      - inferred=number,  declared=integer → False (floats fail integer validation)
    Used by the validator to produce [WARN] when inferred is wider than declared.
    """
    return declared in _SUBTYPES.get(inferred, frozenset())
