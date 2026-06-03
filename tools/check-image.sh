#!/usr/bin/env bash
#
# Inspect a built Raspberry Pi image offline on macOS (OrbStack / Docker).
# Mounts the image's boot + root partitions in a throwaway container, prints
# a few sanity checks, then unmounts and exits. No persistent container needed.
#
# Usage:  ./check-image.sh [path-to-img]      # default: workspace/output.img
#
set -euo pipefail

IMG_HOST="${1:-workspace/output.img}"
[ -f "$IMG_HOST" ] || { echo "Image not found: $IMG_HOST"; exit 1; }
DIR="$(cd "$(dirname "$IMG_HOST")" && pwd)"
NAME="$(basename "$IMG_HOST")"

docker run --rm --privileged -e IMGNAME="$NAME" -v "$DIR:/w" debian:stable-slim bash -c '
  set -e
  IMG="/w/$IMGNAME"

  # Map each partition to its own loop device via byte offset (the same
  # approach CustoPiZer uses; avoids needing /dev/loopXpY partition nodes).
  BOOT_START=$(partx -g -o START -n 1:1 "$IMG" | tr -dc "0-9")
  ROOT_START=$(partx -g -o START -n 2:2 "$IMG" | tr -dc "0-9")
  LB=$(losetup -f --show -o $((BOOT_START * 512)) "$IMG")
  LR=$(losetup -f --show -o $((ROOT_START * 512)) "$IMG")
  mkdir -p /mnt/boot /mnt/root
  mount "$LB" /mnt/boot
  mount "$LR" /mnt/root
  R=/mnt/root

  echo "===== default user (UID 1000) ====="
  grep ":1000:" "$R/etc/passwd" || echo "  NONE FOUND"

  echo "===== ssh enabled ====="
  ls "$R/etc/systemd/system/multi-user.target.wants/" | grep -i ssh || echo "  no ssh symlink"

  echo "===== wifi regdom (cmdline.txt) ====="
  cat /mnt/boot/cmdline.txt

  echo "===== guestbook units enabled ====="
  ls "$R/etc/systemd/system/multi-user.target.wants/" | grep -E "audioGuestBook|agb-" || echo "  none"
  ls "$R/etc/systemd/system/timers.target.wants/" 2>/dev/null | grep agb || echo "  no agb timer"

  echo "===== hotspot keyfile (perms + content) ====="
  ls -l "$R/etc/NetworkManager/system-connections/AGB-Hotspot.nmconnection"
  cat "$R/etc/NetworkManager/system-connections/AGB-Hotspot.nmconnection"

  echo "===== config.yaml alsa mapping ====="
  grep -n alsa_hw_mapping "$R/opt/rotary-phone-audio-guestbook/config.yaml" || echo "  config.yaml missing"

  echo "===== asound.conf (should be ABSENT - written at first boot) ====="
  ls -l "$R/etc/asound.conf" 2>/dev/null || echo "  not present (expected)"

  umount /mnt/boot /mnt/root
  losetup -d "$LB" "$LR"
  echo ">> check complete"
'
