import io
import logging
import os
import re
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
    Response,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from ruamel.yaml import YAML

# Set up logging and app configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path="/static", static_folder="./static")
app.secret_key = "supersecretkey"  # Needed for flashing messages
config_path = Path(__file__).parent.parent / "config.yaml"
upload_folder = Path(__file__).parent.parent / "uploads"
upload_folder.mkdir(parents=True, exist_ok=True)

# Initialize ruamel.yaml
yaml = YAML()

# Attempt to grab recording path from the configuration file
try:
    with config_path.open("r") as f:
        config = yaml.load(f)
except FileNotFoundError as e:
    logger.error(f"Configuration file not found: {e}")
    sys.exit(1)

recordings_path = Path(config["recordings_path"])


def normalize_path(path):
    """Normalize and convert paths to Unix format."""
    return str(path.as_posix())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/<filename>", methods=["GET"])
def download_file(filename):
    """Download a file dynamically from the recordings folder."""
    return send_from_directory(recordings_path, filename, as_attachment=True)


@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    """Delete a specific recording."""
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
    """API route to get a list of all recordings."""
    files = [f.name for f in recordings_path.iterdir() if f.is_file()]
    return jsonify(files)


@app.route("/config", methods=["GET", "POST"])
def edit_config():
    """Handle GET and POST requests to edit the configuration."""
    if request.method == "POST":
        logger.info("Form data received:")
        for key, value in request.form.items():
            logger.info(f"  {key}: {value}")
        try:
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
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            flash(f"Error updating configuration: {str(e)}", "error")
            # Continue with current configuration but show error

    # Load the current configuration
    try:
        with config_path.open("r") as f:
            current_config = yaml.load(f)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        current_config = {}

    return render_template("config.html", config=current_config)


@app.route("/recordings/<filename>")
def serve_recording(filename):
    """Serve a specific recording with proper streaming and range support."""
    file_path = os.path.join(recordings_path, filename)

    # Get file size for range requests
    file_size = os.path.getsize(file_path)

    # Parse Range header
    range_header = request.headers.get('Range', None)

    if range_header:
        # Parse the range header
        byte1, byte2 = 0, None
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])

        if byte2 is None:
            byte2 = file_size - 1

        length = byte2 - byte1 + 1

        # Create the response with the proper headers for range request
        resp = Response(
            generate_file_chunks(file_path, byte1, byte2),
            status=206,
            mimetype='audio/wav',
            direct_passthrough=True
        )

        resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(length))
        return resp

    # If no range header, serve the whole file
    resp = Response(
        generate_file_chunks(file_path, 0, file_size - 1),
        mimetype='audio/wav'
    )
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(file_size))
    return resp

def generate_file_chunks(file_path, byte1=0, byte2=None):
    """Generator to stream file in chunks with range support."""
    with open(file_path, 'rb') as f:
        f.seek(byte1)
        while True:
            buffer_size = 8192
            if byte2:
                buffer_size = min(buffer_size, byte2 - f.tell() + 1)
                if buffer_size <= 0:
                    break
            chunk = f.read(buffer_size)
            if not chunk:
                break
            yield chunk


@app.route("/download-all")
def download_all():
    """Download all recordings as a zip file."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        wav_files = [f for f in recordings_path.iterdir() if f.suffix == ".wav"]

        # Log the files being added to the zip
        logger.info(f"Adding {len(wav_files)} files to zip")

        for file_path in wav_files:
            # Use absolute path for reading
            abs_path = str(file_path.absolute())
            logger.info(f"Adding file: {abs_path}")

            # Verify file exists and is readable
            if os.path.exists(abs_path) and os.access(abs_path, os.R_OK):
                # Add to zip with just the filename as the internal path
                zf.write(abs_path, arcname=file_path.name)
            else:
                logger.error(f"Cannot access file: {abs_path}")

    memory_file.seek(0)

    logger.info(f"Zip file size: {memory_file.getbuffer().nbytes} bytes")

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="recordings.zip",
    )


@app.route("/download-selected", methods=["POST"])
def download_selected():
    """Download selected recordings as a zip file."""
    selected_files = request.form.getlist("files[]")
    logger.info(f"Selected files for download: {selected_files}")

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for filename in selected_files:
            file_path = os.path.join(recordings_path, filename)
            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                logger.info(f"Adding to zip: {file_path}")
                zf.write(file_path, filename)
            else:
                logger.error(f"Cannot access file: {file_path}")

    memory_file.seek(0)
    logger.info(f"Zip file size: {memory_file.getbuffer().nbytes} bytes")

    return send_file(
        memory_file,
        mimetype="application/zip",
        download_name="selected_recordings.zip",
        as_attachment=True,
    )


@app.route("/rename/<old_filename>", methods=["POST"])
def rename_recording(old_filename):
    """Rename a recording."""
    new_filename = request.json["newFilename"]
    old_path = os.path.join(recordings_path, old_filename)
    new_path = os.path.join(recordings_path, new_filename)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        return jsonify(success=True)
    else:
        return jsonify(success=False), 404


@app.route("/reboot", methods=["POST"])
def reboot():
    """Reboot the system."""
    try:
        os.system("sudo reboot now")
        return jsonify({"success": True, "message": "System is rebooting..."})
    except Exception as e:
        logger.error(f"Failed to reboot: {e}")
        return jsonify(
            {"success": False, "message": "Failed to reboot the system!"}
        ), 500


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Shut down the system."""
    try:
        os.system("sudo shutdown now")
        return jsonify({"success": True, "message": "System is shutting down..."})
    except Exception as e:
        logger.error(f"Failed to shut down: {e}")
        return jsonify(
            {"success": False, "message": "Failed to shut down the system!"}
        ), 500


def update_config(form_data):
    """Update the YAML configuration with form data."""
    for key, value in form_data.items():
        # Skip CSRF token if it exists
        if key == 'csrf_token':
            continue

        # Check if key exists in config
        if key not in config:
            logger.warning(f"Form field '{key}' not found in config, skipping")
            continue

        # Log the conversion attempt
        logger.info(f"Updating '{key}': {config[key]} (type: {type(config[key]).__name__}) → '{value}'")

        try:
            # Convert value based on the type in config
            if isinstance(config[key], bool):
                # Convert string to boolean
                new_value = (value.lower() == "true")
                logger.info(f"Converting to boolean: {value} → {new_value}")
                config[key] = new_value
            elif isinstance(config[key], int):
                config[key] = int(value)
            elif isinstance(config[key], float):
                config[key] = float(value)
            else:
                config[key] = value

            # Verify the conversion worked
            logger.info(f"Updated '{key}' to: {config[key]} (type: {type(config[key]).__name__})")

        except (ValueError, TypeError) as e:
            logger.error(f"Failed to update '{key}': {e}")


@app.route("/api/system-status")
def system_status():
    """Return basic system information for the dashboard."""
    try:
        import psutil

        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage("/").percent
        recording_count = len([f for f in recordings_path.iterdir() if f.is_file()])

        return jsonify(
            {
                "success": True,
                "cpu": cpu_usage,
                "memory": memory_usage,
                "disk": disk_usage,
                "recordings": recording_count,
            }
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
