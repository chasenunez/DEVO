"""Command-line front-end for DEVO.

Three subcommands:
  enrich   — CSV → iCSV + schema
  validate — iCSV + schema → report
  run      — enrich then validate (or just validate if input is already .icsv)

Exit codes: 0 = success, 1 = validation failed (data errors), 2 = usage/runtime error.
"""
from __future__ import annotations

import argparse
import sys

from .enrich import ICSVEnricher
from .exceptions import DEVOError
from .validate import validate_icsv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="devo", description="DEVO — CSV to iCSV enrichment and validation")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_enrich = sub.add_parser("enrich", help="Convert a CSV to iCSV + Frictionless schema")
    p_enrich.add_argument("infile", help="Input CSV file")
    p_enrich.add_argument("--out", default="DEVO_output", metavar="DIR", help="Output directory")
    p_enrich.add_argument("--delimiter", metavar="CHAR", help="Force input delimiter")
    p_enrich.add_argument("--nodata", metavar="VALUE", help="Force nodata sentinel")
    p_enrich.add_argument("--app", metavar="PROFILE", help="iCSV application profile")

    p_val = sub.add_parser("validate", help="Validate an iCSV against its schema")
    p_val.add_argument("infile", help="Input .icsv file")
    p_val.add_argument("--schema", metavar="PATH", help="Schema JSON path (default: auto-discover)")
    p_val.add_argument("--out", default="DEVO_output", metavar="DIR", help="Output directory")

    p_run = sub.add_parser(
        "run",
        help="Enrich then validate. If input is already .icsv, skips enrichment.",
    )
    p_run.add_argument("infile", help="Input CSV or iCSV file")
    p_run.add_argument("--out", default="DEVO_output", metavar="DIR", help="Output directory")
    p_run.add_argument("--delimiter", metavar="CHAR", help="Force input delimiter (CSV only)")
    p_run.add_argument("--nodata", metavar="VALUE", help="Force nodata sentinel (CSV only)")
    p_run.add_argument("--app", metavar="PROFILE", help="iCSV application profile (CSV only)")

    return p


def main(argv=None) -> None:
    p = build_parser()
    args = p.parse_args(argv)

    try:
        if args.cmd == "enrich":
            enr = ICSVEnricher()
            icsv, schema = enr.make_icsv(
                args.infile, args.out,
                user_delimiter=args.delimiter,
                nodata_override=args.nodata,
                application_profile=args.app,
            )
            print(f"[OK] {icsv}")
            print(f"[OK] {schema}")

        elif args.cmd == "validate":
            report, valid = validate_icsv(
                args.infile, schema_path=args.schema, outdir=args.out
            )
            print(f"[{'OK' if valid else 'FAIL'}] Report: {report}")
            if not valid:
                sys.exit(1)

        elif args.cmd == "run":
            from pathlib import Path
            from ._parser import is_icsv

            inpath = Path(args.infile)
            if is_icsv(inpath):
                # Already enriched — skip enrichment, use sibling schema if it exists
                icsv = str(inpath)
                schema = str(inpath.with_name(inpath.stem + "_schema.json"))
                print(f"[OK] Input is already an iCSV — skipping enrichment.")
            else:
                enr = ICSVEnricher()
                icsv, schema = enr.make_icsv(
                    args.infile, args.out,
                    user_delimiter=args.delimiter,
                    nodata_override=args.nodata,
                    application_profile=args.app,
                )
                print(f"[OK] Enriched: {icsv}")

            report, valid = validate_icsv(icsv, schema_path=schema, outdir=args.out)
            print(f"[{'OK' if valid else 'FAIL'}] Report: {report}")
            if not valid:
                sys.exit(1)

    except (DEVOError, FileNotFoundError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
