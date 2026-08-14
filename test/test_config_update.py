"""Off-device tests for ``webserver.server.update_config()``.

Form values always arrive as strings; they have to land in config.yaml as real
types, because ``src/audioGuestBook.py`` does arithmetic and comparisons on
them (``int(volume * 100)``, ``elapsed >= recording_limit``). A field that
degrades to a string takes the guestbook service down on the next restart.

Pure Python -- no Pi, no GPIO:

    python -m unittest discover -s test
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from ruamel.yaml import YAML

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Build a throwaway config from the installer's own template (the same trick
# test_server.py uses) and point the real app at it before importing.
_yaml = YAML()
_tmp = tempfile.mkdtemp()
_config_file = Path(_tmp) / "config.yaml"
_config_file.write_text(
    (PROJECT_ROOT / "config.example.yaml").read_text().replace("__INSTALL_DIR__", _tmp)
)
(Path(_tmp) / "recordings").mkdir(exist_ok=True)
os.environ["AGB_CONFIG_PATH"] = str(_config_file)
os.environ["AGB_UPLOAD_FOLDER"] = str(Path(_tmp) / "uploads")

import webserver.server as server  # noqa: E402


def tearDownModule():
    shutil.rmtree(_tmp, ignore_errors=True)


class UpdateConfigTypeTest(unittest.TestCase):
    """Types already present in config.yaml must survive a round trip.

    ruamel's round-trip loader returns ScalarFloat/ScalarInt subclasses to
    preserve formatting, so these only pass if update_config() tests with
    isinstance rather than an identity check on type(...).
    """

    def setUp(self):
        server.config = _yaml.load(_config_file.read_text())

    def test_existing_float_stays_float(self):
        server.update_config({"greeting_volume": "0.8"})
        self.assertIsInstance(server.config["greeting_volume"], float)
        self.assertNotIsInstance(server.config["greeting_volume"], str)
        self.assertAlmostEqual(server.config["greeting_volume"], 0.8)

    def test_existing_int_stays_int(self):
        server.update_config({"recording_limit": "120"})
        self.assertIsInstance(server.config["recording_limit"], int)
        self.assertEqual(server.config["recording_limit"], 120)

    def test_existing_bool_stays_bool(self):
        server.update_config({"invert_hook": "true"})
        self.assertIs(server.config["invert_hook"], True)

    def test_every_example_float_survives(self):
        """Guard the whole template, not just the one field above."""
        floats = [k for k, v in server.config.items()
                  if isinstance(v, float) and not isinstance(v, bool)]
        self.assertTrue(floats, "expected float fields in config.example.yaml")
        for key in floats:
            with self.subTest(key=key):
                server.update_config({key: "0.5"})
                self.assertIsInstance(server.config[key], float)


class UpgradedInstallTest(unittest.TestCase):
    """Keys missing from an older config.yaml must still be settable.

    config.yaml is not tracked and install.sh never merges new keys into an
    existing one, so on an upgraded device these arrive absent. Without the
    NEW_FIELD_TYPES fallback the web UI drops them and the feature can never
    be enabled.
    """

    def setUp(self):
        server.config = _yaml.load(_config_file.read_text())

    def test_new_int_field(self):
        del server.config["playback_gpio"]
        server.update_config({"playback_gpio": "27"})
        self.assertEqual(server.config["playback_gpio"], 27)
        self.assertIsInstance(server.config["playback_gpio"], int)

    def test_new_float_field(self):
        del server.config["playback_min_duration"]
        server.update_config({"playback_min_duration": "3.5"})
        self.assertEqual(server.config["playback_min_duration"], 3.5)
        self.assertIsInstance(server.config["playback_min_duration"], float)

    def test_new_bool_field(self):
        del server.config["playback_discard_stub"]
        server.update_config({"playback_discard_stub": "false"})
        self.assertIs(server.config["playback_discard_stub"], False)

    def test_new_str_field(self):
        del server.config["playback_type"]
        server.update_config({"playback_type": "NO"})
        self.assertEqual(server.config["playback_type"], "NO")

    def test_every_declared_new_field_is_settable(self):
        for key in server.NEW_FIELD_TYPES:
            with self.subTest(key=key):
                server.config.pop(key, None)
                server.update_config({key: "1"})
                self.assertIn(key, server.config,
                              f"{key} declared in NEW_FIELD_TYPES but dropped")

    def test_unknown_key_is_still_dropped(self):
        server.update_config({"totally_bogus": "x"})
        self.assertNotIn("totally_bogus", server.config)


if __name__ == "__main__":
    unittest.main()
