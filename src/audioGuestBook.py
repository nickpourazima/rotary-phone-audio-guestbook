#! /usr/bin/env python3

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from signal import pause

import yaml
from gpiozero import Button

from audioInterface import AudioInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioGuestBook:
    """
    Manages the rotary phone audio guest book application.

    This class initializes the application, handles phone hook events, and
    coordinates audio playback and recording based on the phone's hook status.

    Attributes:
        config_path (str): Path to the application configuration file.
        config (dict): Configuration parameters loaded from the YAML file.
        audio_interface (AudioInterface): Interface for audio playback and recording.
    """

    def __init__(self, config_path):
        """
        Initializes the audio guest book application with specified configuration.

        Args:
            config_path (str): Path to the configuration YAML file.
        """
        self.config_path = config_path
        self.config = self.load_config()
        self.audio_interface = AudioInterface(
            alsa_hw_mapping=self.config["alsa_hw_mapping"],
            format=self.config["format"],
            file_type=self.config["file_type"],
            recording_limit=self.config["recording_limit"],
            sample_rate=self.config["sample_rate"],
            channels=self.config["channels"],
            mixer_control_name=self.config["mixer_control_name"],
        )
        self.setup_hook()
        self.continue_playback = False

    def load_config(self):
        """
        Loads the application configuration from a YAML file.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
        """
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            sys.exit(1)

    def setup_hook(self):
        """
        Sets up the phone hook switch with GPIO based on the configuration.
        """
        hook_gpio = self.config["hook_gpio"]
        pull_up = self.config["hook_type"] == "NC"
        self.hook = Button(hook_gpio, pull_up=pull_up)
        self.hook.when_pressed = self.off_hook
        self.hook.when_released = self.on_hook

    def off_hook(self):
        """
        Handles the off-hook event to start playback and recording.
        """
        logger.info("Phone off hook, ready to begin!")

        self.continue_playback = True  # Ensure playback can continue
        # Start the greeting playback in a separate thread
        self.greeting_thread = threading.Thread(target=self.play_greeting_and_beep)
        self.greeting_thread.start()

    def start_recording(self):
        """
        Starts the audio recording process and sets a timer for time exceeded event.
        """
        output_file = str(
            Path(self.config["recordings_path"]) / f"{datetime.now().isoformat()}.wav"
        )
        self.audio_interface.start_recording(output_file)
        logger.info("Recording started...")

        # Start a timer to handle the time exceeded event
        self.timer = threading.Timer(
            self.config["time_exceeded_length"], self.time_exceeded
        )
        self.timer.start()

    def play_greeting_and_beep(self):
        """
        Plays the greeting and beep sounds, checking for the on-hook event.
        """
        # Play the greeting
        self.audio_interface.continue_playback = self.continue_playback
        logger.info("Playing voicemail...")
        self.audio_interface.play_audio(
            self.config["greeting"],
            self.config["greeting_volume"],
            self.config["greeting_start_delay"],
        )

        # Check if the phone is still off-hook
        # Start recording already BEFORE the beep
        if self.continue_playback:
            self.start_recording()

        # Play the beep
        if self.continue_playback:
            logger.info("Playing beep...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"],
            )


    def on_hook(self):
        """
        Handles the on-hook event to stop and save the recording.
        """
        logger.info("Phone on hook. Ending call and saving recording.")
        self.continue_playback = False  # Stop playback
        self.audio_interface.stop_recording()
        if hasattr(self, "timer"):
            self.timer.cancel()
        if hasattr(self, "greeting_thread") and self.greeting_thread.is_alive():
            logger.info("Stopping voicemail playback.")
            self.audio_interface.stop_playback()

    def time_exceeded(self):
        """
        Handles the event when the recording time exceeds the limit.
        """
        logger.info("Recording time exceeded. Stopping recording.")
        self.audio_interface.stop_recording()
        self.audio_interface.play_audio(
            self.config["time_exceeded"], self.config["time_exceeded_volume"], 0
        )

    def run(self):
        """
        Starts the main event loop waiting for phone hook events.
        """
        logger.info("System ready. Lift the handset to start.")
        pause()


if __name__ == "__main__":
    CONFIG_PATH = Path(__file__).parent / "../config.yaml"
    logger.info(f"Using configuration file: {CONFIG_PATH}")
    guest_book = AudioGuestBook(CONFIG_PATH)
    guest_book.run()
