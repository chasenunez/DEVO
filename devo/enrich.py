"""CSV -> iCSV enrichment utilities

This module contains a class `ICSVEnricher` that is a cleaned and slightly refactored
version of the single-file implementation. Its responsibilities:
- detect input delimiter and nodata placeholder
- infer types and constraints
- produce a Frictionless-compatible schema JSON
- write an iCSV file with METADATA, FIELDS and DATA sections

Note: frictionless is not used during the creation step here — it simply builds the
schema dict and writes it as JSON so frictionless may later load it for validation.
"""

from __future__ import annotations
import csv
import json
import os
from itertools import islice
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

COMMON_MISSING = {"", "NA", "N/A", "na", "n/a", "NULL", "null", "nan", "NaN", "-999", "-999.0", "-999.000000"}
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


class ICSVEnricher:
    def __init__(self, nodata_candidates=None):
        self.nodata_candidates = set(nodata_candidates or COMMON_MISSING)

    def detect_delimiter(self, sample: str) -> str:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[",", "|", ";", ":", "\t", "/"])
            return dialect.delimiter
        except csv.Error:
            return ","

    def load_rows(self, path: str, user_delimiter: Optional[str] = None) -> Tuple[List[str], List[List[str]]]:
        """Read the CSV, detect delimiter and return (header, rows).

        header: list of column names (first row)
        rows: list of rows (each a list of strings)
        """
        # Read a small sample safely (works if file has <10 lines)
        sample = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                sample = "".join(list(islice(fh, 10)))
        except FileNotFoundError:
            raise

        delim = user_delimiter or self.detect_delimiter(sample)
        rows: List[List[str]] = []
        header: List[str] = []
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.reader(fh, delimiter=delim)
            for i, r in enumerate(reader):
                if i == 0:
                    header = [c.strip() for c in r]
                else:
                    rows.append([c for c in r])
        return header, rows


    def detect_nodata(self, rows: List[List[str]]) -> str:
        counts = {}
        for r in rows:
            for c in r:
                if c in self.nodata_candidates:
                    counts[c] = counts.get(c, 0) + 1
        if not counts:
            return ""
        return max(counts.items(), key=lambda x: x[1])[0]

    def infer_column_type(self, values: List[str]) -> str:
        pruned = [v.strip() for v in values if v.strip() not in self.nodata_candidates]
        if not pruned:
            return "string"
        is_int = all(INT_RE.match(v) for v in pruned)
        is_float = all(INT_RE.match(v) or FLOAT_RE.match(v) for v in pruned)
        is_dt = all(self._is_datetime(v) for v in pruned)
        if is_int:
            return "integer"
        if is_float:
            return "number"
        if is_dt:
            return "datetime"
        return "string"

    def _is_datetime(self, s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        try:
            datetime.fromisoformat(s)
            return True
        except (ValueError, TypeError):
            return False

    def build_schema(self, header: List[str], rows: List[List[str]], nodata: str) -> Dict[str, Any]:
        # normalize rows
        norm = []
        for r in rows:
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            elif len(r) > len(header):
                r = r[: len(header)]
            norm.append([str(x).strip() for x in r])
        cols = list(zip(*norm)) if norm else [[] for _ in header]
        fields = []
        for i, name in enumerate(header):
            vals = list(cols[i]) if cols else []
            t = self.infer_column_type(vals)
            field = {"name": name, "type": t}
            pruned = [v for v in vals if v not in self.nodata_candidates and v != ""]
            missing_count = sum(1 for v in vals if v in self.nodata_candidates or v == "")
            if t in ("integer", "number") and pruned:
                try:
                    nums = [int(x) if t == "integer" else float(x) for x in pruned]
                    field["min"] = min(nums)
                    field["max"] = max(nums)
                    field.setdefault("constraints", {})
                    field["constraints"]["minimum"] = field["min"]
                    field["constraints"]["maximum"] = field["max"]
                except (ValueError, TypeError):
                    pass
            if t == "datetime" and pruned:
                try:
                    dts = [datetime.fromisoformat(x) for x in pruned if self._is_datetime(x)]
                    if dts:
                        field.setdefault("constraints", {})
                        field["min"] = min(dts).isoformat()
                        field["max"] = max(dts).isoformat()
                        field["constraints"]["minimum"] = field["min"]
                        field["constraints"]["maximum"] = field["max"]
                except (ValueError, TypeError):
                    pass
            if pruned and missing_count == 0:
                field.setdefault("constraints", {})
                field["constraints"]["required"] = True
            field["missing_count"] = missing_count
            fields.append(field)
        schema = {"fields": fields, "missingValues": list(self.nodata_candidates)}
        return schema

    def write_icsv(self, outpath: str, header: List[str], rows: List[List[str]], metadata: Dict[str, str], fields_meta_lines: List[str], field_delimiter: str):
        Path(outpath).parent.mkdir(parents=True, exist_ok=True)
        with open(outpath, "w", encoding="utf-8", newline="") as fh:
            fh.write("# iCSV 1.0 UTF-8\n")
            fh.write("# [METADATA]\n")
            for k, v in metadata.items():
                fh.write(f"# {k} = {v}\n")
            fh.write("\n")
            fh.write("# [FIELDS]\n")
            for l in fields_meta_lines:
                fh.write(f"# {l}\n")
            fh.write("\n")
            fh.write("# [DATA]\n")
            writer = csv.writer(fh, delimiter=field_delimiter)
            writer.writerow(header)
            for r in rows:
                if len(r) < len(header):
                    r = r + [""] * (len(header) - len(r))
                writer.writerow(r)

    def make_icsv(self, infile: str, outdir: str, user_delimiter: Optional[str] = None, nodata_override: Optional[str] = None, application_profile: Optional[str] = None) -> Tuple[str, str]:
        header, rows = self.load_rows(infile, user_delimiter)
        detected = user_delimiter or self.detect_delimiter("\n".join(["|".join(r) for r in rows[:5]]))
        icsv_delim = detected if detected != "," else "|"
        nodata = nodata_override if nodata_override is not None else self.detect_nodata(rows)
        schema = self.build_schema(header, rows, nodata)
        # metadata
        metadata = {
            "field_delimiter": icsv_delim,
            "rows": str(len(rows)),
            "columns": str(len(header)),
            "creation_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator": "DEVO (python)"
        }
        if nodata:
            metadata["nodata"] = nodata
        fields_lines = [
            f"fields = {icsv_delim.join(header)}",
            f"types = {icsv_delim.join([f.get('type','') for f in schema['fields']])}",
            f"min = {icsv_delim.join([str(f.get('min','')) for f in schema['fields']])}",
            f"max = {icsv_delim.join([str(f.get('max','')) for f in schema['fields']])}",
            f"missing_count = {icsv_delim.join([str(f.get('missing_count','')) for f in schema['fields']])}",
        ]
        outdir_path = Path(outdir)
        outdir_path.mkdir(parents=True, exist_ok=True)
        base = Path(infile).stem
        icsv_path = outdir_path / f"{base}.icsv"
        schema_path = outdir_path / f"{base}_schema.json"
        self.write_icsv(str(icsv_path), header, rows, metadata, fields_lines, icsv_delim)
        with open(schema_path, "w", encoding="utf-8") as fh:
            json.dump(schema, fh, indent=2, ensure_ascii=False)
        return str(icsv_path), str(schema_path)
