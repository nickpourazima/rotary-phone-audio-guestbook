#!/usr/bin/env python3
import logging
import RPi.GPIO as GPIO
import subprocess
import time
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

def play_wav_interruptible(file_path, pin_hook, hw_mapping, volume, mixer_control, hook_type, invert_hook):
    """
    Play a WAV file with aplay, checking GPIO during playback.
    Returns True if played to completion, False if interrupted by on-hook.
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
            time.sleep(0.05)
    except Exception as e:
        logger.error(f"Playback error: {e}")
        return False
    
    return True

def start_recording(config):
    """Start arecord process for guest recording."""
    timestamp = datetime.now().isoformat()
    recordings_path = Path(config['recordings_path'])
    recordings_path.mkdir(exist_ok=True)
    
    out_file = recordings_path / f"{timestamp}.wav"
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
    
    # Shutdown button (optional)
    has_shutdown = config.get('shutdown_gpio', 0) != 0
    if has_shutdown:
        GPIO.setup(config['shutdown_gpio'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    logger.info("=" * 50)
    logger.info("Rotary Phone Audio Guest Book - Ready")
    logger.info("Lift handset to begin recording a message")
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
                    invert_hook
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
                    invert_hook
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
            
            # Check max recording duration
            if recording_proc and recording_proc.poll() is None and recording_start_ts:
                elapsed = time.time() - recording_start_ts
                if elapsed >= config['recording_limit']:
                    logger.warning(f"[TIME EXCEEDED] Max recording time {config['recording_limit']}s reached")
                    stop_recording(recording_proc)
                    recording_proc = None
                    recording_start_ts = None
                    
                    # Play time exceeded message (interruptible)
                    play_wav_interruptible(
                        config['time_exceeded'],
                        config['hook_gpio'],
                        config['alsa_hw_mapping'],
                        config['time_exceeded_volume'],
                        config['mixer_control_name'],
                        hook_type,
                        invert_hook
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
