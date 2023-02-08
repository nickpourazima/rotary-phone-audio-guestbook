#! /usr/bin/env python3

import pyaudio
import time
import wave
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
from pydub.scipy_effects import band_pass_filter



class AudioInterface:
    def __init__(self, config, hook) -> None:
        self.audio = pyaudio.PyAudio()
        self.chunk = config["buffer_size"]
        self.chans = config["channels"]
        self.format = pyaudio.paInt16  # 16-bit resolution
        self.frames = []  # raw data frames recorded from mic
        self.hook = hook
        self.samp_rate = config["sample_rate"]
        self.recording_limit = config["recording_limit"]
        self.dev_index = config["alsa_hw_mapping"] # device index found by p.get_device_info_by_index(ii)

    def record(self):
        # create pyaudio stream
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
            print("Done recording")
        except Exception as e:
            print(str(e))

    def play(self, file):
        self.wf = wave.open(file, "rb")
        self.stream = self.audio.open(
            format=self.audio.get_format_from_width(self.wf.getsampwidth()),
            channels=self.wf.getnchannels(),
            rate=self.wf.getframerate(),
            output=True,
        )
        """ Play entire file """
        data = self.wf.readframes(self.chunk)
        while len(data):
            self.stream.write(data)
            data = self.wf.readframes(self.chunk)

    def stop(self):
        # stop the stream
        self.stream.stop_stream()
        # close it
        self.stream.close()
        # terminate the pyaudio instantiation
        self.audio.terminate()

    def close(self, output_file):
        # save the audio frames as .wav file
        with wave.open(output_file, "wb") as wavefile:
            wavefile.setnchannels(self.chans)
            wavefile.setsampwidth(self.audio.get_sample_size(self.format))
            wavefile.setframerate(self.samp_rate)
            wavefile.writeframes(b"".join(self.frames))

    def postProcess(self, outputFile):
        """
        TODO: Evaluate whether this is worthwhile...
        """
        source = AudioSegment.from_wav(outputFile + ".wav")

        print("Filtering...")
        filtered = band_pass_filter(source, 300, 10000)
        print("Normalizing...")
        normalized = normalize(filtered)

        print("Compress Dynamic Range")
        compressed = compress_dynamic_range(normalized)

        print("Exporting normalized")
        normalized.export(outputFile + "normalized.wav", format="wav")

        print("Exporting compressed")
        compressed.export(outputFile + "compressed.mp3", format="mp3")

        print("Finished...")