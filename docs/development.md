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

# Create the environment from the lockfile and install the project.
# `--frozen` installs the EXACT versions pinned in uv.lock with NO re-resolution,
# and uv verifies every downloaded artifact against the hash recorded in the
# lock. So local dev and the manual test harness (test/test_server.py) run
# against a reproducible, tamper-evident set of dependencies — a compromised
# index serving a different "flask 3.0.3" would fail the hash check.
uv sync --frozen

# Activate it (or skip activation and use `uv run <cmd>`)
source .venv/bin/activate            # Windows: .venv\Scripts\activate
```

> Use `uv sync --frozen`, not `uv pip install -e .`, to set up the test
> environment. `uv pip install` is the pip-compatible interface: it resolves
> fresh from the `>=` specifiers in `pyproject.toml`, ignores `uv.lock`, and does
> not enforce hashes — so it can pull newer (or substituted) versions than the
> project is pinned to. After intentionally changing dependencies, run `uv lock`
> to refresh `uv.lock` (and `uv pip compile pyproject.toml -o requirements.txt`
> to refresh the pip mirror), then commit the updated lock.

If you change dependencies in `pyproject.toml`, refresh both the lockfile and
the `requirements.txt` pip mirror:

```
uv lock                                          # update uv.lock
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

## Building and testing the image locally

Two helper scripts under [`tools/`](../tools) let you build and inspect the release image on your own machine (macOS with OrbStack/Docker, or Linux) without waiting for CI. They mirror the CI workflow: download the pinned Trixie base image, run `install.sh` inside it with a Trixie-patched CustoPiZer, and produce `workspace/output.img`.

```
# build from a branch/tag (defaults to main); install.sh is fetched from that ref
./tools/build-local.sh my-branch

# inspect the result offline (mounts the image, prints sanity checks, exits)
./tools/check-image.sh workspace/output.img
```

Notes:

- `build-local.sh` fetches `install.sh` from GitHub for the given ref, so push your branch before building from it.
- It needs Docker with privileged containers; the build runs the armhf chroot under qemu and takes a while (emulated). The loop-mount + chroot work under OrbStack.
- `check-image.sh` verifies the baked-in pieces (default `pi` user, SSH enabled, WiFi regdom in `cmdline.txt`, enabled services/timer, the hotspot keyfile, the ALSA mapping). `/etc/asound.conf` is intentionally absent until first boot.
- To flash `output.img`, use Raspberry Pi Imager → "Use custom".

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

# Boot/service deadlocks and what's listening
systemctl list-jobs                 # a stuck "running" job blocks everything behind it
ss -tlnp | grep 8080                 # should show gunicorn on 0.0.0.0:8080
```

### Common issues and solutions

- **Hook switch detection issues**: check `hook_type` and `invert_hook` in `config.yaml`.
- **No audio / wrong sound card**: the boot detector should select the USB card automatically. Check `journalctl -u agb-audio-detect.service` and `/etc/asound.conf`. For a non-USB card (e.g. an I2S HAT), set an explicit `alsa_hw_mapping` (such as `plughw:CARD=<name>,DEV=0`) in `config.yaml`.
- **A service won't start, `status=217/USER`**: the unit references a user that does not exist. The shipped `.service` files were written for an `admin` user, but the image's user is `pi` and the services run as `root` via the `…/*.service.d/10-agb.conf` drop-in. If you edit the units, keep `User=root` (or a user that exists).
- **A service won't start, `status=203/EXEC`**: `ExecStart` points to a path that doesn't exist. The project lives in `/opt/rotary-phone-audio-guestbook`, but the shipped units hardcode the old `/home/admin/...` path. Drop-ins override `WorkingDirectory`, and the web server's `ExecStart` is replaced with the system `gunicorn`. Inspect the effective unit with `systemctl cat <unit>`.
- **Headless boot hangs, services never start**: run `systemctl list-jobs`. If `userconfig.service` shows as `running`, Raspberry Pi OS's interactive first-boot user setup is blocking `multi-user.target` while waiting on the console. The image masks it (`sudo systemctl mask userconfig.service`); re-mask if it reappears.
- **Web UI reachable on one network but not the other (home WiFi vs hotspot)**: the server must bind to all interfaces (`-b 0.0.0.0:8080`), not a single IP. Verify with `ss -tlnp | grep 8080`.
- **Hotspot won't start**: the WiFi country is baked in (`DE`); for another region run `sudo raspi-config nonint do_wifi_country <CC>` and reboot, and check `rfkill list`. The hotspot stays up and stable while no home network is saved; once one is saved, set `HOTSPOT_AUTORETURN=0` in `/etc/default/agb-hotspot` to keep it from briefly dropping during an event.
- **Race conditions during rapid hook toggling**: increase `hook_bounce_time` in `config.yaml`.
- **No recordings saved**: check that `recordings_path` exists and is writable (it lives under the install directory and the services run as `root`).
