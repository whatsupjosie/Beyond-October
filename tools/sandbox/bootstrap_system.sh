#!/usr/bin/env bash
# PubCast sandbox - system tools for a fresh Debian/Ubuntu machine.
#
# Run once on a new cloud sandbox (needs root or sudo). It installs only what the
# runner cannot get from pip. The PubCast app itself never auto-installs anything
# (see CLAUDE.md); this script is a separate, explicit, one-time step.
#
#   bash tools/sandbox/bootstrap_system.sh --check          # only report what is present
#   bash tools/sandbox/bootstrap_system.sh                  # core set (ffmpeg, Xvfb, git, node, numpy)
#   bash tools/sandbox/bootstrap_system.sh --blender        # + Blender (apt, 4.0.x)
#   bash tools/sandbox/bootstrap_system.sh --rust           # + Rust, only if cargo is missing
#   bash tools/sandbox/bootstrap_system.sh --firefox        # + Firefox and geckodriver
#   bash tools/sandbox/bootstrap_system.sh --powershell     # + PowerShell 7 (lets you run Test-PubCast.ps1 on Linux)
#   bash tools/sandbox/bootstrap_system.sh --all            # everything above
#
# Why Rust and Firefox come from conda-forge: in the cloud sandbox the official
# download hosts (static.rust-lang.org, ftp.mozilla.org, Playwright's browser CDN) are
# blocked, but conda.anaconda.org and GitHub release assets are reachable. micromamba
# (one static binary from GitHub) unpacks conda-forge's real Rust and Firefox builds
# into /opt/rustenv and /opt/ffenv. On your own laptop use the normal installers instead.
#
# Exit code 0 means "everything requested is now present".
set -u

WANT_BLENDER=0; WANT_RUST=0; WANT_FIREFOX=0; WANT_PWSH=0; CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --blender) WANT_BLENDER=1 ;;
    --rust) WANT_RUST=1 ;;
    --firefox) WANT_FIREFOX=1 ;;
    --powershell) WANT_PWSH=1 ;;
    --all) WANT_BLENDER=1; WANT_RUST=1; WANT_FIREFOX=1; WANT_PWSH=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }
status=0
apt_missing=()

# command -> apt package that provides it
declare -A PKG=( [ffmpeg]=ffmpeg [Xvfb]=xvfb [git]=git [node]=nodejs [npm]=npm [python3]=python3 [curl]=curl )
for cmd in "${!PKG[@]}"; do
  if have "$cmd"; then echo "present   $cmd"; else echo "MISSING   $cmd"; apt_missing+=("${PKG[$cmd]}"); fi
done
# numpy for the system Python: Blender's glTF import needs it (found the hard way).
if python3 -c 'import numpy' >/dev/null 2>&1; then echo "present   python3-numpy"; else echo "MISSING   python3-numpy"; apt_missing+=(python3-numpy); fi
if have uv; then echo "present   uv"; else echo "MISSING   uv (install: pip install uv, or see https://docs.astral.sh/uv/)"; status=1; fi

if [ "$WANT_BLENDER" = 1 ]; then
  if have blender; then echo "present   blender"; else echo "MISSING   blender"; apt_missing+=(blender); fi
fi

CARGO_BIN=""
if have cargo; then CARGO_BIN="$(command -v cargo)"; elif [ -x /opt/rustenv/bin/cargo ]; then CARGO_BIN=/opt/rustenv/bin/cargo; fi
FIREFOX_BIN=""
if have firefox; then FIREFOX_BIN="$(command -v firefox)"; elif [ -x /opt/ffenv/bin/firefox ]; then FIREFOX_BIN=/opt/ffenv/bin/firefox; fi
if [ "$WANT_RUST" = 1 ]; then
  if [ -n "$CARGO_BIN" ]; then echo "present   cargo ($CARGO_BIN)"; else echo "MISSING   cargo"; fi
fi
if [ "$WANT_FIREFOX" = 1 ]; then
  if [ -n "$FIREFOX_BIN" ]; then echo "present   firefox ($FIREFOX_BIN)"; else echo "MISSING   firefox"; fi
  if [ -x /opt/ffenv/bin/geckodriver ] || have geckodriver; then echo "present   geckodriver"; else echo "MISSING   geckodriver (selenium can fetch one itself when the network allows)"; fi
  if ls /usr/lib/x86_64-linux-gnu/dri/swrast_dri.so >/dev/null 2>&1; then echo "present   mesa software GL (swrast)"; else echo "MISSING   mesa software GL (libgl1-mesa-dri)"; apt_missing+=(libgl1-mesa-dri libegl1); fi
fi

PWSH_BIN=""
if have pwsh; then PWSH_BIN="$(command -v pwsh)"; elif [ -x /opt/pwsh/pwsh ]; then PWSH_BIN=/opt/pwsh/pwsh; fi
if [ "$WANT_PWSH" = 1 ]; then
  if [ -n "$PWSH_BIN" ]; then echo "present   pwsh ($PWSH_BIN)"; else echo "MISSING   pwsh"; fi
fi
need_pwsh=0; [ "$WANT_PWSH" = 1 ] && [ -z "$PWSH_BIN" ] && need_pwsh=1
need_rust=0; [ "$WANT_RUST" = 1 ] && [ -z "$CARGO_BIN" ] && need_rust=1
need_firefox=0; [ "$WANT_FIREFOX" = 1 ] && [ -z "$FIREFOX_BIN" ] && need_firefox=1

if [ "$CHECK_ONLY" = 1 ]; then
  [ "${#apt_missing[@]}" -eq 0 ] && [ "$need_rust" = 0 ] && [ "$need_firefox" = 0 ] && [ "$need_pwsh" = 0 ] && [ "$status" = 0 ] && exit 0 || exit 1
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then SUDO="sudo"; else
    if [ "${#apt_missing[@]}" -gt 0 ]; then echo "Need root or sudo to install: ${apt_missing[*]}" >&2; exit 1; fi
  fi
fi

if [ "${#apt_missing[@]}" -gt 0 ]; then
  echo "Installing with apt: ${apt_missing[*]}"
  $SUDO apt-get update -y >/dev/null 2>&1 || echo "apt-get update reported a problem; trying the install anyway"
  if ! $SUDO apt-get install -y --no-install-recommends "${apt_missing[@]}"; then
    echo "apt-get install failed. Packages tried: ${apt_missing[*]}" >&2
    status=1
  fi
fi

MICROMAMBA=""
ensure_micromamba() {
  if have micromamba; then MICROMAMBA="$(command -v micromamba)"; return 0; fi
  if [ -x /opt/micromamba/micromamba ]; then MICROMAMBA=/opt/micromamba/micromamba; return 0; fi
  $SUDO mkdir -p /opt/micromamba && $SUDO chmod 777 /opt/micromamba
  if curl -fsSL -m 300 -o /opt/micromamba/micromamba \
      https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64; then
    chmod +x /opt/micromamba/micromamba && MICROMAMBA=/opt/micromamba/micromamba && return 0
  fi
  echo "Could not download micromamba from GitHub releases." >&2
  return 1
}

conda_env() { # conda_env <prefix> <package...>
  local prefix="$1"; shift
  export MAMBA_ROOT_PREFIX=/opt/mamba
  $SUDO mkdir -p "$(dirname "$prefix")" 2>/dev/null
  "$MICROMAMBA" create -y -p "$prefix" -c conda-forge --override-channels "$@"
}

if [ "$need_pwsh" = 1 ]; then
  echo "Installing PowerShell 7 from the GitHub release into /opt/pwsh ..."
  PWSH_VERSION=7.4.6
  tmp="$(mktemp -d)"
  if curl -fsSL -m 600 -o "$tmp/pwsh.tgz" "https://github.com/PowerShell/PowerShell/releases/download/v${PWSH_VERSION}/powershell-${PWSH_VERSION}-linux-x64.tar.gz" \
     && $SUDO mkdir -p /opt/pwsh && $SUDO tar -xzf "$tmp/pwsh.tgz" -C /opt/pwsh && $SUDO chmod +x /opt/pwsh/pwsh; then
    echo "done      pwsh -> /opt/pwsh/pwsh   (run: DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 /opt/pwsh/pwsh -NoProfile -File tools/sandbox/Test-PubCast.ps1 -Tier fast)"
    echo "note      this is PowerShell 7, not the Windows PowerShell 5 your laptop uses; it catches syntax and logic errors, not every 5-only difference"
  else echo "FAILED    PowerShell install" >&2; status=1; fi
  rm -rf "$tmp"
fi
if [ "$need_rust" = 1 ]; then
  echo "Installing Rust from conda-forge into /opt/rustenv ..."
  if ensure_micromamba && conda_env /opt/rustenv rust && [ -x /opt/rustenv/bin/cargo ]; then
    echo "done      cargo -> /opt/rustenv/bin/cargo   (the runner finds it; or set PUBCAST_CARGO)"
  else echo "FAILED    Rust install" >&2; status=1; fi
fi
if [ "$need_firefox" = 1 ]; then
  echo "Installing Firefox and geckodriver from conda-forge into /opt/ffenv ..."
  if ensure_micromamba && conda_env /opt/ffenv firefox geckodriver && [ -x /opt/ffenv/bin/firefox ]; then
    echo "done      firefox -> /opt/ffenv/bin/firefox  (the runner finds it; or set PUBCAST_FIREFOX / PUBCAST_GECKODRIVER)"
  else echo "FAILED    Firefox install" >&2; status=1; fi
fi

echo
echo "Chromium is NOT installed here: the runner matches Playwright to a Chromium already on disk,"
echo "or downloads one only when you pass --allow-browser-download."
[ "$status" = 0 ] && echo "Everything requested is present." || echo "Some items above did not install."
exit "$status"
