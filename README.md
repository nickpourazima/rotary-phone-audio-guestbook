# Rotary Phone Audio Guestbook

This project transforms a rotary phone into a voice recorder for special events such as a wedding audio guestbook.

[![image](https://github.com/nickpourazima/rotary-phone-audio-guestbook/raw/main/images/final_result_2.jpg)](/nickpourazima/rotary-phone-audio-guestbook/blob/main/images/final_result_2.jpg)

- [Rotary Phone Audio Guestbook](#rotary-phone-audio-guestbook)
  - [Background](#background)
  - [Materials](#materials)
  - [Setup](#setup)
    - [Prepare Your Rotary Phone](#prepare-your-rotary-phone)
    - [Download and Install the Image](#download-and-install-the-image)
    - [Initial Configuration](#initial-configuration)
  - [Hotspot (automatic WiFi fallback)](#hotspot-automatic-wifi-fallback)
  - [Supported Raspberry Pi models](#supported-raspberry-pi-models)
  - [Software](#software)
  - [Development](#development)
  - [Support](#support)
  - [Star History](#star-history)

## Background

Inspired by my upcoming wedding, I created a DIY audio guestbook using a rotary phone. After finding that commercial rentals charged high fees without offering custom voicemail options, I developed this affordable and customizable solution. This guide will help you create your own audio guestbook.

## [Materials](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/materials.md)

## Setup

### Prepare Your Rotary Phone

1. Follow the [Hardware](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/hardware.md) section for detailed instructions on wiring your rotary phone to the Raspberry Pi. This is a crucial first step before proceeding to software installation.

*Note: No hardware support will be given as it is very difficult to replicate setups beyond the simple NC/NO switch.*

### Download and Install the Image

The image is based on **Raspberry Pi OS Lite (32-bit, Debian 13 "Trixie")** and is built automatically from this repository, so it stays reproducible and easy to audit.

1. Download the [latest release](https://github.com/nickpourazima/rotary-phone-audio-guestbook/releases) (the `.img.gz`).
2. (Optional) Verify the download against the published `.sha256` file: `sha256sum -c <file>.gz.sha256`
3. Flash the `.img.gz` to an SD card with Raspberry Pi Imager (choose **"Use custom"**) or BalenaEtcher. Both read the compressed image directly and decompress while writing, so there is no need to extract it first.

   > Note: the Imager's **OS customisation** (username, WiFi, SSH) is **disabled for custom images** — that is expected. This image already ships ready to use (see below), and you can optionally pre-configure it with a `custom.toml` file.

4. Insert the SD card into your Raspberry Pi and power it on. Give it a minute on first boot.

The image boots ready to use:

- **Default login:** username `pi`, password `password` (please change it — see below).
- **SSH** is enabled.
- **WiFi:** if you didn't pre-configure a network, the Pi opens its own hotspot so you can reach it (see [Hotspot](#hotspot-automatic-wifi-fallback)). Connect to `RPiHotspot`, then `ssh pi@10.0.0.5` and add your network with `sudo nmcli device wifi connect "<SSID>" password "<password>"`.

**Change the default password** as soon as you log in: `passwd`.

#### Optional: pre-configure WiFi/login before first boot

Since Imager customisation is unavailable, you can drop a `custom.toml` file in the SD card's `bootfs` partition (Raspberry Pi OS applies it on first boot). On macOS/Linux, after flashing:

```
config_version = 1
[system]
hostname = "guestbook"
[user]
name = "admin"
password = "your-password"
password_encrypted = false
[ssh]
enabled = true
password_authentication = true
[wlan]
ssid = "YourWiFi"
password = "YourWiFiPassword"
password_encrypted = false
country = "DE"
[locale]
keymap = "de"
timezone = "Europe/Berlin"
```

Save it as `custom.toml` (no `.txt` extension) in the boot partition, adjust the values, then boot. The WiFi password must be plain text (`password_encrypted = false`).

### Initial Configuration

Once you've completed the hardware setup and flashed the image:

1. Boot up your Raspberry Pi and allow it a minute to initialize.
2. Navigate to `<RPI_IP>:8080` in a web browser to access the control interface:

   [![image](https://github.com/nickpourazima/rotary-phone-audio-guestbook/raw/main/images/webserver_home_light_no_recordings.png)](/nickpourazima/rotary-phone-audio-guestbook/blob/main/images/webserver_home_light_no_recordings.png)
3. Visit the Settings page to customize your configuration:

   [![image](https://github.com/nickpourazima/rotary-phone-audio-guestbook/raw/main/images/webserver_settings_light.png)](/nickpourazima/rotary-phone-audio-guestbook/blob/main/images/webserver_settings_light.png)

Your audio guest book is now ready for test/deployment! For advanced configuration options and detailed explanations of all settings, refer to the [Configuration](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/configuration.md) documentation.

## Hotspot (automatic WiFi fallback)

The guestbook uses **NetworkManager's built-in access-point mode** to provide a fallback hotspot. There is nothing to install and no interactive setup — it just works out of the box.

How it works: on boot the Pi tries to join the WiFi network you configured (via `custom.toml`, or later over SSH). If no known network is in range, it automatically brings up its own access point on channel 1 so you can still reach the device.

```
WiFi SSID name is: RPiHotspot
The WiFi password is: 1234567890
Access Point IP Address for SSH: 10.0.0.5
Web interface of your guestbook is http://10.0.0.5:8080
```

**WiFi country:** the image ships with a default regulatory domain (`DE`) baked in, so the access point starts out of the box. To use a different region, either set `country` in a `custom.toml` before first boot, or run `sudo raspi-config nonint do_wifi_country <CC>` (e.g. `US`) and reboot.

**Adding or changing a WiFi network later** — SSH into the Pi and run:

```
sudo nmcli device wifi connect "<SSID>" password "<PASSWORD>"
```

NetworkManager saves the network and prefers it over the hotspot on the next check.

**Single-radio note:** the Pi has one WiFi radio, so it is either connected to your WiFi *or* running the hotspot, never both. If **no** home network is saved, the hotspot stays up permanently and stable. Once you *have* saved a home network, the Pi re-checks every few minutes and returns to it automatically when it is back in range; while in hotspot mode that auto-return causes a brief interruption every few minutes. To keep the hotspot perfectly stable even with a saved network (e.g. for the duration of an event), set `HOTSPOT_AUTORETURN=0` in `/etc/default/agb-hotspot` and reboot. The hotspot uses WPA2 (AES) on channel 1.

## Supported Raspberry Pi models

Because the image is 32-bit (armhf), it runs on **every** Raspberry Pi model — from the original Pi 1 and Pi Zero through Zero 2 W, Pi 2/3/4/400 and Pi 5/500. GPIO uses the `lgpio` backend, so it also works on the Pi 5.

The hotspot fallback requires **onboard WiFi**. Models without WiFi (the original Pi Zero without "W", Pi 1, Pi 2) can still run the guestbook, but cannot open a hotspot. For a new build, the **Pi Zero 2 W** is the recommended choice: pin-compatible with the original Zero, much faster, and not affected by the eventual end of armv6 support.

## [Software](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/software.md)

## [Development](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/development.md)

For contributors: the whole setup lives in a single, idempotent [`install.sh`](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/install.sh). You can run it on a fresh Raspberry Pi OS Lite install, or let the [build workflow](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/.github/workflows/build-image.yml) produce a flashable release image from it. See the [Development docs](https://github.com/nickpourazima/rotary-phone-audio-guestbook/blob/main/docs/development.md) for details.

## Support

It's great to see this project growing. Big thank you to the current maintainer @[sascha-schieferdecker](https://github.com/sascha-schieferdecker). Special thanks to @[svartis](https://github.com/svartis), @[jmdevita](https://github.com/jmdevita), and @[Mevel](https://github.com/Mevel)!

If this code helped you or if you have feedback, feel free to submit a [topic for discussion](https://github.com/nickpourazima/rotary-phone-audio-guestbook/discussions).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=nickpourazima/rotary-phone-audio-guestbook&type=Date)](https://star-history.com/#nickpourazima/rotary-phone-audio-guestbook&Date)
