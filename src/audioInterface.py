import logging
import os
import signal
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioInterface:
    """
    Interface for handling audio playback and recording.

    This class provides methods to play audio files and manage audio recording processes,
    supporting non-blocking recording to allow application control flow to continue.

    Attributes:
        alsa_hw_mapping (str): ALSA hardware device mapping for audio input/output.
        recording_limit (int): Maximum recording duration in seconds.
        format (str): Audio format for recording and playback.
        file_type (str): File type for recorded audio.
        sample_rate (int): Sampling rate for audio recording.
        channels (int): Number of audio channels for recording.
        recording_process (subprocess.Popen or None): Handle to the current recording process, if any.
    """

    def __init__(
        self,
        alsa_hw_mapping,
        format,
        file_type,
        recording_limit,
        sample_rate=44100,
        channels=1,
        mixer_control_name="Speaker",
    ):
        """
        Initializes the audio interface with specified configuration.

        Args:
            alsa_hw_mapping (str): ALSA hardware device mapping.
            format (str): Audio format (e.g., 'cd' for 16-bit 44100 Hz stereo).
            file_type (str): Type of the file to record (e.g., 'wav').
            recording_limit (int): Maximum duration for recording in seconds.
            sample_rate (int, optional): Sampling rate in Hz. Defaults to 44100.
            channels (int, optional): Number of audio channels. Defaults to 1.
        """
        self.alsa_hw_mapping = alsa_hw_mapping
        self.recording_limit = recording_limit
        self.format = format
        self.file_type = file_type
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording_process = None
        self.playback_process = None
        self.mixer_control_name = mixer_control_name
        self.continue_playback = True

    def set_volume(self, volume_percentage):
        """
        Sets the system volume.

        Args:
            volume_percentage (float): Volume level as a percentage (0-1).
        """
        volume = max(
            0, min(int(volume_percentage * 100), 100)
        )  # Ensure volume is between 0 and 100
        try:
            subprocess.run(
                ["amixer", "set", self.mixer_control_name, f"{volume}%"], check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Error setting volume: {e}")

    def play_audio(self, input_file, volume=1, start_delay_sec=0):
        """
        Plays an audio file using `aplay` after setting the volume with `amixer`.
        """
        if not Path(input_file).exists():
            logger.error(f"Audio file {input_file} not found.")
            return

        self.set_volume(volume)

        # If a start delay is needed, generate and play a silence file
        if start_delay_sec > 0:
            silence_file = "/tmp/silence.wav"
            try:
                subprocess.run(
                    [
                        "sox",
                        "-n",
                        "-r",
                        str(self.sample_rate),
                        "-c",
                        str(self.channels),
                        silence_file,
                        "trim",
                        "0",
                        str(start_delay_sec),
                    ],
                    check=True,
                )
                subprocess.run(
                    ["aplay", "-D", str(self.alsa_hw_mapping), silence_file], check=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Error generating or playing silence file: {e}")

        # Play the actual audio file
        try:
            self.playback_process = subprocess.Popen(
                ["aplay", "-D", str(self.alsa_hw_mapping), str(input_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            while self.playback_process and self.playback_process.poll() is None:
                if not self.continue_playback:
                    self.playback_process.terminate()
                    self.playback_process.wait()
                    break
                time.sleep(0.1)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error playing {input_file}: {e}")
        finally:
            if self.playback_process:
                self.playback_process = None

    def stop_playback(self):
        """
        Stops the ongoing audio playback process.
        """
        if self.playback_process:
            self.playback_process.terminate()
            try:
                self.playback_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if not exited
                self.playback_process.kill()
            logger.info("Playback stopped.")
            self.playback_process = None

    def start_recording(self, output_file):
        """
        Starts recording audio to the specified file in a non-blocking manner.

        Args:
            output_file (str): Path to the output file where the audio will be saved.
        """
        # First, ensure no rogue processes are running
        try:
            subprocess.run(["pkill", "-f", "arecord"], check=False)
        except Exception as e:
            logger.error(f"Error killing stray arecord processes: {e}")

        # Check if output directory exists and is writable
        try:
            output_dir = os.path.dirname(output_file)
            if not os.path.exists(output_dir):
                logger.warning(f"Output directory does not exist: {output_dir}, attempting to create")
                os.makedirs(output_dir, exist_ok=True)

            if not os.access(output_dir, os.W_OK):
                logger.error(f"Output directory is not writable: {output_dir}")
                return
        except OSError as e:
            logger.error(f"Failed to ensure output directory is ready: {e}")
            return

        command = [
            "arecord",
            "-D",
            str(self.alsa_hw_mapping),
            "-f",
            str(self.format),
            "-t",
            str(self.file_type).strip(),
            "-d",
            str(self.recording_limit),
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
            output_file,
        ]

        # Create a new process group for clean termination
        def preexec():
            os.setpgrp()  # Create a new process group
            signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore SIGINT

        try:
            self.recording_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=preexec,
            )
            logger.info(f"Started recording process with PID: {self.recording_process.pid}")
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to start recording process: {e}")

    def stop_recording(self):
        """
        Stops the ongoing audio recording process.
        """
        if self.recording_process:
            logger.info(f"Stopping recording process with PID: {self.recording_process.pid}")
            try:
                # Send SIGINT to the recording process to stop it gracefully
                # This will allow arecord to finalize the file properly
                os.killpg(os.getpgid(self.recording_process.pid), signal.SIGINT)

                # Get the output file name from the command that started the recording
                command = self.recording_process.args
                output_file = command[-1] if len(command) > 0 else "unknown"

                # Give it some time to finalize the recording file
                try:
                    self.recording_process.wait(timeout=2)
                    logger.info("Recording process terminated gracefully")
                    # Check if the file was actually created
                    try:
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            logger.info(f"Recording saved successfully: {output_file} ({os.path.getsize(output_file)} bytes)")
                        else:
                            logger.warning(f"Recording file not found or empty: {output_file}")
                    except OSError as e:
                        logger.error(f"Error checking recording file: {e}")
                except subprocess.TimeoutExpired:
                    logger.info("Recording process is taking time to finalize, waiting...")
                    # Try waiting a bit longer before force killing
                    time.sleep(1)

                    # Check if it's still running
                    if self.recording_process.poll() is None:
                        logger.info("Recording process still running, using SIGTERM")
                        os.killpg(os.getpgid(self.recording_process.pid), signal.SIGTERM)
                        time.sleep(0.5)  # Give it a moment to respond to SIGTERM

                        # Only use SIGKILL as a last resort
                        if self.recording_process.poll() is None:
                            logger.info("Recording process not responding to SIGTERM, using SIGKILL")
                            os.killpg(os.getpgid(self.recording_process.pid), signal.SIGKILL)

                    self.recording_process.wait(timeout=1)

                    # Check again if the file was created after forced termination
                    try:
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            logger.info(f"Recording saved successfully after forced termination: {output_file} ({os.path.getsize(output_file)} bytes)")
                        else:
                            logger.warning(f"Recording file not found or empty after forced termination: {output_file}")
                    except OSError as e:
                        logger.error(f"Error checking recording file after forced termination: {e}")

            except (ProcessLookupError, subprocess.SubprocessError) as e:
                logger.warning(f"Error while terminating recording process: {e}")

            # Final cleanup - ensure all arecord processes are gone
            try:
                # Using pkill with SIGINT first
                result = subprocess.run(["pkill", "-INT", "-f", "arecord"],
                                        check=False,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

                # Short delay to let the processes finalize files
                time.sleep(0.5)

                # Then use regular pkill as a last resort
                result = subprocess.run(["pkill", "-f", "arecord"],
                                    check=False,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

                if result.returncode == 0:
                    logger.info("Additional arecord processes terminated")
            except Exception as e:
                logger.error(f"Error during final cleanup: {e}")

            # Reset process tracking
            self.recording_process = None
            logger.info("Recording stopped and process tracking reset")
        else:
            # No active recording process known, but check for strays
            logger.info("No active recording process to stop, checking for strays")
            try:
                # Use SIGINT first for stray processes too
                subprocess.run(["pkill", "-INT", "-f", "arecord"],
                            check=False,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
                time.sleep(0.5)  # Give them time to finalize

                result = subprocess.run(["pkill", "-f", "arecord"],
                                    check=False,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

                if result.returncode == 0:
                    logger.info("Found and terminated stray arecord processes")
            except Exception as e:
                logger.error(f"Error during stray process cleanup: {e}")