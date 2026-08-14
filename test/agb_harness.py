"""Off-device harness for ``src/audioGuestBook.py``.

The guestbook script does ``import RPi.GPIO`` at import time and its whole
state machine lives in one blocking ``while True``, so it cannot be exercised
on a laptop as-is. This supplies the three things it needs:

* a fake ``RPi.GPIO`` injected into ``sys.modules`` before import,
* a **virtual clock** replacing the module's ``time``, so debounce windows,
  greeting delays and multi-second playbacks resolve instantly and
  deterministically instead of being slept through,
* a fake ``subprocess`` where ``aplay`` runs for a scripted duration and
  ``arecord`` writes a *real* WAV whose length matches the virtual time it
  ran for -- so ``wav_duration``, ``playback_min_duration`` and
  ``playback_stub_max_duration`` are exercised for real, not mocked away.

Pin activity is a timeline of ``(virtual_seconds, pin, level)`` events. The
clock raises :class:`StopLoop` once the deadline passes, which is how
``main()``'s infinite loop is broken.
"""

import sys
import types
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class StopLoop(Exception):
    """Raised by the virtual clock to break main()'s infinite loop."""


# ---------------------------------------------------------------------------
# Fake RPi.GPIO
# ---------------------------------------------------------------------------
class FakeGPIO:
    """Only the surface audioGuestBook.py actually touches."""

    BCM, IN, OUT = "BCM", "IN", "OUT"
    LOW, HIGH = 0, 1
    PUD_UP, PUD_DOWN = "PUD_UP", "PUD_DOWN"

    def __init__(self):
        self.levels = {}
        self.pulls = {}
        self.cleaned = False

    def setmode(self, mode):
        pass

    def setup(self, pin, direction, pull_up_down=None):
        self.pulls[pin] = pull_up_down
        # Idle level follows the pull, as it would on real hardware.
        self.levels.setdefault(
            pin, self.HIGH if pull_up_down == self.PUD_UP else self.LOW
        )

    def input(self, pin):
        return self.levels[pin]

    def cleanup(self):
        self.cleaned = True

    # -- test-side driver
    def set(self, pin, level):
        self.levels[pin] = level


def _install_fakes(gpio):
    rpi = types.ModuleType("RPi")
    rpi.GPIO = gpio
    sys.modules["RPi"] = rpi
    sys.modules["RPi.GPIO"] = gpio
    # audioGuestBook.py imports PyYAML, which is not a declared dependency of
    # this project. It is only used by load_config(), which run_loop replaces.
    sys.modules.setdefault("yaml", types.ModuleType("yaml"))


# ---------------------------------------------------------------------------
# Virtual clock
# ---------------------------------------------------------------------------
class FakeClock:
    """Stands in for the ``time`` module inside audioGuestBook."""

    def __init__(self, gpio, timeline, deadline=120.0):
        self.now = 1000.0
        self.start = self.now
        self.gpio = gpio
        self.timeline = sorted(timeline)  # (seconds_since_start, pin, level)
        self.deadline = deadline

    def time(self):
        return self.now

    def sleep(self, seconds):
        # Always advance, so a sleep(0) cannot spin forever.
        self.now += max(seconds, 0.001)
        elapsed = self.now - self.start
        while self.timeline and self.timeline[0][0] <= elapsed:
            _, pin, level = self.timeline.pop(0)
            self.gpio.set(pin, level)
        if elapsed > self.deadline:
            raise StopLoop()


# ---------------------------------------------------------------------------
# Fake subprocess
# ---------------------------------------------------------------------------
class TimeoutExpired(Exception):
    pass


def write_wav(path, seconds):
    """Write a real (silent) WAV of the given length, matching config.example."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\0" * (int(44100 * max(seconds, 0.0)) * 4))


class FakeProc:
    """A subprocess whose lifetime is measured on the virtual clock."""

    def __init__(self, argv, clock, duration, out_path=None):
        self.argv = argv
        self.clock = clock
        self.t0 = clock.now
        self.duration = duration
        self.out_path = out_path
        self.returncode = None

    def poll(self):
        if self.returncode is None and self.clock.now - self.t0 >= self.duration:
            self._finish()
        return self.returncode

    def terminate(self):
        if self.returncode is None:
            self._finish()

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        self.terminate()
        return self.returncode

    def _finish(self):
        self.returncode = 0
        if self.out_path is not None:
            # arecord flushes a file as long as it actually ran.
            write_wav(self.out_path, self.clock.now - self.t0)


class FakeSubprocess:
    DEVNULL = -3
    TimeoutExpired = TimeoutExpired

    def __init__(self, clock, wav_durations):
        self.clock = clock
        self.wav_durations = wav_durations  # basename -> seconds
        self.calls = []

    def run(self, argv, **kw):  # amixer
        self.calls.append(("run", list(argv)))

    def Popen(self, argv, **kw):
        self.calls.append(("popen", list(argv)))
        if argv[0] == "aplay":
            name = Path(argv[-1]).name
            return FakeProc(argv, self.clock, self.wav_durations.get(name, 1.0))
        if argv[0] == "arecord":
            # Runs until terminated; the WAV is written at that point.
            return FakeProc(argv, self.clock, float("inf"), out_path=argv[-1])
        raise AssertionError(f"unexpected command: {argv[0]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_loop(config, timeline, wav_durations=None, deadline=120.0):
    """Import audioGuestBook against the fakes and run main() over ``timeline``.

    Returns ``(module, gpio, clock, subprocess)`` for assertions.
    """
    gpio = FakeGPIO()
    _install_fakes(gpio)

    sys.modules.pop("audioGuestBook", None)
    src = str(PROJECT_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import audioGuestBook as agb

    clock = FakeClock(gpio, timeline, deadline)
    subproc = FakeSubprocess(clock, wav_durations or {})
    agb.time = clock
    agb.subprocess = subproc
    agb.load_config = lambda _path: config
    agb.recording_proc = None
    agb.recording_start_ts = None
    agb.record_greeting_proc = None
    agb.recording_path = None
    agb.last_played_path = None

    try:
        agb.main()
    except StopLoop:
        pass
    return agb, gpio, clock, subproc


def aplay_calls(subproc):
    """Basenames of every WAV handed to aplay, in order."""
    return [
        Path(argv[-1]).name
        for kind, argv in subproc.calls
        if kind == "popen" and argv[0] == "aplay"
    ]
