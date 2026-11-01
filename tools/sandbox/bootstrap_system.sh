#!/usr/bin/env bash
# PubCast sandbox - system packages for a fresh Debian/Ubuntu machine.
#
# Run once on a new cloud sandbox (needs root or sudo). It installs only what
# the runner cannot get from pip, and it does nothing on startup of the app:
# the PubCast app itself never auto-installs anything (see CLAUDE.md).
#
#   bash tools/sandbox/bootstrap_system.sh            # core set
#   bash tools/sandbox/bootstrap_system.sh --blender  # also Blender (large)
#   bash tools/sandbox/bootstrap_system.sh --check    # only report what is present
#
# Exit code 0 means "everything requested is now present".
set -u

WANT_BLENDER=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --blender) WANT_BLENDER=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }
missing=()

# command -> apt package that provides it
declare -A PKG=( [ffmpeg]=ffmpeg [Xvfb]=xvfb [git]=git [node]=nodejs [npm]=npm [python3]=python3 [curl]=curl )
for cmd in "${!PKG[@]}"; do
  if have "$cmd"; then echo "present   $cmd"; else echo "MISSING   $cmd"; missing+=("${PKG[$cmd]}"); fi
done
# numpy for the system Python: Blender's glTF import needs it (found the hard way).
if python3 -c 'import numpy' >/dev/null 2>&1; then echo "present   python3-numpy"; else echo "MISSING   python3-numpy"; missing+=(python3-numpy); fi
if [ "$WANT_BLENDER" = 1 ]; then
  if have blender; then echo "present   blender"; else echo "MISSING   blender"; missing+=(blender); fi
fi
if have uv; then echo "present   uv"; else echo "MISSING   uv (install: pip install uv, or see https://docs.astral.sh/uv/)"; fi

if [ "$CHECK_ONLY" = 1 ]; then
  [ "${#missing[@]}" -eq 0 ] && exit 0 || exit 1
fi
if [ "${#missing[@]}" -eq 0 ]; then echo "Nothing to install."; exit 0; fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then SUDO="sudo"; else echo "Need root or sudo to install: ${missing[*]}" >&2; exit 1; fi
fi
echo "Installing: ${missing[*]}"
$SUDO apt-get update -y >/dev/null 2>&1 || echo "apt-get update reported a problem; trying the install anyway"
if ! $SUDO apt-get install -y --no-install-recommends "${missing[@]}"; then
  echo "apt-get install failed. Packages tried: ${missing[*]}" >&2
  echo "If the network blocks the package mirror, install them by hand and rerun with --check." >&2
  exit 1
fi
echo "Done. Browsers are NOT installed here: the runner matches Playwright to a Chromium already on disk,"
echo "or downloads one only when you pass --allow-browser-download."
exit 0
