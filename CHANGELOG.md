# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - Unreleased

Reworked build and provisioning. The setup is now driven by a single script
and the release image is produced reproducibly in CI, so no hand-configured
"golden" Pi is required to cut a release.

### Added

- `install.sh`: a single, idempotent installer that is the source of truth for
  provisioning. Runs both on a live Raspberry Pi OS Lite install and inside the
  image-build chroot.
- GitHub Actions workflow (`.github/workflows/build-image.yml`) that builds the
  flashable release image with CustoPiZer from a pinned base image and attaches
  it (plus a `.sha256`) to the release.
- NetworkManager-native hotspot fallback (AP profile, decision script, NM
  dispatcher hook and a periodic systemd timer). Configurable via
  `/etc/default/agb-hotspot` (e.g. `HOTSPOT_AUTORETURN`).
- Boot-time audio auto-detection (`agb-audio-detect.service`): resolves the
  ALSA `default` device to the USB sound card **by name**, so audio works on
  any Pi model regardless of the card number (the cause of "no beeps / error
  524" reports on Pi 4, where the USB card is card 3 rather than card 1).
- `config.example.yaml` template; `config.yaml` is generated from it on first
  install with the install path substituted in.
- Release image ships ready to use: a default user (`pi`/`password`), SSH
  enabled, and a baked default WiFi country, since the Raspberry Pi Imager's OS
  customisation is disabled for custom images. Raspberry Pi OS's interactive
  first-boot user setup (`userconfig.service`) is disabled so a headless boot
  completes without waiting on the console. The hotspot uses WPA2 (AES) on
  channel 1 for universal client compatibility. A `custom.toml` can
  pre-configure WiFi/login before first boot.

### Changed

- Base OS upgraded from Raspberry Pi OS Bullseye to **Debian 13 "Trixie"**.
- GPIO now uses the `lgpio` backend (`GPIOZERO_PIN_FACTORY=lgpio`), which works
  on the new kernel GPIO interface and adds Pi 5 compatibility.
- Python and system dependencies are installed via `apt` (no `pip`/venv on the
  target), which is faster and most reliable on the armv6 Pi Zero and avoids
  PEP 668 issues.
- ALSA configuration is installed system-wide to `/etc/asound.conf`.
- `config.yaml` default `alsa_hw_mapping` is now `default` (was `plughw:1,0`),
  and `config.yaml` is no longer tracked in git (it is runtime-mutable); use
  `config.example.yaml` as the template.
- Project now installs under `/opt/rotary-phone-audio-guestbook` (was
  `/home/admin/...`). The systemd services run as `root` and pick up the install
  path and GPIO backend via drop-ins, because the original units hardcoded the
  `admin` user and home path (which caused `217/USER` / `203/EXEC` failures).
- Web server now runs the system `gunicorn` bound to `0.0.0.0:8080` (previously
  a venv-based `start_server.sh` bound to the `wlan0` IP). It is therefore
  reachable on both the home network and the hotspot at `10.0.0.5`, and no
  longer depends on a virtualenv.
- Hotspot stays up and stable when no home network is saved; auto-return is only
  attempted once a home network exists. The NetworkManager dispatcher no longer
  reacts to the hotspot's own up/down events (which previously caused the AP to
  flap and drop connected clients).

### Removed

- Dependency on the RaspberryConnect AutoHotspot installer and its interactive
  setup. The hotspot is now configured automatically at install time.
- The need to dump a manually configured SD card to produce a release image.

### Notes

- The image is 32-bit (armhf) and runs on all Pi models from Pi 1 / Zero to
  Pi 5. The hotspot requires onboard WiFi.
- Trixie is expected to be the last Raspberry Pi OS release supporting armv6
  (original Pi 1 / Zero). The Pi Zero 2 W is the recommended successor.

[1.1.0]: https://github.com/nickpourazima/rotary-phone-audio-guestbook/releases
