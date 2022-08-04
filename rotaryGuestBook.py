#! /usr/bin/env python3

import os
import pyaudio
import time
import wave
from datetime import datetime
from gpiozero import Button
from multiprocessing import Process
from signal import pause
from pydub.scipy_effects import band_pass_filter
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
from pydub import AudioSegment
from pydub.playback import play

hook = Button(17)
rotaryDial = Button(18, hold_time=0.25, hold_repeat=True)
count = 0
dialed = []
reset_flag = False

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
        while len(data):
            self.stream.write(data)
            data = self.wf.readframes(self.chunk)


    def stop(self):
        # stop the stream, close it, and terminate the pyaudio instantiation
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()

    def close(self, outputFile):
        # save the audio frames as .wav file
        with wave.open(outputFile, "wb") as wavefile:
            wavefile.setnchannels(self.chans)
            wavefile.setsampwidth(self.audio.get_sample_size(self.format))
            wavefile.setframerate(self.samp_rate)
            wavefile.writeframes(b"".join(self.frames))

    
    def postProcess(self, outputFile):
        source = AudioSegment.from_file(outputFile + ".wav", format="wav")

        print("Filtering...")
        filtered = band_pass_filter(source, 200, 15000)
        print("Normalizing...")
        normalized = normalize(filtered)
        # print("Compress Dynamic Range")
        # compressed = compress_dynamic_range(normalized)

        print("Exporting normalized")
        normalized.export(outputFile + "normalized.mp3", format="mp3")
        # print("Exporting compressed")
        # compressed.export(outputFile + "compressed.mp3", format="mp3")
        print("Finished...")
        # Effects.apply_gain_stereo(audio_segment, 3, 3)


def offHook():
    audioInterface = AudioInterface()
    print("Phone off hook, ready to begin!")
    # wait a second for user to place phone to ear
    time.sleep(1)
    # playback voice message through speaker
    print("Playing voicemail message...")
    # audioInterface.play(os.getcwd() + "/sounds/voicemail.wav")
    play(AudioSegment.from_wav(os.getcwd() + "/sounds/voicemail.wav"))
    # start recording beep
    print("Playing beep...")
    # audioInterface.play(os.getcwd() + "/sounds/beep.wav")
    play(AudioSegment.from_file(os.getcwd() + "/sounds/beep.wav", format="wav") - 16)
    # now, while phone is not off the hook, record audio from the microphone
    print("recording")
    audioInterface.record()
    audioInterface.stop()
    outputFile = os.getcwd() + "/recordings/" + f"{datetime.now().isoformat()}"
    audioInterface.close(outputFile + ".wav")
    print("finished recording")
    print("spawn postProcessing thread")
    Process(target=audioInterface.postProcess, args=(outputFile,)).start()


def onHook():
    print("Phone on hook. Sleeping...")


def dialing():
    global count, reset_flag
    count+=1
    print(f"dialing, increment count: {count}")
    reset_flag = False

def reset():
    global count, reset_flag
    count = 0
    toggle = False
    print(f"reset count: {count}")
    reset_flag = True


def held():
    if(not reset_flag):
        print("holding")
        print(count)
        global dialed
        if (count == 10):
            dialed.append(0)
        else:
            dialed.append(count)
        print(f"number dialed: {dialed}")
        reset()


def main():
    rotaryDial.when_pressed = dialing
    rotaryDial.when_held = held
    hook.when_pressed = offHook
    hook.when_released = onHook
    pause()


if __name__ == "__main__":
    main()
