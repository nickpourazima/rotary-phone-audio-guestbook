#!/usr/bin/env bash
#
# Rotary Phone Audio Guestbook - installer for Raspberry Pi OS (Debian 13 "Trixie", Lite).
#
# Single source of truth for setup. Works in TWO contexts:
#   1) Live on a running Pi:        curl -sSL .../install.sh | sudo bash
#                                   (or: sudo ./install.sh from a cloned repo)
#   2) Inside a chroot at image-build time (CustoPiZer / pi-gen).
#
# It is idempotent: safe to re-run. No venv, no pip - everything via apt,
# which is the most reliable path on the armv6 Pi Zero and sidesteps PEP 668.
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via environment variables before running)
# ---------------------------------------------------------------------------
REPO_URL="${REPO_URL:-https://github.com/nickpourazima/rotary-phone-audio-guestbook.git}"
REPO_REF="${REPO_REF:-main}"
INSTALL_DIR_DEFAULT="/opt/rotary-phone-audio-guestbook"

AP_SSID="${AP_SSID:-RPiHotspot}"          # hotspot network name
AP_PSK="${AP_PSK:-1234567890}"            # hotspot password (>= 8 chars)
AP_CON="${AP_CON:-AGB-Hotspot}"           # NetworkManager connection id
AP_IP="${AP_IP:-10.0.0.5}"                # hotspot gateway / SSH / web IP
WIFI_DEV="${WIFI_DEV:-wlan0}"
WIFI_COUNTRY="${WIFI_COUNTRY:-DE}"        # baked default so the hotspot starts out of the box; override via custom.toml
HOTSPOT_AUTORETURN="${HOTSPOT_AUTORETURN:-1}"  # 1 = periodically try to rejoin home WiFi
HOTSPOT_INTERVAL="${HOTSPOT_INTERVAL:-5min}"   # how often to re-check (see caveat in README)

# Default login baked into the release image so it is reachable without the
# Raspberry Pi Imager's OS customisation (which is disabled for custom images).
# Only created on a fresh image (no existing user); a live Pi keeps its user.
DEFAULT_USER="${DEFAULT_USER:-admin}"
DEFAULT_PASS="${DEFAULT_PASS:-password}"

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; exit 1; }

# True only on a live, booted system (false inside a build chroot).
systemd_running() { [ -d /run/systemd/system ]; }
nm_running()      { systemd_running && systemctl is-active --quiet NetworkManager 2>/dev/null; }

[ "$(id -u)" -eq 0 ] || die "Please run as root (sudo)."

# ---------------------------------------------------------------------------
# 1. Locate or fetch the project
# ---------------------------------------------------------------------------
if [ -f "src/audioGuestBook.py" ]; then
    INSTALL_DIR="$(pwd)"                          # running from inside a clone
    log "Using existing checkout at ${INSTALL_DIR}"
elif [ -f "${INSTALL_DIR_DEFAULT}/src/audioGuestBook.py" ]; then
    INSTALL_DIR="${INSTALL_DIR_DEFAULT}"
    log "Updating existing install at ${INSTALL_DIR}"
    git -C "${INSTALL_DIR}" fetch --depth 1 origin "${REPO_REF}" && \
        git -C "${INSTALL_DIR}" reset --hard "origin/${REPO_REF}" || \
        warn "Could not update repo, continuing with what's on disk."
else
    INSTALL_DIR="${INSTALL_DIR_DEFAULT}"
    log "Cloning ${REPO_URL} (${REPO_REF}) into ${INSTALL_DIR}"
    command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
    git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" "${INSTALL_DIR}"
fi
CONFIG="${INSTALL_DIR}/config.yaml"
CONFIG_EXAMPLE="${INSTALL_DIR}/config.example.yaml"

# config.yaml is runtime-mutable (edited via the web UI) and therefore NOT
# tracked in git. Create it from the template on first install, substituting
# the install path so absolute paths match wherever the project lives.
if [ ! -f "${CONFIG}" ] && [ -f "${CONFIG_EXAMPLE}" ]; then
    sed "s|__INSTALL_DIR__|${INSTALL_DIR}|g" "${CONFIG_EXAMPLE}" > "${CONFIG}"
    log "Created config.yaml from config.example.yaml"
fi
install -d "${INSTALL_DIR}/recordings"

# ---------------------------------------------------------------------------
# 2. System packages (no pip / no venv)
# ---------------------------------------------------------------------------
log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 \
    python3-gpiozero \
    python3-lgpio \
    python3-flask \
    python3-gevent \
    gunicorn \
    python3-ruamel.yaml \
    python3-psutil \
    alsa-utils \
    network-manager \
    git
# gpiozero on Trixie must use the lgpio backend (RPi.GPIO no longer works on
# the new kernel GPIO interface). lgpio talks to /dev/gpiochip* directly.

# ---------------------------------------------------------------------------
# 3. First-boot access + WiFi regulatory domain
# ---------------------------------------------------------------------------
# 3a. Baked login. The Imager's OS customisation is disabled for custom images,
#     so the release image ships a working login. Gated by AGB_BAKE_LOGIN=1
#     (set only by the image build) so a manual live install never touches an
#     existing user's password. Note: CustoPiZer's base already creates a 'pi'
#     user, so we set the password on the existing UID-1000 user if present.
if [ "${AGB_BAKE_LOGIN:-0}" = "1" ]; then
    LOGIN_USER="$(getent passwd 1000 | cut -d: -f1)"
    if [ -z "${LOGIN_USER}" ]; then
        LOGIN_USER="${DEFAULT_USER}"
        useradd -m -s /bin/bash -u 1000 "${LOGIN_USER}"
    fi
    echo "${LOGIN_USER}:${DEFAULT_PASS}" | chpasswd
    passwd -u "${LOGIN_USER}" 2>/dev/null || true   # make sure it isn't locked
    for grp in sudo audio video plugdev gpio i2c spi netdev; do
        getent group "$grp" >/dev/null && usermod -aG "$grp" "${LOGIN_USER}" || true
    done
    log "Baked login: user '${LOGIN_USER}' with the configured default password"
fi

# 3b. Enable SSH so the image is reachable headlessly (via the hotspot if needed).
if systemd_running; then
    systemctl enable --now ssh 2>/dev/null || true
else
    systemctl enable ssh 2>/dev/null || true
fi

# 3c. WiFi country (the AP will NOT come up without a regulatory domain).
log "Setting WiFi country to ${WIFI_COUNTRY}"
if command -v raspi-config >/dev/null; then
    raspi-config nonint do_wifi_country "${WIFI_COUNTRY}" || \
        warn "raspi-config could not set the country (expected inside a build chroot)."
fi
# Persist the regulatory domain via the kernel cmdline too. This works offline
# in a build chroot (no netlink needed) and guarantees the regdom on the real Pi.
for cl in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    [ -f "$cl" ] || continue
    if grep -q 'cfg80211.ieee80211_regdom=' "$cl"; then
        sed -i "s/cfg80211.ieee80211_regdom=[A-Za-z0-9]*/cfg80211.ieee80211_regdom=${WIFI_COUNTRY}/" "$cl"
    else
        sed -i "s/\$/ cfg80211.ieee80211_regdom=${WIFI_COUNTRY}/" "$cl"
    fi
    log "Set kernel regdom in ${cl}"
    break
done
systemd_running && { rfkill unblock wifi || true; }

# ---------------------------------------------------------------------------
# 4. Audio: name-based, model-independent device selection
#    Card NUMBERS differ between Pi models (USB dongle is card 1 on a Pi Zero
#    but card 3 on a Pi 4, where HDMI/headphone take 0-2). So we:
#      a) point the app at the ALSA "default" device, and
#      b) install a boot-time service that resolves "default" to the USB card
#         by NAME (plughw:CARD=<id>,DEV=0), which is stable across models.
# ---------------------------------------------------------------------------
log "Configuring model-independent audio..."

# 4a. Point the app at "default" (safety net for configs carried over from an
#     old image that still hardcode a numeric card like plughw:1,0).
if [ -f "${CONFIG}" ] && grep -qE '^\s*alsa_hw_mapping:\s*plughw:[0-9]+,[0-9]+' "${CONFIG}"; then
    sed -i -E 's|^(\s*alsa_hw_mapping:\s*).*$|\1default|' "${CONFIG}"
    log "Set alsa_hw_mapping to 'default' in config.yaml"
fi

# A stale per-user ~/.asoundrc would shadow /etc/asound.conf for the root service.
rm -f /root/.asoundrc

# 4b. The detection script (writes /etc/asound.conf at boot).
install -d /usr/local/sbin
cat > /usr/local/sbin/agb-audio-detect.sh <<'AUDIO_EOF'
#!/usr/bin/env bash
# Route the ALSA "default" device to the USB sound card BY NAME, so it works
# regardless of the card's number (which varies between Pi models / reboots).
set -uo pipefail
ASOUND_CONF="/etc/asound.conf"
MARKER="# managed by rotary-phone-audio-guestbook"

find_usb_card_id() {
    local dev n id
    for dev in /sys/class/sound/card[0-9]*; do
        [ -e "$dev" ] || continue
        case "$(readlink -f "$dev")" in
            *usb*)
                n="${dev##*card}"
                id="$(cat "/proc/asound/card${n}/id" 2>/dev/null || true)"
                [ -n "$id" ] && { printf '%s\n' "$id"; return 0; }
                ;;
        esac
    done
    return 1
}

# USB enumeration can lag slightly after boot (especially on a Pi Zero).
ID=""
for _ in $(seq 1 10); do
    ID="$(find_usb_card_id || true)"
    [ -n "$ID" ] && break
    sleep 1
done

if [ -z "${ID}" ]; then
    echo "agb-audio-detect: no USB audio card found; leaving ALSA config untouched." >&2
    exit 0
fi

# Never clobber an asound.conf we didn't write (e.g. a HAT/I2S user's own file).
if [ -e "${ASOUND_CONF}" ] && ! grep -q "${MARKER}" "${ASOUND_CONF}"; then
    echo "agb-audio-detect: ${ASOUND_CONF} is user-managed; leaving it." >&2
    exit 0
fi

cat > "${ASOUND_CONF}" <<CONF
${MARKER}
# Auto-generated at boot. Detected USB sound card: ${ID}
pcm.!default {
    type asym
    playback.pcm "plughw:CARD=${ID},DEV=0"
    capture.pcm  "plughw:CARD=${ID},DEV=0"
}
ctl.!default {
    type hw
    card ${ID}
}
CONF
echo "agb-audio-detect: routed ALSA default to USB card '${ID}'." >&2
AUDIO_EOF
chmod 755 /usr/local/sbin/agb-audio-detect.sh

# 4c. Run it before the guestbook starts.
cat > /etc/systemd/system/agb-audio-detect.service <<EOF
[Unit]
Description=Detect USB audio card for the audio guestbook
After=sound.target
Wants=sound.target
Before=audioGuestBook.service audioGuestBookWebServer.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/agb-audio-detect.sh

[Install]
WantedBy=multi-user.target
EOF

# ---------------------------------------------------------------------------
# 5. systemd services for the guestbook + web server
#    The repo's unit files keep ExecStart=/usr/bin/python3 ... which is exactly
#    right now that gpiozero/lgpio come from apt. We only layer drop-ins to
#    pin the GPIO backend, fix the working directory, and order audio first.
# ---------------------------------------------------------------------------
log "Installing systemd services..."
for svc in audioGuestBook audioGuestBookWebServer; do
    unit="${INSTALL_DIR}/${svc}.service"
    [ -f "${unit}" ] || { warn "Missing ${unit}, skipping."; continue; }
    install -m 0644 "${unit}" "/etc/systemd/system/${svc}.service"

    dropin="/etc/systemd/system/${svc}.service.d"
    mkdir -p "${dropin}"
    cat > "${dropin}/10-agb.conf" <<EOF
[Service]
WorkingDirectory=${INSTALL_DIR}
Environment=GPIOZERO_PIN_FACTORY=lgpio
EOF
done

# Make sure the guestbook waits for the audio card to be resolved.
mkdir -p /etc/systemd/system/audioGuestBook.service.d
cat > /etc/systemd/system/audioGuestBook.service.d/20-audio.conf <<EOF
[Unit]
After=agb-audio-detect.service
Wants=agb-audio-detect.service
EOF

if systemd_running; then
    systemctl daemon-reload
    systemctl enable --now agb-audio-detect.service
    /usr/local/sbin/agb-audio-detect.sh || true   # configure immediately too
    systemctl enable --now audioGuestBook.service audioGuestBookWebServer.service
    systemctl restart audioGuestBook.service audioGuestBookWebServer.service
else
    systemctl enable agb-audio-detect.service
    systemctl enable audioGuestBook.service audioGuestBookWebServer.service
fi

# ---------------------------------------------------------------------------
# 6. NetworkManager-native hotspot fallback (replaces RaspberryConnect)
# ---------------------------------------------------------------------------
log "Configuring NetworkManager hotspot fallback..."

# 6a. AP connection profile written as a keyfile. This is declarative and works
#     offline in a build chroot (nmcli needs a running daemon, a file does not).
KEYFILE="/etc/NetworkManager/system-connections/${AP_CON}.nmconnection"
cat > "${KEYFILE}" <<EOF
[connection]
id=${AP_CON}
type=wifi
interface-name=${WIFI_DEV}
autoconnect=false

[wifi]
mode=ap
ssid=${AP_SSID}
band=bg
channel=1

[wifi-security]
key-mgmt=wpa-psk
psk=${AP_PSK}

[ipv4]
method=shared
address1=${AP_IP}/24

[ipv6]
method=ignore
EOF
chmod 600 "${KEYFILE}"
chown root:root "${KEYFILE}"

# 6b. Runtime configuration for the check script.
cat > /etc/default/agb-hotspot <<EOF
# Configuration for the audio-guestbook hotspot fallback.
AP_CON="${AP_CON}"
WIFI_DEV="${WIFI_DEV}"
HOTSPOT_AUTORETURN="${HOTSPOT_AUTORETURN}"
EOF

# 6c. The decision script (single radio: client OR access point, never both).
cat > /usr/local/sbin/agb-hotspot.sh <<'AGB_EOF'
#!/usr/bin/env bash
set -uo pipefail
[ -r /etc/default/agb-hotspot ] && . /etc/default/agb-hotspot
AP_CON="${AP_CON:-AGB-Hotspot}"
WIFI_DEV="${WIFI_DEV:-wlan0}"
HOTSPOT_AUTORETURN="${HOTSPOT_AUTORETURN:-1}"

exec 9>/run/agb-hotspot.lock
flock -n 9 || exit 0

ap_active() {
    nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null \
        | grep -q "^${AP_CON}:"
}
client_connected() {
    nmcli -t -f NAME,TYPE,DEVICE connection show --active 2>/dev/null \
        | awk -F: -v dev="$WIFI_DEV" -v ap="$AP_CON" \
            '$2 ~ /wireless/ && $3==dev && $1!=ap {f=1} END{exit f?0:1}'
}
known_ssid_in_range() {
    local profiles inrange p ssid s
    mapfile -t profiles < <(
        nmcli -t -f NAME,TYPE connection show 2>/dev/null \
        | awk -F: -v ap="$AP_CON" '$2 ~ /wireless/ && $1!=ap {print $1}')
    [ "${#profiles[@]}" -eq 0 ] && return 1
    nmcli device wifi rescan ifname "$WIFI_DEV" >/dev/null 2>&1 || true
    sleep 3
    mapfile -t inrange < <(
        nmcli -t -f SSID device wifi list ifname "$WIFI_DEV" --rescan no 2>/dev/null \
        | sed '/^$/d' | sort -u)
    for p in "${profiles[@]}"; do
        ssid="$(nmcli -t -g 802-11-wireless.ssid connection show "$p" 2>/dev/null)"
        [ -z "$ssid" ] && ssid="$p"
        for s in "${inrange[@]}"; do
            [ "$s" = "$ssid" ] && return 0
        done
    done
    return 1
}
start_ap() { ap_active || nmcli connection up "$AP_CON" >/dev/null 2>&1 || true; }
stop_ap()  { ap_active && nmcli connection down "$AP_CON" >/dev/null 2>&1 || true; }

if client_connected; then
    stop_ap
    exit 0
fi
if ap_active && [ "$HOTSPOT_AUTORETURN" != "1" ]; then
    exit 0
fi
stop_ap
if known_ssid_in_range; then
    nmcli device connect "$WIFI_DEV" >/dev/null 2>&1 || true
    sleep 8
    client_connected && exit 0
fi
start_ap
AGB_EOF
chmod 755 /usr/local/sbin/agb-hotspot.sh

# 6d. React immediately to NetworkManager events.
install -d /etc/NetworkManager/dispatcher.d
cat > /etc/NetworkManager/dispatcher.d/90-agb-hotspot <<'DISP_EOF'
#!/usr/bin/env bash
case "$2" in
    up|down|connectivity-change|dhcp4-change)
        /usr/local/sbin/agb-hotspot.sh >/dev/null 2>&1 &
        ;;
esac
exit 0
DISP_EOF
chmod 755 /etc/NetworkManager/dispatcher.d/90-agb-hotspot

# 6e. Periodic re-check (handles auto-return while idle in AP mode).
cat > /etc/systemd/system/agb-hotspot.service <<EOF
[Unit]
Description=Audio Guestbook hotspot fallback check
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/agb-hotspot.sh
EOF
cat > /etc/systemd/system/agb-hotspot.timer <<EOF
[Unit]
Description=Run the Audio Guestbook hotspot check periodically

[Timer]
OnBootSec=30s
OnUnitActiveSec=${HOTSPOT_INTERVAL}

[Install]
WantedBy=timers.target
EOF

if systemd_running; then
    systemctl daemon-reload
    nm_running && nmcli connection reload || true
    systemctl enable --now agb-hotspot.timer
else
    systemctl enable agb-hotspot.timer
fi

log "Done."
log "Project:   ${INSTALL_DIR}"
log "Audio:     USB card auto-detected at boot (ALSA default -> USB by name)"
log "Hotspot:   SSID '${AP_SSID}'  ->  http://${AP_IP}:8080  (SSH: $(getent passwd 1000 | cut -d: -f1)@${AP_IP})"
