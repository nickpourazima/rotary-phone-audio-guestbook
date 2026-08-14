"""Off-device behaviour tests for the random playback button.

No Pi, no GPIO, no audio hardware: see ``test/agb_harness.py`` for how
``src/audioGuestBook.py`` is made importable and drivable on a laptop.

    python -m unittest discover -s test
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agb_harness import FakeGPIO, aplay_calls, run_loop, write_wav  # noqa: E402

HOOK, PLAYBACK = 22, 27

# hook_type NC -> HIGH = on-hook, LOW = off-hook
ON_HOOK, OFF_HOOK = FakeGPIO.HIGH, FakeGPIO.LOW
# playback_type NO -> idle LOW, pressed HIGH
IDLE, PRESSED = FakeGPIO.LOW, FakeGPIO.HIGH


def make_config(tmp, **overrides):
    """A config mirroring config.example.yaml, with the button enabled."""
    config = {
        "alsa_hw_mapping": "default", "mixer_control_name": "Speaker",
        "format": "cd", "file_type": "wav", "channels": 2, "sample_rate": 44100,
        "hook_gpio": HOOK, "hook_type": "NC", "invert_hook": False,
        "hook_bounce_time": 0.1, "recording_limit": 300,
        "record_greeting_gpio": 0, "shutdown_gpio": 0,
        "beep": f"{tmp}/sounds/beep.wav", "beep_volume": 1.0,
        "beep_start_delay": 0.0,
        "greeting": f"{tmp}/sounds/greeting.wav", "greeting_volume": 1.0,
        "greeting_start_delay": 1.5,
        "time_exceeded": f"{tmp}/sounds/time_exceeded.wav",
        "time_exceeded_volume": 1.0,
        "recordings_path": f"{tmp}/recordings",
        "playback_gpio": PLAYBACK, "playback_type": "NO",
        "playback_bounce_time": 0.1, "playback_volume": 1.0,
        "playback_min_duration": 2.0,
        "playback_discard_stub": True, "playback_stub_max_duration": 1.0,
    }
    config.update(overrides)
    return config


class PlaybackTestBase(unittest.TestCase):
    """Isolated recordings dir + the three device sounds, per test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.recordings = Path(self.tmp) / "recordings"
        self.recordings.mkdir()
        for name in ("beep", "greeting", "time_exceeded"):
            write_wav(Path(self.tmp) / "sounds" / f"{name}.wav", 1.0)
        self.durations = {
            "greeting.wav": 4.0, "beep.wav": 0.5, "time_exceeded.wav": 2.0,
        }

    def seed_recording(self, name, seconds):
        """Put an existing guest message in the recordings dir."""
        path = self.recordings / name
        write_wav(path, seconds)
        self.durations[name] = seconds
        return path

    def recording_names(self):
        return sorted(p.name for p in self.recordings.glob("*.wav"))

    def run_phone(self, timeline, deadline=40.0, **config_overrides):
        return run_loop(
            make_config(self.tmp, **config_overrides),
            timeline=timeline,
            wav_durations=self.durations,
            deadline=deadline,
        )


class NormalPickupTest(PlaybackTestBase):
    """The button must not disturb the ordinary record-a-message flow."""

    def test_lift_plays_greeting_then_beep_then_records(self):
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK)], deadline=20.0
        )
        self.assertEqual(aplay_calls(subproc)[:2], ["greeting.wav", "beep.wav"])
        self.assertEqual(len(self.recording_names()), 1)

    def test_disabled_by_default_ignores_the_pin(self):
        self.seed_recording("old.wav", 5.0)
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (7.5, PLAYBACK, PRESSED)],
            deadline=30.0, playback_gpio=0,
        )
        self.assertNotIn("old.wav", aplay_calls(subproc))


class ButtonPressTest(PlaybackTestBase):
    def test_press_while_on_hook_is_ignored(self):
        old = self.seed_recording("old.wav", 5.0)
        _, _, _, subproc = self.run_phone(
            [(1.0, PLAYBACK, PRESSED), (2.0, PLAYBACK, IDLE)], deadline=20.0
        )
        self.assertEqual(aplay_calls(subproc), [],
                         "nothing should play into a hung-up earpiece")
        self.assertTrue(old.exists())

    def test_press_while_recording_plays_an_older_message(self):
        self.seed_recording("old.wav", 5.0)
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (7.5, PLAYBACK, PRESSED),
             (8.0, PLAYBACK, IDLE)]
        )
        self.assertIn("old.wav", aplay_calls(subproc))

    def test_stub_is_discarded_but_real_messages_are_kept(self):
        old = self.seed_recording("old.wav", 5.0)
        self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (7.5, PLAYBACK, PRESSED),
             (8.0, PLAYBACK, IDLE)]
        )
        self.assertTrue(old.exists(), "an existing message must never be deleted")
        leftovers = [n for n in self.recording_names() if n != "old.wav"]
        self.assertEqual(len(leftovers), 1,
                         f"stub should be gone, leaving only the resumed "
                         f"recording; found {leftovers}")

    def test_recordings_below_min_duration_are_never_picked(self):
        self.seed_recording("tooshort.wav", 0.5)
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (7.5, PLAYBACK, PRESSED),
             (8.0, PLAYBACK, IDLE)]
        )
        self.assertNotIn("tooshort.wav", aplay_calls(subproc))

    def test_ending_is_recoverable_beep_then_record_again(self):
        self.seed_recording("old.wav", 5.0)
        agb, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (7.5, PLAYBACK, PRESSED),
             (8.0, PLAYBACK, IDLE)]
        )
        self.assertEqual(aplay_calls(subproc)[-1], "beep.wav",
                         "a beep must invite the guest to keep talking")
        self.assertIsNotNone(agb.recording_proc, "recording should resume")

    def test_press_during_greeting_cuts_it_short_and_plays(self):
        self.seed_recording("old.wav", 5.0)
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (3.0, PLAYBACK, PRESSED),
             (3.5, PLAYBACK, IDLE)]
        )
        self.assertIn("old.wav", aplay_calls(subproc),
                      "abort_check should let the button interrupt the greeting")


class HeldAcrossPickupTest(PlaybackTestBase):
    """Regression test for the press-edge re-arm.

    A button already held while the phone is ON-HOOK has its press edge
    consumed and ignored ("nobody to play to"). When the handset is then
    lifted, the greeting aborts immediately via abort_check -- but without
    re-arming prev_playback_state there is no fresh edge, so the playback
    block never fires and the handset goes silent until hang-up.
    """

    def test_button_held_from_before_pickup_still_plays(self):
        self.seed_recording("old.wav", 5.0)
        _, _, _, subproc = self.run_phone(
            [(0.5, PLAYBACK, PRESSED),   # pressed while still on-hook
             (3.0, HOOK, OFF_HOOK),      # lifted, button still held
             (6.0, PLAYBACK, IDLE)]      # released during playback
        )
        self.assertIn("old.wav", aplay_calls(subproc),
                      "a button held since on-hook must still reach playback")


if __name__ == "__main__":
    unittest.main()
