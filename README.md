# DEVO

DEVO converts CSV files into self-documented iCSV files (iCSV 1.0 UTF-8) and validates data with the Frictionless framework.

## Quickstart

Install (locally):

```bash
pip install -e .
```

Create an iCSV and schema from `examples/sample.csv`:

```bash
python3 -m devo.cli enrich examples/sample.csv --out DEVO_output
```

Validate an iCSV (produces markdown report):

```bash
python3 -m devo.cli validate DEVO_output/sample.icsv --out DEVO_output
```

Run the tiny web UI (simple Flask app):

```bash
export FLASK_APP=devo.webui
flask run
```

Open `http://127.0.0.1:5000` to upload a CSV and run enrich+validate.
