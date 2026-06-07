#!/usr/bin/env bash
#
# Local CustoPiZer build for macOS (OrbStack or Docker Desktop).
# Mirrors .github/workflows/build-image.yml so you can test before pushing.
#
# Usage:  ./build-local.sh [git-ref]      # git-ref defaults to "main"
#         ./build-local.sh my-branch
#         USE_LOCAL_REPO=1 ./build-local.sh [git-ref]  # use local git repo instead of downloading
#
# Result: workspace/output.img  (flash with Raspberry Pi Imager -> "Use custom")
#
set -euo pipefail

BASE_IMG_URL="https://downloads.raspberrypi.com/raspios_lite_armhf/images/raspios_lite_armhf-2025-12-04/2025-12-04-raspios-trixie-armhf-lite.img.xz"
BASE_IMG_SHA256="1b3e49b67b15050a9f20a60267c145e6d468dc9559dd9cd945130a11401a49ff"
REPO_REF="${1:-main}"
USE_LOCAL_REPO="${USE_LOCAL_REPO:-0}"

command -v docker >/dev/null || { echo "docker not found (start OrbStack first)"; exit 1; }

rm -rf workspace scripts
mkdir -p workspace scripts

# If using local repo, copy it to scripts/files for mounting into CustoPiZer
if [ "$USE_LOCAL_REPO" = "1" ]; then
  mkdir -p scripts/files
  echo ">> Cloning local repo to scripts/files..."
  git clone -b "$REPO_REF" $(git rev-parse --show-toplevel) scripts/files/rotary-phone-audio-guestbook
fi

# 1. Download, verify, decompress and grow the base image INSIDE a Linux
#    container, so we don't depend on macOS having xz / truncate / sha256sum.
echo ">> Preparing base image..."
docker run --rm -v "$PWD/workspace:/w" \
  -e URL="$BASE_IMG_URL" -e SHA="$BASE_IMG_SHA256" \
  debian:stable-slim bash -c '
    set -euo pipefail
    apt-get update -qq && apt-get install -y -qq curl xz-utils >/dev/null
    cd /w
    curl -fL -o base.img.xz "$URL"
    echo "$SHA  base.img.xz" | sha256sum -c -
    xz -d base.img.xz
    mv base.img input.img
    truncate -s +2G input.img       # headroom for apt; increase if it runs out
  '

# 2. The customization script that runs inside the image (same as the workflow).
echo ">> Writing build script (ref: ${REPO_REF})..."
cat > scripts/01-guestbook <<EOF
#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl
export REPO_REF="${REPO_REF}"
export AGB_BAKE_LOGIN=1
if [ "${USE_LOCAL_REPO}" = "1" ]; then
  # Use local repo mounted at /files
  export REPO_URL="/files/rotary-phone-audio-guestbook"
  cp /files/rotary-phone-audio-guestbook/install.sh /tmp/install.sh 
else
  # Download from remote
  curl -sSL "https://raw.githubusercontent.com/nickpourazima/rotary-phone-audio-guestbook/\${REPO_REF}/install.sh" -o /tmp/install.sh
fi
bash /tmp/install.sh
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/install.sh
EOF
chmod 755 scripts/01-guestbook

# 3. Register qemu so the armhf image can be chrooted.
#    Required on Apple Silicon (no 32-bit ARM in hardware); harmless on Intel.
echo ">> Registering qemu/binfmt..."
docker run --privileged --rm tonistiigi/binfmt --install arm

# 4. CustoPiZer's own start_chroot_script installs policykit-1, which was
#    removed in Debian Trixie (replaced by polkitd). Patch it so the build's
#    bootstrap doesn't fail before our install.sh runs.
echo ">> Building Trixie-patched CustoPiZer image..."
cat > Dockerfile.custopizer <<'DOCKER'
FROM ghcr.io/octoprint/custopizer:latest
RUN set -e; for f in /CustoPiZer/start_chroot_script /common.sh; do \
      [ -f "$f" ] && sed -i 's/policykit-1/polkitd/g' "$f" || true; \
    done
DOCKER
docker build -t custopizer-trixie -f Dockerfile.custopizer .

# 5. Run CustoPiZer (needs --privileged + loopback mounts).
echo ">> Running CustoPiZer..."
docker run --rm --privileged --dns 8.8.8.8 \
  -v "$PWD/workspace:/CustoPiZer/workspace" \
  -v "$PWD/scripts:/CustoPiZer/workspace/scripts" \
  custopizer-trixie

echo ">> Done. Image: workspace/output.img"
ls -lh workspace/output.img 2>/dev/null || echo "(output.img not found - check the CustoPiZer log above)"
