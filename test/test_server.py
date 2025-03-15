import os
import sys
from pathlib import Path
import logging

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, Response, render_template, redirect, request, url_for, jsonify, flash, send_file
from ruamel.yaml import YAML

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up paths
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
TEST_RECORDINGS_DIR = TEST_DIR / "recordings"
TEST_UPLOADS_DIR = TEST_DIR / "uploads"
TEST_SOUNDS_DIR = TEST_DIR / "sounds"

# Ensure test directories exist
TEST_RECORDINGS_DIR.mkdir(exist_ok=True)
TEST_UPLOADS_DIR.mkdir(exist_ok=True)
TEST_SOUNDS_DIR.mkdir(exist_ok=True)

# Detect template directory - try common locations
possible_template_dirs = [
    PROJECT_ROOT / "webserver" / "templates",
    PROJECT_ROOT / "templates",
]

TEMPLATES_DIR = None
for template_dir in possible_template_dirs:
    if template_dir.exists():
        if (template_dir / "index.html").exists():
            TEMPLATES_DIR = template_dir
            break

if not TEMPLATES_DIR:
    print("ERROR: Could not find templates directory!")
    for dir in possible_template_dirs:
        print(f" - {dir} {'[EXISTS]' if dir.exists() else '[NOT FOUND]'}")
    sys.exit(1)

print(f"Using templates from: {TEMPLATES_DIR}")

# Check for CSS files
CSS_FILE = PROJECT_ROOT / "static" / "css" / "output.min.css"
if not CSS_FILE.exists():
    print(f"WARNING: {CSS_FILE} not found! Tailwind CSS might not be properly compiled.")
    print("Run these commands in your project root:")
    print("  npx tailwindcss build -i static/css/tailwind.css -o static/css/output.css")
    print("  npx postcss static/css/output.css > static/css/output.min.css")

# Create Flask app
app = Flask(__name__, 
            static_url_path="/static",
            static_folder=str(PROJECT_ROOT / "static"),
            template_folder=str(TEMPLATES_DIR))
app.secret_key = "supersecretkey"

# Load or create test configuration
yaml = YAML()
config_file = TEST_DIR / "test_config.yaml"

if not config_file.exists():
    # Create a minimal test config
    config = {
        "alsa_hw_mapping": "default",
        "mixer_control_name": "Speaker",
        "format": "S16_LE",
        "file_type": "wav",
        "channels": 2,
        "hook_gpio": 22,
        "hook_type": "NC",
        "hook_bounce_time": 0.1,
        "recording_limit": 300,
        "sample_rate": 44100,
        "record_greeting_gpio": 23,
        "record_greeting_type": "NC",
        "record_greeting_bounce_time": 0.1,
        "beep": str(TEST_SOUNDS_DIR / "beep.wav"),
        "beep_volume": 1.0,
        "beep_start_delay": 0.0,
        "beep_include_in_message": True,
        "greeting": str(TEST_SOUNDS_DIR / "greeting.wav"),
        "greeting_volume": 1.0,
        "greeting_start_delay": 1.5,
        "time_exceeded": str(TEST_SOUNDS_DIR / "time_exceeded.wav"),
        "time_exceeded_volume": 1.0,
        "recordings_path": str(TEST_RECORDINGS_DIR),
        "time_exceeded_length": 300,
        "shutdown_gpio": 0,
        "shutdown_button_hold_time": 2,
    }
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    print(f"Created test config file at {config_file}")

with open(config_file, "r") as f:
    config = yaml.load(f)

recordings_path = Path(config["recordings_path"])

def normalize_path(path):
    """Normalize and convert paths to Unix format."""
    return str(Path(path).as_posix())

def update_config(form_data):
    """Update the YAML configuration with form data."""
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

# Define all routes from your production server
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/<filename>", methods=["GET"])
def download_file(filename):
    """Download a file dynamically from the recordings folder."""
    return send_file(str(recordings_path / filename), as_attachment=True)

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
        # Handle file uploads
        for field in ["greeting", "beep", "time_exceeded"]:
            if f"{field}_file" in request.files:
                file = request.files[f"{field}_file"]
                if file.filename:
                    file_path = TEST_UPLOADS_DIR / file.filename
                    file.save(file_path)
                    config[field] = normalize_path(file_path)

        update_config(request.form)

        with open(config_file, "w") as f:
            yaml.dump(config, f)

        flash("Configuration updated successfully!", "success")
        return redirect(url_for("edit_config"))

    return render_template("config.html", config=config)

@app.route("/recordings/<filename>")
def serve_recording(filename):
    """Serve a specific recording with proper streaming."""
    def generate():
        file_path = recordings_path / filename
        with open(file_path, "rb") as f:
            chunk = f.read(4096)
            while chunk:
                yield chunk
                chunk = f.read(4096)

    return Response(
        generate(), mimetype="audio/wav", headers={"Accept-Ranges": "bytes"}
    )

@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Mock shutdown the system."""
    logger.info("TEST MODE: System would shut down now")
    return jsonify({"success": True, "message": "TEST MODE: System would shut down now"})

@app.route("/reboot", methods=["POST"])
def reboot():
    """Mock reboot the system."""
    logger.info("TEST MODE: System would reboot now")
    return jsonify({"success": True, "message": "TEST MODE: System would reboot now"})

# Additional routes as needed

if __name__ == "__main__":
    # For a more production-like environment:
    # 1. Use the same port as production
    # 2. Disable debugging
    # 3. Listen on all interfaces (but with host='127.0.0.1' for security)
    
    print("\n=== PRODUCTION TEST SERVER ===")
    print(f"Template folder: {app.template_folder}")
    print(f"Static folder: {app.static_folder}")
    print("Starting server at http://127.0.0.1:8000\n")
    
    # Use the Flask development server in production mode
    app.run(debug=False, host="127.0.0.1", port=8000, use_reloader=False)