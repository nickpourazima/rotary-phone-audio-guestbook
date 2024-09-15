import io
import logging
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from ruamel.yaml import YAML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up app and grab configuration path
app = Flask(__name__, static_url_path="/static", static_folder="./static")
app.secret_key = "supersecretkey"  # Needed for flashing messages
config_path = Path(__file__).parent.parent / "config.yaml"
upload_folder = Path(__file__).parent.parent / "uploads"
upload_folder.mkdir(parents=True, exist_ok=True)

# Initialize ruamel.yaml
yaml = YAML()

# Attempt to grab recording path within the config.yaml file
try:
    with config_path.open("r") as f:
        config = yaml.load(f)
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {e}")
    sys.exit(1)

recordings_path = Path(config["recordings_path"])


# Function to convert and normalize paths to Unix format
def normalize_path(path):
    return str(path.as_posix())


@app.route("/")
def index():
    return render_template("index.html")


# Dynamic file downloader (used for hyperlinks generated above)
@app.route("/<filename>", methods=["GET", "POST"])
def download_file(filename):
    return send_from_directory(recordings_path, filename, as_attachment=True)


@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    file_path = recordings_path / filename
    try:
        file_path.unlink()
        return jsonify({"success": True, "message": f"{filename} has been deleted."})
    except Exception as e:
        return jsonify(
            {"success": False, "message": f"Error deleting file: {str(e)}"}
        ), 500


@app.route("/api/recordings")
def get_recordings():
    files = [f.name for f in recordings_path.iterdir() if f.is_file()]
    return jsonify(files)


def update_config(form_data):
    for key, value in form_data.items():
        if key in config:
            if isinstance(config[key], int):
                config[key] = int(value)
            elif isinstance(config[key], float):
                config[key] = float(value)
            elif isinstance(config[key], bool):
                config[key] = value.lower() == "true"
            else:
                config[key] = value


@app.route("/config", methods=["GET", "POST"])
def edit_config():
    if request.method == "POST":
        # Handle file uploads
        for field in ["greeting", "beep", "time_exceeded"]:
            if f"{field}_file" in request.files:
                file = request.files[f"{field}_file"]
                if file.filename:
                    file_path = upload_folder / file.filename
                    file.save(file_path)
                    config[field] = normalize_path(
                        file_path.relative_to(config_path.parent)
                    )

        update_config(request.form)

        with config_path.open("w") as f:
            yaml.dump(config, f)

        flash("Configuration updated successfully!", "success")
        return redirect(url_for("edit_config"))

    # Load the current configuration to display in the form
    try:
        with config_path.open("r") as f:
            current_config = yaml.load(f)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        current_config = {}

    return render_template("config.html", config=current_config)


@app.route("/recordings/<filename>")
def serve_recording(filename):
    return send_from_directory(str(recordings_path), filename)


@app.route("/download-all")
def download_all():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        wav_files = [f for f in recordings_path.iterdir() if f.suffix == ".wav"]
        for file_path in wav_files:
            zf.write(file_path, arcname=file_path.name)
    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="recordings.zip",
    )


@app.route("/download-selected", methods=["POST"])
def download_selected():
    selected_files = request.form.getlist("files[]")
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for filename in selected_files:
            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                zf.write(file_path, filename)

    memory_file.seek(0)
    return send_file(
        memory_file, download_name="selected_recordings.zip", as_attachment=True
    )


@app.route("/rename/<old_filename>", methods=["POST"])
def rename_recording(old_filename):
    new_filename = request.json["newFilename"]
    old_path = os.path.join(recordings_path, old_filename)
    new_path = os.path.join(recordings_path, new_filename)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        return jsonify(success=True)
    else:
        return jsonify(success=False), 404


@app.route("/shutdown", methods=["POST"])
def shutdown():
    try:
        os.system("sudo shutdown now")
        return jsonify({"success": True, "message": "System is shutting down..."})
    except Exception as e:
        logger.error(f"Failed to shut down: {e}")
        return jsonify(
            {"success": False, "message": "Failed to shut down the system!"}
        ), 500


if __name__ == "__main__":
    app.run()  # Runs at port 8000 w/ Gunicorn
