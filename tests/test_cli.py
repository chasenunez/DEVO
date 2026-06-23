"""CLI tests — call main() directly to test exit codes and output files."""
from pathlib import Path
import pytest
from devo.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_enrich_creates_output_files(simple_csv, tmp_path):
    main(["enrich", str(simple_csv), "--out", str(tmp_path)])
    assert (tmp_path / "simple.icsv").exists()
    assert (tmp_path / "simple_schema.json").exists()

def test_enrich_exits_zero_on_success(simple_csv, tmp_path):
    # main() returns None on success (no sys.exit call)
    result = main(["enrich", str(simple_csv), "--out", str(tmp_path)])
    assert result is None

def test_validate_exits_zero_on_valid(simple_csv, tmp_path):
    main(["enrich", str(simple_csv), "--out", str(tmp_path)])
    result = main(["validate", str(tmp_path / "simple.icsv"), "--out", str(tmp_path)])
    assert result is None

def test_validate_exits_1_on_invalid(invalid_data_icsv, invalid_data_schema, tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([
            "validate",
            str(invalid_data_icsv),
            "--schema", str(invalid_data_schema),
            "--out", str(tmp_path),
        ])
    assert exc.value.code == 1

def test_run_on_csv_creates_all_outputs(simple_csv, tmp_path):
    main(["run", str(simple_csv), "--out", str(tmp_path)])
    assert (tmp_path / "simple.icsv").exists()
    assert (tmp_path / "simple_schema.json").exists()
    assert (tmp_path / "simple_DEVO_report.txt").exists()

def test_run_on_icsv_skips_enrichment(tmp_path, invalid_data_icsv, invalid_data_schema):
    # Pre-stage: copy schema next to icsv in tmp so auto-discovery finds it
    import shutil
    icsv_copy = tmp_path / "invalid_data.icsv"
    schema_copy = tmp_path / "invalid_data_schema.json"
    shutil.copy(invalid_data_icsv, icsv_copy)
    shutil.copy(invalid_data_schema, schema_copy)

    mtime_before = icsv_copy.stat().st_mtime
    with pytest.raises(SystemExit) as exc:
        main(["run", str(icsv_copy), "--out", str(tmp_path)])
    # validation fails (data errors) → exit 1
    assert exc.value.code == 1
    # iCSV was NOT re-written (enrichment skipped)
    assert icsv_copy.stat().st_mtime == mtime_before

def test_bad_input_file_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["enrich", "/nonexistent/file.csv", "--out", str(tmp_path)])
    assert exc.value.code == 2

def test_enrich_icsv_input_exits_2(invalid_data_icsv, tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["enrich", str(invalid_data_icsv), "--out", str(tmp_path)])
    assert exc.value.code == 2
