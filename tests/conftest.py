"""Shared fixtures for all DEVO tests."""
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_csv() -> Path:
    return FIXTURES / "simple.csv"


@pytest.fixture
def semicolon_csv() -> Path:
    return FIXTURES / "semicolon.csv"


@pytest.fixture
def geodata_csv() -> Path:
    return FIXTURES / "geodata.csv"


@pytest.fixture
def with_missing_csv() -> Path:
    return FIXTURES / "with_missing.csv"


@pytest.fixture
def all_types_csv() -> Path:
    return FIXTURES / "all_types.csv"


@pytest.fixture
def invalid_data_icsv() -> Path:
    return FIXTURES / "invalid_data.icsv"


@pytest.fixture
def invalid_data_schema() -> Path:
    return FIXTURES / "invalid_data_schema.json"


@pytest.fixture
def type_mismatch_icsv() -> Path:
    return FIXTURES / "type_mismatch.icsv"


@pytest.fixture
def type_mismatch_schema() -> Path:
    return FIXTURES / "type_mismatch_schema.json"
