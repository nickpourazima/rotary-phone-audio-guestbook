#! /usr/bin/env python3

import logging
import os
import sys
import threading
import time  # already imported once, but safe here
from datetime import datetime
from enum import Enum
from pathlib import Path
from signal import pause

import yaml
from gpiozero import Button, Device
from gpiozero.pins.rpigpio import RPiGPIOFactory

from audioInterface import AudioInterface

def cleanup_session(self):
    """Ensure all session-related flags and threads are properly reset"""
    self.current_event = CurrentEvent.NONE
    self.recording_watchdog_active = False
    if hasattr(self, 'timer') and self.timer:
        self.timer.cancel()

def get_stable_hook_state(button, stable_time=0.2, check_interval=0.02, bounce_tolerance=0.03):
    """
    Poll the hook switch until it has been stable for `stable_time` seconds,
    but allow very short bounces (less than `bounce_tolerance` seconds).
    
    Returns True (pressed/off-hook) or False (released/on-hook).
    Blocks until a stable value is found.
    """
    last_state = button.is_pressed
    stable_since = time.time()
    last_change_time = time.time()

    while True:
        current_state = button.is_pressed
        now = time.time()
        if current_state != last_state:
            # record the time of this state change
            last_change_time = now
            last_state = current_state
            logger.debug(f"Hook state changed: {current_state}")

        # only consider it stable if the state hasn't changed longer than bounce_tolerance
        if now - last_change_time >= bounce_tolerance:
            if now - stable_since >= stable_time:
                logger.info(f"Stable hook state confirmed: {current_state}")
                return current_state
        else:
            # reset stable_since if in bounce window
            stable_since = now

        time.sleep(check_interval)


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
        self.watchdog_active = False

        # Start the off-hook watchdog to catch missed events
        self._start_off_hook_watchdog()

        # In __init__
        self.session_lock = threading.Lock()


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

    def _start_off_hook_watchdog(self):
        """
        Watchdog monitors for missed off-hook events.
        If a lift is detected while no session is active, it triggers off_hook().
        Won't trigger repeatedly during the same idle period.
        """
        triggered = False  # tracks if off_hook has been triggered during idle

        def watchdog():
            nonlocal triggered
            logger.info("[OFF-HOOK WATCHDOG] Monitoring for missed off-hook events.")
            while True:
                if self.current_event == CurrentEvent.NONE and self.hook.is_pressed:
                    if not triggered:
                        logger.warning("[OFF-HOOK WATCHDOG] Missed off-hook detected! User lift detected.")
                        self.off_hook()
                        triggered = True
                else:
                    # Reset flag once phone goes on-hook or session starts
                    triggered = False

                time.sleep(0.2)

        t = threading.Thread(target=watchdog, daemon=True)
        t.start()





    def off_hook(self):
        """
        Handles off-hook event to start session.
        Only one session can run at a time.
        """
        # Acquire lock to prevent double-start
        if not self.session_lock.acquire(blocking=False):
            logger.info("off_hook() ignored: session already starting")
            return

        try:
            if self.current_event != CurrentEvent.NONE:
                logger.info("off_hook() ignored: session already active")
                return

            logger.info(f"off_hook() triggered. current_event: {self.current_event}")
            logger.info("Phone off hook, starting session immediately.")

            # Ensure clean state
            self.stop_recording_and_playback()

            # Start new hook session
            self.current_event = CurrentEvent.HOOK
            self.greeting_thread = threading.Thread(target=self._hook_session)
            self.greeting_thread.start()
        finally:
            self.session_lock.release()

    
    def _check_off_hook(self, stable_time=0.2, cancel_grace=0.3) -> bool:
        """
        Return True if phone is off-hook (stable).
        Only cancels session if an actual session is active.
        Adds a grace period to ignore short bounces.
        """
        # Wait a short grace period before reading
        start = time.time()
        while time.time() - start < cancel_grace:
            if get_stable_hook_state(self.hook, stable_time=stable_time, check_interval=0.05):
                return True
            time.sleep(0.01)

        # Final check
        stable_state = get_stable_hook_state(self.hook, stable_time=stable_time, check_interval=0.05)

        if not stable_state:
            if self.current_event != CurrentEvent.NONE:
                logger.info("Phone went on-hook (stable). Cancelling session via on_hook().")
                # Call on_hook() directly to ensure consistent cleanup
                self.on_hook()
            else:
                logger.info("Phone briefly on-hook during startup. Ignoring.")
            return False

        return True

    def _start_hook_watchdog(self):
        """Start a background thread to monitor hook state while recording."""
        def watchdog():
            self.watchdog_active = True
            logger.info("[WATCHDOG] Started hook monitoring thread.")
            while self.current_event == CurrentEvent.HOOK:  # recording session
                if not self.hook.is_pressed:  # handset down (on-hook)
                    logger.info("[WATCHDOG] Handset detected ON-HOOK during recording.")
                    
                    self.stop_recording_and_playback()
                    self.current_event = CurrentEvent.NONE
                    logger.info("Recording session ended by watchdog.")
                    break
                time.sleep(0.1)
            self.watchdog_active = False
            logger.info("[WATCHDOG] Exiting thread.")

        t = threading.Thread(target=watchdog, daemon=True)
        t.start()



    def start_recording(self, output_file: str):
        """
        Starts the audio recording process and sets a timer for time exceeded event.
        """
        logger.info(f"[{datetime.now()}] start_recording() called. current_event: {self.current_event}")

        # Stop all playback before recording
        self.audio_interface.continue_playback = False
        self.audio_interface.stop_playback()
        import time; time.sleep(0.05)  # tiny delay to let ALSA flush

        # Start Recording
        self.audio_interface.start_recording(output_file)
        logger.info("Recording started...")

        #Start Watchdog Timer
        self.current_event = CurrentEvent.HOOK
        self._start_hook_watchdog()

        # Start a timer to handle the time exceeded event
        self.timer = threading.Timer(
            self.config["time_exceeded_length"], self.time_exceeded
        )
        self.timer.start()

    def _hook_session(self):
        """Manages a single off-hook session: greeting, beep, and recording."""

        # Stop any playback first
        self.audio_interface.continue_playback = False
        self.audio_interface.stop_playback()
        time.sleep(0.05)

        # Wait until off-hook is stable before greeting
        if not self._check_off_hook():
            return  # Abort if user hung up

        logger.info("Playing greeting...")
        self.audio_interface.continue_playback = True
        self.audio_interface.play_audio(
            self.config["greeting"],
            self.config["greeting_volume"],
            self.config["greeting_start_delay"]
        )

        # Only check off-hook **after greeting starts** to catch real hangs
        if not self._check_off_hook():
            return

        # Continue with beep and recording
        timestamp = datetime.now().isoformat()
        output_file = str(Path(self.config["recordings_path"]) / f"{timestamp}.wav")
        logger.info(f"Will save recording to: {output_file}")

        if self.config["beep_include_in_message"]:
            logger.info("Playing beep (included in recording)...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"]
            )
            if not self._check_off_hook():
                return
            self.start_recording(output_file)
        else:
            logger.info("Playing beep (excluded from recording)...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"]
            )
            if not self._check_off_hook():
                return
            self.start_recording(output_file)


    def on_hook(self):
        """
        Handles the on-hook event to stop playback or recording.
        Uses debounce if watchdog isn't running.
        """
        raw_state = self.hook.is_pressed
        logger.info(f"[DEBUG] on_hook() fired. raw_state={raw_state}")

        if self.watchdog_active:
            logger.info("Watchdog already handled on-hook. Ignoring this event.")
            return

        # If we are recording, watchdog handles ON-HOOK exclusively
        if self.current_event == CurrentEvent.HOOK and self.audio_interface.is_recording_active():
            logger.info("on_hook() ignored: recording in progress, watchdog will handle cleanup.")
            return

        # Detect whether watchdog is active
        watchdog_active = (self.current_event == CurrentEvent.HOOK)

        if watchdog_active:
            # Watchdog already debounces, so trust raw_state
            if raw_state:  # still off-hook
                logger.info("Off-hook confirmed while recording. Ignoring on_hook.")
                return
        else:
            # No watchdog running (e.g., greeting phase) → debounce here
            stable = get_stable_hook_state(self.hook)
            logger.info(f"[DEBUG] get_stable_hook_state -> {stable}")
            if stable:  # still off-hook
                logger.info("Debounce check: still off-hook. Ignoring on_hook.")
                return

        logger.info(f"on_hook() called. Current state: {self.current_event}")

        if self.current_event == CurrentEvent.HOOK:
            logger.info("Phone on hook. Ending call and saving recording.")
            self.stop_recording_and_playback()
            self.current_event = CurrentEvent.NONE
            logger.info("Set current_event to NONE.")
            logger.info("=========================================")
            logger.info("System reset completed successfully")
            logger.info("Ready for next recording - lift handset to begin")
            logger.info("=========================================")
        else:
            logger.info("on_hook() triggered, but no active HOOK session.")
            self.current_event = CurrentEvent.NONE



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
            # Stop playback before recording
            self.audio_interface.continue_playback = False
            self.audio_interface.stop_playback()
            import time; time.sleep(0.05)
            self.start_recording(path)

    def stop_recording_and_playback(self):
        """Stop recording and playback cleanly without joining the current thread."""
        if hasattr(self, "timer") and self.timer:
            self.timer.cancel()
            self.timer = None

        self.audio_interface.stop_recording()

        if hasattr(self, "greeting_thread") and self.greeting_thread:
            self.audio_interface.continue_playback = False
            self.audio_interface.stop_playback()
            # Don't join the thread here
            self.greeting_thread = None

        logger.info("Event listeners verified.")

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
