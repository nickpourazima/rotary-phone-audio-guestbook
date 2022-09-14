#! /usr/bin/env python3

import os
import yaml
import pyaudio
import wave
from datetime import datetime
from gpiozero import Button
from multiprocessing import Process
from signal import pause
from pydub.scipy_effects import band_pass_filter
from pydub.effects import normalize
from pydub import AudioSegment
from pydub.playback import play

with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

hook = Button(config["hook_gpio"])
# rotaryDial = Button(pin=config['rotary_gpio'], hold_time=config['rotary_hold_time'], hold_repeat=config['rotary_hold_repeat'])

"""
TODO: These globals are a temp solution for the rotary dialer, would love to not
depend on globals for this logic.
"""
# count = 0
# dialed = []
# reset_flag = False


class AudioInterface:
    def __init__(self) -> None:
        self.audio = pyaudio.PyAudio()
        self.samp_rate = config["sample_rate"]
        self.chunk = config["buffer_size"]
        self.chans = config["channels"]
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
            # TODO: either pass hook as object into class, or figure out another cleaner solution
            while hook.is_pressed:
                data = self.stream.read(self.chunk, exception_on_overflow=True)
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
        # stop the stream
        self.stream.stop_stream()
        # close it
        self.stream.close()
        # terminate the pyaudio instantiation
        self.audio.terminate()

    def close(self, outputFile):
        # save the audio frames as .wav file
        with wave.open(outputFile, "wb") as wavefile:
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

        # print("Compress Dynamic Range")
        # compressed = compress_dynamic_range(normalized)

        print("Exporting normalized")
        normalized.export(outputFile + "normalized.wav", format="wav")

        # print("Exporting compressed")
        # compressed.export(outputFile + "compressed.mp3", format="mp3")

        print("Finished...")


def offHook():
    print("Phone off hook, ready to begin!")
    # if dialed and dialed[0] == 0:
    audioInterface = AudioInterface()

    # playback voice message through speaker
    print("Playing voicemail message...")
    play(
        AudioSegment.from_wav(
            os.path.dirname(os.path.abspath("rotaryGuestBook.py"))
            + "/sounds/voicemail.wav"
        )
        - config["playback_reduction"]
    )

    # start recording beep
    print("Playing beep...")
    play(
        AudioSegment.from_wav(
            os.path.dirname(os.path.abspath("rotaryGuestBook.py")) + "/sounds/beep.wav"
        )
        - config["beep_reduction"]
    )

    # now, while phone is not off the hook, record audio from the microphone
    print("recording")
    audioInterface.record()
    audioInterface.stop()
    outputFile = (
        os.path.dirname(os.path.abspath("rotaryGuestBook.py"))
        + "/recordings/"
        + f"{datetime.now().isoformat()}"
    )
    audioInterface.close(outputFile + ".wav")
    print("finished recording")

    """
    post processing
    """
    # print("spawn postProcessing thread")
    # Process(target=audioInterface.postProcess, args=(outputFil e,)).start()

    """
    rotary dialer special messages
    """
    # if dialed[0:3] == [9,2,7]:
    #     # play special vm
    #     play(AudioSegment.from_wav(os.path.dirname(os.path.abspath("rotaryGuestBook.py")) + "/sounds/927.wav") - config['playback_reduction'])

    # elif dialed[0:4] == [5,4,5,3]:
    #     # play special vm
    #     play(AudioSegment.from_wav(os.path.dirname(os.path.abspath("rotaryGuestBook.py")) + "/sounds/beep.wav") - config['beep_reduction'])


def onHook():
    print("Phone on hook. Sleeping...")
    # print("Resetting dial list")
    # global dialed
    # dialed = []
    # reset_pulse_counter()


# def dialing():
#     if hook.is_pressed:
#         global count, reset_flag
#         count+=1
#         print(f"dialing, increment count: {count}")
#         reset_flag = False

# def reset_pulse_counter():
#     global count, reset_flag
#     count = 0
#     print(f"reset count: {count}")
#     reset_flag = True


# def held():
#     if not reset_flag:
#         print("holding")
#         print(count)
#         global dialed
#         if (count == 10):
#             dialed.append(0)
#         else:
#             dialed.append(count)
#         print(f"number dialed: {dialed}")
#         offHook()
#         reset_pulse_counter()


def main():
    # rotaryDial.when_pressed = dialing
    # rotaryDial.when_held = held

    hook.when_pressed = offHook
    hook.when_released = onHook
    pause()


if __name__ == "__main__":
    main()
