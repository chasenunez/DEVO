# DEVO
<img title="whip it" alt="you know you should" height="100" src="/images/DEVO_Pixels_1.webp">

**Data [Enrichment](https://github.com/chasenunez/DEVO_enricher) and [Validation Operator](https://github.com/chasenunez/DEVO_validator).** Takes a plain CSV, infers types and constraints, writes a self-documenting [iCSV](https://envidat.github.io/iCSV/) file plus a Frictionless schema, and validates the data against it.

If you give it a `.csv`, it enriches → schema → validates. If you give it an `.icsv`, it skips the enrichment step.

## Install

```bash
pip install -e .
```

Requires Python 3.9+ and `frictionless`.

## CLI

```bash
devo enrich   data.csv                    # write data.icsv + data_schema.json
devo validate data.icsv                   # validate against neighbouring schema
devo run      data.csv                    # do both in one go
```

Common flags: `--out DIR` (default `DEVO_output/`), `--delimiter`, `--nodata`, `--schema PATH`.

## What lands on disk

For input `data.csv`, after `devo run`:

| File | What |
|---|---|
| `DEVO_output/data.icsv` | iCSV with `# [METADATA]`, `# [FIELDS]`, `# [DATA]` |
| `DEVO_output/data_schema.json` | Frictionless schema |
| `DEVO_output/data_DEVO_report.md` | Validation report (read this) |

## Python API

```python
from devo.enrich import ICSVEnricher
from devo.validate import validate_icsv

icsv, schema = ICSVEnricher().make_icsv("sample.csv", "DEVO_output")
report_path, valid = validate_icsv(icsv, schema_path=schema)
```

## Files

```
devo/
├── cli.py        # argparse front-end (enrich / validate / run)
├── enrich.py     # CSV → iCSV + schema (ICSVEnricher class)
├── validate.py   # iCSV + schema → Frictionless validation report
└── webui.py      # tiny Flask demo for upload-and-validate
examples/sample.csv
tests/test_syntax_only.py
```

## Web UI (demo)

```bash
python -m flask --app devo.webui run
```

It's a one-page upload form. Useful for showing a researcher what the tool does without dragging them into a terminal.

## Limitations

- Type inference is conservative: integer → number → datetime → string. Mixed-format columns fall back to `string`.
- Datetime detection relies on `datetime.fromisoformat()` and a small list of common formats. Anything weirder needs a custom schema.
- Column descriptions are left blank; fill them in by hand or post-process the schema.

## License

MIT. See `LICENSE`.
