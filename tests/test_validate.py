"""Integration tests for validate_icsv."""
from pathlib import Path
import pytest
from devo.enrich import ICSVEnricher
from devo.validate import validate_icsv

FIXTURES = Path(__file__).parent / "fixtures"


def _make(csv_path, out):
    return ICSVEnricher().make_icsv(str(csv_path), str(out))


# --- Valid round-trip ---

def test_validate_enriched_csv_passes(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    report_path, valid = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    assert valid is True
    assert Path(report_path).exists()

def test_report_extension_is_txt(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    report_path, _ = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    assert Path(report_path).suffix == ".txt"

def test_report_contains_yes_on_valid(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    report_path, _ = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    content = Path(report_path).read_text(encoding="utf-8")
    assert "Valid: YES" in content

def test_report_has_expected_sections(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    report_path, _ = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    content = Path(report_path).read_text(encoding="utf-8")
    assert "METADATA" in content
    assert "TYPE CONSISTENCY" in content
    assert "DATA VALIDATION" in content

def test_no_temp_csv_left_behind(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    leftover = list(tmp_path.glob("tmp*.csv"))
    assert leftover == [], f"Temp files left: {leftover}"


# --- Invalid data ---

def test_validate_invalid_data_fails(invalid_data_icsv, invalid_data_schema, tmp_path):
    report_path, valid = validate_icsv(
        str(invalid_data_icsv),
        schema_path=str(invalid_data_schema),
        outdir=str(tmp_path),
    )
    assert valid is False

def test_report_contains_fail_for_invalid_data(invalid_data_icsv, invalid_data_schema, tmp_path):
    report_path, _ = validate_icsv(
        str(invalid_data_icsv),
        schema_path=str(invalid_data_schema),
        outdir=str(tmp_path),
    )
    content = Path(report_path).read_text(encoding="utf-8")
    assert "FAIL" in content
    assert "Valid: NO" in content


# --- Type cross-check (Option A) ---

def test_type_mismatch_produces_warn_in_report(type_mismatch_icsv, type_mismatch_schema, tmp_path):
    report_path, valid = validate_icsv(
        str(type_mismatch_icsv),
        schema_path=str(type_mismatch_schema),
        outdir=str(tmp_path),
    )
    content = Path(report_path).read_text(encoding="utf-8")
    # 'value' column is declared integer but data is float → WARN
    assert "WARN" in content

def test_type_ok_no_warn_in_report(simple_csv, tmp_path):
    icsv, schema = _make(simple_csv, tmp_path)
    report_path, _ = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    content = Path(report_path).read_text(encoding="utf-8")
    assert "WARN" not in content


# --- Error cases ---

def test_missing_schema_raises_file_not_found(tmp_path):
    icsv = tmp_path / "orphan.icsv"
    icsv.write_text(
        "# iCSV 1.0 UTF-8\n# [METADATA]\n# field_delimiter = |\n"
        "# [FIELDS]\n# fields = x\n# [DATA]\nx\n1\n",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        validate_icsv(str(icsv), outdir=str(tmp_path))

def test_all_types_csv_round_trips_valid(all_types_csv, tmp_path):
    icsv, schema = _make(all_types_csv, tmp_path)
    _, valid = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    assert valid is True

def test_missing_values_csv_round_trips_valid(with_missing_csv, tmp_path):
    icsv, schema = _make(with_missing_csv, tmp_path)
    _, valid = validate_icsv(icsv, schema_path=schema, outdir=str(tmp_path))
    assert valid is True
