# Go rewrite — single-binary design

Porting the two Python processes (`src/audioGuestBook.py` GPIO poller +
`webserver/server.py` Flask UI) into **one statically-linked Go binary** that runs
both as goroutines in a single process and a single systemd service.

The system-level shell pieces (`agb-audio-detect.sh`, `agb-hotspot.sh`, WiFi
regdom in `cmdline.txt`, `config.yaml` templating) are language-agnostic and stay
exactly as they are. Only the app and its two units change.

## Hard rule: stay CGo-free

`CGO_ENABLED=0` is the linchpin. It's what makes
`GOOS=linux GOARCH=arm GOARM=6 go build` produce a binary that runs on every Pi
from the armv6 Zero through a Pi 5 with no cross-toolchain. The moment a CGo dep
sneaks in (native ALSA binding, sqlite, etc.) the armv6 pain from the Python days
returns. So: shell out to `aplay`/`arecord`/`amixer`, and use only pure-Go libs.

```
CGO_ENABLED=0 GOOS=linux GOARCH=arm   GOARM=6 go build -o dist/agb-armv6  ./cmd/agb  # Zero / Zero W
CGO_ENABLED=0 GOOS=linux GOARCH=arm   GOARM=7 go build -o dist/agb-armv7  ./cmd/agb  # Pi 2/3/4 32-bit
CGO_ENABLED=0 GOOS=linux GOARCH=arm64         go build -o dist/agb-arm64  ./cmd/agb  # 64-bit
```

## Repo layout

```
.
├── go.mod  go.sum
├── cmd/
│   └── agb/
│       └── main.go            # flags, load config, start web + guestbook goroutines, signal handling
├── internal/
│   ├── config/
│   │   ├── config.go          # Config struct + Load (yaml.v3) + atomic Save (tmp+rename)
│   │   └── store.go           # thread-safe holder: RWMutex + subscribe channel for live reload
│   ├── gpio/
│   │   └── gpio.go            # thin wrapper over go-gpiocdev (request lines, read level, edge events)
│   ├── audio/
│   │   └── audio.go           # PlayInterruptible / Record / SetVolume — os/exec around aplay/arecord/amixer
│   ├── guestbook/
│   │   ├── guestbook.go       # the hook state machine (port of audioGuestBook.py main loop)
│   │   ├── hook.go            # onHook() logic + debounce (port of is_on_hook + bounce loop)
│   │   └── buttons.go         # record-greeting button + shutdown button
│   ├── web/
│   │   ├── server.go          # http.Server, mux/routes, graceful shutdown
│   │   ├── recordings.go      # list / download / rename / delete / bulk-delete / zip
│   │   ├── stream.go          # GET recording — http.ServeContent (Range handled for free)
│   │   ├── config.go          # GET/POST /config — writes via config.Store, no service restart
│   │   ├── status.go          # /api/system-status via gopsutil
│   │   └── system.go          # /reboot /shutdown
│   └── assets/
│       └── assets.go          # //go:embed templates/* static/* — bundled into the binary
├── web/                       # embedded assets (moved out of webserver/)
│   ├── templates/{base,index,config}.html
│   └── static/{css,js,img}/   # committed output.min.css still lives here, just embedded now
├── deploy/
│   └── agb.service            # the single clean unit (already drafted)
├── sounds/                    # unchanged
├── install.sh                 # trimmed (see below)
└── config.example.yaml        # unchanged template; __INSTALL_DIR__ substitution stays
```

Assets are embedded with `//go:embed`, so the binary is self-contained — no
`templates/`/`static/` dirs need to ship to the device. (`config.yaml`, `sounds/`,
and `recordings/` stay on disk since they're runtime-mutable/user data.)

## Library choices (all pure-Go)

| Concern | Python today | Go |
|---|---|---|
| GPIO | `RPi.GPIO` (needs lgpio shim on Trixie) | `github.com/warthog618/go-gpiocdev` — cdev `/dev/gpiochipN`, native to the new kernel iface |
| Web server | Flask + gunicorn + gevent | stdlib `net/http` |
| Templates / static | Jinja + static dir | `html/template` + `embed.FS` |
| Range streaming | manual `generate_file_chunks` | `http.ServeContent` |
| Config | `ruamel.yaml` | `gopkg.in/yaml.v3` |
| System stats | `psutil` | `github.com/shirou/gopsutil/v3` |
| Audio | `subprocess` → aplay/arecord | `os/exec` → aplay/arecord (unchanged) |

## Process model (the "all in one binary" part)

`main.go` loads config into a `config.Store`, then launches two goroutines and
blocks on a signal:

- **guestbook goroutine** — the port of the `audioGuestBook.py` main loop: poll
  the hook line (or use gpiocdev edge events), debounce, play greeting/beep
  (interruptible), drive `arecord`, enforce `recording_limit`, handle the
  record-greeting and shutdown buttons.
- **web goroutine** — `http.Server` on `0.0.0.0:8080`.

They share one `config.Store`. When the web UI saves config (`POST /config`), it
calls `store.Set(newCfg)`, which atomically writes `config.yaml` **and** notifies
the guestbook goroutine over a channel — so the new config applies live, with no
`systemctl restart` (today's server.py:173 hack goes away).

`SIGINT`/`SIGTERM` → cancel context → stop any `arecord`, release GPIO lines,
`http.Server.Shutdown()`. systemd `Restart=always` covers crashes; wrap each
goroutine in a `recover()` so a panic in one path restarts that loop rather than
killing the process.

## Faithful-port notes

- **Hook logic** (`is_on_hook`, server semantics at audioGuestBook.py:39-70) ports
  directly: NC → HIGH=on-hook, NO → LOW=on-hook, `invert_hook` flips it.
- **Debounce**: keep the poll-and-verify approach first (port of the bounce loop)
  for a behavior-identical v1; switch to gpiocdev edge events + debounce later.
- **Config field coercion**: `update_config` (server.py:369-402) inspects the
  existing value's type to coerce form strings. In Go the `Config` struct types
  do this for you — form binding targets typed fields, so the per-field type
  sniffing and the special `invert_hook` bool branch are no longer needed.
- **`yaml.v3` drops comments on round-trip** (ruamel preserved them). Fine: comments
  live in `config.example.yaml`; `config.yaml` is the runtime file.

## install.sh — what shrinks

The app's service section (install.sh:254-303) collapses from "two units + three
drop-ins + gunicorn ExecStart replacement" to roughly:

```sh
# Fetch the prebuilt binary for this arch (attached to the GitHub release),
# instead of `apt install python3-flask python3-gevent gunicorn python3-ruamel.yaml
# python3-psutil python3-gpiozero python3-lgpio` (install.sh:83-89).
case "$(uname -m)" in
  armv6l)        arch=armv6 ;;
  armv7l)        arch=armv7 ;;
  aarch64|arm64) arch=arm64 ;;
esac
curl -fsSL "${RELEASE_URL}/agb-${arch}" -o "${INSTALL_DIR}/agb"
chmod +x "${INSTALL_DIR}/agb"

install -m 0644 "${INSTALL_DIR}/deploy/agb.service" /etc/systemd/system/agb.service
# no drop-ins needed

if systemd_running; then
  systemctl daemon-reload
  systemctl enable --now agb-audio-detect.service
  systemctl enable --now agb.service
else
  systemctl enable agb-audio-detect.service agb.service   # chroot/image build
fi
```

Dependencies still needed via apt: `alsa-utils` (aplay/arecord/amixer), and
NetworkManager bits for the hotspot — but **no Python at all**. `agb-audio-detect`,
`agb-hotspot`, and the cmdline regdom logic are untouched.

The two vestigial root `.service` files and `start_server.sh` get deleted; the
canonical unit is `deploy/agb.service`.

## Open / deferred

- **Distribution for `curl | sudo bash` on a live Pi**: binaries come from GitHub
  release artifacts (don't commit them). For local/dev installs, either build the
  binary in CI per ref or document a `go build` step.
- **CI**: replace the emulated-armhf Python install with a fast native
  cross-compile matrix that produces the three binaries, then bake the armv6 one
  into the image. (Updates `.github/workflows/build-image.yml`.)
- **Tests**: rewrite `test/` against `net/http/httptest`; the GPIO layer mocks
  cleanly behind a small interface.
