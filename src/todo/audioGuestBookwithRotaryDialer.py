#! /usr/bin/env python3

import src.audioInterface as audioInterface
import os
import yaml
import sys

from datetime import datetime
from gpiozero import Button
from multiprocessing import Process
from signal import pause
from pydub import AudioSegment
from pydub.playback import play
from pydub.scipy_effects import band_pass_filter
from pydub.effects import normalize, compress_dynamic_range

try:
    with open("config.yaml") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
except FileNotFoundError as e:
    print(
        f"Could not find the config.yaml file. FileNotFoundError: {e}. Check config location and retry."
    )
    sys.exit(1)

hook = Button(config["hook_gpio"])
rotaryDial = Button(pin=config['rotary_gpio'], hold_time=config['rotary_hold_time'], hold_repeat=config['rotary_hold_repeat'])

"""
TODO: These globals are a temp solution for the rotary dialer, would love to not
depend on globals for this logic.
"""
count = 0
dialed = []
reset_flag = False

def off_hook() -> None:
    print("Phone off hook, ready to begin!")
    # if dialed and dialed[0] == 0:
    audio_interface = audioInterface.AudioInterface(config, hook)

    # playback voice message through speaker
    print("Playing voicemail message...")
    play(
        AudioSegment.from_wav(
            os.path.dirname(os.path.abspath(config["source_file"]))
            + "/sounds/voicemail.wav"
        )
        - config["playback_reduction"]
    )

    # start recording beep
    print("Playing beep...")
    play(
        AudioSegment.from_wav(
            os.path.dirname(os.path.abspath(config["source_file"])) + "/sounds/beep.wav"
        )
        - config["beep_reduction"]
    )

    # now, while phone is not off the hook, record audio from the microphone
    print("recording")
    audio_interface.record()
    audio_interface.stop()
    output_file = (
        os.path.dirname(os.path.abspath(config["source_file"]))
        + "/recordings/"
        + f"{datetime.now().isoformat()}"
    )
    audio_interface.close(output_file + ".wav")
    print("Finished recording!")

    """
    post processing
    """
    print("spawn postProcessing thread")
    Process(target=audio_interface.postProcess, args=(output_file,)).start()

    """
    rotary dialer special messages
    """
    if dialed[0:3] == [9,2,7]:
        # play special vm
        play(AudioSegment.from_wav(os.path.dirname(os.path.abspath(config["source_file"])) + "/sounds/927.wav") - config['playback_reduction'])

    elif dialed[0:4] == [5,4,5,3]:
        # play special vm
        play(AudioSegment.from_wav(os.path.dirname(os.path.abspath(config["source_file"])) + "/sounds/beep.wav") - config['beep_reduction'])


def on_hook() -> None:
    print("Phone on hook. Sleeping...")
    print("Resetting dial list")
    global dialed
    dialed = []
    reset_pulse_counter()


def dialing() -> None:
    if hook.is_pressed:
        global count, reset_flag
        count+=1
        print(f"dialing, increment count: {count}")
        reset_flag = False

def reset_pulse_counter() -> None:
    global count, reset_flag
    count = 0
    print(f"reset count: {count}")
    reset_flag = True


def held() -> None:
    if not reset_flag:
        print("holding")
        print(count)
        global dialed
        if (count == 10):
            dialed.append(0)
        else:
            dialed.append(count)
        print(f"number dialed: {dialed}")
        off_hook()
        reset_pulse_counter()


def main():
    rotaryDial.when_pressed = dialing
    rotaryDial.when_held = held
    hook.when_pressed = off_hook
    hook.when_released = on_hook
    pause()


if __name__ == "__main__":
    main()
