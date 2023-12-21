#! /usr/bin/env python3

import logging
import time
import wave
from typing import List

import pyaudio
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from pydub.scipy_effects import band_pass_filter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioInterface:
    """
    A class to handle audio recording and playback functionalities.

    :param chunk: The size of each audio chunk to be read or written.
    :type chunk: int
    :param chans: Number of audio channels.
    :type chans: int
    :param format: The format of the audio, e.g., pyaudio.paInt16.
    :type format: int
    :param frames: List to store frame bytes of the recorded audio.
    :type frames: List[bytes]
    :param hook: GPIO Button object to detect on and off-hook events.
    :type hook: Button object
    :param samp_rate: The sample rate of the audio.
    :type samp_rate: int
    :param recording_limit: Maximum recording duration in seconds.
    :type recording_limit: int
    :param dev_index: Index of the audio device to use.
    :type dev_index: int
    :param hook_type: Type of the hook (NC - Normally Closed, NO - Normally Open).
    :type hook_type: str
    :param filter_low_freq: Lower frequency for band-pass filter.
    :type filter_low_freq: int
    :param filter_high_freq: Higher frequency for band-pass filter.
    :type filter_high_freq: int
    :param audio: PyAudio object for audio operations.
    :type audio: PyAudio object
    :param stream: Audio stream for recording or playback.
    :type stream: Audio

    """

    def __init__(
        self,
        hook,
        buffer_size,
        channels,
        format,
        sample_rate,
        recording_limit,
        dev_index,
        hook_type,
        filter_low_freq=300,
        filter_high_freq=10000,
    ) -> None:
        """
        Initializes the audio interface with the specified configuration.

        Args:
            hook: GPIO Button object for hook detection.
            buffer_size (int): Size of each audio buffer chunk.
            channels (int): Number of audio channels.
            format (int): Audio format (e.g., pyaudio.paInt16).
            sample_rate (int): Audio sample rate.
            recording_limit (int): Maximum recording time in seconds.
            dev_index (int): Index of the audio device.
            hook_type (str): Type of the hook (NC or NO).
            filter_low_freq (int): Lower frequency for band-pass filter.
            filter_high_freq (int): Higher frequency for band-pass filter.
        """
        # Audio configuration
        self.chunk = buffer_size
        self.chans = channels
        self.format = format
        self.frames = []
        self.hook = hook
        self.samp_rate = sample_rate
        self.recording_limit = recording_limit
        self.dev_index = dev_index
        self.hook_type = hook_type
        self.filter_low_freq = filter_low_freq
        self.filter_high_freq = filter_high_freq

        # Audio resources
        self.audio = None
        self.stream = None
        logger.info(
            f"Initializing Audio Interface with sample rate: {sample_rate}, format: {format}"
        )

    def init_audio(self):
        """
        Initializes (or reinitializes) the audio resources for recording.
        Closes any existing stream and PyAudio instance before re-creating them.
        """
        # Closing existing stream if open
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Terminating existing PyAudio instance if it exists
        if self.audio is not None:
            self.audio.terminate()

        # Creating new PyAudio instance and resetting frame list
        self.audio = pyaudio.PyAudio()
        self.frames = []
        logger.info("Audio resources initialized.")

    def record(self):
        """
        Records audio until the off-hook condition is false or the recording limit is reached.

        This method initializes the audio stream and reads audio chunks in a loop, appending them to the frame list.
        If the recording time exceeds the set limit, a 'time exceeded' notification is played.
        """
        self.init_audio()
        logger.info("Audio stream initialized for recording.")
        self.stream = self.audio.open(
            format=self.format,
            rate=self.samp_rate,
            channels=self.chans,
            input_device_index=self.dev_index,
            input=True,
            frames_per_buffer=self.chunk,
        )

        # loop through stream and append audio chunks to frame array
        try:
            start = time.time()
            while self.off_hook_condition():
                if time.time() - start < self.recording_limit:
                    data = self.stream.read(self.chunk, exception_on_overflow=True)
                    self.frames.append(data)
                else:
                    # Notify the user that their recording time is up
                    self.play("time_exceeded.wav")
                    break
        except KeyboardInterrupt:
            logger.info("Done recording")
        except Exception as e:
            logger.error(f"Recording error: {e}")

    def off_hook_condition(self):
        """
        Determines the off-hook condition based on the hook type.

        Returns:
            bool: True if the off-hook condition is met, False otherwise.
        """
        return (
            not self.hook.is_pressed if self.hook_type == "NC" else self.hook.is_pressed
        )

    def play(self, file):
        """
        Plays an audio file.

        This method initializes the audio resources and plays the specified audio file.

        Args:
            file (str): The path to the audio file to be played.

        Raises:
            FileNotFoundError: If the specified audio file does not exist.
            wave.Error: If there is an error processing the wave file.
        """
        try:
            self.init_audio()
            with wave.open(file, "rb") as wf:
                self.stream = self.audio.open(
                    format=self.audio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )
                data = wf.readframes(self.chunk)
                while data:
                    self.stream.write(data)
                    data = wf.readframes(self.chunk)
        except FileNotFoundError:
            logger.error(f"File not found: {file}")
        except wave.Error as e:
            logger.error(f"Wave error: {e}")
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

    def stop(self):
        """
        Stops the audio stream and terminates the PyAudio session.

        This method is used to cleanly stop audio playback or recording and release resources.
        """
        if self.stream:
            logger.info("Stopping audio stream.")
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            logger.info("Terminating PyAudio session.")
            self.audio.terminate()

    def close(self, output_file):
        """
        Closes the audio interface and saves the recorded frames to a file.

        Args:
            output_file (str): The path to the output file where the recording will be saved.

        Raises:
            OSError: If there is an error writing the audio data to the file.
        """
        try:
            with wave.open(output_file, "wb") as wavefile:
                wavefile.setnchannels(self.chans)
                wavefile.setsampwidth(self.audio.get_sample_size(self.format))
                wavefile.setframerate(self.samp_rate)
                wavefile.writeframes(b"".join(self.frames))
            logger.info(f"Recording saved to {output_file}")
        except OSError as e:
            logger.error(f"Error writing to file {output_file}. Error: {e}")

    def post_process(self, output_file):
        """
        Applies post-processing to the recorded audio and saves the processed files.

        The post-processing includes filtering, normalization, and dynamic range compression.
        The processed audio is saved in both WAV and MP3 formats.

        Args:
            output_file (str): The base path for the output files.

        Raises:
            Exception: If there is an error during post-processing.
        """
        try:
            source = AudioSegment.from_wav(output_file + ".wav")
            filtered = self.filter_audio(source)
            normalized = self.normalize_audio(filtered)
            compressed = self.compress_audio(normalized)

            normalized.export(output_file + "normalized.wav", format="wav")
            compressed.export(output_file + "compressed.mp3", format="mp3")
            logger.info("Post-processing completed successfully.")
        except Exception as e:
            logger.error(f"Post-processing error: {e}")

    def filter_audio(self, audio):
        """
        Applies a band-pass filter to the given audio.

        Args:
            audio (AudioSegment): The audio segment to be filtered.

        Returns:
            AudioSegment: The filtered audio segment.
        """
        logger.info("Filtering audio.")
        return band_pass_filter(audio, self.filter_low_freq, self.filter_high_freq)

    def normalize_audio(self, audio):
        """
        Normalizes the given audio segment.

        Args:
            audio (AudioSegment): The audio segment to be normalized.

        Returns:
            AudioSegment: The normalized audio segment.
        """
        logger.info("Normalizing audio.")
        return normalize(audio)

    def compress_audio(self, audio):
        """
        Compresses the dynamic range of the given audio segment.

        Args:
            audio (AudioSegment): The audio segment to be compressed.

        Returns:
            AudioSegment: The audio segment with compressed dynamic range.
        """
        logger.info("Compressing dynamic range of audio.")
        return compress_dynamic_range(audio)
