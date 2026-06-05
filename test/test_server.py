"""Off-device manual test harness for the Audio Guestbook web UI.

This imports the **real** Flask app from ``webserver/server.py`` rather than
re-implementing its routes, so the UI and all endpoints stay in sync with
production automatically — there is no duplicated route logic to drift.

It only does the bits that make the device app safe and runnable on a laptop:

* Generates a throwaway config from the **same** ``config.example.yaml`` template
  the installer uses (so new config fields appear here for free), pointed at
  isolated ``test/`` directories.
* Points the server at that config + an isolated uploads dir via the
  ``AGB_CONFIG_PATH`` / ``AGB_UPLOAD_FOLDER`` env overrides.
* Stubs out the device-only side effects (``systemctl restart`` on config save,
  and ``reboot`` / ``shutdown``) so the buttons are harmless to click.

Run:

    python test/test_server.py

then browse to http://127.0.0.1:8000

Note: the test config and directories are regenerated on each run (clean slate),
so config edits made through the UI do not persist across restarts.
"""

import logging
import os
import sys
from pathlib import Path
from unittest import mock

from ruamel.yaml import YAML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_server")

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent

# Make `import webserver.server` resolvable when run as `python test/test_server.py`.
sys.path.insert(0, str(PROJECT_ROOT))

# Isolated, disposable test directories (test/**/*.wav is gitignored).
TEST_RECORDINGS_DIR = TEST_DIR / "recordings"
TEST_UPLOADS_DIR = TEST_DIR / "uploads"
TEST_SOUNDS_DIR = TEST_DIR / "sounds"
for _d in (TEST_RECORDINGS_DIR, TEST_UPLOADS_DIR, TEST_SOUNDS_DIR):
    _d.mkdir(exist_ok=True)

# Build the test config from the installer's own template so it never drifts:
# substitute __INSTALL_DIR__ (as install.sh does) and override the recordings
# path to the isolated test dir.
yaml = YAML()
TEMPLATE = PROJECT_ROOT / "config.example.yaml"
TEST_CONFIG = TEST_DIR / "test_config.yaml"

config = yaml.load(TEMPLATE.read_text().replace("__INSTALL_DIR__", str(TEST_DIR)))
config["recordings_path"] = str(TEST_RECORDINGS_DIR)
with TEST_CONFIG.open("w") as f:
    yaml.dump(config, f)

# Point the production app at the test config + uploads dir before importing it.
os.environ["AGB_CONFIG_PATH"] = str(TEST_CONFIG)
os.environ["AGB_UPLOAD_FOLDER"] = str(TEST_UPLOADS_DIR)

# Neuter device-only side effects (this is a dedicated, throwaway process):
#   * edit_config() shells out to `sudo systemctl restart audioGuestBook.service`
#   * reboot() / shutdown() call os.system("sudo reboot/shutdown ...")
mock.patch(
    "webserver.server.subprocess.run",
    side_effect=lambda *a, **k: logger.info("suppressed subprocess.run: %s", a[0] if a else ""),
).start()
mock.patch(
    "webserver.server.os.system",
    side_effect=lambda cmd: logger.info("suppressed os.system: %s", cmd),
).start()

from webserver.server import app  # noqa: E402  (must follow env setup + patches)

if __name__ == "__main__":
    print("\n=== Audio Guestbook test server (real app, device actions mocked) ===")
    print(f"Config:     {TEST_CONFIG}")
    print(f"Recordings: {TEST_RECORDINGS_DIR}")
    print(f"Uploads:    {TEST_UPLOADS_DIR}")
    print(f"Templates:  {app.template_folder}")
    print(f"Static:     {app.static_folder}")
    print("Serving at  http://127.0.0.1:8000\n")
    app.run(debug=False, host="127.0.0.1", port=8000, use_reloader=False)
