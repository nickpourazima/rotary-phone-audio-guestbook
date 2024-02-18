import logging
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from pydub.scipy_effects import band_pass_filter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioProcessing:

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
