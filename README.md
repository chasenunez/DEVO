# DEVO

DEVO takes a plain CSV, infers column types and statistics, and produces three output files:

| Output file | What it is |
|---|---|
| `data.icsv` | Self-documenting [iCSV](https://envidat.github.io/iCSV/) with embedded metadata |
| `data_schema.json` | [Frictionless Table Schema](https://specs.frictionlessdata.io/table-schema/) for data validation |
| `data_DEVO_report.txt` | Human-readable validation report (**start here**) |

Before uploading, confirm:

- [ ] `Valid: YES` in the report
- [ ] All `# types` entries match the real-world meaning of each column
- [ ] `# min` and `# max` values are physically plausible
- [ ] `# missing_count` values match your expectations
- [ ] No `[WARN]` lines in TYPE CONSISTENCY
- [ ] `# description` fields are filled in (if required by your data archive)
- [ ] The `.icsv` file and its `_schema.json` are both included in your upload

---

## Contents

1. [Installation](#1-installation)
2. [The Three Commands](#2-the-three-commands)
3. [Tutorial: From Messy CSV to Upload-Ready iCSV](#3-tutorial-from-messy-csv-to-upload-ready-icsv)
4. [Understanding the Validation Report](#4-understanding-the-validation-report)
5. [Understanding the iCSV Format](#5-understanding-the-icsv-format)
6. [Common Errors and How to Fix Them](#6-common-errors-and-how-to-fix-them)
7. [CLI Reference](#7-cli-reference)
8. [Python API](#8-python-api)

---

## 1. Installation

```bash
pip install py-devo
```

Requires Python 3.9 or later. The `frictionless` package is installed automatically.

To install from a local clone:

```bash
pip install -e .
```

Verify the installation:

```bash
devo --help
```

---

## 2. The Three Commands

```
devo run      data.csv     # enrich → validate → report (most common)
devo enrich   data.csv     # CSV → iCSV + schema only (no validation)
devo validate data.icsv    # validate an iCSV against its schema
```

All three write their outputs to `DEVO_output/` by default. Use `--out MY_DIR` to write elsewhere.

**Exit codes:** `0` = everything passed, `1` = validation found data errors, `2` = usage or file error.

---

## 3. Tutorial: From Messy CSV to Upload-Ready iCSV

This tutorial walks through a realistic scenario: environmental sensor data with two common problems. You will enrich the file, read the output to spot the problems, fix the source CSV, and confirm the corrected file is ready for upload.

### Step 1: The raw data (with errors)

Save the following as `sensor_data.csv`:

```csv
station_id,observation_date,temperature_c,humidity_pct,wind_speed_ms
S001,2024-01-15,21.4,65,3.2
S002,2024-01-15,MISSING,72,N/A
S003,2024-01-15,19.8,168,5.1
S004,2024-01-15,23.1,71,2.8
S005,2024-01-16,20.0,71,4.0
```

Two problems are hidden in this file:

- **Row 2, `temperature_c`**: the value `MISSING` is a custom nodata sentinel that DEVO does not recognise by default. DEVO will treat it as a real string value, which forces the entire column's inferred type to `string` instead of `number`.
- **Row 3, `humidity_pct`**: the value `168` is a data-entry error; relative humidity cannot exceed 100%. DEVO will not catch impossible domain values on its own, but the iCSV will expose the inflated maximum so you can spot it.

(Note: `N/A` in `wind_speed_ms` is fine; it is a recognised nodata sentinel and is handled correctly.)

---

### Step 2: First run

```bash
devo run sensor_data.csv
```

Terminal output:

```
[OK] Enriched: DEVO_output/sensor_data.icsv
[OK] Report: DEVO_output/sensor_data_DEVO_report.txt
```

The command exits with code `0` (success) because DEVO describes the data as it finds it; the schema it builds from the data will technically fit the data. Errors only appear in the report when the data contradicts the schema. Reading the outputs is how you find hidden problems.

---

### Step 3: Read the validation report

Open `DEVO_output/sensor_data_DEVO_report.txt`:

```
DEVO Validation Report
======================
File:  sensor_data.icsv
Date:  2024-01-20T10:35:22Z
Valid: YES

METADATA
----------------------------------------
[OK] All required metadata present.

TYPE CONSISTENCY
----------------------------------------
[OK]   station_id: declared=string, inferred=string
[OK]   observation_date: declared=datetime, inferred=datetime
[OK]   temperature_c: declared=string, inferred=string
[OK]   humidity_pct: declared=integer, inferred=integer
[OK]   wind_speed_ms: declared=number, inferred=number

DATA VALIDATION
----------------------------------------
[PASS] No data errors found.
```

**The report says `Valid: YES`.** But look at `temperature_c`: it is declared and inferred as `string`. Temperature readings should be numbers. The report is technically correct (the declared type matches the inferred type), but the inferred type is wrong because DEVO did not know that `MISSING` should be treated as a nodata sentinel.

The report alone is not enough. You also need to read the iCSV.

---

### Step 4: Read the iCSV to spot the problems

Open `DEVO_output/sensor_data.icsv`. The `# [FIELDS]` section is the most important part to review:

```
# [FIELDS]
# fields = station_id|observation_date|temperature_c|humidity_pct|wind_speed_ms
# types  = string|datetime|string|integer|number
# min    = |2024-01-15T00:00:00||65|2.8
# max    = |2024-01-16T00:00:00||168|5.1
# missing_count = 0|0|0|0|1
# description   = ||||
```

Scan each column from left to right:

| Column | Type | Min | Max | Missing | Problem? |
|---|---|---|---|---|---|
| `station_id` | string | — | — | 0 | No |
| `observation_date` | datetime | 2024-01-15 | 2024-01-16 | 0 | No |
| `temperature_c` | **string** | — | — | **0** | **Yes: should be number; `MISSING` not recognised** |
| `humidity_pct` | integer | 65 | **168** | 0 | **Yes: max of 168 is physically impossible** |
| `wind_speed_ms` | number | 2.8 | 5.1 | 1 | No |

Two red flags:
1. `temperature_c` type is `string` and `missing_count` is `0`; the column has a nodata value (`MISSING`) that was treated as a real string.
2. `humidity_pct` max is `168`. Relative humidity cannot exceed 100; this is a data-entry error.

---

### Step 5: Fix the errors

#### Fix 1: The unrecognised nodata sentinel

The cleanest fix is to replace `MISSING` in the source CSV with a sentinel DEVO already recognises: `N/A`, `NA`, `null`, or an empty cell are all understood automatically.

Change row 2, column `temperature_c` from `MISSING` to `N/A` (or leave the cell blank).

If you cannot change the source data and `MISSING` will always appear in your files, pass `--nodata MISSING` on the command line. DEVO will then treat `MISSING` the same way it treats `N/A`:

```bash
devo run sensor_data.csv --nodata MISSING
```

#### Fix 2: The impossible humidity value

Row 3 has `humidity_pct = 168`. Investigate the source; it is likely a typo for `68`. Correct it in the CSV.

---

### Step 6: Re-run on the corrected file

After making both corrections, `sensor_data.csv` should look like this:

```csv
station_id,observation_date,temperature_c,humidity_pct,wind_speed_ms
S001,2024-01-15,21.4,65,3.2
S002,2024-01-15,N/A,72,N/A
S003,2024-01-15,19.8,68,5.1
S004,2024-01-15,23.1,71,2.8
S005,2024-01-16,20.0,71,4.0
```

Run DEVO again:

```bash
devo run sensor_data.csv
```

Terminal output:

```
[OK] Enriched: DEVO_output/sensor_data.icsv
[OK] Report: DEVO_output/sensor_data_DEVO_report.txt
```

Validation report:

```
DEVO Validation Report
======================
File:  sensor_data.icsv
Date:  2024-01-20T10:40:15Z
Valid: YES

METADATA
----------------------------------------
[OK] All required metadata present.

TYPE CONSISTENCY
----------------------------------------
[OK]   station_id: declared=string, inferred=string
[OK]   observation_date: declared=datetime, inferred=datetime
[OK]   temperature_c: declared=number, inferred=number
[OK]   humidity_pct: declared=integer, inferred=integer
[OK]   wind_speed_ms: declared=number, inferred=number

DATA VALIDATION
----------------------------------------
[PASS] No data errors found.
```

The `# [FIELDS]` section of the iCSV now shows correct types and a plausible maximum for humidity:

```
# [FIELDS]
# fields = station_id|observation_date|temperature_c|humidity_pct|wind_speed_ms
# types  = string|datetime|number|integer|number
# min    = |2024-01-15T00:00:00|19.8|65|2.8
# max    = |2024-01-16T00:00:00|23.1|72|5.1
# missing_count = 0|0|1|0|1
# description   = ||||
```

---

### Step 7: How to know the file is ready for upload

A file is ready for upload when all of the following are true:

- [ ] **Report says `Valid: YES`**
- [ ] **All column types in `# types` are correct** for the data: numbers are `integer` or `number`, dates are `datetime`, free text is `string`
- [ ] **`# min` and `# max` values are physically plausible**, with no impossible extremes like `humidity_pct = 168`
- [ ] **`# missing_count` matches your expectation.** If a column should have no gaps and shows `missing_count = 5`, investigate before uploading.
- [ ] **No `[WARN]` lines in TYPE CONSISTENCY.** A warning means the declared type does not match what DEVO sees in the data (see [Common Errors](#6-common-errors-and-how-to-fix-them)).

Once all boxes are checked, submit the `.icsv` file and its accompanying `_schema.json`.

---

## 4. Understanding the Validation Report

The report has three sections:

### Report header

```
DEVO Validation Report
======================
File:  sensor_data.icsv
Date:  2024-01-20T10:40:15Z
Valid: YES
```

`Valid: YES` means **both** the metadata check and the Frictionless data check passed. Type consistency warnings (`[WARN]`) do not make the file invalid; they are advisory. `Valid: NO` means at least one `[FAIL]` was found in METADATA or DATA VALIDATION.

---

### METADATA section

Checks that the required iCSV metadata keys are present.

```
METADATA
----------------------------------------
[OK] All required metadata present.
```

Or, if there are problems:

```
METADATA
----------------------------------------
[FAIL] Missing required metadata key: field_delimiter
[WARN] Spatial columns detected but 'geometry' metadata key is missing
[WARN] Spatial columns detected but 'srid' metadata key is missing
```

| Message                                                                  | Meaning                                                                       | Effect on `Valid` |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------- | ----------------- |
| `[OK] All required metadata present.`                                    | Everything is in order                                                        | —                 |
| `[FAIL] Missing required metadata key: field_delimiter`                  | The `field_delimiter` key is absent from `# [METADATA]`                       | Sets `Valid: NO`  |
| `[WARN] Spatial columns detected but 'geometry' metadata key is missing` | Columns named `lat`/`lon`/`geometry` found but `geometry` key is not declared | Advisory only     |
| `[WARN] Spatial columns detected but 'srid' metadata key is missing`     | Lat/lon columns found but no coordinate reference system declared             | Advisory only     |

`[FAIL]` in METADATA sets the overall result to `Valid: NO`. `[WARN]` in METADATA does not.

---

### TYPE CONSISTENCY section

DEVO re-infers each column's type from the actual data rows and compares it to the type declared in `# [FIELDS]`. This catches cases where the declared type was manually edited to be stricter than what the data actually contains.

```
TYPE CONSISTENCY
----------------------------------------
[OK]   temperature_c: declared=number, inferred=number
[WARN] humidity_pct: declared=integer, inferred=number
       Inferred type is wider than declared. Data may not satisfy 'integer' constraints.
```

| Result   | Meaning                                                                                                                                         |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `[OK]`   | Inferred type is equal to or narrower than declared (e.g., inferred `integer` satisfies declared `number`)                                      |
| `[WARN]` | Inferred type is **wider** than declared (e.g., inferred `number` does not satisfy declared `integer`; floats exist but integers are expected) |

Type hierarchy (narrowest to widest): `integer` → `number` → `string`, and `datetime` → `string`.

`[WARN]` in TYPE CONSISTENCY is advisory and does **not** set `Valid: NO`. However, it usually means the data has values that will fail Frictionless validation. Check the DATA VALIDATION section for accompanying `[FAIL]` lines.

---

### DATA VALIDATION section

Frictionless validates the actual data rows against the schema JSON. This catches type mismatches, out-of-range values, and required-field violations.

```
DATA VALIDATION
----------------------------------------
[PASS] No data errors found.
```

Or, when errors are found:

```
DATA VALIDATION
----------------------------------------
[FAIL] 3 error(s) found:
  Row 2, Col temperature_c [type-error]: type is "number/default" and value "MISSING" is not valid
  Row 3, Col humidity_pct [constraint-error]: constraint "maximum is 100" is not satisfied for value "168"
  Row 4, Col station_id [required-error]: constraint "required is True" is not satisfied for value ""
```

Each error line shows:
- **Row number**: the row in the data section (row 1 is the header, so row 2 is the first data row)
- **Column name**: which field failed
- **Error code**: the Frictionless error type (see table below)
- **Message**: the specific constraint that was violated

| Error code | What it means | How to fix |
|---|---|---|
| `type-error` | A value cannot be parsed as the declared type | Correct the value in the source CSV, or adjust the type in the schema if the declaration is wrong |
| `constraint-error` | A value falls outside a `minimum`, `maximum`, or other constraint | Correct the value in the source CSV, or update the schema constraint if it was set too tightly |
| `required-error` | A required field has a blank or missing value | Fill in the missing value, or mark the field as not required in the schema |

If there are more than 50 errors, the report shows only the first 50 and notes the total count. Fix the listed errors first; re-running often reveals whether additional errors exist.

---

## 5. Understanding the iCSV Format

An iCSV file is a plain-text CSV with a structured comment header. Comments begin with `#`. There are three named sections.

### `# [METADATA]` section

Key/value pairs describing the file as a whole.

```
# iCSV 1.0 UTF-8
# [METADATA]
# iCSV_version   = 1.0
# field_delimiter = |
# rows            = 5
# columns         = 5
# creation_date   = 2024-01-20T10:40:15.123456Z
# nodata          = N/A
# generator       = DEVO
```

**`field_delimiter`** is the character used to separate values in `# [FIELDS]` lines and in the `# [DATA]` section. DEVO maps commas to `|` (pipe) to avoid ambiguity with the `,` separator in metadata lines. This key is **required**; its absence is a `[FAIL]`.

**`nodata`** is the most commonly seen missing-value sentinel in the data. DEVO detects this automatically from the data; you can override it with `--nodata VALUE`.

**`geometry`** and **`srid`** are written automatically when DEVO detects spatial columns (columns named `lat`/`latitude`, `lon`/`lng`/`longitude`, or `geometry`).

---

### `# [FIELDS]` section

Per-column metadata. Each line is a pipe-delimited list aligned to the column order in `# [DATA]`.

```
# [FIELDS]
# fields        = station_id|observation_date|temperature_c|humidity_pct|wind_speed_ms
# types         = string|datetime|number|integer|number
# min           = |2024-01-15T00:00:00|19.8|65|2.8
# max           = |2024-01-16T00:00:00|23.1|72|5.1
# missing_count = 0|0|1|0|1
# description   = ||||
```

| Field line | What to look for |
|---|---|
| `types` | Confirm every column has the type you expect. `string` for a column that should be numeric is a red flag. |
| `min` / `max` | Verify the range makes sense for your domain. A humidity maximum of 168 is physically impossible and indicates a data-entry error. String and all-missing columns have no min/max (blank). |
| `missing_count` | A `0` on a column that should have gaps means your nodata sentinel was not recognised. A high count on a column that should be complete is worth investigating. |
| `description` | Blank by default. Fill these in by hand before uploading if your archive requires field descriptions. |

The recognised **Frictionless types** are: `string`, `integer`, `number`, `datetime`. DEVO infers them in this order of preference: `integer` → `number` → `datetime` → `string`.

---

### `# [DATA]` section

The data rows, written with the `field_delimiter` as the separator. The first row after `# [DATA]` is the column header.

```
# [DATA]
station_id|observation_date|temperature_c|humidity_pct|wind_speed_ms
S001|2024-01-15|21.4|65|3.2
S002|2024-01-15|N/A|72|N/A
...
```

You can edit values in `# [DATA]` directly, but if you do, re-run `devo validate` afterwards to confirm the edited file still passes.

---

## 6. Common Errors and How to Fix Them

### A numeric column is typed as `string`

**Symptom:** `# types` shows `string` for a column that holds measurements or counts. `min` and `max` are blank for that column.

**Cause:** At least one value in the column is not a number and is not a recognised nodata sentinel. Common culprits: custom sentinels like `MISSING`, `ND`, `NM`, `-`, `na`, `none`; stray text like `error` or `N/M`; unit suffixes like `21.4°C`.

**Fix options:**

1. Replace the non-numeric values with a standard sentinel (`N/A`, `NA`, `null`, or an empty cell) in the source CSV, then re-run.
2. If you cannot change the source, tell DEVO about the custom sentinel:
   ```bash
   devo run data.csv --nodata MISSING
   ```
3. If the column genuinely has mixed text (e.g., a notes field), `string` may be correct; no action is needed.

---

### `[WARN]` in TYPE CONSISTENCY

**Symptom:**
```
[WARN] temperature_c: declared=number, inferred=string
       Inferred type is wider than declared. Data may not satisfy 'number' constraints.
```

**Cause:** The type declared in `# [FIELDS]` (usually set during enrichment or edited manually) is stricter than what the actual data rows contain. The most common cause is editing the iCSV type from `string` to `number` without also fixing the values that caused the original `string` inference.

**Fix:** Look for non-numeric, non-sentinel values in that column's data rows. Either:
- Replace them with a recognised sentinel and re-run `devo run` on the corrected source CSV, or
- Revert the type in `# [FIELDS]` to `string` if the column really contains mixed content.

---

### `[FAIL] type-error` in DATA VALIDATION

**Symptom:**
```
[FAIL] 1 error(s) found:
  Row 2, Col temperature_c [type-error]: type is "number/default" and value "MISSING" is not valid
```

**Cause:** A value in the data cannot be parsed as the declared type in the schema JSON. This often occurs together with a TYPE CONSISTENCY `[WARN]` and typically means the schema says one type (e.g., `number`) while the data contains incompatible values (e.g., the string `MISSING`).

**Fix:** Correct the value in the source data and re-run. If the value is a nodata sentinel, use `--nodata VALUE` so it is excluded from type inference and added to the schema's `missingValues` list.

---

### `[FAIL] constraint-error` in DATA VALIDATION

**Symptom:**
```
[FAIL] 1 error(s) found:
  Row 3, Col humidity_pct [constraint-error]: constraint "maximum is 72" is not satisfied for value "168"
```

**Cause:** A value violates a `minimum` or `maximum` constraint in the schema. The schema constraints are derived from the data at enrichment time; if you later add or correct rows that push values outside the original range, validation will fail.

**Fix options:**

1. Correct the outlier in the source CSV (e.g., change `168` to `68`) and re-run `devo run`.
2. If the new range is legitimate, re-run `devo enrich` to rebuild the schema from the updated data, then `devo validate` to confirm.

---

### `[FAIL] required-error` in DATA VALIDATION

**Symptom:**
```
[FAIL] 1 error(s) found:
  Row 4, Col station_id [required-error]: constraint "required is True" is not satisfied for value ""
```

**Cause:** A field was declared `required: true` in the schema (because it had no missing values at enrichment time), but a later row has an empty or missing value for that field.

**Fix options:**

1. Fill in the missing value in the source CSV and re-run.
2. If blanks are valid for that column, rebuild the schema after adding a row with a blank value; DEVO will set `required: false` and `missing_count` to a non-zero value.

---

### `[FAIL] Missing required metadata key: field_delimiter`

**Symptom:**
```
METADATA
----------------------------------------
[FAIL] Missing required metadata key: field_delimiter
```
`Valid: NO`

**Cause:** The iCSV's `# [METADATA]` section is missing the `field_delimiter` key. This should not occur in iCSV files generated by DEVO, but can happen in hand-authored files.

**Fix:** Add `# field_delimiter = |` (or your actual delimiter) to the `# [METADATA]` section of the iCSV file.

---

### `[ERROR] Column name(s) contain the iCSV delimiter`

**Symptom (terminal):**
```
[ERROR] Column name(s) contain the iCSV delimiter '|': ['flow|rate']. 
Rename the columns or force a different delimiter with --delimiter.
```

**Cause:** A column header in the source CSV contains the pipe character `|`. DEVO uses `|` as the iCSV field delimiter, so a pipe inside a column name is ambiguous.

**Fix options:**

1. Rename the column in the source CSV (e.g., `flow|rate` → `flow_rate`).
2. Force a different delimiter that does not appear in your column names:
   ```bash
   devo run data.csv --delimiter ":"
   ```
   Valid iCSV delimiters are: `,  |  /  \  :  ;`

---

### `[ERROR] No schema provided and none found`

**Symptom (terminal):**
```
[ERROR] No schema provided and none found alongside data.icsv.
Run 'devo enrich' first or pass --schema.
```

**Cause:** `devo validate` expects a schema JSON file in the same directory as the iCSV, named `<stem>_schema.json`. If the schema file is missing or in a different location, validation cannot run.

**Fix options:**

1. Run `devo enrich data.csv` first to generate the schema, then `devo validate`.
2. Point to an existing schema explicitly:
   ```bash
   devo validate data.icsv --schema /path/to/data_schema.json
   ```

---

### `[ERROR] data.icsv is already an iCSV file`

**Symptom (terminal):**
```
[ERROR] data.icsv is already an iCSV file.
Use 'devo validate' to validate it, or 'devo run' which handles both.
```

**Cause:** You ran `devo enrich` on a `.icsv` file.

**Fix:** Use `devo validate data.icsv` to validate it, or `devo run data.icsv` (which detects the `.icsv` format and skips enrichment automatically).

---

### Nodata sentinels DEVO recognises automatically

The following values are treated as missing by default; no `--nodata` flag needed:

```
(empty cell)  NA  N/A  na  n/a  NULL  null  nan  NaN  -999  -999.0  -999.000000
```

Any other sentinel, such as `MISSING`, `ND`, `NM`, `none`, `-`, or `9999`, must be declared with `--nodata VALUE`.

---

## 7. CLI Reference

### `devo run`: enrich then validate (most common)

```bash
devo run INPUT [--out DIR] [--delimiter CHAR] [--nodata VALUE] [--app PROFILE]
```

If `INPUT` is a `.csv`, DEVO enriches it first, then validates. If `INPUT` is already a `.icsv`, enrichment is skipped.

| Flag | Default | Description |
|---|---|---|
| `--out DIR` | `DEVO_output` | Directory for all output files |
| `--delimiter CHAR` | auto-detected | Force a specific input delimiter (CSV files only) |
| `--nodata VALUE` | auto-detected | Declare a custom missing-value sentinel |
| `--app PROFILE` | (none) | Set the `application_profile` metadata key |

---

### `devo enrich`: CSV → iCSV + schema

```bash
devo enrich INPUT.csv [--out DIR] [--delimiter CHAR] [--nodata VALUE] [--app PROFILE]
```

Writes `INPUT.icsv` and `INPUT_schema.json` to `--out DIR`. Does not validate.

---

### `devo validate`: iCSV → validation report

```bash
devo validate INPUT.icsv [--out DIR] [--schema PATH]
```

| Flag | Default | Description |
|---|---|---|
| `--out DIR` | `DEVO_output` | Directory for the report |
| `--schema PATH` | auto-discover | Path to the schema JSON; defaults to `INPUT_schema.json` in the same directory |

---

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success: validation passed (or enrichment completed without errors) |
| `1` | Validation failed: data errors found; read the report |
| `2` | Usage or runtime error: bad arguments, missing file, etc. |

---

## 8. Python API

For scripted or batch use cases:

```python
from devo.enrich import ICSVEnricher
from devo.validate import validate_icsv

# Step 1: Enrich CSV → iCSV + schema
icsv_path, schema_path = ICSVEnricher().make_icsv(
    "sensor_data.csv",
    outdir="DEVO_output",
    nodata_override="MISSING",   # optional: custom sentinel
    application_profile="MyApp" # optional: profile name
)

# Step 2: Validate
report_path, is_valid = validate_icsv(
    icsv_path,
    schema_path=schema_path,
    outdir="DEVO_output"
)

print(f"Valid: {is_valid}")
print(f"Report: {report_path}")

if not is_valid:
    # Read the report for details
    print(open(report_path).read())
```

### Error handling

```python
from devo.exceptions import DEVOError, EnrichError, ParseError, ValidationError

try:
    icsv_path, schema_path = ICSVEnricher().make_icsv("data.csv", "out")
    report_path, is_valid = validate_icsv(icsv_path, schema_path=schema_path)
except EnrichError as e:
    print(f"Enrichment failed: {e}")
except ParseError as e:
    print(f"Could not parse iCSV header: {e}")
except ValidationError as e:
    print(f"Validation infrastructure error: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

| Exception | When it is raised |
|---|---|
| `EnrichError` | Input CSV cannot be read, is already an iCSV, or has column names that contain the output delimiter |
| `ParseError` | An iCSV file is missing its `# [METADATA]` section or cannot be opened |
| `ValidationError` | The `frictionless` package is not installed |
| `FileNotFoundError` | The input file or schema file does not exist |

All four inherit from `DEVOError`, so `except DEVOError` catches any DEVO-specific failure.

---

### Batch processing example

```python
from pathlib import Path
from devo.enrich import ICSVEnricher
from devo.validate import validate_icsv
from devo.exceptions import DEVOError

enricher = ICSVEnricher()
results = []

for csv_file in Path("incoming").glob("*.csv"):
    try:
        icsv, schema = enricher.make_icsv(str(csv_file), outdir="DEVO_output")
        report, valid = validate_icsv(icsv, schema_path=schema)
        results.append((csv_file.name, valid, report))
    except DEVOError as e:
        results.append((csv_file.name, False, str(e)))

for name, valid, info in results:
    status = "READY" if valid else "NEEDS REVIEW"
    print(f"{status}  {name}  →  {info}")
```

---


## License

MIT. See `LICENSE`.
