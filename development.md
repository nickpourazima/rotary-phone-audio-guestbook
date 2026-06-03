# Development Setup

For contributors working on the project and testing new features before cutting a release.

There are two layers: a **local development environment** on your own machine (editor support, linting, running the web server off-device) and **provisioning/testing on a Pi**. Note that on the Pi itself, everything is installed via `apt` by `install.sh` — the `uv`/venv flow below is only for local development convenience.

## Prerequisites

- Python 3.11+ (Raspberry Pi OS Trixie ships 3.11)
- For on-device testing: a Raspberry Pi running Raspberry Pi OS Lite (Trixie)
- Node.js and npm (only for rebuilding the Tailwind CSS)

## Local development environment (optional)

This project uses [uv](https://github.com/astral-sh/uv) by @astral-sh for a fast local virtual environment.

```
# Install uv if you don't have it
pip install uv

# Create and activate a virtual environment
uv venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .                  # or: uv pip install -r requirements.txt
```

If you change dependencies in `pyproject.toml`, regenerate `requirements.txt`:

```
uv pip compile pyproject.toml -o requirements.txt
```

`libffi-dev` is only needed if you compile `gevent` from source inside a venv; the device install uses the prebuilt `python3-gevent` apt package instead.

## Frontend development with Tailwind CSS

```
# Install required npm packages
npm install -D tailwindcss postcss autoprefixer cssnano

# Build
cd webserver
npx tailwindcss -i static/css/tailwind.css -o static/css/output.css

# Minify for production
npx postcss static/css/output.css -o static/css/output.min.css
```

**Commit the built `output.min.css`.** The device installer does not install Node/npm, so the compiled CSS must be present in the repo.

## Streaming audio support

The web server uses gevent workers under Gunicorn so that streaming longer recordings doesn't time out. `start_server.sh` runs:

```
exec gunicorn -w 1 -k gevent -b ${IP_ADDRESS}:8080 webserver.server:app
```

## Provisioning a Pi for testing

The entire device setup lives in a single, idempotent [`install.sh`](../install.sh) — there is no hand-configured "golden" image. On a fresh Raspberry Pi OS Lite (Trixie):

1. Flash the OS, and in Raspberry Pi Imager's OS customisation set username/password, WiFi (with **WiFi country**), and enable SSH.
2. SSH in and run the installer:

```
curl -sSL https://raw.githubusercontent.com/nickpourazima/rotary-phone-audio-guestbook/main/install.sh | sudo bash
```

Or, from a checkout, passing the WiFi country so the hotspot can start:

```
WIFI_COUNTRY=DE sudo -E ./install.sh
```

`install.sh` installs the apt dependencies, configures GPIO (`lgpio` backend), boot-time USB audio auto-detection, the NetworkManager hotspot fallback, and the systemd services. It is safe to re-run.

## Iterating on code on the device

The project is installed under `/opt/rotary-phone-audio-guestbook` (owned by root). To push your working copy and restart the services:

```
rsync -av --exclude-from='./rsync-exclude.txt' ./ root@<pi>:/opt/rotary-phone-audio-guestbook/
ssh root@<pi> 'systemctl restart audioGuestBook.service audioGuestBookWebServer.service'
```

`config.yaml` is not tracked in git and lives only on the device, so rsync won't overwrite the device's configuration.

For quick web-UI iteration you can also run the server directly:

```
flask --app webserver/server.py run -h 0.0.0.0 -p 8080
```

## Creating a release

No golden Pi and no manual image backup. The release image is built reproducibly in CI by [`/.github/workflows/build-image.yml`](../.github/workflows/build-image.yml):

- It downloads the pinned Raspberry Pi OS Lite (Trixie, armhf) base image, runs `install.sh` inside it with CustoPiZer, then compresses and attaches the `.img.gz` (plus a `.sha256`) to the release.
- **Cut a release:** `git tag vX.Y.Z && git push origin vX.Y.Z`. The tag triggers the build and attaches the image to the release.
- **Test the build without releasing:** Actions → "Build release image" → Run workflow (ref `main`), then download the artifact.

> The previous `deploy.sh` + [RonR-RPi-image-utils](https://github.com/seamusdemora/RonR-RPi-image-utils) flow is no longer used; you no longer dump a manually configured SD card to produce a release.

## Debugging

```
# Guestbook and web server logs (use -n N --no-pager for a snapshot;
# -f follows live and is exited with Ctrl+C — it is not a freeze)
journalctl -u audioGuestBook.service -n 50 --no-pager
journalctl -u audioGuestBookWebServer.service -n 50 --no-pager

# Audio: what card was detected and how the default is routed
journalctl -u agb-audio-detect.service --no-pager
cat /etc/asound.conf
aplay -l

# Hotspot fallback
journalctl -u agb-hotspot.service --no-pager
nmcli connection show
```

### Common issues and solutions

- **Hook switch detection issues**: check `hook_type` and `invert_hook` in `config.yaml`.
- **No audio / wrong sound card**: the boot detector should select the USB card automatically. Check `journalctl -u agb-audio-detect.service` and `/etc/asound.conf`. For a non-USB card (e.g. an I2S HAT), set an explicit `alsa_hw_mapping` (such as `plughw:CARD=<name>,DEV=0`) in `config.yaml`.
- **Hotspot won't start**: ensure the WiFi country is set (`sudo raspi-config nonint do_wifi_country <CC>`) and the radio is unblocked (`rfkill list`). To keep the AP stable during an event, set `HOTSPOT_AUTORETURN=0` in `/etc/default/agb-hotspot`.
- **Race conditions during rapid hook toggling**: increase `hook_bounce_time` in `config.yaml`.
- **No recordings saved**: check that `recordings_path` exists and is writable.
