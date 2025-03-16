# Configuration

- [ ] Replace the voicemail.wav with your own custom recording
- [ ] Check your ALSA HW mapping

  Depending on your audio interface's configuration, you may need to adjust the ALSA settings further. If after running `aplay -l` you find that the ALSA hardware mapping differs from what is expected or if you're experiencing audio issues, consider modifying `.asoundrc` to ensure your device correctly identifies and uses your audio interface. For example, if your USB audio interface is listed as card 1, device 0, you might add or modify `.asoundrc` to include:

  ```bash
  pcm.!default {
      type hw
      card 1
  }

  ctl.!default {
      type hw
      card 1
  }
  ```

- [ ] Adjust the `config.yaml`

  This file allows you to customize your own set up (edit rpi GPIO pins, alsa mapping, etc), modify the yaml as necessary.

  - `alsa_hw_mapping`: The ALSA hardware mapping for your audio interface. Use aplay --help for format guidance.
  - `format`: Set the audio format (default is cd). Refer to aplay --help for options.
  - `file_type`: The type of file to save recordings as (default is wav).
  - `channels`: Number of audio channels (default is 2 for stereo).
  - `hook_gpio`: The GPIO pin connected to the phone's hook switch.

    - For GPIO mapping, refer to the wiring diagram specific to your rpi (i.e):

      <img src="images/rpi_GPIO.png" width="50%" height="50%">

  - `hook_type`: Set to NC (Normally Closed) or NO (Normally Open), depending on your phone's hook switch hardware setup.
  - `recording_limit`: The maximum length for a recording in seconds (default is 300).
  - `sample_rate`: The sample rate for recordings (default is 44100 Hz).

  _Note: Adjust these settings as needed based on your specific hardware setup and preferences._

- [ ] Test audio playback/recording

To ensure your settings are correctly applied, you can test audio playback and recording after making changes. For playback, you can use a sample WAV file and the `aplay` command. For recording, `arecord` can be used followed by `aplay` to play back the recorded audio.

- [ ] Check [audioGuestBook systemctl service](audioGuestBook.service)

This service ensures smooth operation without manual intervention every time your Raspberry Pi boots up. The service file is sym linked to the `/etc/systemd/system` directory. Manual control of the service is possible as it operates as any other [`.service` entity](https://www.freedesktop.org/software/systemd/man/systemd.service.html). You can quickly check the status with `journalctl -u audioGuestBook.service`
