# Rotary Phone Audio Guestbook

This project transforms a rotary phone into a voice recorder for special events such as a wedding audio guestbook.

![image](images/final_result_2.jpg)

- [Rotary Phone Audio Guestbook](#rotary-phone-audio-guestbook)
  - [Background](#background)
  - [Materials](#materials)
  - [Setup](#setup)
    - [Prepare Your Rotary Phone](#prepare-your-rotary-phone)
    - [Download and Install the Custom Image](#download-and-install-the-custom-image)
    - [Initial Configuration](#initial-configuration)
  - [Software](#software)
  - [Development](#development)
  - [Support](#support)
  - [Star History](#star-history)

## Background

Inspired by my upcoming wedding, I created a DIY audio guestbook using a rotary phone. After finding that commercial rentals charged high fees without offering custom voicemail options, I developed this affordable and customizable solution. This guide will help you create your own audio guestbook.

## [Materials](docs/materials.md)

## Setup

### Prepare Your Rotary Phone

1. Follow the [Hardware](docs/hardware.md) section for detailed instructions on wiring your rotary phone to the Raspberry Pi. This is a crucial first step before proceeding to software installation.

_Note: No hardware support will be given as it is very difficult to replicate setups beyond the simple NC/NO switch._

### Download and Install the Custom Image

With your hardware prepared, install the custom Raspberry Pi image that contains all necessary software:

1. Download the [latest release](https://github.com/nickpourazima/rotary-phone-audio-guestbook/releases)
2. Extract the .gz file: `gunzip rpizero_rotary_phone_audio_guestbook_v<latest>_imagebackup.img.gz`
3. Flash the image to an SD card using Raspberry Pi Imager or BalenaEtcher:

   <img src="images/rpi_imager_custom.png" width="50%" height="50%">

   Hint: If using Raspberry Pi Imager Version 2, make sure to use Version 2.0.2 or later, as it is not possible to set a WiFi-password with 2.0.0 or 2.0.1.

4. Configure the following credentials when prompted:
   ```bash
   username: admin
   password: password
   ```
5. Set up your WiFi network connection
6. Insert the SD card into your Raspberry Pi and power it on

### Initial Configuration

Once you've completed the hardware setup and installed the image:

1. Boot up your Raspberry Pi and allow it a minute to initialize
2. Navigate to `<RPI_IP>:8080` in a web browser to access the control interface:

   ![image](images/webserver_home_light_no_recordings.png)

3. Visit the Settings page to customize your configuration:

   ![image](images/webserver_settings_light.png)

Your audio guest book is now ready for test/deployment! For advanced configuration options and detailed explanations of all settings, refer to the [Configuration](docs/configuration.md) documentation.

## Optional: Hotspot-Setup

As of release 1.0.6, it is possible to set up hotspot WiFi access, that automatically opens if your set WiFi network is not in range. For this to work, you have to SSH once into your Rasperry Pi and set the WiFi region:

```bash
sudo raspi-config
```

Then choose "Localisation Options" > "WLAN-Country" and set your country. 

After that run the Setup for the auto-hotspot:

```bash
sudo ~/Autohotspot/autohotspot-setup.sh
```
Choose option 2, press "Enter" after the setup. Select option 8 to exit the setup.

Reboot afterwards. That's it.

The Hotspots WiFi SSID name is: RPiHotspot
The WiFi password is: 1234567890
Access Point IP Address for SSH: 10.0.0.5

So the web interface of your guestbook is http://10.0.0.5:8080



## [Software](docs/software.md)

## [Development](docs/development.md)

## Support

It's great to see this project growing. Big thank you to the current maintainer @[sascha-schieferdecker](https://github.com/sascha-schieferdecker). Special thanks to @[svartis](https://github.com/svartis), @[jmdevita](https://github.com/jmdevita), and @[Mevel](https://github.com/Mevel)!

If this code helped you or if you have feedback, feel free to submit a [topic for discussion](https://github.com/nickpourazima/rotary-phone-audio-guestbook/discussions).

## Star History

<a href="https://star-history.com/#nickpourazima/rotary-phone-audio-guestbook&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=nickpourazima/rotary-phone-audio-guestbook&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=nickpourazima/rotary-phone-audio-guestbook&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=nickpourazima/rotary-phone-audio-guestbook&type=Date" />
 </picture>
</a>
