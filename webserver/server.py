import os
import sys
import logging
import yaml
from pathlib import Path
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up app and grab configuration path
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages
config_path = Path(__file__).parent / '../config.yaml'
upload_folder = Path(__file__).parent / '../uploads'  # Directory to save uploaded files
upload_folder.mkdir(parents=True, exist_ok=True)  # Create the upload folder if it doesn't exist

# Attempt to grab recording path within the config.yaml file
try:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
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
    
    return render_template('index.html', files=files, hyperlinks=hyperlinks)

# Dynamic file downloader (used for hyperlinks generated above)
@app.route('/<filename>', methods=['GET', 'POST'])
def download_file(filename):
    return send_from_directory(recordings_path, filename, as_attachment=True)

# Configuration editor
@app.route('/config', methods=['GET', 'POST'])
def edit_config():
    if request.method == 'POST':
        # Handle file upload
        if 'greeting_file' in request.files:
            greeting_file = request.files['greeting_file']
            if greeting_file.filename != '':
                greeting_filename = greeting_file.filename
                greeting_path = upload_folder / greeting_filename
                greeting_file.save(greeting_path)
                # Store the Unix-compatible relative path
                config['greeting'] = normalize_path(greeting_path.relative_to(Path(__file__).parent.parent))

        # Save the updated configuration
        try:
            updated_config = {
                'alsa_hw_mapping': request.form['alsa_hw_mapping'],
                'mixer_control_name': request.form['mixer_control_name'],
                'format': request.form['format'],
                'file_type': request.form['file_type'],
                'channels': int(request.form['channels']),
                'hook_gpio': int(request.form['hook_gpio']),
                'hook_type': request.form['hook_type'],
                'hook_bounce_time': float(request.form['hook_bounce_time']),
                'recording_limit': int(request.form['recording_limit']),
                'sample_rate': int(request.form['sample_rate']),
                'record_greeting_gpio': int(request.form['record_greeting_gpio']),
                'record_greeting_type': request.form['record_greeting_type'],
                'record_greeting_bounce_time': float(request.form['record_greeting_bounce_time']),
                'beep': normalize_path(request.form['beep']),
                'beep_volume': float(request.form['beep_volume']),
                'beep_start_delay': float(request.form['beep_start_delay']),
                'beep_include_in_message': request.form['beep_include_in_message'] == 'True',
                'greeting': config.get('greeting', request.form['greeting']),
                'greeting_volume': float(request.form['greeting_volume']),
                'greeting_start_delay': float(request.form['greeting_start_delay']),
                'time_exceeded': normalize_path(request.form['time_exceeded']),
                'time_exceeded_volume': float(request.form['time_exceeded_volume']),
                'recordings_path': normalize_path(request.form['recordings_path']),
                'time_exceeded_length': int(request.form['time_exceeded_length']),
            }
            with open(config_path, 'w') as f:
                yaml.safe_dump(updated_config, f)
            flash('Configuration updated successfully!', 'success')
            return redirect(url_for('edit_config'))
        except Exception as e:
            logger.error(f'Failed to save configuration: {e}')
            flash('Failed to update configuration.', 'error')
    
    # Load the current configuration to display in the form
    try:
        with open(config_path, 'r') as f:
            current_config = yaml.safe_load(f)
    except FileNotFoundError as e:
        logger.error(f'Configuration file not found: {e}')
        current_config = {}
    
    return render_template('edit_config.html', config=current_config)

if __name__ == '__main__':
    app.run()  # Runs at port 8000 w/ Gunicorn
