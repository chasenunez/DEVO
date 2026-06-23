"""Tests for _parser.py — iCSV header parsing."""
from pathlib import Path
import pytest
from devo._parser import is_icsv, parse_header, ICSVHeader
from devo.exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


def test_is_icsv_true(invalid_data_icsv):
    assert is_icsv(invalid_data_icsv) is True

def test_is_icsv_false(simple_csv):
    assert is_icsv(simple_csv) is False

def test_is_icsv_missing_file():
    assert is_icsv(Path("/nonexistent/file.icsv")) is False

def test_parse_header_basic(invalid_data_icsv):
    h = parse_header(invalid_data_icsv)
    assert h.field_delimiter == "|"
    assert h.metadata["field_delimiter"] == "|"
    assert h.metadata["rows"] == "3"
    assert h.fields_meta["fields"] == ["id", "temp"]
    assert h.fields_meta["types"] == ["integer", "number"]

def test_parse_header_returns_dataclass(invalid_data_icsv):
    h = parse_header(invalid_data_icsv)
    assert isinstance(h, ICSVHeader)

def test_parse_header_delimiter_used_for_fields(tmp_path):
    # Write a minimal iCSV with semicolon delimiter and verify fields are split correctly
    icsv = tmp_path / "test.icsv"
    icsv.write_text(
        "# iCSV 1.0 UTF-8\n"
        "# [METADATA]\n"
        "# field_delimiter = ;\n"
        "# [FIELDS]\n"
        "# fields = a;b;c\n"
        "# [DATA]\n"
        "a;b;c\n",
        encoding="utf-8",
    )
    h = parse_header(icsv)
    assert h.field_delimiter == ";"
    assert h.fields_meta["fields"] == ["a", "b", "c"]

def test_parse_header_missing_section_raises(tmp_path):
    bad = tmp_path / "bad.icsv"
    bad.write_text("# iCSV 1.0 UTF-8\n# no sections here\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_header(bad)

def test_parse_header_stops_at_data_section(tmp_path):
    # Keys that appear after # [DATA] must not be parsed as metadata
    icsv = tmp_path / "test.icsv"
    icsv.write_text(
        "# iCSV 1.0 UTF-8\n"
        "# [METADATA]\n"
        "# field_delimiter = |\n"
        "# [FIELDS]\n"
        "# fields = x|y\n"
        "# [DATA]\n"
        "# fake_key = should_not_appear\n"
        "1|2\n",
        encoding="utf-8",
    )
    h = parse_header(icsv)
    assert "fake_key" not in h.metadata
    assert "fake_key" not in h.fields_meta

def test_parse_header_unreadable_file_raises():
    with pytest.raises(ParseError):
        parse_header(Path("/nonexistent/file.icsv"))
