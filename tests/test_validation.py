import tempfile
import os
from devo.enrichment import make_icsv_from_csv
from devo.validation import validate_icsv

def test_validation_roundtrip():
    csv_text = "timestamp,ta\n2020-01-01T00:00:00,10\n2020-01-01T01:00:00,not_a_number\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
        tmp.write(csv_text)
        tmp_name = tmp.name
    try:
        icsv, schema = make_icsv_from_csv(tmp_name)
        valid, report = validate_icsv(icsv)
        assert os.path.exists(report)
        # second row has invalid number -> validation should be False
        assert not valid
    finally:
        for p in (tmp_name, icsv, schema, report):
            try:
                os.remove(p)
            except Exception:
                pass
