# DEVO
DEVO provides a simple command-line tool and library to enrich CSV files into the standardized “iCSV” format (with embedded metadata) and then validate the data using the Frictionless framework. 
It supports two modes: if given a plain `.csv`, DEVO will infer metadata and output an `.icsv` (with METADATA, FIELDS, and DATA sections) and then validate it; if given an existing `.icsv`, DEVO will skip enrichment and only perform validation. 
The Frictionless library is used to infer schema and validate data, producing detailed, user-friendly error reports.

DEVO is packaged for easy installation (on PyPI) with all dependencies (e.g. `frictionless`, `pytest`, `psycopg2-binary`, and `python-dateutil`) specified. The source code is modular and well-documented so users can adjust or extend metadata fields and validation rules. 
The package includes a CLI entry point so a novice user can run something like `devo mydata.csv` to get the enriched `.icsv` and a validation report.

## CSV Enrichment (iCSV Generation)

When given a plain `.csv` file, DEVO performs the following steps to create an `iCSV`:

- Read and sample the `CSV`. DEVO detects the delimiter (comma, tab, pipe, etc.) using Python’s `csv.Sniffer` or similar heuristics. DEVO then loads the header row (column names) and all data rows.

- Infer field types and statistics. For each column, DEVO proposes a simple type (integer, number, datetime, or string) by examining its values.

- DEVO uses regular expressions and date parsing (optionally via dateutil.parser) to classify values. For numeric columns it computes minimum and maximum; for datetime it computes min/max in ISO format. It also count missing values (common placeholders like NA, null, etc., are treated as “missing”). If a column has no missing values, DEVO marks it as required in the schema.

- DEVO builds lines for the METADATA section of the iCSV. This includes required keys like `iCSV_version = 1.0`, `field_delimiter = {delim}`, plus optional keys like `generator = DEVO <version>`, `c`reation_date`, `srid`, etc. (These follow the iCSV specification.) 

        For example:

        ```
        # iCSV 1.0 UTF-8
        # [METADATA]
        # iCSV_version = 1.0
        # field_delimiter = |
        # columns = 5
        # rows = 123
        # creation_date = 2025-10-01T12:34:56Z
        # nodata = -999
        # ...
        ```

        DEVO will include any user-provided hints (e.g. a --nodata argument or a config override) here.

- Build the fields section. Under # [FIELDS], DEVO lists `fields = name1|name2|...` (the column names) and other aligned lists (types, min, max, missing count, etc.) separated by the same delimiter. 

        For instance:
        ```
        # [FIELDS]
        # fields = timestamp|temperature|humidity
        # types = datetime|number|number
        # min = 2020-01-01T00:00:00|10.0|0.0
        # max = 2021-01-01T00:00:00|35.7|1.0
        # missing_count = 0|5|2
        ```

        This section fully describes each column (long_name, units, etc., could be added similarly if available).

- Write the iCSV file. According to the iCSV spec, the file starts with `# iCSV 1.0 UTF-8`, then `# [METADATA]` block, then `# [FIELDS]` block, then `# [DATA]`. In the DATA section, no lines begin with #. DEVO writes each data row (values separated by field_delimiter). Importantly, DEVO does not repeat the header row under `# [DATA]`—the fields are already defined in metadata. 

        For example:
        ```
        # [DATA]
        2020-01-01T00:00:00Z|15.2|0.85
        2020-01-01T01:00:00Z|15.1|0.87
        ...
        ```


## Data Validation (Schema & Error Reporting)

After enrichment (or if an .icsv is already provided), DEVO validates the data:

- Parse `METADATA` and `FIELDS`. DEVO will read the `iCSV` and extract the key metadata and field lists. For each # key = value line under `# [METADATA]` and `# [FIELDS]`, DEVO strips the leading # and parse keys and values. It verifies that required metadata (like field_delimiter, geometry, srid) and the fields list are present. Any problems here generate errors. Fun!

- Extract the `DATA` rows. DEVO locates the `# [DATA]` marker and reads all following lines (ignoring lines that start with #). It then splits each line using the discovered `field_delimiter` to get raw data values. (Note: DEVO dynamically uses the metadata’s delimiter.)

- Build a Frictionless schema. Using the field names from metadata and the parsed rows, DEVO constructs a `.JSON` table schema compatible with Frictionless. This schema lists each field’s name, type, format (if needed), description, and constraints (minimum, maximum, required, etc.).DEVO can reuse the same inference logic from enrichment: for each column, use the collected values to determine type and constraints. 

        For example:
        ```
        {
        "fields": [
            {"name": "timestamp", "type": "datetime", "format": "any", "constraints": {"required": true}},
            {"name": "temperature", "type": "number", "minimum": -50, "maximum": 60},
            {"name": "humidity", "type": "number", "minimum": 0, "maximum": 1}
        ],
        "missingValues": ["", "NA", "null"]
        }
        ```

- Validate with Frictionless. DEVO uses frictionless.Resource to validate the data rows against the schema. 

        For example:
        ```
        from frictionless import Resource

        # (Assume data_rows is a list of lists, and schema_json is the schema dict)
        # Write data_rows to a temporary CSV file or feed directly if supported:
        resource = Resource(path=temporary_csv_path, schema=schema_path_or_dict)
        report = resource.validate()
        ```

DEVO relies Frictionless to produces a report of all detected issues. 

For example, it will flag duplicate or blank column labels, type mismatches (e.g. text in a numeric field), missing cells, extra cells, etc. Each error includes the row number, field number, an error code (like type-error, missing-cell), and a descriptive message.

- Write a readable error report. DEVO collects the validation errors and formats them into a text report (`<input>_data_report.txt` by default). If the data is valid, DEVO will write `"Data validation [OK]"`. Otherwise, it will iterate over `report.flatten(...)` and write lines such as:

```
ERROR: Row 12, Column 3 [type-error]: Type error: cannot parse "abc" as integer
ERROR: Row 25, Column 1 [missing-cell]: Missing value in field "timestamp"
```

Since the error report will be the primary mode of user interface with this process, messages have been written to be kind and helpful. For example, if a numeric field has non-numeric text, the message suggests the value is wrong type. 
Frictionless’s messages are usually clear, but DEVO will also prepend tips like “Check that all values are valid numbers/date”.) The emphasis is on helping users locate and fix problems. 

## File structure

```
devo/                   # Top-level package directory
├── __init__.py         # Package initialization
├── cli.py              # Command-line interface
├── enrichment.py       # CSV → iCSV generation (metadata enrichment)
├── validation.py       # iCSV parsing → schema building → validation
├── utils.py            # (Optional: shared utility functions, e.g. config loading)
└── tests/              # Pytest test cases
setup.py                # Package metadata and dependencies
README.md               # Project description
config_example.yaml     # Example configuration file (optional)
# ...

```

- `cli.py` contains the `main()` function or entry-point logic. It detects the input type (CSV or iCSV), dispatches to the enrichment and/or validation routines, and writes the outputs.

- `enrichment.py` implements CSV reading and metadata inference, building the iCSV structure and writing it out.

- `validation.py` implements parsing the METADATA/FIELDS from an iCSV, constructing a Frictionless schema, running the validation, and writing a readable report.

- `utils.py` (optional) can hold shared helpers (e.g. a config file loader using `python-dateutil` for datetime parsing).

- `tests/` contains `pytest` tests for each module to ensure correctness.

- `setup.py` (or pyproject.toml) contains the packaging instructions (see below).

- `README.md` explains DEVO’s purpose and usage to end users (recommended by packaging best practices.