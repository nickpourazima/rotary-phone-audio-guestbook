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
    def __init__(
        self,
        hook,
        buffer_size,
        channels,
        format,
        sample_rate,
        recording_limit,
        dev_index,
    ) -> None:
        self.chunk = buffer_size
        self.chans = channels
        self.format = format
        self.frames: List[bytes] = []
        self.hook = hook
        self.samp_rate = sample_rate
        self.recording_limit = recording_limit
        self.dev_index = dev_index

        self.audio = None
        self.stream = None

    def init_audio(self):
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def record(self):
        self.init_audio()
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
            while self.hook.is_pressed:
                if time.time() - start < self.recording_limit:
                    data = self.stream.read(self.chunk, exception_on_overflow=True)
                    self.frames.append(data)
                else:
                    break
        except KeyboardInterrupt:
            logger.info("Done recording")
        except Exception as e:
            logger.error(str(e))

    def play(self, file):
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

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio:
            self.audio.terminate()

    def close(self, output_file):
        try:
            with wave.open(output_file, "wb") as wavefile:
                wavefile.setnchannels(self.chans)
                wavefile.setsampwidth(self.audio.get_sample_size(self.format))
                wavefile.setframerate(self.samp_rate)
                wavefile.writeframes(b"".join(self.frames))
        except OSError as e:
            logger.error(f"Error writing to file {output_file}. Error: {e}")

    def postProcess(self, outputFile):
        source = AudioSegment.from_wav(outputFile + ".wav")
        filtered = self.filter_audio(source)
        normalized = self.normalize_audio(filtered)
        compressed = self.compress_audio(normalized)

        normalized.export(outputFile + "normalized.wav", format="wav")
        compressed.export(outputFile + "compressed.mp3", format="mp3")

    def filter_audio(self, audio):
        logger.info("Filtering...")
        return band_pass_filter(audio, 300, 10000)

    def normalize_audio(self, audio):
        logger.info("Normalizing...")
        return normalize(audio)

    def compress_audio(self, audio):
        logger.info("Compress Dynamic Range")
        return compress_dynamic_range(audio)
