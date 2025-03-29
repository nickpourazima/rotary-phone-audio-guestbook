#! /usr/bin/env python3

import logging
import os
import sys
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from signal import pause

import yaml
from gpiozero import Button, Device
from gpiozero.pins.rpigpio import RPiGPIOFactory

from audioInterface import AudioInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
Device.pin_factory = RPiGPIOFactory()


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
            logger.info(
                f"Recordings folder does not exist. Creating folder: {recordings_path}"
            )
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

        For NC (Normally Closed) switches:
          - NC switches use pull_up=True (internal pull-up resistor)
          - When the hook is down (on hook), the circuit is CLOSED (button NOT pressed)
          - When the hook is up (off hook), the circuit is OPEN (button IS pressed)

        For NO (Normally Open) switches:
          - NO switches use pull_up=False (internal pull-down resistor)
          - When the hook is down (on hook), the circuit is OPEN (button NOT pressed)
          - When the hook is up (off hook), the circuit is CLOSED (button IS pressed)
        """
        hook_gpio = self.config["hook_gpio"]
        hook_type = self.config["hook_type"]
        invert_hook = self.config.get("invert_hook", False)
        bounce_time = self.config["hook_bounce_time"]

        # Log the configuration for debugging
        logger.info(f"Hook setup: GPIO={hook_gpio}, type={hook_type}, invert={invert_hook}, bounce_time={bounce_time}")

        pull_up = hook_type == "NC"

        # Create button with appropriate pull-up/down resistor
        self.hook = Button(hook_gpio, pull_up=pull_up, bounce_time=bounce_time)
        logger.info(f"Button initialized with pull_up={pull_up}")

        # The combination of hook_type and invert_hook determines the mapping
        if invert_hook:
            # Inverted behavior
            if pull_up:  # NC
                self.hook.when_released = self.off_hook  # Circuit opens (hook up)
                self.hook.when_pressed = self.on_hook    # Circuit closes (hook down)
            else:  # NO
                self.hook.when_released = self.on_hook   # Circuit opens (hook down)
                self.hook.when_pressed = self.off_hook   # Circuit closes (hook up)
        else:
            # Normal behavior
            if pull_up:  # NC
                self.hook.when_pressed = self.off_hook   # Circuit opens (hook up)
                self.hook.when_released = self.on_hook   # Circuit closes (hook down)
            else:  # NO
                self.hook.when_pressed = self.on_hook    # Circuit closes (hook down)
                self.hook.when_released = self.off_hook  # Circuit opens (hook up)

    def off_hook(self):
        """
        Handles the off-hook event to start playback and recording.
        """
        # Check that no other event is currently in progress
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring off-hook event.")
            return

        logger.info("Phone off hook, ready to begin!")

        # Ensure clean state by forcing stop of any existing processes
        self.stop_recording_and_playback()

        self.current_event = CurrentEvent.HOOK  # Ensure playback can continue
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

        # Create output filename with timestamp
        timestamp = datetime.now().isoformat()
        output_file = str(
            Path(self.config["recordings_path"]) / f"{timestamp}.wav"
        )
        logger.info(f"Will save recording to: {output_file}")

        # Verify recording path exists and is writable
        recordings_path = Path(self.config["recordings_path"])
        logger.info(f"Recording directory exists: {recordings_path.exists()}")
        logger.info(f"Recording directory is writable: {os.access(str(recordings_path), os.W_OK)}")

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
        if self.current_event == CurrentEvent.HOOK:
            logger.info("Phone on hook. Ending call and saving recording.")
            # Stop any ongoing processes before resetting the state
            self.stop_recording_and_playback()

            # Reset everything to initial state
            self.current_event = CurrentEvent.NONE

            # Make sure we're ready for the next call with more verbose logging
            logger.info("=========================================")
            logger.info("System reset completed successfully")
            logger.info("Ready for next recording - lift handset to begin")
            logger.info("=========================================")

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
        self.record_greeting = Button(
            record_greeting_gpio, pull_up=pull_up, bounce_time=bounce_time
        )
        self.record_greeting.when_pressed = self.pressed_record_greeting
        self.record_greeting.when_released = self.released_record_greeting

    def shutdown(self):
        print("System shutting down...")
        os.system("sudo shutdown now")

    def setup_shutdown_button(self):
        shutdown_gpio = self.config["shutdown_gpio"]
        if shutdown_gpio == 0:
            logger.info("no shutdown button declared, skipping button init")
            return
        hold_time = self.config["shutdown_button_hold_time"] == 2
        self.shutdown_button = Button(shutdown_gpio, pull_up=True, hold_time=hold_time)
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

        self.current_event = (
            CurrentEvent.RECORD_GREETING
        )  # Ensure record greeting can continue
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
        self.current_event = CurrentEvent.NONE  # Stop playback and reset current event
        self.stop_recording_and_playback()

    def beep_and_record_greeting(self):
        """
        Plays the beep and start recording a new greeting message #, checking for the button event.
        """

        self.audio_interface.continue_playback = (
            self.current_event == CurrentEvent.RECORD_GREETING
        )

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
            path = str(Path(self.config["greeting"]))
            # Start recording new greeting message
            self.start_recording(path)

    def stop_recording_and_playback(self):
        """
        Stop recording and playback processes.
        """
        # Cancel the timer first to prevent any race conditions
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()
            self.timer = None

        # Stop recording if it's active
        self.audio_interface.stop_recording()

        # Stop playback if the greeting thread is still running
        # Check if the attribute exists and is not None before checking is_alive()
        if hasattr(self, "greeting_thread") and self.greeting_thread is not None:
            try:
                if self.greeting_thread.is_alive():
                    logger.info("Stopping playback.")
                    self.audio_interface.continue_playback = False
                    self.audio_interface.stop_playback()

                    # Wait for the thread to complete with a longer timeout
                    self.greeting_thread.join(timeout=3.0)
            except (RuntimeError, AttributeError) as e:
                # Handle any race conditions where the thread might change state
                # between our check and the operation
                logger.warning(f"Error while stopping playback thread: {e}")

            # Force set to None to ensure clean state for next call
            self.greeting_thread = None

        # Ensure the hook listeners are still active
        logger.info("Verifying event listeners are active")

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
