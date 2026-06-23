"""Integration tests for ICSVEnricher.make_icsv."""
import json
from pathlib import Path
import pytest
from devo.enrich import ICSVEnricher
from devo._parser import parse_header
from devo.exceptions import EnrichError

FIXTURES = Path(__file__).parent / "fixtures"


def _enrich(csv_path, tmp_path, **kwargs):
    return ICSVEnricher().make_icsv(str(csv_path), str(tmp_path), **kwargs)


# --- Output files exist ---

def test_enrich_creates_icsv_and_schema(simple_csv, tmp_path):
    icsv, schema = _enrich(simple_csv, tmp_path)
    assert Path(icsv).exists()
    assert Path(schema).exists()

def test_output_files_named_after_input_stem(simple_csv, tmp_path):
    icsv, schema = _enrich(simple_csv, tmp_path)
    assert Path(icsv).name == "simple.icsv"
    assert Path(schema).name == "simple_schema.json"


# --- iCSV structure ---

def test_icsv_firstline(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    first = Path(icsv).read_text(encoding="utf-8").splitlines()[0]
    assert first == "# iCSV 1.0 UTF-8"

def test_icsv_has_all_three_sections(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    text = Path(icsv).read_text(encoding="utf-8")
    assert "# [METADATA]" in text
    assert "# [FIELDS]" in text
    assert "# [DATA]" in text

def test_icsv_metadata_keys_present(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    for key in ("iCSV_version", "field_delimiter", "rows", "columns", "creation_date", "generator"):
        assert key in h.metadata, f"Missing metadata key: {key}"

def test_icsv_correct_row_and_column_counts(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert h.metadata["rows"] == "3"
    assert h.metadata["columns"] == "3"

def test_icsv_fields_match_csv_header(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert h.fields_meta["fields"] == ["timestamp", "PSUM", "TA"]

def test_icsv_types_inferred_correctly(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert h.fields_meta["types"] == ["datetime", "integer", "number"]

def test_icsv_has_min_max_missing_count_description(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    for key in ("min", "max", "missing_count", "description"):
        assert key in h.fields_meta, f"Missing fields key: {key}"


# --- Delimiter handling ---

def test_comma_input_remapped_to_pipe(simple_csv, tmp_path):
    # Comma delimiter must be remapped to | to avoid ambiguity in metadata lines
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert h.field_delimiter == "|"

def test_semicolon_input_preserves_semicolon(semicolon_csv, tmp_path):
    icsv, _ = _enrich(semicolon_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert h.field_delimiter == ";"
    assert h.fields_meta["fields"] == ["timestamp", "PSUM", "TA"]

def test_forced_delimiter_respected(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path, user_delimiter=",")
    h = parse_header(Path(icsv))
    # Comma is remapped to | regardless of user forcing it
    assert h.field_delimiter == "|"


# --- Geometry detection ---

def test_geometry_written_for_lat_lon_columns(geodata_csv, tmp_path):
    icsv, _ = _enrich(geodata_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert "geometry" in h.metadata
    assert "srid" in h.metadata
    assert h.metadata["srid"] == "EPSG:4326"

def test_geometry_absent_for_non_spatial_csv(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert "geometry" not in h.metadata
    assert "srid" not in h.metadata


# --- Missing values ---

def test_nodata_detected_and_written(with_missing_csv, tmp_path):
    icsv, _ = _enrich(with_missing_csv, tmp_path)
    h = parse_header(Path(icsv))
    assert "nodata" in h.metadata

def test_nodata_override(simple_csv, tmp_path):
    icsv, _ = _enrich(simple_csv, tmp_path, nodata_override="-9999")
    h = parse_header(Path(icsv))
    assert h.metadata["nodata"] == "-9999"

def test_missing_values_excluded_from_type_inference(with_missing_csv, tmp_path):
    icsv, _ = _enrich(with_missing_csv, tmp_path)
    h = parse_header(Path(icsv))
    # temp column has -999 missing values; remaining values are numeric → should be number
    types = dict(zip(h.fields_meta["fields"], h.fields_meta["types"]))
    assert types["temp"] == "number"
    assert types["precip"] == "number"


# --- Frictionless schema JSON ---

def test_schema_has_standard_frictionless_keys_only(simple_csv, tmp_path):
    _, schema_path = _enrich(simple_csv, tmp_path)
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    assert "fields" in schema
    assert "missingValues" in schema
    # DEVO-specific stats must NOT appear in the Frictionless schema
    for field in schema["fields"]:
        assert "missing_count" not in field
        # min/max at field level (non-standard) must not be present
        assert "min" not in field
        assert "max" not in field

def test_schema_field_types_match_icsv(simple_csv, tmp_path):
    icsv, schema_path = _enrich(simple_csv, tmp_path)
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    h = parse_header(Path(icsv))
    schema_types = {f["name"]: f["type"] for f in schema["fields"]}
    fields_types = dict(zip(h.fields_meta["fields"], h.fields_meta["types"]))
    assert schema_types == fields_types


# --- All four types ---

def test_all_four_types_inferred(all_types_csv, tmp_path):
    icsv, _ = _enrich(all_types_csv, tmp_path)
    h = parse_header(Path(icsv))
    types = dict(zip(h.fields_meta["fields"], h.fields_meta["types"]))
    assert types["an_int"] == "integer"
    assert types["a_float"] == "number"
    assert types["a_date"] == "datetime"
    assert types["a_string"] == "string"


# --- Error cases ---

def test_icsv_input_raises_enrich_error(tmp_path, invalid_data_icsv):
    with pytest.raises(EnrichError, match="already an iCSV"):
        ICSVEnricher().make_icsv(str(invalid_data_icsv), str(tmp_path))

def test_missing_input_file_raises(tmp_path):
    with pytest.raises(EnrichError):
        ICSVEnricher().make_icsv("/nonexistent/file.csv", str(tmp_path))
