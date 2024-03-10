import logging
import signal
import subprocess
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

    def play_audio(self, filename):
        """
        Plays an audio file using the ALSA `aplay` utility.

        Args:
            filename (str): Name of the audio file to play, located in the `sounds` directory.
        """
        sound_path = Path(__file__).parent / "../sounds" / filename
        if not sound_path.exists():
            logger.error(f"Audio file {filename} not found at {sound_path}.")
            return

        try:
            subprocess.run(["aplay", str(sound_path)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error playing {filename}: {e}")

    def start_recording(self, output_file):
        """
        Starts recording audio to the specified file in a non-blocking manner.

        Args:
            output_file (str): Path to the output file where the audio will be saved.
        """
        command = [
            "arecord",
            "-D",
            str(self.alsa_hw_mapping),
            "-f",
            str(self.format),
            "-t",
            str(self.file_type),
            "-d",
            str(self.recording_limit),
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
            output_file,
        ]
        self.recording_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
        )

    def stop_recording(self):
        """
        Stops the ongoing audio recording process.
        """
        if self.recording_process:
            self.recording_process.terminate()
            try:
                self.recording_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if not exited
                self.recording_process.kill()
            logger.info("Recording stopped.")
