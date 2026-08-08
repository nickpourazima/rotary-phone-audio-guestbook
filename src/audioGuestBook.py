#!/usr/bin/env python3
import logging
import RPi.GPIO as GPIO
import random
import subprocess
import time
import wave
import yaml
from datetime import datetime
from pathlib import Path
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)

# Global state
recording_proc = None
recording_start_ts = None
record_greeting_proc = None
recording_path = None
last_played_path = None

def set_volume(volume_pct, mixer_control):
    """Set system volume using amixer."""
    vol = max(0, min(int(volume_pct * 100), 100))
    subprocess.run(["amixer", "set", mixer_control, f"{vol}%"], check=False, 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def is_on_hook(pin, hook_type, invert_hook):
    """
    Determine if handset is on-hook based on GPIO state and configuration.
    
    For NC (Normally Closed) with pull-up:
      - When on-hook: circuit closed, GPIO pulled to GND → reads LOW
      - When off-hook: circuit open, pull-up resistor → reads HIGH
      - Therefore: HIGH = on-hook, LOW = off-hook
      
    Actually, based on working simple implementation:
      - NC: HIGH = on-hook, LOW = off-hook (handset down = high)
      
    For NO (Normally Open):
      - When on-hook: circuit open → reads HIGH (with pull-up)
      - When off-hook: circuit closed → reads LOW
      - Therefore: LOW = on-hook, HIGH = off-hook
    
    invert_hook flips the logic.
    """
    state = GPIO.input(pin)
    
    if hook_type == "NC":
        # NC: HIGH = on-hook, LOW = off-hook (based on working simple implementation)
        on_hook = (state == GPIO.HIGH)
    else:  # NO
        # NO: LOW = on-hook, HIGH = off-hook
        on_hook = (state == GPIO.LOW)
    
    if invert_hook:
        on_hook = not on_hook
    
    return on_hook

def play_wav_interruptible(file_path, pin_hook, hw_mapping, volume, mixer_control, hook_type, invert_hook, abort_check=None):
    """
    Play a WAV file with aplay, checking GPIO during playback.
    Returns True if played to completion, False if interrupted by on-hook or
    by `abort_check` (an optional zero-argument predicate polled alongside the
    hook; used so the playback button can cut long sounds short).
    """
    if not Path(file_path).exists():
        logger.error(f"Missing audio file: {file_path}")
        return False
    
    logger.info(f"Playing: {Path(file_path).name}")
    set_volume(volume, mixer_control)
    
    proc = subprocess.Popen(
        ["aplay", "-q", "-D", hw_mapping, str(file_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    try:
        while proc.poll() is None:
            # Check if handset is on-hook
            if is_on_hook(pin_hook, hook_type, invert_hook):
                logger.info(f"Interrupted {Path(file_path).name} (on-hook)")
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return False
            if abort_check is not None and abort_check():
                logger.info(f"Interrupted {Path(file_path).name} (playback button)")
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return False
            time.sleep(0.05)
    except Exception as e:
        logger.error(f"Playback error: {e}")
        return False
    
    return True

def start_recording(config):
    """Start arecord process for guest recording."""
    global recording_path
    timestamp = datetime.now().isoformat().replace(':','-')
    recordings_path = Path(config['recordings_path'])
    recordings_path.mkdir(exist_ok=True)
    
    out_file = recordings_path / f"{timestamp}.wav"
    recording_path = out_file
    logger.info(f"Recording to: {out_file.name}")
    
    proc = subprocess.Popen([
        "arecord", "-q",
        "-f", config['format'],
        "-t", config['file_type'],
        "-D", config['alsa_hw_mapping'],
        "-r", str(config['sample_rate']),
        "-c", str(config['channels']),
        str(out_file)
    ])
    return proc

def start_recording_greeting(config):
    """Start arecord process for recording greeting message."""
    greeting_path = Path(config['greeting'])
    greeting_path.parent.mkdir(exist_ok=True)
    
    logger.info(f"Recording greeting to: {greeting_path.name}")
    
    proc = subprocess.Popen([
        "arecord", "-q",
        "-f", config['format'],
        "-t", config['file_type'],
        "-D", config['alsa_hw_mapping'],
        "-r", str(config['sample_rate']),
        "-c", str(config['channels']),
        str(greeting_path)
    ])
    return proc

def stop_recording(proc, name="recording"):
    """Stop an arecord process if running."""
    if proc and proc.poll() is None:
        logger.info(f"Stopping {name}")
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

def wav_duration(path):
    """Length of a WAV file in seconds, or 0.0 if it cannot be read."""
    try:
        with wave.open(str(path)) as wav:
            return wav.getnframes() / float(wav.getframerate())
    except Exception:
        return 0.0


def pick_random_recording(config, exclude=None, last_played=None):
    """
    Pick a random earlier message to play back.

    Recordings shorter than `playback_min_duration` are skipped: an accidental
    pickup leaves a file containing just the beep and a moment of silence. The
    message played immediately before is also avoided, so pressing the button
    twice in a row gives two different messages.

    Returns a Path, or None if there is nothing worth playing yet.
    """
    recordings_path = Path(config['recordings_path'])
    min_duration = float(config.get('playback_min_duration', 2.0))

    candidates = [
        f for f in recordings_path.glob("*.wav")
        if f != exclude and wav_duration(f) >= min_duration
    ]
    if not candidates:
        return None
    if len(candidates) > 1 and last_played in candidates:
        candidates.remove(last_played)
    return random.choice(candidates)


def check_shutdown_button(pin_shutdown, hold_time=4.0):
    """
    Check if shutdown button is held LOW for hold_time seconds.
    If so, initiate system shutdown.
    """
    if GPIO.input(pin_shutdown) == GPIO.LOW:
        start = time.time()
        while GPIO.input(pin_shutdown) == GPIO.LOW:
            if time.time() - start >= hold_time:
                logger.warning(f"Shutdown button held for {hold_time}s -> shutting down...")
                stop_recording(recording_proc)
                stop_recording(record_greeting_proc, "greeting recording")
                logger.warning("System shutting down...")
                os.system("sudo shutdown now")
                return True
            time.sleep(0.1)
    return False

def main():
    global recording_proc, recording_start_ts, record_greeting_proc
    global recording_path, last_played_path
    
    # Load configuration
    config_path = Path(__file__).parent / "../config.yaml"
    config = load_config(config_path)
    
    logger.info(f"Loaded configuration from: {config_path}")
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    
    # Hook GPIO (handset)
    GPIO.setup(config['hook_gpio'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Record greeting button (optional)
    has_record_greeting = config.get('record_greeting_gpio', 0) != 0
    if has_record_greeting:
        GPIO.setup(config['record_greeting_gpio'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        prev_record_greeting_state = GPIO.input(config['record_greeting_gpio'])
    
    # Random playback button (optional)
    has_playback = config.get('playback_gpio', 0) != 0
    if has_playback:
        playback_type = config.get('playback_type', 'NC')
        # NC: idle HIGH, pressed LOW (plain switch to GND with a pull-up)
        # NO: idle LOW, pressed HIGH (modules that actively drive the line)
        playback_pressed_level = GPIO.LOW if playback_type == 'NC' else GPIO.HIGH
        GPIO.setup(
            config['playback_gpio'], GPIO.IN,
            pull_up_down=GPIO.PUD_UP if playback_type == 'NC' else GPIO.PUD_DOWN
        )
        prev_playback_state = GPIO.input(config['playback_gpio'])

    # Lets a long playback be cut short by the playback button, not just by
    # the hook. None when the button is disabled; only constructed when
    # has_playback is true, so playback_pressed_level is guaranteed bound.
    playback_pressed = (
        (lambda: GPIO.input(config['playback_gpio']) == playback_pressed_level)
        if has_playback else None
    )

    # Shutdown button (optional)
    has_shutdown = config.get('shutdown_gpio', 0) != 0
    if has_shutdown:
        GPIO.setup(config['shutdown_gpio'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    logger.info("=" * 50)
    logger.info("Rotary Phone Audio Guest Book - Ready")
    logger.info("Lift handset to begin recording a message")
    if has_playback:
        logger.info(
            f"Playback button on GPIO{config['playback_gpio']}: "
            f"press while off-hook to hear a random message"
        )
    logger.info("=" * 50)
    
    # Get hook configuration
    hook_type = config.get('hook_type', 'NC')
    invert_hook = config.get('invert_hook', False)
    hook_bounce_time = config.get('hook_bounce_time', 0.1)  # Default 0.1s
    
    prev_was_on_hook = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
    
    try:
        while True:
            # Check current hook state
            currently_on_hook = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
            
            # Detect state change
            if currently_on_hook != prev_was_on_hook:
                # State changed - verify it's stable for bounce_time before acting
                change_time = time.time()
                stable_state = currently_on_hook
                
                # Wait and verify stability
                while time.time() - change_time < hook_bounce_time:
                    current_check = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
                    if current_check != stable_state:
                        # State bounced back, ignore this change
                        stable_state = current_check
                        change_time = time.time()
                    time.sleep(0.01)  # Check every 10ms during debounce
                
                # After debounce period, verify final state
                final_state = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
                if final_state != prev_was_on_hook:
                    # State change confirmed after debounce
                    currently_on_hook = final_state
                else:
                    # State bounced back to original, ignore
                    currently_on_hook = prev_was_on_hook
            
            # ========== MAIN HANDSET HOOK LOGIC ==========
            
            # OFF-HOOK: User lifted handset
            if prev_was_on_hook and not currently_on_hook:
                logger.info("\n[OFF-HOOK] Handset lifted")
                
                # Greeting start delay
                delay = config.get('greeting_start_delay', 0)
                if delay > 0:
                    logger.info(f"Waiting {delay}s before greeting...")
                    time.sleep(delay)
                    # Check if user hung up during delay
                    if is_on_hook(config['hook_gpio'], hook_type, invert_hook):
                        logger.info("Handset replaced during delay - aborting")
                        prev_was_on_hook = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
                        continue
                
                # Play greeting (interruptible)
                if not play_wav_interruptible(
                    config['greeting'],
                    config['hook_gpio'],
                    config['alsa_hw_mapping'],
                    config['greeting_volume'],
                    config['mixer_control_name'],
                    hook_type,
                    invert_hook,
                    abort_check=playback_pressed
                ):
                    prev_was_on_hook = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
                    continue
                
                # Beep delay
                beep_delay = config.get('beep_start_delay', 0)
                if beep_delay > 0:
                    time.sleep(beep_delay)
                
                # Play beep (interruptible)
                if not play_wav_interruptible(
                    config['beep'],
                    config['hook_gpio'],
                    config['alsa_hw_mapping'],
                    config['beep_volume'],
                    config['mixer_control_name'],
                    hook_type,
                    invert_hook,
                    abort_check=playback_pressed
                ):
                    prev_was_on_hook = is_on_hook(config['hook_gpio'], hook_type, invert_hook)
                    continue
                
                # Start recording if still off-hook
                if not is_on_hook(config['hook_gpio'], hook_type, invert_hook) and recording_proc is None:
                    recording_proc = start_recording(config)
                    recording_start_ts = time.time()
            
            # ON-HOOK: User replaced handset
            if not prev_was_on_hook and currently_on_hook:
                logger.info("[ON-HOOK] Handset replaced")
                if recording_proc:
                    stop_recording(recording_proc)
                    recording_proc = None
                    recording_start_ts = None
                    recording_path = None
            
            # Check max recording duration
            if recording_proc and recording_proc.poll() is None and recording_start_ts:
                elapsed = time.time() - recording_start_ts
                if elapsed >= config['recording_limit']:
                    logger.warning(f"[TIME EXCEEDED] Max recording time {config['recording_limit']}s reached")
                    stop_recording(recording_proc)
                    recording_proc = None
                    recording_start_ts = None
                    recording_path = None
                    
                    # Play time exceeded message (interruptible)
                    play_wav_interruptible(
                        config['time_exceeded'],
                        config['hook_gpio'],
                        config['alsa_hw_mapping'],
                        config['time_exceeded_volume'],
                        config['mixer_control_name'],
                        hook_type,
                        invert_hook,
                        abort_check=playback_pressed
                    )
            
            prev_was_on_hook = currently_on_hook
            
            # ========== RECORD GREETING BUTTON LOGIC ==========
            
            if has_record_greeting:
                record_greeting_state = GPIO.input(config['record_greeting_gpio'])
                
                # Debounce record greeting button
                record_greeting_bounce_time = config.get('record_greeting_bounce_time', 0.1)
                
                # Detect state change
                if record_greeting_state != prev_record_greeting_state:
                    # State changed - verify it's stable for bounce_time
                    change_time = time.time()
                    stable_state = record_greeting_state
                    
                    # Wait and verify stability
                    while time.time() - change_time < record_greeting_bounce_time:
                        current_check = GPIO.input(config['record_greeting_gpio'])
                        if current_check != stable_state:
                            # State bounced back
                            stable_state = current_check
                            change_time = time.time()
                        time.sleep(0.01)
                    
                    # After debounce period, verify final state
                    final_state = GPIO.input(config['record_greeting_gpio'])
                    if final_state != prev_record_greeting_state:
                        # State change confirmed
                        record_greeting_state = final_state
                    else:
                        # State bounced back to original
                        record_greeting_state = prev_record_greeting_state
                
                # Button pressed (HIGH -> LOW for NC)
                if prev_record_greeting_state == GPIO.HIGH and record_greeting_state == GPIO.LOW:
                    logger.info("\n[RECORD GREETING] Button pressed - recording new greeting")
                    
                    # Play beep to indicate recording start
                    play_wav_interruptible(
                        config['beep'],
                        config['record_greeting_gpio'],  # Use record button as interrupt
                        config['alsa_hw_mapping'],
                        config['beep_volume'],
                        config['mixer_control_name'],
                        config.get('record_greeting_type', 'NC'),
                        False  # No invert for record greeting
                    )
                    
                    # Start recording greeting
                    if record_greeting_proc is None:
                        record_greeting_proc = start_recording_greeting(config)
                
                # Button released (LOW -> HIGH for NC)
                if prev_record_greeting_state == GPIO.LOW and record_greeting_state == GPIO.HIGH:
                    logger.info("[RECORD GREETING] Button released - saving greeting")
                    if record_greeting_proc:
                        stop_recording(record_greeting_proc, "greeting recording")
                        record_greeting_proc = None
                
                prev_record_greeting_state = record_greeting_state
            
            # ========== RANDOM PLAYBACK BUTTON LOGIC ==========
            
            if has_playback:
                playback_state = GPIO.input(config['playback_gpio'])
                
                # Debounce playback button
                playback_bounce_time = config.get('playback_bounce_time', 0.1)
                
                # Detect state change
                if playback_state != prev_playback_state:
                    # State changed - verify it's stable for bounce_time
                    change_time = time.time()
                    stable_state = playback_state
                    
                    # Wait and verify stability
                    while time.time() - change_time < playback_bounce_time:
                        current_check = GPIO.input(config['playback_gpio'])
                        if current_check != stable_state:
                            # State bounced back
                            stable_state = current_check
                            change_time = time.time()
                        time.sleep(0.01)
                    
                    # After debounce period, verify final state
                    final_state = GPIO.input(config['playback_gpio'])
                    if final_state != prev_playback_state:
                        # State change confirmed
                        playback_state = final_state
                    else:
                        # State bounced back to original
                        playback_state = prev_playback_state
                
                # Button pressed
                if (prev_playback_state != playback_pressed_level
                        and playback_state == playback_pressed_level):
                    if is_on_hook(config['hook_gpio'], hook_type, invert_hook):
                        # The earpiece is the only output, so there is nobody to play to
                        logger.info("[PLAYBACK] Button pressed while on-hook - ignored")
                    else:
                        logger.info("\n[PLAYBACK] Button pressed - playing a random message")
                        
                        # Stop the recording this pickup started, otherwise the
                        # playback would be recorded into it
                        interrupted = recording_path
                        if recording_proc:
                            stop_recording(recording_proc)
                            recording_proc = None
                            recording_start_ts = None
                        recording_path = None
                        
                        # Deleting is gated on its own, deliberately tight
                        # threshold: playback_min_duration decides what is worth
                        # PLAYING and may be raised freely; the delete window
                        # must not widen with it. A genuine stub is just the
                        # beep and a moment of silence, well under a second.
                        stub_max = float(config.get('playback_stub_max_duration', 1.0))
                        if (config.get('playback_discard_stub', True)
                                and interrupted is not None and interrupted.exists()
                                and wav_duration(interrupted) < stub_max):
                            try:
                                interrupted.unlink()
                                logger.info(f"[PLAYBACK] Discarded {interrupted.name} "
                                            f"(nothing but the beep was recorded)")
                            except OSError as e:
                                logger.warning(f"[PLAYBACK] Could not discard stub: {e}")
                        
                        choice = pick_random_recording(
                            config, exclude=interrupted, last_played=last_played_path
                        )
                        if choice is None:
                            logger.info("[PLAYBACK] No recordings long enough to play yet")
                        else:
                            logger.info(f"[PLAYBACK] Playing {choice.name}")
                            # Deliberately no abort_check here: a guest still
                            # holding the button when the message starts would
                            # abort it instantly.
                            play_wav_interruptible(
                                str(choice),
                                config['hook_gpio'],
                                config['alsa_hw_mapping'],
                                config.get('playback_volume', 1.0),
                                config['mixer_control_name'],
                                hook_type,
                                invert_hook
                            )
                            last_played_path = choice

                        # Recoverable ending, played or not: beep and record
                        # again. An accidental press no longer leaves a dead
                        # phone until hang-up, and an empty playlist still
                        # gives the guest audible feedback instead of silence.
                        if not is_on_hook(config['hook_gpio'], hook_type, invert_hook):
                            if play_wav_interruptible(
                                config['beep'],
                                config['hook_gpio'],
                                config['alsa_hw_mapping'],
                                config['beep_volume'],
                                config['mixer_control_name'],
                                hook_type,
                                invert_hook
                            ) and recording_proc is None:
                                recording_proc = start_recording(config)
                                recording_start_ts = time.time()
                                logger.info("[PLAYBACK] Recording a new message - press again for another playback")
                
                prev_playback_state = playback_state
            
            # ========== SHUTDOWN BUTTON CHECK ==========
            
            if has_shutdown:
                if check_shutdown_button(
                    config['shutdown_gpio'],
                    hold_time=config.get('shutdown_button_hold_time', 4.0)
                ):
                    break  # Shutting down
            
            # Main loop delay
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        logger.info("\n\nExiting...")
    finally:
        stop_recording(recording_proc)
        stop_recording(record_greeting_proc, "greeting recording")
        GPIO.cleanup()
        logger.info("Cleanup complete. Goodbye!")

if __name__ == "__main__":
    main()
