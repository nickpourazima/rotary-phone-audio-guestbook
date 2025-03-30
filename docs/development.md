# Development Setup

For contributors interested in working on the project and testing new features before cutting a release, here's a brief guide.

## Prerequisites

- Python 3.9.2 or higher
- Raspberry Pi OS with necessary system dependencies

### System Dependencies

Install these system-level packages required for building Python extensions:

```bash
# Required system packages for development
sudo apt-get update
sudo apt-get install libffi-dev
```

The libffi-dev package provides necessary header files for compiling Python packages with C extensions, including gevent which improves web server performance.

### Node.js and npm

Install Node.js and npm for frontend development:

```bash
sudo apt-get install npm
```

## Python Dependencies Management

This project uses [uv](https://github.com/astral-sh/uv) by @astral-sh as the package manager. It's extremely fast and more robust compared to pip.

### Setting Up a Development Environment

```bash
# Install uv if you don't have it
pip install uv

# Create and activate a virtual environment
uv venv
# On Linux/Mac
source .venv/bin/activate
# On Windows (Command Prompt)
.venv\Scripts\activate
# On Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies from pyproject.toml
uv pip install -e .

# Or install from requirements.txt
uv pip install -r requirements.txt
```

If you modify dependencies in pyproject.toml, update requirements.txt with:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Alternatively, to directly run the main audioGuestBook script:

```bash
# Directly run audioGuestBook
uv run src/audioGuestBook.py
```

### Installing Gevent

For better web server performance, install gevent:

```bash
uv pip install gevent
```

## Frontend Development with Tailwind CSS

Tailwind CSS is used for styling the web interface. To set up the frontend build process:

```bash
# Install required npm packages
npm install -D tailwindcss postcss autoprefixer cssnano
```

### Building and Optimizing CSS

For development, build the CSS files:

```bash
# Build Tailwind CSS
cd webserver
npx tailwindcss -i static/css/tailwind.css -o static/css/output.css
```

For production, optimize and minify the CSS:

```bash
# Generate optimized CSS by removing unused styles
cd webserver
npx tailwindcss -i static/css/tailwind.css -o static/css/output.css
# Further minify CSS to reduce file size
npx postcss static/css/output.css -o static/css/output.min.css
```

## Streaming Audio Support

The project uses gevent workers for the Gunicorn server to enable proper streaming of audio files. This prevents the server from timing out when playing longer recordings. The `start_server.sh` script is configured to use gevent workers with:

```bash
exec gunicorn -w 1 -k gevent -b ${IP_ADDRESS}:8080 webserver.server:app
```

## Development Workflow

The typical development workflow involves:

1. Making changes on your local development machine
2. Syncing those changes to the Raspberry Pi
3. Testing the changes on the Raspberry Pi
4. Creating backups/releases when satisfied

### Syncing Files with Raspberry Pi

To upload changes from your local dev machine to the Raspberry Pi (Pi Zero or similar), you can use the following rsync command:

```bash
# Sync files with Pi
rsync -av --exclude-from='./rsync-exclude.txt' ./ admin@192.168.x.x:/home/admin/rotary-phone-audio-guestbook
# Replace 192.168.x.x with the actual IP address of your Raspberry Pi.
```

### Starting the Web Server in Development Mode

For testing the Flask-based web server on the Raspberry Pi:

```bash
# Start webserver on Raspberry Pi
flask --app webserver/server.py run -h 192.168.x.x -p 8080
```

## Deploying and Creating Releases

### Using the Deploy Script

The included `deploy.sh` script automates the deployment process. It:

1. Syncs files from your local machine to the Raspberry Pi
2. Installs and configures service files on the Raspberry Pi
3. Creates a backup image of the Raspberry Pi's SD card (using incremental backup when possible)
4. Copies the backup image back to your local machine's backup directory

To use it:

```bash
# Edit the variables at the top of deploy.sh to match your environment
./deploy.sh
```

Make sure to configure these variables in the script:

- `RPI_USER`: Username on the Raspberry Pi (usually "admin")
- `RPI_IP`: IP address of your Raspberry Pi
- `IMG_VERSION`: Version number for the backup image

#### Setting Up SSH Key Authentication (Optional)

To avoid having to enter your password multiple times during deployment, you can set up SSH key authentication:

```bash
# Generate an SSH key if you don't have one
ssh-keygen -t rsa -b 4096

# Copy your public key to the Raspberry Pi
ssh-copy-id admin@192.168.x.x
```

After setting up SSH keys, the deploy script will run without password prompts.

### Generating an Image for a Release Manually

The deploy script uses [RonR-RPi-image-utils](https://github.com/seamusdemora/RonR-RPi-image-utils) (thank you to @scruss & @seamusdemora) to create backup images.

To install it on your Raspberry Pi:

```bash
# Clone the repository
git clone https://github.com/seamusdemora/RonR-RPi-image-utils.git

# Install the script
cd RonR-RPi-image-utils
sudo ./install.sh
```

Alternatively, a manual run would look something like this:

```bash
# Create a full image backup
sudo image-backup -i /mnt/rpizero_rotary_phone_audio_guestbook_v<version_number>_imagebackup.img

# Check the integrity
md5sum /mnt/rpizero_rotary_phone_audio_guestbook_v<version_number>_imagebackup.img
```

**Note**: For incremental backups (much faster) point to the existing img file:

```bash
sudo image-backup /mnt/rpizero_rotary_phone_audio_guestbook_v<prior_version_number>_imagebackup.img
```

### Backup Strategy

The deploy script automatically handles finding the best backup strategy:

1. It first checks if the current version backup already exists (for updates to the same version)
2. If not, it tries to find previous versions to use as a base for incremental backup
3. If no previous versions are found, it falls back to a full backup

This approach minimizes backup time when working with iterative releases.

## Debugging

To help with debugging the `audioGuestBook` service and the webserver, use these commands:

```bash
# Monitor the audioGuestBook service logs
journalctl -fu audioGuestBook.service
# OR
journalctl -fu audioGuestBookWebServer.service
```

### Common Issues and Solutions

- **Hook switch detection issues**: Check the `hook_type` and `invert_hook` settings in `config.yaml`
- **Audio not working**: Verify ALSA configuration with `aplay -l` and `amixer scontrols`
- **Race conditions during rapid hook toggling**: Increase `hook_bounce_time` in `config.yaml`
- **No recordings saved**: Check file permissions and make sure `recordings_path` directory exists
- **Deploy script asking for password multiple times**: Set up SSH key authentication as described above
