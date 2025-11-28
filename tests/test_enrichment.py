import tempfile
import os
from devo.enrichment import make_icsv_from_csv

def test_make_icsv_basic():
    csv_text = "timestamp,ta,rh\n2020-01-01T00:00:00,10,0.5\n2020-01-01T01:00:00,12,0.55\n"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
        tmp.write(csv_text)
        tmp_name = tmp.name
    try:
        icsv, schema = make_icsv_from_csv(tmp_name)
        assert os.path.exists(icsv)
        assert os.path.exists(schema)
    finally:
        for p in (tmp_name, icsv, schema):
            try:
                os.remove(p)
            except Exception:
                pass
