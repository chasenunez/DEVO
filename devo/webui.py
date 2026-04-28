"""A tiny Flask web UI which allows uploading a CSV, creating an iCSV, and running validation.

This is intentionally minimal — suitable for local testing and demonstration.
"""
from flask import Flask, request, render_template_string, send_file
from pathlib import Path
from .enrich import ICSVEnricher
from .validate import validate_icsv

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<title>DEVO demo</title>
<h1>DEVO — upload CSV</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
{% if message %}
<hr>
<h2>Result</h2>
<pre>{{ message }}</pre>
{% endif %}
"""

@app.route("/", methods=["GET", "POST"])
def index():
    message = None
    if request.method == "POST":
        f = request.files.get("file")
        if not f:
            message = "No file uploaded"
        else:
            outdir = Path("DEVO_output")
            outdir.mkdir(exist_ok=True)
            infile = outdir / f.filename
            f.save(infile)
            enr = ICSVEnricher()
            try:
                icsv, schema = enr.make_icsv(str(infile), str(outdir))
                report, valid = validate_icsv(icsv, schema_path=schema, outdir=str(outdir))
                message = f"iCSV: {icsv}\nSchema: {schema}\nReport: {report}\nValid: {valid}"
            except Exception as e:  # top-level demo catch-all; render any error to the UI rather than 500
                message = f"Error: {e}"
    return render_template_string(TEMPLATE, message=message)
