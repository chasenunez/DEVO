"""Plain-text validation report writer.

Produces a human-readable .txt file covering three checks:
  1. Metadata completeness
  2. Type consistency (declared vs re-inferred)
  3. Frictionless data validation
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_report(
    path: Path,
    icsv_name: str,
    metadata_issues: list[str],
    type_issues: list[tuple[str, str, str, bool]],
    frictionless_report: Any,
    is_valid: bool,
) -> None:
    """
    Write a plain-text DEVO validation report to `path`.

    type_issues: list of (column_name, declared_type, inferred_type, is_ok).
      is_ok=True means inferred is a subtype of (or equal to) declared.
    frictionless_report: the object returned by frictionless Resource.validate().
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _SEP = "-" * 40

    with open(path, "w", encoding="utf-8") as fh:

        fh.write("DEVO Validation Report\n")
        fh.write("=" * 22 + "\n")
        fh.write(f"File:  {icsv_name}\n")
        fh.write(f"Date:  {now}\n")
        fh.write(f"Valid: {'YES' if is_valid else 'NO'}\n\n")

        # --- Metadata ---
        fh.write("METADATA\n")
        fh.write(_SEP + "\n")
        if metadata_issues:
            for issue in metadata_issues:
                fh.write(f"{issue}\n")
        else:
            fh.write("[OK] All required metadata present.\n")
        fh.write("\n")

        # --- Type consistency (Option A cross-check) ---
        fh.write("TYPE CONSISTENCY\n")
        fh.write(_SEP + "\n")
        if not type_issues:
            fh.write("[OK] No declared types to cross-check.\n")
        else:
            for col, declared, inferred, ok in type_issues:
                if ok:
                    fh.write(f"[OK]   {col}: declared={declared}, inferred={inferred}\n")
                else:
                    fh.write(f"[WARN] {col}: declared={declared}, inferred={inferred}\n")
                    fh.write(
                        f"       Inferred type is wider than declared. "
                        f"Data may not satisfy '{declared}' constraints.\n"
                    )
        fh.write("\n")

        # --- Frictionless data validation ---
        fh.write("DATA VALIDATION\n")
        fh.write(_SEP + "\n")
        try:
            errors = frictionless_report.flatten(
                ["rowNumber", "fieldNumber", "fieldName", "code", "message"]
            )
        except (AttributeError, TypeError):
            errors = []
            fh.write("[WARN] Could not extract error details from frictionless report.\n")

        if not errors:
            fh.write("[PASS] No data errors found.\n")
        else:
            shown = errors[:50]
            suffix = f" (showing first 50 of {len(errors)})" if len(errors) > 50 else ""
            fh.write(f"[FAIL] {len(errors)} error(s) found{suffix}:\n")
            for row, col_num, col_name, code, message in shown:
                row_str = str(row) if row is not None else "?"
                col_str = col_name or (str(col_num) if col_num is not None else "?")
                fh.write(f"  Row {row_str}, Col {col_str} [{code}]: {message}\n")
