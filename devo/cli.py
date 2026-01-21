"""Thin command-line front-end for DEVO.

It mirrors the earlier single-file CLI and calls the package modules.
"""
import argparse
from .enrich import ICSVEnricher
from .validate import validate_icsv


def build_parser():
    p = argparse.ArgumentParser(prog="devo")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_enrich = sub.add_parser("enrich")
    p_enrich.add_argument("infile")
    p_enrich.add_argument("--out", default="DEVO_output")
    p_enrich.add_argument("--delimiter")
    p_enrich.add_argument("--nodata")
    p_enrich.add_argument("--app")

    p_val = sub.add_parser("validate")
    p_val.add_argument("infile")
    p_val.add_argument("--schema")
    p_val.add_argument("--out", default="DEVO_output")

    p_run = sub.add_parser("run")
    p_run.add_argument("infile")
    p_run.add_argument("--out", default="DEVO_output")
    p_run.add_argument("--delimiter")
    p_run.add_argument("--nodata")
    p_run.add_argument("--app")
    return p


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    if args.cmd == "enrich":
        enr = ICSVEnricher()
        icsv, schema = enr.make_icsv(args.infile, args.out, user_delimiter=args.delimiter, nodata_override=args.nodata, application_profile=args.app)
        print("Wrote:", icsv, schema)
    elif args.cmd == "validate":
        rp, valid = validate_icsv(args.infile, schema_path=args.schema, outdir=args.out)
        print("Report:", rp)
    elif args.cmd == "run":
        enr = ICSVEnricher()
        icsv, schema = enr.make_icsv(args.infile, args.out, user_delimiter=args.delimiter, nodata_override=args.nodata, application_profile=args.app)
        rp, valid = validate_icsv(icsv, schema_path=schema, outdir=args.out)
        print("Run complete. Report:", rp)

if __name__ == "__main__":
    main()
