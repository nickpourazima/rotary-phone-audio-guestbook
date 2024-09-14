import os
import sys
import logging
from pathlib import Path
from flask import Flask, render_template, send_from_directory, request, send_file, redirect, url_for, flash
from ruamel.yaml import YAML
import zipfile
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up app and grab configuration path
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages
config_path = Path(__file__).parent / '../config.yaml'
upload_folder = Path(__file__).parent / '../uploads'  # Directory to save uploaded files
upload_folder.mkdir(parents=True, exist_ok=True)  # Create the upload folder if it doesn't exist

# Initialize ruamel.yaml
yaml = YAML()

# Attempt to grab recording path within the config.yaml file
try:
    with open(config_path, 'r') as f:
        config = yaml.load(f)
except FileNotFoundError as e:
    logger.error(f'Configuration file not found: {e}')
    sys.exit(1)

recordings_path = config['recordings_path']

# Function to convert and normalize paths to Unix format
def normalize_path(path_str):
    return str(Path(path_str).as_posix())  # Ensures path is Unix-compatible

# Homepage
@app.route('/')
def index():
    files = []
    hyperlinks = []
    for filename in os.listdir(recordings_path):
        if os.path.isfile(os.path.join(recordings_path, filename)):
            files.append(filename)
            hyperlinks.append(request.url + filename)
            
    print(files)  # Debugging
    
    return render_template('index.html', files=files, hyperlinks=hyperlinks)

# Dynamic file downloader (used for hyperlinks generated above)
@app.route('/<filename>', methods=['GET', 'POST'])
def download_file(filename):
    return send_from_directory(recordings_path, filename, as_attachment=True)

# Configuration editor
@app.route('/config', methods=['GET', 'POST'])
def edit_config():
    if request.method == 'POST':
        # Handle Greeting file upload
        if 'greeting_file' in request.files:
            greeting_file = request.files['greeting_file']
            if greeting_file.filename != '':
                greeting_filename = greeting_file.filename
                greeting_path = upload_folder / greeting_filename
                greeting_file.save(greeting_path)
                # Update the greeting path in the config
                config['greeting'] = normalize_path(greeting_path.relative_to(Path(__file__).parent.parent))

        # Handle Beep file upload
        if 'beep_file' in request.files:
            beep_file = request.files['beep_file']
            if beep_file.filename != '':
                beep_filename = beep_file.filename
                beep_path = upload_folder / beep_filename
                beep_file.save(beep_path)
                # Update the beep path in the config
                config['beep'] = normalize_path(beep_path.relative_to(Path(__file__).parent.parent))

        # Handle Time Exceeded file upload
        if 'time_exceeded_file' in request.files:
            time_exceeded_file = request.files['time_exceeded_file']
            if time_exceeded_file.filename != '':
                time_exceeded_filename = time_exceeded_file.filename
                time_exceeded_path = upload_folder / time_exceeded_filename
                time_exceeded_file.save(time_exceeded_path)
                # Update the time exceeded path in the config
                config['time_exceeded'] = normalize_path(time_exceeded_path.relative_to(Path(__file__).parent.parent))

        # Update the config fields without losing comments
        config['alsa_hw_mapping'] = request.form['alsa_hw_mapping']
        config['mixer_control_name'] = request.form['mixer_control_name']
        config['format'] = request.form['format']
        config['file_type'] = request.form['file_type']
        config['channels'] = int(request.form['channels'])
        config['hook_gpio'] = int(request.form['hook_gpio'])
        config['hook_type'] = request.form['hook_type']
        config['hook_bounce_time'] = float(request.form['hook_bounce_time'])
        config['recording_limit'] = int(request.form['recording_limit'])
        config['sample_rate'] = int(request.form['sample_rate'])
        config['record_greeting_gpio'] = int(request.form['record_greeting_gpio'])
        config['record_greeting_type'] = request.form['record_greeting_type']
        config['record_greeting_bounce_time'] = float(request.form['record_greeting_bounce_time'])
        config['beep_volume'] = float(request.form['beep_volume'])
        config['beep_start_delay'] = float(request.form['beep_start_delay'])
        config['beep_include_in_message'] = request.form['beep_include_in_message'] == 'True'
        config['greeting'] = config.get('greeting', request.form['greeting'])
        config['greeting_volume'] = float(request.form['greeting_volume'])
        config['greeting_start_delay'] = float(request.form['greeting_start_delay'])
        config['time_exceeded_volume'] = float(request.form['time_exceeded_volume'])
        config['recordings_path'] = normalize_path(request.form['recordings_path'])
        config['time_exceeded_length'] = int(request.form['time_exceeded_length'])

        # Write the updated config back to the file
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        flash('Configuration updated successfully!', 'success')
        return redirect(url_for('edit_config'))

    # Load the current configuration to display in the form
    try:
        with open(config_path, 'r') as f:
            current_config = yaml.load(f)
    except FileNotFoundError as e:
        logger.error(f'Configuration file not found: {e}')
        current_config = {}
    
    return render_template('edit_config.html', config=current_config)


@app.route('/recordings/<filename>')
def serve_recording(filename):
    return send_from_directory(config['recordings_path'], filename)


@app.route('/download-all')
def download_all():
    # Erstelle ein Byte-Stream für die ZIP-Datei
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for filename in os.listdir(recordings_path):
            if filename.endswith('.wav'):
                # Füge jede Datei zum ZIP-Archiv hinzu
                file_path = os.path.join(recordings_path, filename)
                zf.write(file_path, arcname=filename)  # arcname = nur der Dateiname in der ZIP
    memory_file.seek(0)

    # Sende die ZIP-Datei an den Benutzer
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name='recordings.zip')


@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Shuts down the Raspberry Pi system.
    """
    try:
        os.system("sudo shutdown now")
        flash('System is shutting down...', 'info')
    except Exception as e:
        logger.error(f"Failed to shut down: {e}")
        flash('Failed to shut down the system!', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()  # Runs at port 8000 w/ Gunicorn
