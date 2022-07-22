#! /usr/bin/env python3

import os
import pyaudio
import time
import wave
from datetime import datetime
from gpiozero import Button
from signal import pause

hook = Button(17)

# TODO: rotary encoder: special key codes trigger certain voicemails

class AudioInterface:
    def __init__(self) -> None:
        self.audio = pyaudio.PyAudio()  # create pyaudio instantiation
        self.samp_rate = 44100  # 44.1kHz sampling rate
        self.chunk = 4096  # 2^12 samples for buffer
        self.chans = 1  # 1 channel
        self.format = pyaudio.paInt16  # 16-bit resolution
        self.frames = []  # raw data frames recorded from mic

    def record(self):
        # create pyaudio stream
        dev_index = 1  # device index found by p.get_device_info_by_index(ii)
        self.stream = self.audio.open(
            format=self.format,
            rate=self.samp_rate,
            channels=self.chans,
            input_device_index=dev_index,
            input=True,
            frames_per_buffer=self.chunk,
        )
        # loop through stream and append audio chunks to frame array
        try:
            while hook.is_pressed:
                data = self.stream.read(self.chunk, exception_on_overflow = True)   # Set to False when live
                self.frames.append(data)
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
        while data != b"":
            self.stream.write(data)
            data = self.wf.readframes(self.chunk)

    def stop(self):
        # stop the stream, close it, and terminate the pyaudio instantiation
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()

    def close(self):
        # save the audio frames as .wav file
        with wave.open(os.getcwd() + "/recordings/"
            + f"{datetime.now().isoformat()}.wav", "wb") as wavefile:
            wavefile.setnchannels(self.chans)
            wavefile.setsampwidth(self.audio.get_sample_size(self.format))
            wavefile.setframerate(self.samp_rate)
            wavefile.writeframes(b"".join(self.frames))

def offHook():
    audioInterface = AudioInterface()
    print("Phone off hook, ready to begin!")
    # wait a second for user to place phone to ear
    time.sleep(1)
    # playback voice message through speaker
    print("Playing voicemail message...")
    audioInterface.play(os.getcwd() + "/sounds/voicemail.wav")
    # start recording beep
    print("Playing beep...")
    audioInterface.play(os.getcwd() + "/sounds/beep.wav")
    # now, while phone is not off the hook, record audio from the microphone
    print("recording")
    audioInterface.record()
    audioInterface.stop()
    audioInterface.close()
    print("finished recording")


def onHook():
    print("Phone on hook. Sleeping...")


def main():
    hook.when_pressed = offHook
    hook.when_released = onHook
    pause()


if __name__ == "__main__":
    main()
