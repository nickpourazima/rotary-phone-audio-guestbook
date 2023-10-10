# Rotary Phone Audio Guestbook

This project transforms a rotary phone into a voice recorder for use at special events (i.e. wedding audio guestbook, etc.).

![image](images/final_result_2.jpg)

- [Rotary Phone Audio Guestbook](#rotary-phone-audio-guestbook)
  - [Background](#background)
  - [Post-Event Reflection](#post-event-reflection)
  - [Future Enhancements](#future-enhancements)
  - [Quick-Start](#quick-start)
  - [Materials](#materials)
  - [Hardware](#hardware)
    - [Wiring](#wiring)
      - [Hook](#hook)
      - [Phone Cord](#phone-cord)
    - [Optional: Microphone Replacement](#optional-microphone-replacement)
  - [Software](#software)
    - [Dev Environment](#dev-environment)
    - [Installation](#installation)
    - [audioGuestBook systemctl service](#audioguestbook-systemctl-service)
    - [Config](#config)
    - [AudioInterface Class](#audiointerface-class)
    - [Operation Mode 1: audioGuestBook](#operation-mode-1-audioguestbook)
    - [Operation Mode 2: audioGuestBookwithRotaryDialer](#operation-mode-2-audioguestbookwithrotarydialer)
  - [Troubleshooting](#troubleshooting)
    - [Configuring Hook Type](#configuring-hook-type)
    - [Verify default audio interface](#verify-default-audio-interface)
      - [Check the Sound Card Configuration](#check-the-sound-card-configuration)
      - [Set the Default Sound Card](#set-the-default-sound-card)
      - [Restart ALSA](#restart-alsa)
  - [Support](#support)

## Background

Inspired by my own upcoming wedding, I created a DIY solution for an audio guestbook using a rotary phone. With most online rentals charging exorbitant fees without offering custom voicemail options, I sought a more affordable and customizable solution. Here, I've detailed a guide on creating your own audio guestbook. If you have questions, don't hesitate to reach out.

## Post-Event Reflection

The real event provided insights into areas of improvement for the setup. For instance, introducing a recording time limit became essential after some younger attendees left lengthy messages, draining the battery. Depending on the situation, you might also consider connecting the setup directly to a 5V power supply.

## Future Enhancements

In anticipation of my wedding, I had code in place to detect dialed numbers from the rotary encoder, allowing us to play special messages for specific guests based on their dialed combination. However, this required users to dial zero before leaving a voice message, introducing an extra step. We opted for simplicity, but if you're interested in expanding on this, you're welcome to explore further. The details of this operation mode are described in [Mode 2](#operation-mode-2-audioguestbookwithrotarydialer)

Additionally, threading the audio playback would be beneficial, allowing for a watchdog service to terminate the thread upon a hook callback. This would stop the message playback when a user hangs up.

## Quick-Start

After cloning the repo on the rpi:

```bash
chmod +x installer.sh
./installer.sh
```

## Materials

<details>
  <summary>Parts List</summary>

| Part                                                                                                                                                                                                                                                                                                                                      | Notes                                                                                                                                                                                                 | Quantity | Cost         |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ |
| [rotary phone](https://www.ebay.com/b/Rotary-Dial-Telephone/38038/bn_55192308)                                                                                                                                                                                                                                                            | Estate/garage/yard sales are probably the best places to find once of these. Ideally one with a phone jack since we will be using these four wires extensively.                                       | 1        | $0.00-$60.00 |
| [raspberry pi zero](https://www.raspberrypi.com/products/raspberry-pi-zero/)                                                                                                                                                                                                                                                              | I didn't realize how hard these are to find these days. You can use any rpi or arduino style single-board computer but be aware of size constraints (i.e. must fit inside the rotary phone enclosure) | 1        | $9.99        |
| [raspberry pi zero case](https://www.adafruit.com/product/3252)                                                                                                                                                                                                                                                                           | Optional: added for protection. One of the cases on Amazon has a heat-sink cutout which might be nice for better heat dissapation since it will all be enclosed in the end.                           | 1        | $4.95        |
| [micro SD card](https://a.co/d/1gb2zhC)                                                                                                                                                                                                                                                                                                   | Any high capacity/throughput micro SD card that is rpi compatible                                                                                                                                     | 1        | $8.99        |
| [USB Audio Adapter](https://www.adafruit.com/product/1475)                                                                                                                                                                                                                                                                                | Note: I removed the external plastic shell and directly soldered the wires instead of using the female 3.5mm receptacle.                                                                              | 1        | $4.95        |
| [USB OTG Host Cable - MicroB OTG male to A female](https://www.adafruit.com/product/1099)                                                                                                                                                                                                                                                 |                                                                                                                                                                                                       | 1        | $2.50        |
| ---                                                                                                                                                                                                                                                                                                                                       | **--- If you don't want to solder anything ---**                                                                                                                                                      | ---      | ---          |
| [3.5mm Male to Screw Terminal Connector](https://www.parts-express.com/3.5mm-Male-to-Screw-Terminal-Connector-090-110?quantity=1&utm_source=google&utm_medium=cpc&utm_campaign=18395892906&utm_content=145242146127&gadid=623430178298&gclid=CjwKCAiAioifBhAXEiwApzCztl7aVb18WP4hDxnlQUCHsb62oIcnduFCSCbn9LFkZovYTQdr6omb3RoCD_gQAvD_BwE) | Optional: can connect the handset cables directly to the USB audio interface via these screw terminals                                                                                                | 2        | $1.37        |
| ---                                                                                                                                                                                                                                                                                                                                       | **--- If running off a battery ---**                                                                                                                                                                  | ---      | ---          |
| [LiPo Battery](https://www.adafruit.com/product/2011)                                                                                                                                                                                                                                                                                     | Optional: maximize capacity based on what will fit within your rotary enclosure.                                                                                                                      | 1        | $12.50       |
| [LiPo Shim](https://www.adafruit.com/product/3196)                                                                                                                                                                                                                                                                                        | Optional: if you plan to run this off a LiPo I would recommend something like this to interface with the rpi zero.                                                                                    | 1        | $9.95        |
| [LiPo Charger](https://www.adafruit.com/product/1904)                                                                                                                                                                                                                                                                                     | Optional: for re-charging the LiPo.                                                                                                                                                                   | 1        | $6.95        |
| ---                                                                                                                                                                                                                                                                                                                                       | **--- If replacing the built-it microphone ---**                                                                                                                                                      | ---      | ---          |
| [LavMic](https://www.amazon.com/dp/B01N6P80OQ?ref=nb_sb_ss_w_as-reorder-t1_ypp_rep_k3_1_9&amp=&crid=15WZEWMZ17EM9&amp=&sprefix=saramonic)                                                                                                                                                                                                 | Optional: if you'd like to replace the carbon microphone. This is an omnidirectional lavalier mic and outputs via a 3.5mm TRS                                                                         | 1        | $24.95       |

</details>

## Hardware

### Wiring

#### Hook

**Understanding Hook Types:** Depending on your rotary phone model, the hook switch may be Normally Closed (NC) or Normally Open (NO). When the phone is on the hook:

- NC: The circuit is closed (current flows).
- NO: The circuit is open (no current).

To accommodate either type, you'll need to update the `config.yaml` with the appropriate hook type setting.

- Use multimeter to do a continuity check to find out which pins control the hook:

| On-hook --> Open circuit (Value == 1) | Off-hook --> Current flowing     |
| ------------------------------------- | -------------------------------- |
| ![image](images/hook_test_1.jpg)      | ![image](images/hook_test_2.jpg) |

- The B screw terminal on the rotary phone is connected to the black wire which is grounded to the rpi.
- The L2 screw terminal on the rotary phone is connected to the white wire which is connected to GPIO pin 22 on the rpi.

  ![image](images/pi_block_terminal_wiring.jpg)

- _Note: the green wire was used for the experimental rotary encoder feature identified in the [future work](#future-enhancements) section._

| Rotary Phone Block Terminal         | Top-down view                                |
| ----------------------------------- | -------------------------------------------- |
| ![image](images/block_terminal.jpg) | ![image](images/top_view_block_terminal.jpg) |

#### Phone Cord

- The wires from the handset cord need to be connected to the USB audio interface
  - I soldered it but you can alternatively use 2x [3.5mm Male to Screw Terminal Connector](https://www.parts-express.com/3.5mm-Male-to-Screw-Terminal-Connector-090-110?quantity=1&utm_source=google&utm_medium=cpc&utm_campaign=18395892906&utm_content=145242146127&gadid=623430178298&gclid=CjwKCAiAioifBhAXEiwApzCztl7aVb18WP4hDxnlQUCHsb62oIcnduFCSCbn9LFkZovYTQdr6omb3RoCD_gQAvD_BwE) which plug directly into the rpi.
    - _Note: The USB audio interface looks weird in the pics since I stripped the plastic shell off in order to solder directly to the mic/speaker leads_

![image](images/dissected_view_1.jpg)

- Use this ALSA command from the command line to test if the mic is working on the rpi before you set up the rotary phone: `aplay -l`
  - You might have a different hardware mapping than I did, in which case you would change the `alsa_hw_mapping` in the [config.yaml](config.yaml).
  - [Here's](https://superuser.com/questions/53957/what-do-alsa-devices-like-hw0-0-mean-how-do-i-figure-out-which-to-use) a good reference to device selection.
  - You can also check [this](https://stackoverflow.com/questions/32838279/getting-list-of-audio-input-devices-in-python) from Python.

### Optional: Microphone Replacement

For improved sound quality, consider replacing the built-in [carbon microphone](https://en.wikipedia.org/wiki/Carbon_microphone).

I found the sound quality of the built-in mic on the rotary phone to be quite lacking in terms of amplitude, dynamic range and overall vocal quality. I tried boosting the gain from the digital (ALSA driver) side but this introduced an incredible amount of noise as expected. I then approached this from the analog domain and tried alternative circuitry to boost the sound quality based off this [carbon-to-dynamic converter](https://www.circuits-diy.com/mic-converter-circuit/).

Might be worth a further investigation in the future since it retains the integrity of the original rotary phone.

My final attempt involved the introduction of some post-proceesing (see dev branch) to bandpass some of the freqs outside the speech domain and add some normalization. The processing was costly in terms of processing and power consumption/rendering time and I ultimately decided it was worth acquiring something that yielded a better capture right out the gate. Crap in, crap out - as they say in the sound recording industry.

To replace:

- Unscrew mouthpiece and remove the carbon mic
- Pop out the plastic terminal housing with the two metal leads
- Unscrew red and black wires from terminal
- Prepare your lav mic
  - I pulled off the 3.5mm male headphone pin since it is usually coated and annoyingly difficult to solder directly on to.
  - Carefully separate the two wires from the lav mic and spiral up the surrounding copper. This will act as our ground signal.
- Extend the green wire from the phone cord clip to the ground point of the lav mic.
- Red to red, black to blue as per the following diagram:

![image](images/phone_wiring.jpg)

![image](images/handset_mic_wiring.jpg)

![image](images/handset_mic_positioning.jpg)

## Software

### Dev Environment

- rpi image: [Rasbian](https://www.raspberrypi.com/documentation/computers/getting-started.html) w/ SSH enabled
- rpi on same network as development machine
- _Optional: vscode w/ [SSH FS extension](https://marketplace.visualstudio.com/items?itemName=Kelvin.vscode-sshfs)_

[Here's](https://jayproulx.medium.com/headless-raspberry-pi-zero-w-setup-with-ssh-and-wi-fi-8ddd8c4d2742) a great guide to get the rpi setup headless w/ SSH & WiFi dialed in.

### Installation

- On the networked rpi - clone the repository:

```bash
git clone git@github.com:nickpourazima/rotary-phone-audio-guestbook.git
cd rotary-phone-audio-guestbook
```

- Next, use the installer script for a hassle-free setup.:

```bash
chmod +x installer.sh
./installer.sh
```

- Note, this script takes care of several tasks:

  1. Install required dependencies.
  2. Populate config.yaml based on user input
  3. Replace placeholders in the service file to adapt to your project directory.
  4. Move the modified service file to the systemd directory.
  5. Create necessary directories (recordings and sounds).
  6. Grant execution permissions to the Python scripts.
  7. Reload systemd, enable, and start the service.

### [audioGuestBook systemctl service](audioGuestBook.service)

This service ensures smooth operation without manual intervention every time your Raspberry Pi boots up. The installer script will place this service file in the `/etc/systemd/system` directory and modify paths according to your project directory.

Manual control of the service is possible as it operates as any other [`.service` entity](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

### [Config](config.yaml)

- This file allows you to customize your own set up (edit rpi pins, audio reduction, alsa mapping, etc), modify the yaml as necessary.
- Ensure the sample rate is supported by your audio interface (default = 44100 Hz (decimal not required))
- For GPIO mapping, refer to the wiring diagram specific to your rpi:
  ![image](images/rpi_GPIO.png)
- **hook_type**: Define your hook switch type here. Set it to "NC" if your phone uses a Normally Closed hook switch or "NO" for Normally Open.

### [AudioInterface Class](audioInterface.py)

- Utilizes pydub and pyaudio extensively.
- Houses the main playback/record logic and has future #TODO expansion for postprocessing the audio. Would like to test on an rpi4 to see if it can handle it better for real-time applications.

### Operation Mode 1: [audioGuestBook](/audioGuestBook.py)

- This is the main operation mode of the device.
- There are two callbacks in main which poll the gpio pins for the specified activity (hook depressed, hook released).
- In the code, depending on the `hook_type` set in the `config.yaml`, the software will adapt its behavior. For NC types, hanging up the phone will trigger the `on_hook` behavior, and lifting the phone will trigger the `off_hook` behavior. The opposite will be true for NO types.
- Once triggered the appropriate function is called.
- On hook (depressed)
  - Nothing happens
- Off hook (released)
  - Plays back your own added welcome message located in `/sounds/voicemail.wav` followed by the [beep](/sounds/beep.wav) indicating the start of recording.
  - Begins recording the guests voice message.
  - Guest hangs up, recording is stopped and stored to the `/recordings/` directory.
  - If the guest exceeds the **recording_limit** specified in the [config.yaml](/config.yaml), play the warning [time_exceeded.wav](/sounds/time_exceeded.wav) sound and stop recording.

### Operation Mode 2: [audioGuestBookwithRotaryDialer](./todo/audioGuestBookwithRotaryDialer.py)

**_Note_:** Untested - decided not to go this route for my own wedding

- This mode is a special modification of the normal operation and requires a slightly different wiring connection since it accepts input from the rotary dialer.
- The idea was to playback special messages when particular users dial a certain number combination (i.e. 909 would play back a message for certain guests who lived with the groom in that area code).
- In this mode of operation the users will need to dial 0 on the rotary dialer in order to initiate the voicemail.
- The rotary dialer is a bit more complex to set up, you need a pull up resistor connected between the F screw terminal and 5V on the rpi and the other end on GPIO 23. #TODO: Diagram

## Troubleshooting

### Configuring Hook Type

If you find that the behaviors for hanging up and lifting the phone are reversed, it's likely that the `hook_type` in `config.yaml` is incorrectly set. Ensure that it matches your phone's hook switch type (NC or NO).

### Verify default audio interface

A few users had issues where audio I/O was defaulting to HDMI. To alleviate this, check the following:

#### Check the Sound Card Configuration

Verify the available sound devices using the following command:

```bash
aplay -l
```

_Ensure that your USB audio interface is listed and note the card and device numbers._

#### Set the Default Sound Card

If you want to route audio through your USB audio interface, you'll need to make it the default sound card.
Edit the ALSA configuration file (usually located at `/etc/asound.conf` or `~/.asoundrc`) and add the following:

```bash
defaults.pcm.card X
defaults.ctl.card X
```

_Replace X with the card number of your USB audio interface obtained from the previous step._

#### Restart ALSA

```bash
sudo /etc/init.d/alsa-utils restart
```

## Support

If this code helped you or if you have some feedback, I'd be thrilled to [hear about it](mailto:dillpicholas@duck.com)!
Feel like saying thanks? You can [buy me a coffee](https://www.buymeacoffee.com/dillpicholas) ☕.
