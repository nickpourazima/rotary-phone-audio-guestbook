#! /usr/bin/env python3

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from signal import pause
from enum import Enum
import os

import yaml
from gpiozero import Button

from audioInterface import AudioInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CurrentEvent(Enum):
    NONE = 0
    HOOK = 1
    RECORD_GREETING = 2

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
        
        # Check if the recordings folder exists, if not, create it.
        recordings_path = Path(self.config["recordings_path"])
        if not recordings_path.exists():
            logger.info(f"Recordings folder does not exist. Creating folder: {recordings_path}")
            recordings_path.mkdir(parents=True, exist_ok=True)
        
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
        self.setup_record_greeting()
        self.setup_shutdown_button()
        self.current_event = CurrentEvent.NONE

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
        bounce_time = self.config["hook_bounce_time"]
        self.hook = Button(hook_gpio, pull_up=pull_up, bounce_time=bounce_time)
        if pull_up:
            self.hook.when_pressed = self.off_hook
            self.hook.when_released = self.on_hook
        else:
            self.hook.when_pressed = self.on_hook
            self.hook.when_released = self.off_hook

    def off_hook(self):
        """
        Handles the off-hook event to start playback and recording.
        """
        # Check that no other event is currently in progress
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring off-hook event.")
            return

        logger.info("Phone off hook, ready to begin!")

        self.current_event = CurrentEvent.HOOK # Ensure playback can continue
        # Start the greeting playback in a separate thread
        self.greeting_thread = threading.Thread(target=self.play_greeting_and_beep)
        self.greeting_thread.start()

    def start_recording(self, output_file: str):        
        """
        Starts the audio recording process and sets a timer for time exceeded event.
        """
                      
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
        self.audio_interface.continue_playback = self.current_event == CurrentEvent.HOOK
        logger.info("Playing voicemail...")
        self.audio_interface.play_audio(
            self.config["greeting"],
            self.config["greeting_volume"],
            self.config["greeting_start_delay"],
        )

        output_file = str(
            Path(self.config["recordings_path"]) / f"{datetime.now().isoformat()}.wav"
        )
        include_beep = bool(self.config["beep_include_in_message"])

        # Check if the phone is still off-hook
        # Start recording already BEFORE the beep (beep will be included in message)
        if self.current_event == CurrentEvent.HOOK and include_beep:
            self.start_recording(output_file)

        # Play the beep
        if self.current_event == CurrentEvent.HOOK:
            logger.info("Playing beep...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"],
            )

        # Check if the phone is still off-hook
        # Start recording AFTER the beep (beep will NOT be included in message)
        if self.current_event == CurrentEvent.HOOK and not include_beep:
            self.start_recording(output_file)

    def on_hook(self):
        """
        Handles the on-hook event to stop and save the recording.
        """
        # Check that the off-hook event is in progress
        if self.current_event != CurrentEvent.HOOK:
            return
        
        logger.info("Phone on hook. Ending call and saving recording.")
        self.current_event = CurrentEvent.NONE # Stop playback and reset current event
        self.stop_recording_and_playback()

    def time_exceeded(self):
        """
        Handles the event when the recording time exceeds the limit.
        """
        logger.info("Recording time exceeded. Stopping recording.")
        self.audio_interface.stop_recording()
        self.audio_interface.play_audio(
            self.config["time_exceeded"], self.config["time_exceeded_volume"], 0
        )

    def setup_record_greeting(self):
        """
        Sets up the phone record greeting switch with GPIO based on the configuration.
        """
        record_greeting_gpio = self.config["record_greeting_gpio"]
        if record_greeting_gpio == 0:
            logger.info("record_greeting_gpio is 0, skipping setup.")
            return
        pull_up = self.config["record_greeting_type"] == "NC"
        bounce_time = self.config["record_greeting_bounce_time"]
        self.record_greeting = Button(record_greeting_gpio, pull_up=pull_up, bounce_time=bounce_time)
        self.record_greeting.when_pressed = self.pressed_record_greeting
        self.record_greeting.when_released = self.released_record_greeting
        
    def shutdown():
        print("System shutting down...")
        os.system("sudo shutdown now")

        
    def setup_shutdown_button(self):
        shutdown_gpio = self.config["shutdown_gpio"]
        if shutdown_gpio == 0:
            logger.info("no shutdown button declared, skipping button init")
            return
        hold_time = self.config["shutdown_button_hold_time"] == 2
        self.shutdown_button =  Button(shutdown_gpio, pull_up=True, hold_time=hold_time)
        self.shutdown_button.when_held = self.shutdown
    
    
    def pressed_record_greeting(self):
        """
        Handles the record greeting to start recording a new greeting message.
        """
        # Check that no other event is currently in progress
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring record greeting event.")
            return

        logger.info("Record greeting pressed, ready to begin!")

        self.current_event = CurrentEvent.RECORD_GREETING # Ensure record greeting can continue
        # Start the record greeting in a separate thread
        self.greeting_thread = threading.Thread(target=self.beep_and_record_greeting)
        self.greeting_thread.start()

    def released_record_greeting(self):
        """
        Handles the record greeting event to stop and save the greeting.
        """
        # Check that the record greeting event is in progress
        if self.current_event != CurrentEvent.RECORD_GREETING:
            return
        
        logger.info("Record greeting released. Save the greeting.")
        self.current_event = CurrentEvent.NONE # Stop playback and reset current event
        self.stop_recording_and_playback()

    def beep_and_record_greeting(self):
        """
        Plays the beep and start recording a new greeting message #, checking for the button event.
        """

        self.audio_interface.continue_playback = self.current_event == CurrentEvent.RECORD_GREETING

        # Play the beep
        if self.current_event == CurrentEvent.RECORD_GREETING:
            logger.info("Playing beep...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"],
            )

        # Check if the record greeting message button is still pressed      
        if self.current_event == CurrentEvent.RECORD_GREETING:
            path = str(
                Path(self.config["greeting"])
            )
            # Start recording new greeting message       
            self.start_recording(path)

    def stop_recording_and_playback(self):
        """
        Stop recording and playback processes.
        """
        self.audio_interface.stop_recording()
        if hasattr(self, "timer"):
            self.timer.cancel()
        if hasattr(self, "greeting_thread") and self.greeting_thread.is_alive():
            logger.info("Stopping playback.")
            self.audio_interface.stop_playback()

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
