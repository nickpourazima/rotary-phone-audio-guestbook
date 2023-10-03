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


def off_hook(args):
    logger.info("Phone off hook, ready to begin!")
    audio_interface = audioInterface.AudioInterface(
        hook=args["hook"],
        buffer_size=args["config"]["buffer_size"],
        channels=args["config"]["channels"],
        format=FORMATS.get(args["config"]["format"], pyaudio.paInt16),
        sample_rate=args["config"]["sample_rate"],
        recording_limit=args["config"]["recording_limit"],
        dev_index=args["config"]["alsa_hw_mapping"],
    )

    logger.info("Playing voicemail message...")
    play_audio("voicemail.wav", args["config"]["playback_reduction"])

    logger.info("Playing beep...")
    play_audio("beep.wav", args["config"]["beep_reduction"])

    logger.info("recording")
    audio_interface.record()
    audio_interface.stop()

    output_file = BASE_DIR / "recordings" / f"{datetime.now().isoformat()}.wav"
    audio_interface.close(output_file)
    logger.info("Finished recording!")


def on_hook():
    logger.info("Phone on hook.\nSleeping...")


def main():
    config = load_config()
    hook = Button(config["hook_gpio"])
    args = {"config": config, "hook": hook}
    hook.when_pressed = lambda: off_hook(args)
    hook.when_released = on_hook
    pause()


if __name__ == "__main__":
    main()
