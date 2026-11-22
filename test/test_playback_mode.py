"""Off-device tests for the playback mode (phone gifted to the couple).

    python -m unittest discover -s test
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agb_harness import aplay_calls  # noqa: E402
from test_playback_button import (  # noqa: E402
    HOOK, OFF_HOOK, ON_HOOK, PLAYBACK, PRESSED, PlaybackTestBase,
)

A, B, C = "2026-01-01T10-00-00.wav", "2026-01-01T11-00-00.wav", "2026-01-01T12-00-00.wav"


class PlaybackModeTest(PlaybackTestBase):
    def setUp(self):
        super().setUp()
        self.state = Path(self.tmp) / "state.json"
        for name in (A, B, C):
            self.seed_recording(name, 5.0)

    def pickups(self, n, **overrides):
        """Lift and replace the handset n times; return the aplay calls."""
        timeline, t = [], 1.0
        for _ in range(n):
            timeline += [(t, HOOK, OFF_HOOK), (t + 8.0, HOOK, ON_HOOK)]
            t += 12.0
        _, _, _, subproc = self.run_phone(
            timeline, deadline=t + 5.0, phone_mode="playback",
            phone_playback_state_file=str(self.state), **overrides,
        )
        return aplay_calls(subproc)

    def test_plays_a_message_without_greeting_beep_or_recording(self):
        calls = self.pickups(1)
        self.assertEqual(calls, [A])
        self.assertEqual(self.recording_names(), sorted([A, B, C]))

    def test_sequential_goes_in_recorded_order_and_wraps(self):
        self.assertEqual(self.pickups(4), [A, B, C, A])

    def test_position_survives_power_loss(self):
        self.assertEqual(self.pickups(2), [A, B])
        self.assertEqual(json.loads(self.state.read_text())["last_played"], B)
        # "reboot": fresh run, same state file
        self.assertEqual(self.pickups(1), [C])

    def test_random_never_repeats_immediately(self):
        calls = self.pickups(6, phone_playback_order="random")
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(x != y for x, y in zip(calls, calls[1:])))

    def test_corrupt_state_file_starts_from_the_beginning(self):
        self.state.write_text("{not json")
        self.assertEqual(self.pickups(1), [A])

    def test_deleted_last_message_continues_after_its_position(self):
        self.state.write_text(json.dumps({"last_played": B}))
        (self.recordings / B).unlink()
        self.assertEqual(self.pickups(1), [C])

    def test_stubs_are_skipped(self):
        self.seed_recording("2025-12-31T00-00-00.wav", 0.5)
        self.assertEqual(self.pickups(1), [A])

    def test_no_recordings_plays_nothing(self):
        for p in self.recordings.glob("*.wav"):
            p.unlink()
        self.assertEqual(self.pickups(1), [])

    def test_playback_button_is_inert_in_playback_mode(self):
        _, _, _, subproc = self.run_phone(
            [(1.0, HOOK, OFF_HOOK), (3.0, PLAYBACK, PRESSED)], deadline=15.0,
            phone_mode="playback", phone_playback_state_file=str(self.state),
        )
        self.assertEqual(aplay_calls(subproc), [A])
        self.assertEqual(len(self.recording_names()), 3)

    def test_record_mode_is_unchanged(self):
        _, _, _, subproc = self.run_phone([(1.0, HOOK, OFF_HOOK)], deadline=20.0,
                                          phone_mode="record")
        self.assertEqual(aplay_calls(subproc)[:2], ["greeting.wav", "beep.wav"])
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
