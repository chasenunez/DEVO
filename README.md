
# DEVO 
<img title="whip it" alt="whip it good"  height="75" src="/images/DEVO_Pixels_1.webp"><br>

## Table of contents

* [File structure](#file-structure)
* [iCSV format](#icsv-format-quick-overview)
* [CLI usage](#cli-usage)
* [Python API](#python-api)
* [Configuration](#configuration)
* [Example run (end-to-end)](#example-run-end-to-end)
* [Troubleshooting & common errors](#troubleshooting--common-errors)
* [Contributing](#contributing)
* [License](#license)


Data Enrichment and Validation Operator (DEVO) provides a simple tool and library to enrich CSV files into the standardized “iCSV” format (a comma separated values file with embedded metadata) and then validate the data using the Frictionless framework. More specifically, it will:

* Convert `*.csv` → `*.icsv` (iCSV format with `# [METADATA]`, `# [FIELDS]`, `# [DATA]`).
* Infer Frictionless-compatible schema (`*_schema.json`) automatically.
* Validate data with Frictionless and produce human-friendly text reports (`*_data_report.txt`, `*_metadata_report.txt`).
* Configurable via YAML/JSON config file or CLI flags.
* Lightweight, documented, with tests via `pytest`.
* Includes helpful suggestions for common error codes (type mismatches, missing cells, extra cells, duplicate labels).

It supports two modes: if given a plain `.csv`, DEVO will infer metadata and output an `.icsv` (with METADATA, FIELDS, and DATA sections) and then validate it; if given an existing `.icsv`, DEVO will skip enrichment and only perform validation. 
The Frictionless library is used to infer schema and validate data, producing detailed, user-friendly error reports.

The [validation](https://gitlab.eawag.ch/chase.nunez/envidat_frictionless) and [enrichment](https://gitlab.eawag.ch/chase.nunez/csv_enrichment) code were developed in separate repositories.

## File structure

```
devo/                        # package
├── __init__.py
├── cli.py
├── enrichment.py
├── validation.py
├── utils.py
config_example.yaml
README.md
pyproject.toml
setup.py
tests/
├── test_enrichment.py
└── test_validation.py
```

- `cli.py` contains the `main()` function or entry-point logic. It detects the input type (CSV or iCSV), dispatches to the enrichment and/or validation routines, and writes the outputs.

- `enrichment.py` implements CSV reading and metadata inference, building the iCSV structure and writing it out.

- `validation.py` implements parsing the METADATA/FIELDS from an iCSV, constructing a Frictionless schema, running the validation, and writing a readable report.

- `utils.py` (optional) can hold shared helpers (e.g. a config file loader using `python-dateutil` for datetime parsing).

- `tests/` contains `pytest` tests for each module to ensure correctness.

- `setup.py` (or pyproject.toml) contains the packaging instructions (see below).

- `README.md` explains DEVO’s purpose and usage to end users (recommended by packaging best practices.



## iCSV format (quick overview)

DEVO follows this structure for iCSV files:

```
# iCSV 1.0 UTF-8
# [METADATA]
# key = value
# ...

# [FIELDS]
# fields = col1|col2|col3
# types = datetime|number|string
# min = ...
# max = ...
# missing_count = ...
# description = ...

# [DATA]
col1|col2|col3
row1col1|row1col2|row1col3
...
```

* Metadata and fields lines must be prepended with `#`.
* The `field_delimiter` is stored in METADATA and governs how the DATA section is parsed.
* DEVO writes a header row in the DATA section for compatibility with tools; remove it if you require strict iCSV formatting (configurable).


## CLI usage

Basic usage:

```bash
devo path/to/file.csv
# or validate an existing iCSV:
devo path/to/file.icsv
```

CLI flags:

```
usage: devo [-h] [--config CONFIG] [--delimiter DELIMITER]
            [--nodata NODATA] [--app APP] [--schema-out SCHEMA_OUT]
            [--out OUT]
            infile
```

Key options:

* `--config / -c PATH` : YAML or JSON config file path.
* `--delimiter / -d` : force input delimiter (auto-detected by default).
* `--nodata` : force the nodata placeholder.
* `--app` : application profile for the iCSV first line.
* `--schema-out` : write schema to a custom path.
* `--out` : specify output iCSV path.

Example (force pipe delimiter and nodata):

```bash
devo sample.csv --delimiter '|' --nodata -999
```

Outputs (default, per input `data.csv`):

* `data.icsv` — the enriched iCSV file.
* `data_schema.json` — inferred Frictionless schema.
* `data_metadata_report.txt` — metadata consistency checks.
* `data_data_report.txt` — validation summary & errors.


## Python API

Import and use programmatically.

```python
from devo.enrichment import make_icsv_from_csv
from devo.validation import validate_icsv

icsv_path, schema_path = make_icsv_from_csv("sample.csv")
valid, report_path = validate_icsv(icsv_path)

print("iCSV:", icsv_path)
print("schema:", schema_path)
print("valid:", valid)
print("report:", report_path)
```

Function summaries:

* `make_icsv_from_csv(infile, out_icsv=None, out_schema=None, user_delimiter=None, nodata_override=None, application_profile=None)`
  Returns `(out_icsv_path, out_schema_path)`.

* `validate_icsv(infile, out_report=None)`
  Returns `(is_valid_bool, out_report_path)`.


## Configuration

DEVO supports a config file (YAML or JSON). Example `devo.yaml`:

```yaml
application_profile: "DEVO_DEFAULT"
field_delimiter: "|"
nodata: "-999"
out_icsv: null
schema_out: null
```

Load via `--config devo.yaml` or place values as CLI flags (CLI flags take precedence).


## Example run (end-to-end)

Create a sample CSV:

```csv
# file: sample_valid.csv
timestamp,ta,rh
2020-01-01T00:00:00,10,0.5
2020-01-01T01:00:00,12,0.55
```

Run:

```bash
devo sample_valid.csv
```

Expected files:

* `sample_valid.icsv` — contains METADATA, FIELDS, DATA
* `sample_valid_schema.json` — inferred schema
* `sample_valid_metadata_report.txt` — metadata OK message
* `sample_valid_data_report.txt` — contains `Data validation [OK]` for valid data

For invalid sample:

```csv
# file: sample_bad.csv
timestamp,ta
2020-01-01T00:00:00,10
2020-01-01T01:00:00,not_a_number
```

Run:

```bash
devo sample_bad.csv
# data report will contain a type-error and a friendly suggestion
```

Open the report:

```bash
less sample_bad_data_report.txt
```

## Troubleshooting & common errors

### `ModuleNotFoundError: No module named 'devo'`

* Likely cause: you ran `pip install -e .` from the wrong directory, or the project root is misstructured (package folder and packaging metadata must not be the same directory).
* Fix:

  * Ensure `pyproject.toml` / `setup.py` are in the project root and there is a **subfolder** `devo/` containing `__init__.py`.
  * Reinstall: `pip uninstall -y devo && pip install -e .`

### `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`

* Cause: code used Python 3.10 union `str | None` syntax but running on Python 3.9.
* Fix: Use `Optional[str]` or upgrade Python to 3.10+.

### `ValueError: Invalid suffix '_schema.json'`

* Cause: calling `Path.with_suffix('_schema.json')` (invalid suffix).
* Fix: use `infile.with_name(infile.stem + "_schema.json")` or `infile.with_suffix('.json')` and assemble filename.

### Delimiter issues

* If DEVO mis-detects delimiter or your data uses a special delimiter, pass `--delimiter` or set `field_delimiter` in the config file.

### Validation exceptions from Frictionless

* Inspect the generated `*_schema.json` and `*_data_report.txt`. Adjust schema or clean data accordingly.

If an error persists, collect the traceback and the following diagnostics and open an issue (or paste here):

```bash
python -V
which python          # or .venv/bin/python -c "import sys; print(sys.executable)"
pip show devo
ls -la
ls -la devo
sed -n '1,160p' .venv/bin/devo
```


## Contributing

Contributions welcome!

* Open an issue to discuss larger changes.
* For small fixes, open a PR against `main`.
* Tests: add `pytest` tests under `tests/`.
* Formatting: use `black` and `isort`.
* CI suggestion: GitHub Actions that runs tests across Python 3.9–3.11, builds package, and runs linters.

Suggested workflow:

```bash
git clone <repo>
git checkout -b feature/your-feature
pip install -e .[dev]
pytest
# make changes, add tests, open PR
```


## License

DEVO is distributed under the **MIT License**. See `LICENSE` for full text.
