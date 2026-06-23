"""Canonical iCSV header parser — single implementation shared by enricher and validator.

Parses [METADATA] and [FIELDS] sections from iCSV files per the iCSV 1.0 spec.
Stops at # [DATA] and does not read data rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .exceptions import ParseError


@dataclass
class ICSVHeader:
    metadata: dict[str, str]
    fields_meta: dict[str, list[str]]
    field_delimiter: str


def is_icsv(path: Path) -> bool:
    """Return True if the file's first line marks it as an iCSV file."""
    try:
        # utf-8-sig strips the BOM if present
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.readline().strip().startswith("# iCSV")
    except (OSError, UnicodeDecodeError):
        return False


def parse_header(path: Path) -> ICSVHeader:
    """
    Parse [METADATA] and [FIELDS] sections of an iCSV file.

    field_delimiter is read from metadata before the FIELDS section is split,
    so key order in the file does not matter — the correct delimiter is always used.
    Raises ParseError if the file is unreadable or has no [METADATA] section.
    """
    metadata: dict[str, str] = {}
    raw_fields: dict[str, str] = {}  # key → unsplit value string; split after delimiter known
    section: str | None = None

    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                stripped = line.rstrip("\r\n")

                if not stripped.startswith("#"):
                    continue

                content = stripped.lstrip("#").strip()

                if content == "[METADATA]":
                    section = "metadata"
                    continue
                if content == "[FIELDS]":
                    section = "fields"
                    continue
                if content == "[DATA]":
                    break

                # Skip blank comment lines and section headers
                if not content or "=" not in content or section is None:
                    continue

                key, _, val = content.partition("=")
                key = key.strip()
                val = val.strip()

                if section == "metadata":
                    metadata[key] = val
                else:
                    raw_fields[key] = val

    except OSError as e:
        raise ParseError(f"Cannot read {path}: {e}") from e

    if not metadata:
        raise ParseError(f"{path.name}: no [METADATA] section found or file is empty")

    field_delimiter = metadata.get("field_delimiter", ",")
    fields_meta = {
        k: [v.strip() for v in raw.split(field_delimiter)]
        for k, raw in raw_fields.items()
    }

    return ICSVHeader(
        metadata=metadata,
        fields_meta=fields_meta,
        field_delimiter=field_delimiter,
    )
