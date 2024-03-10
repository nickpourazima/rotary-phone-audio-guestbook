#! /usr/bin/env python3

import logging
import sys
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
        logger.info("Playing voicemail...")
        self.audio_interface.play_audio(
            self.config["greeting"],
            self.config["greeting_volume"],
            self.config["greeting_start_delay"],
        )
        logger.info("Playing beep...")
        self.audio_interface.play_audio(
            self.config["beep"],
            self.config["beep_volume"],
            self.config["beep_start_delay"],
        )

        output_file = str(
            Path(self.config["recordings_path"]) / f"{datetime.now().isoformat()}.wav"
        )
        self.audio_interface.start_recording(output_file)
        logger.info("Recording started...")

    def on_hook(self):
        """
        Handles the on-hook event to stop and save the recording.
        """
        logger.info("Phone on hook. Ending call and saving recording.")
        self.audio_interface.stop_recording()

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
