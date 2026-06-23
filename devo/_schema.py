"""Frictionless schema builder and per-column statistics.

Separates DEVO-specific stats (min, max, missing_count — written to the iCSV FIELDS section)
from the Frictionless schema JSON (which must only contain standard Frictionless keys).
"""
from __future__ import annotations

from typing import Any, Optional

from ._infer import STRPTIME_FORMATS, COMMON_MISSING


def _numeric_minmax(
    pruned: list[str], as_type: str
) -> tuple[Optional[float | int], Optional[float | int]]:
    """Compute min/max for integer or number columns. Returns (None, None) on failure."""
    if not pruned:
        return None, None
    try:
        nums = [int(x) if as_type == "integer" else float(x) for x in pruned]
        return min(nums), max(nums)
    except (ValueError, TypeError):
        return None, None


def _datetime_minmax(pruned: list[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Compute min/max for datetime columns.
    Returns ISO-format strings or (None, None) if nothing can be parsed.
    Uses the same format list as _infer.py to stay consistent.
    """
    from datetime import datetime

    parsed = []
    for v in pruned:
        try:
            parsed.append(datetime.fromisoformat(v))
            continue
        except (ValueError, TypeError):
            pass
        for fmt in STRPTIME_FORMATS:
            try:
                parsed.append(datetime.strptime(v, fmt))
                break
            except (ValueError, TypeError):
                continue
    if not parsed:
        return None, None
    return min(parsed).isoformat(), max(parsed).isoformat()


def compute_col_stats(
    vals: list[str],
    inferred_type: str,
    missing: frozenset[str] = COMMON_MISSING,
) -> dict[str, Any]:
    """
    Compute per-column statistics for the iCSV [FIELDS] section.
    These values go into # min =, # max =, # missing_count =.
    They do NOT appear in the Frictionless schema JSON.
    """
    pruned = [v for v in vals if v not in missing and v.strip() != ""]
    missing_count = len(vals) - len(pruned)
    stats: dict[str, Any] = {
        "type": inferred_type,
        "min": None,
        "max": None,
        "missing_count": missing_count,
        # required only if no missing values were observed in the current data
        "required": missing_count == 0 and len(vals) > 0,
    }
    if inferred_type in ("integer", "number") and pruned:
        stats["min"], stats["max"] = _numeric_minmax(pruned, inferred_type)
    elif inferred_type == "datetime" and pruned:
        stats["min"], stats["max"] = _datetime_minmax(pruned)
    return stats


def build_frictionless_schema(
    header: list[str],
    col_stats: list[dict[str, Any]],
    missing: frozenset[str] = COMMON_MISSING,
) -> dict[str, Any]:
    """
    Build a clean Frictionless Table Schema dict.
    Only standard Frictionless keys are written here.
    DEVO-specific stats (min, max, missing_count) live in the iCSV FIELDS section only.
    """
    fields = []
    for name, stats in zip(header, col_stats):
        field: dict[str, Any] = {"name": name, "type": stats["type"]}
        # frictionless datetime/default rejects partial datetime strings (e.g. date-only).
        # format=any tells frictionless to accept any parseable datetime representation,
        # consistent with DEVO's own broad datetime detection.
        if stats["type"] == "datetime":
            field["format"] = "any"
        constraints: dict[str, Any] = {}
        if stats["min"] is not None:
            constraints["minimum"] = stats["min"]
        if stats["max"] is not None:
            constraints["maximum"] = stats["max"]
        if stats.get("required"):
            constraints["required"] = True
        if constraints:
            field["constraints"] = constraints
        fields.append(field)

    return {
        "fields": fields,
        "missingValues": sorted(missing),
    }
