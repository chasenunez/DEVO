"""Validation utilities that wrap frictionless to validate the DATA section of an iCSV.

The code uses the frictionless library to perform validation. Because frictionless is an
external dependency we do not import it at module import time to avoid import errors in
environments where it is not present. The function `validate_icsv` will import frictionless
when it is called and raise a friendly error if frictionless is not installed.
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def parse_icsv_header(filepath: str) -> Tuple[Dict[str, str], Dict[str, List[str]], str]:
    metadata = {}
    fields_meta = {}
    field_delimiter = ","
    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            l = line.rstrip("\n")
            if l.strip() == "# [DATA]":
                break
            if l.startswith("#"):
                content = l.lstrip("#").strip()
                if content.startswith("["):
                    continue
                if "=" in content:
                    k, v = content.split("=", 1)
                    k = k.strip(); v = v.strip()
                    if k in ("fields", "types", "min", "max", "missing_count"):
                        # capture raw; split later when we know delimiter
                        fields_meta[k] = [v]
                    else:
                        metadata[k] = v
    field_delimiter = metadata.get("field_delimiter", ",")
    # join and split the fields_meta entries
    parsed = {k: [s.strip() for s in "".join(v).split(field_delimiter)] for k, v in fields_meta.items()}
    return metadata, parsed, field_delimiter


def extract_data_to_csv(icsv_path: str, out_csv: str, field_delimiter: str) -> int:
    written = 0
    with open(icsv_path, "r", encoding="utf-8") as src, open(out_csv, "w", encoding="utf-8", newline="") as tgt:
        writer = csv.writer(tgt, delimiter=field_delimiter)
        in_data = False
        for line in src:
            if line.strip() == "# [DATA]":
                in_data = True
                continue
            if in_data:
                if line.strip() and not line.lstrip().startswith("#"):
                    row = list(csv.reader([line.strip()], delimiter=field_delimiter))[0]
                    writer.writerow(row)
                    written += 1
    return written


def validate_with_frictionless(clean_csv: str, schema_path: str):
    try:
        from frictionless import Resource
    except Exception as e:
        raise RuntimeError("The 'frictionless' package is required to run validation. Please install it (pip install frictionless)") from e
    resource = Resource(path=clean_csv, schema=schema_path)
    report = resource.validate()
    return report


def validate_icsv(icsv_path: str, schema_path: Optional[str] = None, outdir: str = "DEVO_output") -> Tuple[str, bool]:
    metadata, fields_meta, field_delim = parse_icsv_header(icsv_path)
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)
    tmp_csv = outdir_path / f"{Path(icsv_path).stem}_tmp.csv"
    rows = extract_data_to_csv(icsv_path, str(tmp_csv), field_delim)
    if not schema_path:
        candidate = Path(icsv_path).with_name(Path(icsv_path).stem + "_schema.json")
        if candidate.exists():
            schema_path = str(candidate)
        else:
            raise FileNotFoundError("No schema provided and none found next to the iCSV.")
    report = validate_with_frictionless(str(tmp_csv), schema_path)
    report_path = outdir_path / f"{Path(icsv_path).stem}_DEVO_report.md"
    # Minimal markdown writer (user-friendly summary)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(f"# DEVO Validation Report: {Path(icsv_path).name}\n\n")
        fh.write(f"Valid: {report.valid}\n\n")
        fh.write("## Flattened errors (first 50):\n")
        flat = report.flatten(["rowNumber", "fieldNumber", "fieldName", "code", "message"])[:50]
        fh.write(json.dumps(flat, indent=2))
    # cleanup
    try:
        tmp_csv.unlink()
    except Exception:
        pass
    return str(report_path), report.valid
