"""CSV → iCSV enrichment.

Public API: ICSVEnricher().make_icsv(infile, outdir, ...)
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ._infer import COMMON_MISSING, VALID_ICSV_DELIMITERS, infer_type
from ._parser import is_icsv
from ._schema import build_frictionless_schema, compute_col_stats
from .exceptions import EnrichError


def _detect_delimiter(sample: str) -> str:
    """Sniff a delimiter from a text sample; fall back to comma on failure."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",|;:\t/")
        return dialect.delimiter
    except csv.Error:
        return ","


def _to_icsv_delimiter(detected: str) -> str:
    """
    Map the detected input delimiter to a valid iCSV output delimiter.
    - Comma → pipe: avoids ambiguity with the ',' separator inside metadata lines.
    - Tab → pipe: tab is not in the iCSV spec's allowed set [,|/:;].
    - Anything else not in the spec → pipe as a safe default.
    """
    if detected not in VALID_ICSV_DELIMITERS:
        return "|"
    return "|" if detected == "," else detected


def _detect_geometry(header: list[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Heuristic spatial-column detection.
    Returns (geometry_value, srid_value) or (None, None) when no spatial columns are found.
    Per Q1: geometry and srid are written only when spatial columns are detected.
    """
    lower = [h.lower() for h in header]
    if "geometry" in lower:
        idx = lower.index("geometry")
        return f"column:{header[idx]}", None
    lat_idx = lon_idx = None
    for i, h in enumerate(lower):
        if h in ("lat", "latitude"):
            lat_idx = i
        if h in ("lon", "lng", "longitude"):
            lon_idx = i
    if lat_idx is not None and lon_idx is not None:
        return f"column:{header[lat_idx]},{header[lon_idx]}", "EPSG:4326"
    return None, None


class ICSVEnricher:
    def __init__(self, nodata_candidates: Optional[set[str]] = None):
        self.missing: frozenset[str] = (
            frozenset(nodata_candidates) if nodata_candidates else COMMON_MISSING
        )

    def _load_rows(
        self,
        path: Path,
        user_delimiter: Optional[str],
    ) -> tuple[list[str], list[list[str]], str]:
        """
        Read a CSV in a single pass: collect a 10-line sample, sniff the delimiter,
        then parse all rows. Returns (header, rows, detected_delimiter).
        Using utf-8-sig to transparently strip a BOM if present.
        """
        lines: list[str] = []
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as e:
            raise EnrichError(f"Cannot read {path}: {e}") from e

        if not lines:
            raise EnrichError(f"{path.name}: file is empty")

        sample = "".join(lines[:10])
        delimiter = user_delimiter or _detect_delimiter(sample)

        header: list[str] = []
        rows: list[list[str]] = []
        for i, line in enumerate(lines):
            row = list(csv.reader([line], delimiter=delimiter))[0]
            if i == 0:
                header = [c.strip() for c in row]
            else:
                rows.append(row)

        if not header or all(c == "" for c in header):
            raise EnrichError(f"{path.name}: no usable header row found")

        return header, rows, delimiter

    def _detect_nodata(self, rows: list[list[str]]) -> str:
        """Return the most common missing-value sentinel seen in the data, or ''."""
        counts: dict[str, int] = {}
        for row in rows:
            for cell in row:
                if cell in self.missing:
                    counts[cell] = counts.get(cell, 0) + 1
        return max(counts, key=lambda k: counts[k]) if counts else ""

    def make_icsv(
        self,
        infile: str,
        outdir: str,
        user_delimiter: Optional[str] = None,
        nodata_override: Optional[str] = None,
        application_profile: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Convert a CSV to an iCSV + Frictionless schema JSON.
        Returns (icsv_path, schema_path) as strings.
        Raises EnrichError if the input is already an iCSV or cannot be read.
        """
        path = Path(infile)
        if is_icsv(path):
            raise EnrichError(
                f"{path.name} is already an iCSV file. "
                "Use 'devo validate' to validate it, or 'devo run' which handles both."
            )

        header, rows, detected_delim = self._load_rows(path, user_delimiter)
        icsv_delim = _to_icsv_delimiter(detected_delim)
        bad_names = [c for c in header if icsv_delim in c]
        if bad_names:
            raise EnrichError(
                f"Column name(s) contain the iCSV delimiter '{icsv_delim}': {bad_names}. "
                "Rename the columns or force a different delimiter with --delimiter."
            )
        nodata = nodata_override if nodata_override is not None else self._detect_nodata(rows)

        # Normalise all rows to header length once, then transpose to column lists.
        padded = []
        for row in rows:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            else:
                row = row[: len(header)]
            padded.append([c.strip() for c in row])

        col_values: list[list[str]] = (
            [[row[i] for row in padded] for i in range(len(header))]
            if padded else [[] for _ in header]
        )

        types = [infer_type(col, self.missing) for col in col_values]
        col_stats = [
            compute_col_stats(col_values[i], types[i], self.missing)
            for i in range(len(header))
        ]
        schema = build_frictionless_schema(header, col_stats, self.missing)

        geometry, srid = _detect_geometry(header)

        metadata: dict[str, str] = {
            "iCSV_version": "1.0",
        }
        if application_profile:
            metadata["application_profile"] = application_profile
        metadata["field_delimiter"] = icsv_delim
        metadata["rows"] = str(len(rows))
        metadata["columns"] = str(len(header))
        metadata["creation_date"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        if nodata:
            metadata["nodata"] = nodata
        if geometry:
            metadata["geometry"] = geometry
        if srid:
            metadata["srid"] = srid
        metadata["generator"] = "DEVO"

        def _join(vals: list) -> str:
            return icsv_delim.join("" if v is None else str(v) for v in vals)

        fields_lines = [
            f"fields = {_join(header)}",
            f"types = {_join(types)}",
            f"min = {_join(s['min'] for s in col_stats)}",
            f"max = {_join(s['max'] for s in col_stats)}",
            f"missing_count = {_join(s['missing_count'] for s in col_stats)}",
            f"description = {_join('' for _ in header)}",
        ]

        out = Path(outdir)
        out.mkdir(parents=True, exist_ok=True)
        base = path.stem
        icsv_path = out / f"{base}.icsv"
        schema_path = out / f"{base}_schema.json"

        self._write_icsv(icsv_path, metadata, fields_lines, header, padded, icsv_delim)

        with open(schema_path, "w", encoding="utf-8") as fh:
            json.dump(schema, fh, indent=2, ensure_ascii=False)

        return str(icsv_path), str(schema_path)

    def _write_icsv(
        self,
        path: Path,
        metadata: dict[str, str],
        fields_lines: list[str],
        header: list[str],
        rows: list[list[str]],
        field_delimiter: str,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("# iCSV 1.0 UTF-8\n")
            fh.write("# [METADATA]\n")
            for k, v in metadata.items():
                fh.write(f"# {k} = {v}\n")
            fh.write("\n")
            fh.write("# [FIELDS]\n")
            for line in fields_lines:
                fh.write(f"# {line}\n")
            fh.write("\n")
            fh.write("# [DATA]\n")
            writer = csv.writer(fh, delimiter=field_delimiter)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
