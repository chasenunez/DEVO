"""Command-line interface for DEVO."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .enrichment import make_icsv_from_csv
from .validation import validate_icsv, parse_icsv_metadata
from .utils import load_config


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="devo", description="DEVO: Data Enrichment and Validation Operator")
    p.add_argument("infile", help="Input CSV or iCSV file")
    p.add_argument("--config", "-c", help="Path to config file (YAML or JSON)", default=None)
    p.add_argument("--delimiter", "-d", help="Force input delimiter (autodetect otherwise)", default=None)
    p.add_argument("--nodata", help="Force nodata placeholder value", default=None)
    p.add_argument("--app", help="Optional application profile for iCSV firstline", default=None)
    p.add_argument("--schema-out", help="Path to write inferred schema JSON", default=None)
    p.add_argument("--out", help="Output iCSV path (for CSV input)", default=None)
    args = p.parse_args(argv)

    cfg = load_config(args.config)

    infile = Path(args.infile)
    if not infile.exists():
        print(f"[!] File not found: {infile}")
        return 2

    # If infile ends with .csv -> run enrichment then validation
    if infile.suffix.lower() == ".csv":
        out_icsv = args.out or cfg.get("out_icsv") or str(infile.with_suffix(".icsv"))
        out_schema = args.schema_out or cfg.get("schema_out") or str(infile.with_suffix("_schema.json"))
        print(f"[i] Enriching CSV -> {out_icsv}")
        try:
            icsv_path, schema_path = make_icsv_from_csv(
                infile=str(infile),
                out_icsv=out_icsv,
                out_schema=out_schema,
                user_delimiter=args.delimiter or cfg.get("field_delimiter"),
                nodata_override=args.nodata or cfg.get("nodata"),
                application_profile=args.app or cfg.get("application_profile"),
            )
            print(f"[OK] iCSV written: {icsv_path}")
            print(f"[OK] Schema written: {schema_path}")
        except Exception as exc:
            print(f"[!] Enrichment failed: {exc}")
            return 3
        # continue to validation step on the produced icsv
        target_icsv = icsv_path
    elif infile.suffix.lower() == ".icsv":
        target_icsv = str(infile)
    else:
        print("[!] Unsupported file type. Provide a .csv or .icsv")
        return 4

    print(f"[i] Validating iCSV: {target_icsv}")
    try:
        valid, report_path = validate_icsv(target_icsv)
        if valid:
            print(f"[OK] Validation passed. Report: {report_path}")
        else:
            print(f"[!] Validation found issues. See: {report_path}")
            # also print metadata report path
            meta_report = target_icsv.replace(".icsv", "_metadata_report.txt")
            print(f"[i] Metadata report: {meta_report}")
    except Exception as exc:
        print(f"[!] Validation failed: {exc}")
        return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
