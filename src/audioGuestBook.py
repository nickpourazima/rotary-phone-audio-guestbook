#! /usr/bin/env python3

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from signal import pause
from threading import Event

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
        self.greeting_thread = None
        self.timer = None
        self._stop_playback_evt: Event = Event()
        self.setup_hook()
        self.setup_record_greeting()
        self.setup_shutdown_button()
        self.current_event = CurrentEvent.NONE

    def is_system_ready(self):
        """
        Check if system is in a ready state for new calls.
        """
        ready = (
            self.current_event == CurrentEvent.NONE
            and not self._stop_playback_evt.is_set()
            and hasattr(self, "hook")
            and not self.hook.is_active
            and self.audio_interface.recording_process is None
            and self.audio_interface.playback_process is None
            and (self.greeting_thread is None or not self.greeting_thread.is_alive())
        )

        if not ready:
            logger.debug(
                f"System not ready: event={self.current_event}, "
                f"stop_evt={self._stop_playback_evt.is_set()}, "
                f"hook_active={hasattr(self, 'hook') and self.hook.is_active}, "
                f"rec_proc={self.audio_interface.recording_process is not None}, "
                f"play_proc={self.audio_interface.playback_process is not None}, "
                f"thread_alive={self.greeting_thread and self.greeting_thread.is_alive()}"
            )

        return ready

    def _force_cleanup(self):
        """
        Force system back to a clean state. Used when normal cleanup fails.
        """
        logger.warning("Forcing system cleanup...")

        # Kill any stray processes
        try:
            subprocess.run(["pkill", "-KILL", "-f", "arecord.*-D"], check=False)
            subprocess.run(["pkill", "-KILL", "-f", "aplay.*-D"], check=False)
        except Exception as e:
            logger.error(f"Error during force cleanup: {e}")

        # Reset all state
        self.current_event = CurrentEvent.NONE
        self._stop_playback_evt.clear()
        self.audio_interface.recording_process = None
        self.audio_interface.playback_process = None
        self.greeting_thread = None
        self.timer = None

        # Verify cleanup
        time.sleep(0.5)  # Give processes time to die
        if self.is_system_ready():
            logger.info("Force cleanup successful - system ready")
        else:
            logger.error("Force cleanup may have failed - system still not ready")

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
        Configures the button so that 'active' always means 'off-hook'.
        """
        hook_gpio = self.config["hook_gpio"]
        hook_type = self.config["hook_type"]
        invert_hook = self.config.get("invert_hook", False)
        bounce_time = self.config["hook_bounce_time"]

        logger.info(
            f"Hook setup: GPIO={hook_gpio}, type={hook_type}, "
            f"invert={invert_hook}, bounce_time={bounce_time}"
        )

        pull_up = hook_type == "NC"

        # Determine the active state so that "active" always means "off-hook"
        # For normal wiring (not inverted):
        #   - NC: off-hook opens circuit → pin goes HIGH (pull-up)
        #   - NO: off-hook closes circuit → pin goes HIGH (connected to 3.3V)
        # So off-hook = HIGH unless logically inverted
        off_hook_is_high = not invert_hook

        # Create button with active_state configured so active = off-hook
        self.hook = Button(
            hook_gpio,
            pull_up=pull_up,
            bounce_time=bounce_time,
            active_state=off_hook_is_high,
        )

        logger.info(
            f"Button initialized: pull_up={pull_up}, "
            f"active_state={'high' if off_hook_is_high else 'low'} (off-hook)"
        )

        self.hook.when_activated = self.off_hook  # Phone picked up
        self.hook.when_deactivated = self.on_hook  # Phone hung up

        # Log initial state
        if self.hook.is_active:
            logger.warning("Hook is already off-hook at startup!")
        else:
            logger.info("Hook is on-hook at startup (ready)")

    def off_hook(self):
        """
        Handles the off-hook event to start playback and recording.
        """
        try:
            if self.current_event != CurrentEvent.NONE:
                logger.info("Another event is in progress. Ignoring off-hook event.")
                return

            # Verify system is truly ready before starting
            if not self.is_system_ready():
                logger.warning(
                    "System not fully ready at off-hook, attempting to proceed anyway"
                )

            # Defensive cleanup of any stuck state
            if hasattr(self, "_stop_playback_evt") and self._stop_playback_evt.is_set():
                logger.warning(
                    "Stop event was still set from previous call, clearing..."
                )
                self._stop_playback_evt.clear()

            logger.info("Phone off hook, ready to begin!")
            self.stop_recording_and_playback()

            self.current_event = CurrentEvent.HOOK

            # Ensure legacy flag is set for backward compatibility
            self.audio_interface.continue_playback = True

            self.greeting_thread = threading.Thread(
                target=self.play_greeting_and_beep, daemon=True
            )
            self.greeting_thread.start()

        except Exception as e:
            logger.error(f"Error in off_hook: {e}")

    def start_recording(self, output_file: str, skip_hook_check=False):
        """
        Starts the audio recording process and sets a timer for time exceeded event.
        Only starts if the handset is still off-hook (unless skip_hook_check for greeting).
        """
        # Check if handset is still off-hook (unless recording greeting)
        if not skip_hook_check and not self.hook.is_active:
            logger.info("Handset went back on-hook before recording could start")
            return

        # Start recording
        self.audio_interface.start_recording(output_file)
        logger.info(f"Recording started -> {output_file}")

        # Cancel any existing timer
        if hasattr(self, "timer") and self.timer is not None:
            try:
                self.timer.cancel()
            except Exception as e:
                logger.debug(f"Error canceling existing timer: {e}")
            self.timer = None

        # Start a new timer for time exceeded event
        self.timer = threading.Timer(
            self.config["time_exceeded_length"], self.time_exceeded
        )
        self.timer.start()

    def play_greeting_and_beep(self):
        """
        Play greeting and beep interruptibly, and start recording only if the
        handset is still off-hook at the critical points.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = str(Path(self.config["recordings_path"]) / f"{timestamp}.wav")
        include_beep = bool(self.config.get("beep_include_in_message", True))

        # 1) GREETING (interruptible)
        if self._stop_playback_evt.is_set() or self.current_event != CurrentEvent.HOOK:
            return

        self.audio_interface.play_audio(
            self.config["greeting"],
            volume=self.config.get("greeting_volume", 1.0),
            start_delay_sec=self.config.get("greeting_start_delay", 0.0),
            stop_event=self._stop_playback_evt,
        )

        if self._stop_playback_evt.is_set() or self.current_event != CurrentEvent.HOOK:
            return

        # If including beep in the message, start recording now (before the beep)
        if include_beep:
            if self.hook.is_active:
                self.start_recording(output_file)
            else:
                logger.debug(
                    "Skipping recording start (before beep) - handset back on-hook"
                )
                return

        # 2) BEEP (interruptible)
        if self._stop_playback_evt.is_set() or self.current_event != CurrentEvent.HOOK:
            return

        self.audio_interface.play_audio(
            self.config["beep"],
            volume=self.config.get("beep_volume", 1.0),
            start_delay_sec=self.config.get("beep_start_delay", 0.0),
            stop_event=self._stop_playback_evt,
        )

        if self._stop_playback_evt.is_set() or self.current_event != CurrentEvent.HOOK:
            return

        # If NOT including beep in the message, start recording after the beep
        if not include_beep:
            if self.hook.is_active:
                self.start_recording(output_file)
            else:
                logger.debug(
                    "Skipping recording start (after beep) - handset back on-hook"
                )

    def on_hook(self):
        """
        Handles the on-hook event to stop and save the recording.
        """
        try:
            if self.current_event != CurrentEvent.HOOK:
                return

            logger.info("Phone on hook. Ending call and saving recording.")

            # Cancel any in-flight playback
            self._stop_playback_evt.set()

            # Capture thread reference BEFORE cleanup (to avoid race condition)
            greeting_thread = getattr(self, "greeting_thread", None)

            # Stop recording and playback
            self.stop_recording_and_playback()

            # Extra verification that thread really stopped
            if greeting_thread and greeting_thread.is_alive():
                logger.error(
                    "CRITICAL: Greeting thread still alive after cleanup - attempting force join"
                )
                greeting_thread.join(timeout=2.0)
                if greeting_thread.is_alive():
                    logger.error("Thread still alive - system may be unstable")

            # Reset state
            self.current_event = CurrentEvent.NONE
            self._stop_playback_evt.clear()

            # Check system health
            if self.is_system_ready():
                logger.info("=========================================")
                logger.info("System reset completed successfully")
                logger.info("Ready for next recording - lift handset to begin")
                logger.info("=========================================")
            else:
                logger.error("WARNING: System may not be fully ready after hang-up")
                logger.error("Attempting recovery...")
                self._force_cleanup()

        except Exception as e:
            logger.error(f"Error in on_hook: {e}")
            # Force reset to known good state
            self.current_event = CurrentEvent.NONE
            self._stop_playback_evt.clear()
            self._force_cleanup()

    def time_exceeded(self):
        """
        Handles the event when the recording time exceeds the limit.
        """
        logger.info("Recording time exceeded. Stopping recording.")
        self.audio_interface.stop_recording()

        # Make the time exceeded message interruptible if user hangs up
        self.audio_interface.play_audio(
            self.config["time_exceeded"],
            self.config.get("time_exceeded_volume", 1.0),
            0,
            stop_event=self._stop_playback_evt,
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
        hold_time = int(self.config.get("shutdown_button_hold_time", 2))
        self.shutdown_button = Button(shutdown_gpio, pull_up=True, hold_time=hold_time)
        self.shutdown_button.when_held = self.shutdown

    def pressed_record_greeting(self):
        """
        Handles the record greeting to start recording a new greeting message.
        """
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring record greeting event.")
            return

        logger.info("Record greeting pressed, ready to begin!")

        self.current_event = CurrentEvent.RECORD_GREETING
        # Make this a daemon thread so it won't block shutdown
        self.greeting_thread = threading.Thread(
            target=self.beep_and_record_greeting, daemon=True
        )
        self.greeting_thread.start()

    def released_record_greeting(self):
        """
        Handles the record greeting event to stop and save the greeting.
        """
        # Check that the record greeting event is in progress
        if self.current_event != CurrentEvent.RECORD_GREETING:
            return

        logger.info("Record greeting released. Save the greeting.")
        self.current_event = CurrentEvent.NONE
        self.stop_recording_and_playback()

        # Clear the stop event for next use
        if hasattr(self, "_stop_playback_evt"):
            self._stop_playback_evt.clear()

    def beep_and_record_greeting(self):
        """
        Plays the beep and start recording a new greeting message.
        """
        self.audio_interface.continue_playback = (
            self.current_event == CurrentEvent.RECORD_GREETING
        )

        # Play the beep
        if self.current_event == CurrentEvent.RECORD_GREETING:
            logger.info("Playing beep...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config.get("beep_volume", 1.0),
                self.config.get("beep_start_delay", 0.0),
            )

        # Check if the record greeting message button is still pressed
        if self.current_event == CurrentEvent.RECORD_GREETING:
            path = str(Path(self.config["greeting"]))
            # Start recording new greeting message (skip hook check for greeting)
            self.start_recording(path, skip_hook_check=True)

    def stop_recording_and_playback(self):
        """
        Stop recording and playback processes.
        """
        # Signal cooperative cancellation for any in-flight playback
        # This ensures ALL paths that stop playback also cancel properly
        if hasattr(self, "_stop_playback_evt"):
            self._stop_playback_evt.set()

        # Cancel the timer first to prevent any race conditions
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()
            self.timer = None

        # Stop recording if it's active
        self.audio_interface.stop_recording()

        # Capture thread reference to avoid race with None assignment
        t = getattr(self, "greeting_thread", None)
        if t and t.is_alive():
            logger.info("Stopping playback.")
            self.audio_interface.continue_playback = False
            self.audio_interface.stop_playback()

            # Wait for the thread to complete
            try:
                t.join(timeout=3.0)
            except (RuntimeError, AttributeError) as e:
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
