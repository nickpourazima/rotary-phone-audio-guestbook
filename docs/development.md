# Development Setup

For contributors interested in working on the project and testing new features before cutting a release, here’s a brief guide:

- Install node & npm

## Tailwind CSS Setup

Tailwind CSS is used for styling the web interface. To play around with the source code and style changes, you can use the following commands:

```bash
# Build Tailwind CSS
npx tailwindcss build -i static/css/tailwind.css -o static/css/output.css
```

To further optimize the CSS output for production:

```bash
# Minify CSS
npx postcss static/css/output.css > static/css/output.min.css
```

## Syncing Files with Raspberry Pi

To upload changes from your local dev machine to the Raspberry Pi (Pi Zero or similar), you can use the following rsync command:

```bash
# Sync files with Pi
rsync -av --exclude-from='./rsync-exclude.txt' ${CWD}/rotary-phone-audio-guestbook admin@192.168.x.x:/home/admin
# Replace 192.168.x.x with the actual IP address of your Raspberry Pi.
```

## Starting the Web Server in Development Mode

For testing the Flask-based web server on the Raspberry Pi:

```bash
# Start webserver on Raspberry Pi
flask --app webserver/server.py run -h 192.168.x.x -p 8080
```

## Python dependencies

I've been using [uv](https://github.com/astral-sh/uv) by @astral-sh, and love it! Would highly recommend as it is extremely fast and much more robust relative to pip.

```bash
pip3 install uv
uv pip install -r requirements.txt
#OR
uv pip install -r pyproject.toml
```

Alternatively, to directly run the main audioGuestBook script (this will pull necessary dependencies from pyproject.toml):

```bash
# Directly run audioGuestBook
uv run src/audioGuestBook.py
```

## Generating an img for a release

I use [RonR-RPi-image-utils](https://github.com/seamusdemora/RonR-RPi-image-utils), thank you to @scruss & @seamusdemora!

If you would like to create a full image for ease f deployment there's a [`deploy.sh`](deploy.sh) script that I created which will run through this process. Edit the ENV VARS inside to point to your own local dev environment.

Alternatively, a manual run would look something like this:

```bash
sudo image-backup -i /mnt/rpizero_rotary_phone_audio_guestbook_v<insert_incremental_version_number_here>_imagebackup.img
md5sum /mnt/rpizero_rotary_phone_audio_guestbook_v<version number>_imagebackup.img
```

**Note**: for incremental backups (much faster) point to the existing img and run:

```sh
sudo image-backup /mnt/rpizero_rotary_phone_audio_guestbook_v<prior_version_number>_imagebackup.img
```

## Debugging

To help with debugging the `audioGuestBook` service and the webserver, use these commands:

```bash
# Monitor the audioGuestBook service logs
journalctl -fu audioGuestBook.service
# OR
journalctl -fu audioGuestBookWebServer.service
```
