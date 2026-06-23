"""iCSV validation.

Public API: validate_icsv(icsv_path, schema_path=None, outdir="DEVO_output")

Three-stage check:
  1. Metadata completeness (field_delimiter required; geometry/srid conditional on Q1).
  2. Type consistency: re-infer column types from data and compare to declared types
     (Option A: declared type is authoritative; inferred wider than declared → [WARN]).
  3. Frictionless data validation against the schema JSON.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from ._infer import COMMON_MISSING, infer_type, is_subtype_or_equal
from ._parser import ICSVHeader, parse_header
from ._report import write_report
from .exceptions import ParseError, ValidationError

# How many data rows (excluding header) to sample for type re-inference.
_INFER_SAMPLE = 500


def _check_metadata(header: ICSVHeader) -> list[str]:
    """
    Return a list of issue strings (empty = clean).
    geometry/srid are only flagged when spatial column names are present (Q1).
    srid is only required for lat/lon columns — WKT geometry embeds its own CRS.
    """
    issues = []

    if "field_delimiter" not in header.metadata:
        issues.append("[FAIL] Missing required metadata key: field_delimiter")

    fields = header.fields_meta.get("fields", [])
    lat_lon_names = {"lat", "latitude", "lon", "lng", "longitude"}
    wkt_names = {"geometry"}
    has_lat_lon = any(f.lower() in lat_lon_names for f in fields)
    has_wkt = any(f.lower() in wkt_names for f in fields)

    if has_lat_lon or has_wkt:
        if "geometry" not in header.metadata:
            issues.append(
                "[WARN] Spatial columns detected but 'geometry' metadata key is missing"
            )
    if has_lat_lon:
        if "srid" not in header.metadata:
            issues.append(
                "[WARN] Spatial columns detected but 'srid' metadata key is missing"
            )

    return issues


def _extract_data(
    icsv_path: Path,
    tmp_csv: Path,
    field_delimiter: str,
) -> list[list[str]]:
    """
    Write the [DATA] section of the iCSV to a comma-delimited temp CSV.
    Returns the first _INFER_SAMPLE data rows (excluding the header row) for type inference.

    Writing with comma delimiter avoids fighting the Frictionless dialect API across v4/v5;
    csv.writer quotes any values that contain a comma, so round-tripping is lossless.
    """
    sampled: list[list[str]] = []
    in_data = False
    header_done = False  # first DATA row is the column header, not a data row

    with open(icsv_path, "r", encoding="utf-8-sig") as src, \
         open(tmp_csv, "w", encoding="utf-8", newline="") as tgt:
        writer = csv.writer(tgt)
        for line in src:
            if line.strip() == "# [DATA]":
                in_data = True
                continue
            if not in_data:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            row = list(csv.reader([line.rstrip("\r\n")], delimiter=field_delimiter))[0]
            writer.writerow(row)
            if not header_done:
                header_done = True
            elif len(sampled) < _INFER_SAMPLE:
                sampled.append(row)

    return sampled


def _cross_check_types(
    declared_types: list[str],
    data_rows: list[list[str]],
    field_names: list[str],
    missing: frozenset[str] = COMMON_MISSING,
) -> list[tuple[str, str, str, bool]]:
    """
    Re-infer column types from data_rows and compare to declared types.
    Returns list of (col_name, declared, inferred, is_ok).
    is_ok=True means inferred is a subtype of or equal to declared (Option A).
    Pass the iCSV's own nodata sentinel merged into missing so custom sentinels
    are not treated as real data values during re-inference.
    """
    if not declared_types or not data_rows:
        return []

    n = len(declared_types)
    col_values: list[list[str]] = [[] for _ in range(n)]
    for row in data_rows:
        for i in range(min(len(row), n)):
            col_values[i].append(row[i])

    results = []
    for i, declared in enumerate(declared_types):
        name = field_names[i] if i < len(field_names) else str(i)
        inferred = infer_type(col_values[i], missing)
        results.append((name, declared, inferred, is_subtype_or_equal(inferred, declared)))
    return results


def _import_frictionless_schema():
    """Lazy import for frictionless.Schema — avoids module-level import of an optional dep."""
    try:
        from frictionless import Schema
        return Schema
    except ImportError as exc:
        raise ValidationError(
            "The 'frictionless' package is required. Install it: pip install frictionless"
        ) from exc


def validate_icsv(
    icsv_path: str,
    schema_path: Optional[str] = None,
    outdir: str = "DEVO_output",
) -> tuple[str, bool]:
    """
    Validate an iCSV file. Returns (report_path, valid).
    valid=True only when metadata is clean AND Frictionless reports no data errors.
    Type-consistency [WARN] entries do not affect the valid flag.
    Raises ValidationError if frictionless is not installed.
    Raises FileNotFoundError if no schema can be found.
    """
    try:
        from frictionless import Resource
    except ImportError as exc:
        raise ValidationError(
            "The 'frictionless' package is required. Install it: pip install frictionless"
        ) from exc

    path = Path(icsv_path)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    header = parse_header(path)
    metadata_issues = _check_metadata(header)
    metadata_ok = not any(line.startswith("[FAIL]") for line in metadata_issues)

    declared_types = header.fields_meta.get("types", [])
    field_names = header.fields_meta.get("fields", [])

    if not schema_path:
        candidate = path.with_name(path.stem + "_schema.json")
        if candidate.exists():
            schema_path = str(candidate)
        else:
            raise FileNotFoundError(
                f"No schema provided and none found alongside {path.name}. "
                "Run 'devo enrich' first or pass --schema."
            )

    # Create a unique temp file so concurrent calls on different inputs do not collide.
    fd, tmp_str = tempfile.mkstemp(suffix=".csv", dir=out)
    os.close(fd)
    tmp_csv = Path(tmp_str)

    try:
        data_rows = _extract_data(path, tmp_csv, header.field_delimiter)
        nodata_val = header.metadata.get("nodata", "")
        effective_missing = COMMON_MISSING | {nodata_val} if nodata_val else COMMON_MISSING
        type_issues = _cross_check_types(declared_types, data_rows, field_names, effective_missing)

        # frictionless v5 rejects absolute paths outside the working directory.
        # Fix: pass the filename relative to its parent via basepath.
        # Schema is loaded as a dict first so schema-path resolution is ours, not theirs.
        schema_dict = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        Schema = _import_frictionless_schema()
        schema_obj = Schema.from_descriptor(schema_dict)
        resource = Resource(
            path=tmp_csv.name,
            basepath=str(tmp_csv.parent),
            schema=schema_obj,
        )
        report = resource.validate()
        data_valid = report.valid

    finally:
        if tmp_csv.exists():
            tmp_csv.unlink()

    is_valid = metadata_ok and data_valid
    report_path = out / f"{path.stem}_DEVO_report.txt"
    write_report(
        path=report_path,
        icsv_name=path.name,
        metadata_issues=metadata_issues,
        type_issues=type_issues,
        frictionless_report=report,
        is_valid=is_valid,
    )

    return str(report_path), is_valid
