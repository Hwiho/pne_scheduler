"""
app.py  -- Battery Scheduler Flask application
Run: python app.py
"""
import os, io, json, threading, webbrowser
from flask import Flask, render_template, request, jsonify, send_file

from sch_core import schedule_to_sch
from sch_reader import sch_to_schedule
from mermaid_gen import schedule_to_mermaid

app = Flask(__name__)
SAVE_DIR = os.path.join(os.path.dirname(__file__), "saved")
os.makedirs(SAVE_DIR, exist_ok=True)


# -- Pages -------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -- API ---------------------------------------------------------------------
@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Return Mermaid diagram code for the current schedule."""
    try:
        data = request.get_json(force=True)
        mermaid_code = schedule_to_mermaid(data)
        return jsonify({"ok": True, "mermaid": mermaid_code})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/export", methods=["POST"])
def api_export():
    """Generate .sch binary and return as download."""
    try:
        data     = request.get_json(force=True)
        raw      = schedule_to_sch(data)
        buf      = io.BytesIO(raw)
        buf.seek(0)
        name     = data.get("schedule_name", "schedule").replace(" ", "_")
        filename = name + ".sch"
        try:
            return send_file(buf, as_attachment=True,
                             download_name=filename,
                             mimetype="application/octet-stream")
        except TypeError:
            return send_file(buf, as_attachment=True,
                             attachment_filename=filename,
                             mimetype="application/octet-stream")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/save", methods=["POST"])
def api_save():
    """Save schedule JSON to a named file."""
    try:
        data = request.get_json(force=True)
        name = data.get("schedule_name", "untitled").replace(" ", "_")
        path = os.path.join(SAVE_DIR, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "filename": name + ".json"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/list_saved", methods=["GET"])
def api_list_saved():
    """Return list of saved schedule files."""
    files = [f for f in os.listdir(SAVE_DIR) if f.endswith(".json")]
    return jsonify({"files": sorted(files)})


@app.route("/api/load", methods=["POST"])
def api_load():
    """Load a saved schedule JSON file."""
    try:
        body     = request.get_json(force=True)
        filename = body.get("filename", "")
        path     = os.path.join(SAVE_DIR, filename)
        if not os.path.exists(path):
            return jsonify({"ok": False, "error": "File not found"}), 404
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/import_sch", methods=["POST"])
def api_import_sch():
    """Import an uploaded .sch binary as editable schedule JSON."""
    try:
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"ok": False, "error": "No .sch file uploaded"}), 400
        if not uploaded.filename.lower().endswith(".sch"):
            return jsonify({"ok": False, "error": "Only .sch files are supported"}), 400

        cell_capacity_mAh = float(request.form.get("cell_capacity_mAh") or 100.0)
        data = uploaded.read()
        if not data:
            return jsonify({"ok": False, "error": "Uploaded file is empty"}), 400

        schedule = sch_to_schedule(data, cell_capacity_mAh=cell_capacity_mAh)
        return jsonify({"ok": True, "data": schedule})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# -- Launch ------------------------------------------------------------------
def open_browser():
    webbrowser.open("http://localhost:5000")

if __name__ == "__main__":
    threading.Timer(1.2, open_browser).start()
    app.run(debug=False, port=5000, use_reloader=False)
