Rotary Phone Audio Guestbook
============================

This project transforms a rotary phone into a voice recorder for use at
special events (i.e. wedding audio guestbook, etc.).

.. figure:: _static/images/final_result_2.jpg
   :alt: image

   image

-  `Rotary Phone Audio Guestbook <#rotary-phone-audio-guestbook>`__

   -  `Background <#background>`__
   -  `Post-Event Reflection <#post-event-reflection>`__
   -  `Future Enhancements <#future-enhancements>`__
   -  `Quick-Start <#quick-start>`__
   -  `Materials <#materials>`__
   -  `Hardware <#hardware>`__

      -  `Wiring <#wiring>`__

         -  `Hook <#hook>`__
         -  `Phone Cord <#phone-cord>`__

      -  `Optional: Microphone
         Replacement <#optional-microphone-replacement>`__

   -  `Software <#software>`__

      -  `Dev Environment <#dev-environment>`__
      -  `Installation <#installation>`__
      -  `audioGuestBook systemctl
         service <#audioguestbook-systemctl-service>`__
      -  `Config <#config>`__
      -  `AudioInterface Class <#audiointerface-class>`__
      -  `Operation Mode 1:
         audioGuestBook <#operation-mode-1-audioguestbook>`__
      -  `Operation Mode 2:
         audioGuestBookwithRotaryDialer <#operation-mode-2-audioguestbookwithrotarydialer>`__

   -  `Troubleshooting <#troubleshooting>`__

      -  `Configuring Hook Type <#configuring-hook-type>`__
      -  `Verify default audio
         interface <#verify-default-audio-interface>`__

         -  `Check the Sound Card
            Configuration <#check-the-sound-card-configuration>`__
         -  `Set the Default Sound Card <#set-the-default-sound-card>`__
         -  `Restart ALSA <#restart-alsa>`__

   -  `Support <#support>`__

Background
----------

Inspired by my own upcoming wedding, I created a DIY solution for an
audio guestbook using a rotary phone. With most online rentals charging
exorbitant fees without offering custom voicemail options, I sought a
more affordable and customizable solution. Here, I’ve detailed a guide
on creating your own audio guestbook. If you have questions, don’t
hesitate to reach out.

Post-Event Reflection
---------------------

The real event provided insights into areas of improvement for the
setup. For instance, introducing a recording time limit became essential
after some younger attendees left lengthy messages, draining the
battery. Depending on the situation, you might also consider connecting
the setup directly to a 5V power supply.

Future Enhancements
-------------------

In anticipation of my wedding, I had code in place to detect dialed
numbers from the rotary encoder, allowing us to play special messages
for specific guests based on their dialed combination. However, this
required users to dial zero before leaving a voice message, introducing
an extra step. We opted for simplicity, but if you’re interested in
expanding on this, you’re welcome to explore further. The details of
this operation mode are described in `Mode
2 <#operation-mode-2-audioguestbookwithrotarydialer>`__

Additionally, threading the audio playback would be beneficial, allowing
for a watchdog service to terminate the thread upon a hook callback.
This would stop the message playback when a user hangs up.

Quick-Start
-----------

After cloning the repo on the rpi:

.. code:: bash

   chmod +x installer.sh
   ./installer.sh

Materials
---------

.. raw:: html

   <details>

Parts List

+------------------------------------------+------------------------+---+---+
| Part                                     | Notes                  | Q | C |
|                                          |                        | u | o |
|                                          |                        | a | s |
|                                          |                        | n | t |
|                                          |                        | t |   |
|                                          |                        | i |   |
|                                          |                        | t |   |
|                                          |                        | y |   |
+==========================================+========================+===+===+
| `rotary                                  | Estate/garage/yard     | 1 | $ |
| phone <https://www.ebay.com/b/Rot        | sales are probably the |   | 0 |
| ary-Dial-Telephone/38038/bn_55192308>`__ | best places to find    |   | . |
|                                          | once of these. Ideally |   | 0 |
|                                          | one with a phone jack  |   | 0 |
|                                          | since we will be using |   | - |
|                                          | these four wires       |   | $ |
|                                          | extensively.           |   | 6 |
|                                          |                        |   | 0 |
|                                          |                        |   | . |
|                                          |                        |   | 0 |
|                                          |                        |   | 0 |
+------------------------------------------+------------------------+---+---+
| `raspberry pi                            | I didn’t realize how   | 1 | $ |
| zero <https://www.raspber                | hard these are to find |   | 9 |
| rypi.com/products/raspberry-pi-zero/>`__ | these days. You can    |   | . |
|                                          | use any rpi or arduino |   | 9 |
|                                          | style single-board     |   | 9 |
|                                          | computer but be aware  |   |   |
|                                          | of size constraints    |   |   |
|                                          | (i.e. must fit inside  |   |   |
|                                          | the rotary phone       |   |   |
|                                          | enclosure)             |   |   |
+------------------------------------------+------------------------+---+---+
| `raspberry pi zero                       | Optional: added for    | 1 | $ |
| case <h                                  | protection. One of the |   | 4 |
| ttps://www.adafruit.com/product/3252>`__ | cases on Amazon has a  |   | . |
|                                          | heat-sink cutout which |   | 9 |
|                                          | might be nice for      |   | 5 |
|                                          | better heat            |   |   |
|                                          | dissapation since it   |   |   |
|                                          | will all be enclosed   |   |   |
|                                          | in the end.            |   |   |
+------------------------------------------+------------------------+---+---+
| `micro SD                                | Any high               | 1 | $ |
| card <https://a.co/d/1gb2zhC>`__         | capacity/throughput    |   | 8 |
|                                          | micro SD card that is  |   | . |
|                                          | rpi compatible         |   | 9 |
|                                          |                        |   | 9 |
+------------------------------------------+------------------------+---+---+
| `USB Audio                               | Note: I removed the    | 1 | $ |
| Adapter <h                               | external plastic shell |   | 4 |
| ttps://www.adafruit.com/product/1475>`__ | and directly soldered  |   | . |
|                                          | the wires instead of   |   | 9 |
|                                          | using the female 3.5mm |   | 5 |
|                                          | receptacle.            |   |   |
+------------------------------------------+------------------------+---+---+
| `USB OTG Host Cable - MicroB OTG male to |                        | 1 | $ |
| A                                        |                        |   | 2 |
| female <h                                |                        |   | . |
| ttps://www.adafruit.com/product/1099>`__ |                        |   | 5 |
|                                          |                        |   | 0 |
+------------------------------------------+------------------------+---+---+
| —                                        | **— If you don’t want  | — | — |
|                                          | to solder anything —** |   |   |
+------------------------------------------+------------------------+---+---+
| `3.5mm Male to Screw Terminal            | Optional: can connect  | 2 | $ |
| Connector <https://www                   | the handset cables     |   | 1 |
| .parts-express.com/3.5mm-Male-to-Screw-T | directly to the USB    |   | . |
| erminal-Connector-090-110?quantity=1&utm | audio interface via    |   | 3 |
| _source=google&utm_medium=cpc&utm_campai | these screw terminals  |   | 7 |
| gn=18395892906&utm_content=145242146127& |                        |   |   |
| gadid=623430178298&gclid=CjwKCAiAioifBhA |                        |   |   |
| XEiwApzCztl7aVb18WP4hDxnlQUCHsb62oIcnduF |                        |   |   |
| CSCbn9LFkZovYTQdr6omb3RoCD_gQAvD_BwE>`__ |                        |   |   |
+------------------------------------------+------------------------+---+---+
| —                                        | **— If running off a   | — | — |
|                                          | battery —**            |   |   |
+------------------------------------------+------------------------+---+---+
| `LiPo                                    | Optional: maximize     | 1 | $ |
| Battery <h                               | capacity based on what |   | 1 |
| ttps://www.adafruit.com/product/2011>`__ | will fit within your   |   | 2 |
|                                          | rotary enclosure.      |   | . |
|                                          |                        |   | 5 |
|                                          |                        |   | 0 |
+------------------------------------------+------------------------+---+---+
| `LiPo                                    | Optional: if you plan  | 1 | $ |
| Shim <h                                  | to run this off a LiPo |   | 9 |
| ttps://www.adafruit.com/product/3196>`__ | I would recommend      |   | . |
|                                          | something like this to |   | 9 |
|                                          | interface with the rpi |   | 5 |
|                                          | zero.                  |   |   |
+------------------------------------------+------------------------+---+---+
| `LiPo                                    | Optional: for          | 1 | $ |
| Charger <h                               | re-charging the LiPo.  |   | 6 |
| ttps://www.adafruit.com/product/1904>`__ |                        |   | . |
|                                          |                        |   | 9 |
|                                          |                        |   | 5 |
+------------------------------------------+------------------------+---+---+
| —                                        | **— If replacing the   | — | — |
|                                          | built-it microphone    |   |   |
|                                          | —**                    |   |   |
+------------------------------------------+------------------------+---+---+
| `LavMic <https://www                     | Optional: if you’d     | 1 | $ |
| .amazon.com/dp/B01N6P80OQ?ref=nb_sb_ss_w | like to replace the    |   | 2 |
| _as-reorder-t1_ypp_rep_k3_1_9&amp=&crid= | carbon microphone.     |   | 4 |
| 15WZEWMZ17EM9&amp=&sprefix=saramonic>`__ | This is an             |   | . |
|                                          | omnidirectional        |   | 9 |
|                                          | lavalier mic and       |   | 5 |
|                                          | outputs via a 3.5mm    |   |   |
|                                          | TRS                    |   |   |
+------------------------------------------+------------------------+---+---+

.. raw:: html

   </details>

Hardware
--------

Wiring
~~~~~~

Hook
^^^^

**Understanding Hook Types:** Depending on your rotary phone model, the
hook switch may be Normally Closed (NC) or Normally Open (NO). When the
phone is on the hook:

-  NC: The circuit is closed (current flows).
-  NO: The circuit is open (no current).

To accommodate either type, you’ll need to update the ``config.yaml``
with the appropriate hook type setting.

-  Use multimeter to do a continuity check to find out which pins
   control the hook:

==================================== ===========================
On-hook –> Open circuit (Value == 1) Off-hook –> Current flowing
==================================== ===========================
|hook1|                              |hook2|
==================================== ===========================

-  The B screw terminal on the rotary phone is connected to the black
   wire which is grounded to the rpi.

-  The L2 screw terminal on the rotary phone is connected to the white
   wire which is connected to GPIO pin 22 on the rpi.

   .. figure:: _static/images/pi_block_terminal_wiring.jpg
      :alt: image

      image

-  *Note: the green wire was used for the experimental rotary encoder
   feature identified in the*\ `future
   work <#future-enhancements>`__\ *section.*

=========================== =============
Rotary Phone Block Terminal Top-down view
=========================== =============
|term1|                     |term2|
=========================== =============

Phone Cord
^^^^^^^^^^

-  The wires from the handset cord need to be connected to the USB audio
   interface

   -  I soldered it but you can alternatively use 2x `3.5mm Male to
      Screw Terminal
      Connector <https://www.parts-express.com/3.5mm-Male-to-Screw-Terminal-Connector-090-110?quantity=1&utm_source=google&utm_medium=cpc&utm_campaign=18395892906&utm_content=145242146127&gadid=623430178298&gclid=CjwKCAiAioifBhAXEiwApzCztl7aVb18WP4hDxnlQUCHsb62oIcnduFCSCbn9LFkZovYTQdr6omb3RoCD_gQAvD_BwE>`__
      which plug directly into the rpi.

      -  *Note: The USB audio interface looks weird in the pics since I
         stripped the plastic shell off in order to solder directly to
         the mic/speaker leads*

.. figure:: _static/images/dissected_view_1.jpg
   :alt: image

   image

-  Use this ALSA command from the command line to test if the mic is
   working on the rpi before you set up the rotary phone: ``aplay -l``

   -  You might have a different hardware mapping than I did, in which
      case you would change the ``alsa_hw_mapping`` in the
      `config.yaml <config.yaml>`__.
   -  `Here’s <https://superuser.com/questions/53957/what-do-alsa-devices-like-hw0-0-mean-how-do-i-figure-out-which-to-use>`__
      a good reference to device selection.
   -  You can also check
      `this <https://stackoverflow.com/questions/32838279/getting-list-of-audio-input-devices-in-python>`__
      from Python.

Optional: Microphone Replacement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For improved sound quality, consider replacing the built-in `carbon
microphone <https://en.wikipedia.org/wiki/Carbon_microphone>`__.

I found the sound quality of the built-in mic on the rotary phone to be
quite lacking in terms of amplitude, dynamic range and overall vocal
quality. I tried boosting the gain from the digital (ALSA driver) side
but this introduced an incredible amount of noise as expected. I then
approached this from the analog domain and tried alternative circuitry
to boost the sound quality based off this `carbon-to-dynamic
converter <https://www.circuits-diy.com/mic-converter-circuit/>`__.

Might be worth a further investigation in the future since it retains
the integrity of the original rotary phone.

My final attempt involved the introduction of some post-proceesing (see
dev branch) to bandpass some of the freqs outside the speech domain and
add some normalization. The processing was costly in terms of processing
and power consumption/rendering time and I ultimately decided it was
worth acquiring something that yielded a better capture right out the
gate. Crap in, crap out - as they say in the sound recording industry.

To replace:

-  Unscrew mouthpiece and remove the carbon mic
-  Pop out the plastic terminal housing with the two metal leads
-  Unscrew red and black wires from terminal
-  Prepare your lav mic

   -  I pulled off the 3.5mm male headphone pin since it is usually
      coated and annoyingly difficult to solder directly on to.
   -  Carefully separate the two wires from the lav mic and spiral up
      the surrounding copper. This will act as our ground signal.

-  Extend the green wire from the phone cord clip to the ground point of
   the lav mic.
-  Red to red, black to blue as per the following diagram:

.. figure:: _static/images/phone_wiring.jpg
   :alt: image

   image

.. figure:: _static/images/handset_mic_wiring.jpg
   :alt: image

   image

.. figure:: _static/images/handset_mic_positioning.jpg
   :alt: image

   image

Software
--------

Dev Environment
~~~~~~~~~~~~~~~

-  rpi image:
   `Rasbian <https://www.raspberrypi.com/documentation/computers/getting-started.html>`__
   w/ SSH enabled
-  rpi on same network as development machine
-  *Optional: vscode w/*\ `SSH FS
   extension <https://marketplace.visualstudio.com/items?itemName=Kelvin.vscode-sshfs>`__

`Here’s <https://jayproulx.medium.com/headless-raspberry-pi-zero-w-setup-with-ssh-and-wi-fi-8ddd8c4d2742>`__
a great guide to get the rpi setup headless w/ SSH & WiFi dialed in.

Installation
~~~~~~~~~~~~

-  On the networked rpi - clone the repository:

.. code:: bash

   git clone git@github.com:nickpourazima/rotary-phone-audio-guestbook.git
   cd rotary-phone-audio-guestbook

-  Next, use the installer script for a hassle-free setup.:

.. code:: bash

   chmod +x installer.sh
   ./installer.sh

-  Note, this script takes care of several tasks:

   1. Install required dependencies.
   2. Populate config.yaml based on user input
   3. Replace placeholders in the service file to adapt to your project
      directory.
   4. Move the modified service file to the systemd directory.
   5. Create necessary directories (recordings and sounds).
   6. Grant execution permissions to the Python scripts.
   7. Reload systemd, enable, and start the service.

`audioGuestBook systemctl service <audioGuestBook.service>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This service ensures smooth operation without manual intervention every
time your Raspberry Pi boots up. The installer script will place this
service file in the ``/etc/systemd/system`` directory and modify paths
according to your project directory.

Manual control of the service is possible as it operates as any other
```.service``
entity <https://www.freedesktop.org/software/systemd/man/systemd.service.html>`__

`Config <config.yaml>`__
~~~~~~~~~~~~~~~~~~~~~~~~

-  This file allows you to customize your own set up (edit rpi pins,
   audio reduction, alsa mapping, etc), modify the yaml as necessary.
-  Ensure the sample rate is supported by your audio interface (default
   = 44100 Hz (decimal not required))
-  For GPIO mapping, refer to the wiring diagram specific to your rpi:
   |rpi|
-  **hook_type**: Define your hook switch type here. Set it to “NC” if
   your phone uses a Normally Closed hook switch or “NO” for Normally
   Open.

`AudioInterface Class <audioInterface.py>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Utilizes pydub and pyaudio extensively.
-  Houses the main playback/record logic and has future #TODO expansion
   for postprocessing the audio. Would like to test on an rpi4 to see if
   it can handle it better for real-time applications.

Operation Mode 1: `audioGuestBook </audioGuestBook.py>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  This is the main operation mode of the device.
-  There are two callbacks in main which poll the gpio pins for the
   specified activity (hook depressed, hook released).
-  In the code, depending on the ``hook_type`` set in the
   ``config.yaml``, the software will adapt its behavior. For NC types,
   hanging up the phone will trigger the ``on_hook`` behavior, and
   lifting the phone will trigger the ``off_hook`` behavior. The
   opposite will be true for NO types.
-  Once triggered the appropriate function is called.
-  On hook (depressed)

   -  Nothing happens

-  Off hook (released)

   -  Plays back your own added welcome message located in
      ``/sounds/voicemail.wav`` followed by the
      `beep </sounds/beep.wav>`__ indicating the start of recording.
   -  Begins recording the guests voice message.
   -  Guest hangs up, recording is stopped and stored to the
      ``/recordings/`` directory.
   -  If the guest exceeds the **recording_limit** specified in the
      `config.yaml </config.yaml>`__, play the warning
      `time_exceeded.wav </sounds/time_exceeded.wav>`__ sound and stop
      recording.

Operation Mode 2: `audioGuestBookwithRotaryDialer <./todo/audioGuestBookwithRotaryDialer.py>`__
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Note:** Untested - decided not to go this route for my own wedding

-  This mode is a special modification of the normal operation and
   requires a slightly different wiring connection since it accepts
   input from the rotary dialer.
-  The idea was to playback special messages when particular users dial
   a certain number combination (i.e. 909 would play back a message for
   certain guests who lived with the groom in that area code).
-  In this mode of operation the users will need to dial 0 on the rotary
   dialer in order to initiate the voicemail.
-  The rotary dialer is a bit more complex to set up, you need a pull up
   resistor connected between the F screw terminal and 5V on the rpi and
   the other end on GPIO 23. #TODO: Diagram

Troubleshooting
---------------

Configuring Hook Type
~~~~~~~~~~~~~~~~~~~~~

If you find that the behaviors for hanging up and lifting the phone are
reversed, it’s likely that the ``hook_type`` in ``config.yaml`` is
incorrectly set. Ensure that it matches your phone’s hook switch type
(NC or NO).

Verify default audio interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A few users had issues where audio I/O was defaulting to HDMI. To
alleviate this, check the following:

Check the Sound Card Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Verify the available sound devices using the following command:

.. code:: bash

   aplay -l

*Ensure that your USB audio interface is listed and note the card and
device numbers.*

Set the Default Sound Card
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to route audio through your USB audio interface, you’ll need
to make it the default sound card. Edit the ALSA configuration file
(usually located at ``/etc/asound.conf`` or ``~/.asoundrc``) and add the
following:

.. code:: bash

   defaults.pcm.card X
   defaults.ctl.card X

*Replace X with the card number of your USB audio interface obtained
from the previous step.*

Restart ALSA
^^^^^^^^^^^^

.. code:: bash

   sudo /etc/init.d/alsa-utils restart

Support
-------

If this code helped you or if you have some feedback, I’d be thrilled to
`hear about it <mailto:dillpicholas@duck.com>`__! Feel like saying
thanks? You can `buy me a coffee <https://ko-fi.com/dillpicholas>`__\ ☕.

.. |hook1| image:: _static/images/hook_test_1.jpg
.. |hook2| image:: _static/images/hook_test_2.jpg
.. |term1| image:: _static/images/block_terminal.jpg
.. |term2| image:: _static/images/top_view_block_terminal.jpg
.. |rpi| image:: _static/images/rpi_GPIO.png
