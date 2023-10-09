#! /usr/bin/env python3

import logging
import sys
from datetime import datetime
from pathlib import Path
from signal import pause

import pyaudio
import yaml
from gpiozero import Button
from pydub import AudioSegment, playback

import audioInterface

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
FORMATS = {
    "INT16": pyaudio.paInt16,
    "INT32": pyaudio.paInt32,
    "FLOAT32": pyaudio.paFloat32,
}


def load_config():
    try:
        with CONFIG_PATH.open() as f:
            return yaml.safe_load(f)
    except FileNotFoundError as e:
        logger.error(
            f"Could not find {CONFIG_PATH}. FileNotFoundError: {e}. Check config location and retry."
        )
        sys.exit(1)


def play_audio(filename, reduction=0):
    try:
        sound_path = BASE_DIR / "sounds" / filename
        sound = AudioSegment.from_wav(sound_path) - reduction
        playback.play(sound)
    except Exception as e:
        logger.error(f"Error playing {filename}. Error: {e}")


def off_hook():
    global hook, config

    logger.info("Phone off hook, ready to begin!")

    audio_interface = audioInterface.AudioInterface(
        hook=hook,
        buffer_size=config["buffer_size"],
        channels=config["channels"],
        format=FORMATS.get(config["format"], pyaudio.paInt16),
        sample_rate=config["sample_rate"],
        recording_limit=config["recording_limit"],
        dev_index=config["alsa_hw_mapping"],
        hook_type=config["hook_type"],
    )

    logger.info("Playing voicemail message...")
    play_audio("voicemail.wav", config["playback_reduction"])

    logger.info("Playing beep...")
    play_audio("beep.wav", config["beep_reduction"])

    logger.info("recording")
    audio_interface.record()
    audio_interface.stop()

    output_file = str(BASE_DIR / "recordings" / f"{datetime.now().isoformat()}.wav")
    audio_interface.close(output_file)
    logger.info("Finished recording!")


def on_hook():
    logger.info("Phone on hook.\nSleeping...")


def main():
    global config, hook
    config = load_config()
    if config["hook_type"] == "NC":
        hook = Button(config["hook_gpio"], pull_up=True)
        hook.when_pressed = on_hook
        hook.when_released = off_hook
    else:  # Assuming NO if not NC
        hook = Button(config["hook_gpio"], pull_up=False)
        hook.when_pressed = off_hook
        hook.when_released = on_hook
    pause()


if __name__ == "__main__":
    main()
