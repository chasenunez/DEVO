"""Unit tests for _infer.py — pure functions, no I/O."""
import pytest
from devo._infer import infer_type, is_subtype_or_equal, COMMON_MISSING


# --- infer_type ---

def test_integer_column():
    assert infer_type(["1", "2", "3"]) == "integer"

def test_negative_integer():
    assert infer_type(["-1", "-2", "0"]) == "integer"

def test_number_column():
    assert infer_type(["1.5", "2.7", "3.0"]) == "number"

def test_mixed_int_and_float_gives_number():
    # An integer is a valid number, so mixed int+float columns → number
    assert infer_type(["1", "2.5", "3"]) == "number"

def test_datetime_iso():
    assert infer_type(["2005-08-23T15:30:00", "2005-08-24T00:00:00"]) == "datetime"

def test_datetime_date_only():
    assert infer_type(["2005-08-23", "2005-08-24"]) == "datetime"

def test_datetime_strptime_dot_format():
    # %d.%m.%Y — not caught by fromisoformat, tests the strptime fallback
    assert infer_type(["23.08.2005", "24.08.2005"]) == "datetime"

def test_datetime_strptime_slash_format():
    assert infer_type(["23/08/2005", "24/08/2005"]) == "datetime"

def test_string_column():
    assert infer_type(["hello", "world", "foo"]) == "string"

def test_mixed_types_fall_back_to_string():
    assert infer_type(["1", "hello", "2"]) == "string"

def test_all_missing_returns_string():
    assert infer_type(["", "NA", "-999"]) == "string"

def test_nodata_excluded_from_inference():
    # Missing sentinels should not corrupt type detection
    assert infer_type(["-999", "1", "2", "3"]) == "integer"
    assert infer_type(["NA", "1.5", "2.7"]) == "number"

def test_empty_list_returns_string():
    assert infer_type([]) == "string"

def test_custom_missing_set():
    # Custom sentinel should be excluded; value "MISSING" is not in COMMON_MISSING
    assert infer_type(["MISSING", "1", "2"], frozenset({"MISSING"})) == "integer"

def test_whitespace_stripped_before_inference():
    assert infer_type(["  1  ", " 2 ", "3"]) == "integer"


# --- is_subtype_or_equal ---

@pytest.mark.parametrize("inferred,declared", [
    ("integer",  "integer"),
    ("number",   "number"),
    ("datetime", "datetime"),
    ("string",   "string"),
])
def test_same_type_is_ok(inferred, declared):
    assert is_subtype_or_equal(inferred, declared)

@pytest.mark.parametrize("inferred,declared", [
    ("integer",  "number"),   # all integers are valid numbers
    ("integer",  "string"),   # integers can be represented as strings
    ("number",   "string"),
    ("datetime", "string"),
])
def test_narrower_inferred_is_ok(inferred, declared):
    assert is_subtype_or_equal(inferred, declared)

@pytest.mark.parametrize("inferred,declared", [
    ("number",   "integer"),  # floats fail integer validation → WARN
    ("string",   "integer"),
    ("string",   "number"),
    ("string",   "datetime"),
    ("datetime", "integer"),
    ("datetime", "number"),
    ("number",   "datetime"),
    ("integer",  "datetime"),
])
def test_wider_inferred_is_not_ok(inferred, declared):
    assert not is_subtype_or_equal(inferred, declared)
