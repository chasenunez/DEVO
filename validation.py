"""
validation.py

Parse iCSV metadata, create frictionless schema, run validation,
and produce human-friendly error reports.
"""

from __future__ import annotations
import csv
import json
import tempfile
import os
from typing import Tuple, Dict, List, Any, Optional
from frictionless import Resource

# Friendly suggestions for common frictionless error codes
ERROR_SUGGESTIONS = {
    "type-error": "Check that values in this column match the expected type (e.g., numbers, ISO datetimes).",
    "missing-cell": "Consider filling missing values, setting a nodata marker, or making the field optional.",
    "blank-row": "There is an unexpected blank row; remove or investigate formatting issues.",
    "extra-cell": "A row has too many cells: check delimiter or quoting.",
    "duplicate-label": "Duplicate column name: rename columns to unique names.",
    # fallback suggestion
    "default": "Inspect the flagged value and fix formatting or data entry issues.",
}


def parse_icsv_metadata(filepath: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Read METADATA and FIELDS sections and return (metadata_dict, fields_meta_dict).
    """
    metadata: Dict[str, str] = {}
    fields_meta: Dict[str, List[str]] = {}
    section: Optional[str] = None
    with open(filepath, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if line.strip() == "# [METADATA]":
                section = "metadata"
                continue
            if line.strip() == "# [FIELDS]":
                section = "fields"
                continue
            if line.strip() == "# [DATA]":
                break
            if line.startswith("#") and section:
                content = line.lstrip("#").strip()
                if "=" in content:
                    key, value = content.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if section == "metadata":
                        metadata[key] = value
                    else:
                        # we will split fields values later using the metadata delimiter
                        fields_meta[key] = [v.strip() for v in value.split("|")]  # default split, re-split later
    # if fields_meta used '|' but metadata says different delimiter, we'll re-split
    if "field_delimiter" in metadata:
        delim = metadata["field_delimiter"]
        corrected = {}
        for k, v in fields_meta.items():
            # join with '|' then split by delim to handle previous naive split
            joined = "|".join(v)
            corrected[k] = [x.strip() for x in joined.split(delim)]
        fields_meta = corrected
    return metadata, fields_meta


def check_metadata(metadata: Dict[str, str], fields_meta: Dict[str, List[str]]) -> List[str]:
    errors: List[str] = []
    # required keys for iCSV per your spec: field_delimiter is required; geometry/srid recommended
    if "field_delimiter" not in metadata or not metadata["field_delimiter"]:
        errors.append("Missing required metadata: field_delimiter")
    # fields list required
    if "fields" not in fields_meta:
        errors.append("Missing [FIELDS] 'fields' list")
    else:
        num = len(fields_meta["fields"])
        for key, values in fields_meta.items():
            if key != "fields" and values and len(values) != num:
                errors.append(f"Inconsistent count in '{key}': expected {num}, found {len(values)}")
    return errors


def _read_data_rows(filepath: str, delimiter: str) -> Tuple[List[str], List[List[str]]]:
    """
    Extract header and rows from DATA section using delimiter; header returned as list of field names.
    """
    in_data = False
    rows: List[List[str]] = []
    header: List[str] = []
    with open(filepath, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.strip() == "# [DATA]":
                in_data = True
                continue
            if not in_data:
                continue
            # skip commented lines inside data
            if line.strip().startswith("#"):
                continue
            if line.strip() == "":
                continue
            parts = [p for p in csv.reader([line], delimiter=delimiter)][0]
            if not header:
                header = [h.strip() for h in parts]
            else:
                rows.append(parts)
    return header, rows


def build_schema_from_metadata(fields_meta: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Build a frictionless-compatible schema dict from the FIELDS metadata.
    minimal: use names, types if present.
    """
    schema: Dict[str, Any] = {"fields": [], "missingValues": ["", "NA", "N/A", "null", "-999", "-999.0"]}
    fields = fields_meta.get("fields", [])
    types = fields_meta.get("types", [])
    description = fields_meta.get("description", [])
    min_vals = fields_meta.get("min", [])
    max_vals = fields_meta.get("max", [])

    for i, name in enumerate(fields):
        f = {"name": name}
        if i < len(types) and types[i]:
            f["type"] = types[i]
        else:
            f["type"] = "string"
        if i < len(description) and description[i]:
            f["description"] = description[i]
        constraints = {}
        if i < len(min_vals) and min_vals[i]:
            try:
                constraints["minimum"] = float(min_vals[i]) if "." in min_vals[i] else int(min_vals[i])
            except Exception:
                # might be datetime; leave as-is
                constraints["minimum"] = min_vals[i]
        if i < len(max_vals) and max_vals[i]:
            try:
                constraints["maximum"] = float(max_vals[i]) if "." in max_vals[i] else int(max_vals[i])
            except Exception:
                constraints["maximum"] = max_vals[i]
        if constraints:
            f["constraints"] = constraints
        schema["fields"].append(f)
    return schema


def _format_report(report) -> str:
    """
    Turn a frictionless report into a friendly text summary with suggestions.
    """
    lines = []
    if report.valid:
        lines.append("Data validation [OK]")
        return "\n".join(lines)

    lines.append("Data validation errors:")
    try:
        # flatten provides rows of issues
        for rownum, fieldnum, code, message in report.flatten(["rowNumber", "fieldNumber", "code", "message"]):
            suggestion = ERROR_SUGGESTIONS.get(code, ERROR_SUGGESTIONS["default"])
            lines.append(f"  Row {rownum or '?'}, Col {fieldnum or '?'} [{code}]: {message}")
            lines.append(f"    Suggestion: {suggestion}")
    except Exception:
        # fallback: iterate over errors attribute
        for error in report.flatten():
            lines.append(str(error))
    return "\n".join(lines)


def validate_icsv(infile: str, out_report: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate an iCSV file. Returns (valid, report_path).
    Produces:
      - metadata check results (in-memory)
      - schema built from FIELDS metadata
      - validation of DATA section using frictionless
    """
    if not out_report:
        out_report = infile.replace(".icsv", "_data_report.txt")

    metadata, fields_meta = parse_icsv_metadata(infile)
    meta_errors = check_metadata(metadata, fields_meta)
    meta_report_path = infile.replace(".icsv", "_metadata_report.txt")
    with open(meta_report_path, "w", encoding="utf-8") as mf:
        if meta_errors:
            for e in meta_errors:
                mf.write(f"ERROR: {e}\n")
            mf.write("\nPlease fix metadata issues above.\n")
        else:
            mf.write("OK: Metadata checks passed.\n")

    if meta_errors:
        # If metadata is invalid, produce report and stop
        with open(out_report, "w", encoding="utf-8") as rf:
            rf.write("Validation aborted due to metadata errors. See metadata report.\n")
        return False, out_report

    # Use delimiter from metadata
    delim = metadata.get("field_delimiter", "|")
    header, data_rows = _read_data_rows(infile, delim)

    # Build schema from fields metadata
    schema = build_schema_from_metadata(fields_meta)

    # Write a temporary CSV including a header so Frictionless can read it easily
    with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="", encoding="utf-8", suffix=".csv") as tmp:
        tmp_name = tmp.name
        writer = csv.writer(tmp, delimiter=delim)
        if header:
            writer.writerow(header)
        else:
            # fallback to fields_meta names
            writer.writerow(fields_meta.get("fields", []))
        for r in data_rows:
            # normalize row length
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            elif len(r) > len(header):
                r = r[: len(header)]
            writer.writerow(r)

    try:
        resource = Resource(path=tmp_name, schema=schema)
        report = resource.validate()
        summary = _format_report(report)
        with open(out_report, "w", encoding="utf-8") as rf:
            rf.write(summary)
    except Exception as e:
        with open(out_report, "w", encoding="utf-8") as rf:
            rf.write(f"Validation failed: {e}\n")
        return False, out_report
    finally:
        try:
            os.remove(tmp_name)
        except Exception:
            pass

    return report.valid, out_report
