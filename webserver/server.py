import os, sys, logging, yaml
from pathlib import Path
from flask import Flask, render_template, send_from_directory, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up app and grab configuration path
app = Flask(__name__)
config_path = Path(__file__).parent / '../config.yaml'

# Attempt to grab recording path within the config.yaml file
try:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
except FileNotFoundError as e:
    logger.error(f'Configuration file not found: {e}')
    sys.exit(1)

recordings_path = config['recordings_path']

# Homepage
@app.route('/')
def index():
    files = []
    hyperlinks = []
    for filename in os.listdir(recordings_path):
        if os.path.isfile(os.path.join(recordings_path, filename)):
            files.append(filename)
            hyperlinks.append(request.url+filename)
    
    return render_template('index.html', files=files, hyperlinks=hyperlinks)

# Dynamic file downloader (used for hyperlinks generated above)
@app.route('/<filename>', methods=['GET', 'POST'])
def download_file(filename):
    return send_from_directory(recordings_path, filename, as_attachment=True)

if __name__=='__main__':
    app.run() # Runs at port 8000 w/ Gunicorn