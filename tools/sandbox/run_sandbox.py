#!/usr/bin/env python3
"""PubCast test sandbox: one command that builds an isolated environment, runs
a defined set of real tests, and writes a small report you can compare.

Standard library only, so it runs under any Python 3.8+ on Linux, macOS or
Windows (Windows PowerShell 5 users go through ``Test-PubCast.ps1``).

Why this exists
  * Every new session or AI used to lose 10-15 minutes rebuilding a test
    environment and re-discovering the same traps (a Playwright version that
    does not match the installed Chromium, a missing numpy for Blender).
    This script does that setup the same way every time.
  * It never uses GitHub Actions. Everything runs where you run it.
  * Two reports can be compared (``--compare``): your laptop against the cloud
    sandbox, or a clean-room run against a warm one. A difference between the
    two is a bug that only exists in one of the environments.

Honesty rules (see QUALITY_STANDARDS.md)
  * A step is PASS only when its command exited 0. Nothing is rounded up.
  * Browser tests that are skipped because no usable Chromium was found are
    reported as UNVERIFIED, never as a pass.
  * The report lists what this run could NOT test.

Tiers
  fast      syntax checks, Node tests, preflight, backend tests (about 1-2 min)
  standard  fast + launcher audit + real-browser tests (about 6-10 min)
  full      standard + the entire pytest suite and npm tests (about 15-25 min)

Examples
  python tools/sandbox/run_sandbox.py --tier fast
  python tools/sandbox/run_sandbox.py --tier standard --capture
  python tools/sandbox/run_sandbox.py --matrix 3.11,3.12,3.13
  python tools/sandbox/run_sandbox.py --compare .sandbox/reports/A .sandbox/reports/B
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SANDBOX = ROOT / ".sandbox"
IS_WINDOWS = os.name == "nt"

# Chromium revision on disk -> the Playwright release that launches it.
# Extend this table when you meet a new pairing; the self-check below proves
# a pairing works by really launching the browser, so a wrong entry is caught.
KNOWN_PLAYWRIGHT_FOR_CHROMIUM = {1194: "1.56.0", 1243: "1.63.0"}

FAST_PY_TESTS = [
    "tests/test_shared_studio_switchers.py",
    "tests/test_studio25d_media_routes.py",
    "tests/test_studio25d_recording_guard.py",
    "tests/test_recording_portable_bundle.py",
]
NODE_TESTS = [
    "tests/production25d.test.cjs",
    "tests/test_production25d_core.cjs",
    "tests/test_production25d_wiring.cjs",
    "tests/test_production25d_switcher_bridge.cjs",
    "tests/test_studio25d_confidence.cjs",
    "tests/test_editor_sync_interchange.cjs",
]
BROWSER_PY_TESTS = [
    "tests/test_production25d_browser.py",
    "tests/test_foresight_file_workspace.py",
    "tests/test_world_walk_glb_browser.py",
    "tests/test_foresight_airgapped_ui.py",
]

SYNTAX_CHECK = r"""
import pathlib, sys
bad = []
files = [pathlib.Path(p) for p in ("main.py", "run_reach.py")]
files += sorted(pathlib.Path("modules").rglob("*.py"))
files += sorted(pathlib.Path("tools").rglob("*.py"))
for f in files:
    try:
        # Compile BYTES, as the interpreter does, so a UTF-8 byte-order mark is
        # handled the same way it is at import time (decoding to text first
        # raised a false error on modules/voxel_block_kit.py).
        compile(f.read_bytes(), str(f), "exec")
    except SyntaxError as e:
        bad.append("%s:%s %s" % (f, e.lineno, e.msg))
print("python files checked: %d, syntax errors: %d" % (len(files), len(bad)))
for b in bad:
    print("SYNTAX ERROR " + b)
sys.exit(1 if bad else 0)
"""

BROWSER_PROBE = r"""
import importlib.metadata as m, json, os, sys
out = {"playwright": m.version("playwright")}
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        args = ["--no-sandbox"] if (os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0) else []
        args += ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
        b = p.chromium.launch(args=args)
        out["launch"] = "ok"
        out["browser_version"] = b.version
        page = b.new_page()
        page.set_content("<canvas id=c></canvas>")
        out["probe"] = page.evaluate('''() => {
          const r = {};
          const gl2 = document.createElement('canvas').getContext('webgl2');
          if (gl2) { const e = gl2.getExtension('WEBGL_debug_renderer_info');
            r.webgl2 = e ? gl2.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl2.getParameter(gl2.RENDERER); } else { r.webgl2 = null; }
          r.mediaRecorder_vp9_opus = typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus');
          r.mediaRecorder_h264_mp4 = typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('video/mp4;codecs=avc1.42E01E,mp4a.40.2');
          r.webaudio = typeof AudioContext !== 'undefined';
          return r; }''')
        b.close()
except Exception as e:  # report the real reason; never hide it
    out["launch"] = "fail"
    out["error"] = (type(e).__name__ + ": " + str(e)).splitlines()[0][:300]
print("PROBE_JSON " + json.dumps(out))
"""

NOT_TESTED_ALWAYS = [
    "Real GPU speed. Rendering here is software (SwiftShader or similar) unless the report says otherwise.",
    "Real microphone, camera and speakers. Browser fake devices and WebAudio meters only.",
    "Real phones. Only phone-sized emulation is possible in this tool.",
    "Firefox and Safari. Only Chromium is exercised.",
    "A local AI model with real weights. No model weights ship in this repository.",
    "A real DaVinci Resolve import and relink of exported files.",
    "A second physical machine, long soak runs and network partitions.",
]


# ---------------------------------------------------------------- utilities
def now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_capture(argv, cwd=None, timeout=60, env=None):
    """Run a short command and return (exit_code, text). Never raises."""
    try:
        p = subprocess.run(argv, cwd=str(cwd or ROOT), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except FileNotFoundError:
        return 127, "not found: " + str(argv[0])
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ss" % timeout
    except OSError as e:
        return 126, "OS error: %s" % e


def tool_version(name, flag="--version"):
    path = shutil.which(name)
    if not path:
        return None
    code, text = run_capture([path, flag], timeout=20)
    if code != 0 and not text:
        return "present (version unreadable)"
    return (text.splitlines() or ["present"])[0][:90]


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def find_python(spec: str):
    """Return an argv prefix for the requested Python ('3.12' or a path)."""
    if os.sep in spec or (os.altsep and os.altsep in spec) or Path(spec).is_file():
        return [spec], True
    if IS_WINDOWS:
        launcher = shutil.which("py")
        if launcher:
            return [launcher, "-" + spec], True
        return [sys.executable], spec in "%d.%d" % sys.version_info[:2]
    exact = shutil.which("python" + spec)
    if exact:
        return [exact], True
    return [sys.executable], spec == "%d.%d" % sys.version_info[:2]


# ------------------------------------------------------------ step execution
class Recorder:
    def __init__(self, report_dir: Path):
        self.dir = report_dir
        self.logs = report_dir / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.steps = []
        self.notes = []
        self.tmpdirs = []          # disposable data copies, removed at the end
        self.data_baseline = None  # set of `git status` lines for data/ before the run
        self.pollution = {}        # file line -> name of the step that changed it

    @staticmethod
    def data_state():
        """Everything git can see changing under data/ (tracked edits, new files, ignored files)."""
        code, text = run_capture(["git", "status", "--porcelain", "--ignored", "--untracked-files=all", "--", "data"])
        if code != 0:
            return None
        return {l for l in text.splitlines() if l.strip()}

    def disposable_env(self, env):
        """Give a step its own throwaway copy of data/, the same way conftest.py does for pytest.
        Without this, app startup writes databases, keys and Blackbox files into the source tree
        and can modify the tracked Alex vessel file (found on the first standard run)."""
        scratch = Path(tempfile.mkdtemp(prefix="pubcast-sandbox-data-", dir=str(SANDBOX)))
        if (ROOT / "data").is_dir():
            shutil.copytree(ROOT / "data", scratch, dirs_exist_ok=True)
        self.tmpdirs.append(scratch)
        e = dict(env)
        e["PUBCAST_DATA_DIR"] = str(scratch)
        return e

    def step(self, name, argv, cwd=None, env=None, timeout=900, kind="generic"):
        log = self.logs / (re.sub(r"[^A-Za-z0-9_.-]+", "_", name) + ".log")
        started = time.monotonic()
        status, code = "PASS", 0
        try:
            with open(log, "wb") as fh:
                fh.write(("$ " + " ".join(str(a) for a in argv) + "\n\n").encode())
                fh.flush()
                p = subprocess.run([str(a) for a in argv], cwd=str(cwd or ROOT), env=env,
                                   stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
                code = p.returncode
                status = "PASS" if code == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            status, code = "TIMEOUT", 124
        except (FileNotFoundError, OSError) as e:
            status, code = "FAIL", 127
            log.write_text("could not start: %s\n" % e, encoding="utf-8")
        seconds = round(time.monotonic() - started, 1)
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        record = {"name": name, "result": status, "exit": code, "seconds": seconds,
                  "log": str(log.relative_to(self.dir)), "kind": kind}
        record.update(parse_output(text, kind))
        if "Chromium unavailable" in text or "Executable doesn't exist" in text:
            record["unverified_browser_skipped"] = True
        if self.data_baseline is not None:
            now = self.data_state()
            if now is not None:
                changed = sorted(now - self.data_baseline)
                if changed:
                    record["touched_repo_data"] = changed
                    for line in changed:
                        self.pollution.setdefault(line, name)
                    self.data_baseline = now
        self.steps.append(record)
        print("  [%-7s] %-24s %6.1fs  %s" % (status, name, seconds, record.get("summary", "")), flush=True)
        return record

    def skip(self, name, reason):
        self.steps.append({"name": name, "result": "SKIPPED", "exit": None, "seconds": 0,
                           "summary": reason, "kind": "skipped"})
        print("  [SKIPPED] %-24s %s" % (name, reason), flush=True)


def parse_output(text: str, kind: str):
    out = {}
    if kind == "pytest":
        counts = {}
        for line in reversed(text.splitlines()[-40:]):
            if " in " in line and re.search(r"\b(passed|failed|error|errors|skipped)\b", line):
                for n, word in re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)", line):
                    counts["error" if word.startswith("error") else word] = int(n)
                break
        out["counts"] = counts
        failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+)", text, flags=re.M)))
        out["failed_tests"] = failed
        if counts.get("skipped"):
            out["skipped_tests"] = counts["skipped"]
        out["summary"] = ", ".join("%d %s" % (v, k) for k, v in counts.items()) or "no pytest summary found"
    elif kind == "node":
        counts = {}
        for key in ("tests", "pass", "fail", "skipped"):
            m = re.findall(r"^# %s (\d+)" % key, text, flags=re.M)
            if m:
                counts[key] = int(m[-1])
        out["counts"] = counts
        out["summary"] = ", ".join("%d %s" % (v, k) for k, v in counts.items()) or "no node summary found"
    else:
        lines = [l for l in text.splitlines() if l.strip()]
        out["summary"] = (lines[-1][:110] if lines else "")
    return out


# ------------------------------------------------------------ environment setup
def create_environment(rec: Recorder, spec: str, venv: Path, reuse: bool, args):
    """Create (or reuse) a venv with the project's requirements. Returns python path or None."""
    py_exe = venv_python(venv)
    uv = shutil.which("uv")
    if reuse and py_exe.exists():
        rec.notes.append("Reused existing environment %s (warm run)." % venv.name)
    else:
        if venv.exists():
            shutil.rmtree(venv, ignore_errors=True)
        base, exact = find_python(spec)
        if not exact:
            rec.notes.append("Python %s was requested but not found; using %s instead." % (spec, " ".join(base)))
        if uv:
            r = rec.step("create-venv", [uv, "venv", "--python", spec if exact else sys.executable, str(venv)], timeout=600)
        else:
            r = rec.step("create-venv", base + ["-m", "venv", str(venv)], timeout=600)
        if r["result"] != "PASS":
            return None
        req = ["-r", str(ROOT / "requirements.txt")]
        dev = ROOT / "requirements-dev.txt"
        if dev.exists():
            req += ["-r", str(dev)]
        # A clean-room run always gets a fresh environment. By default the
        # package download cache is kept (fast). --cold-cache also drops that
        # cache, which is the only way to prove a from-nothing install works.
        install_env = dict(os.environ)
        if args.cold_cache:
            install_env["UV_NO_CACHE"] = "1"
            install_env["PIP_NO_CACHE_DIR"] = "1"
            rec.notes.append("Cold cache: package cache was bypassed for the install.")
        if uv:
            r = rec.step("install-requirements", [uv, "pip", "install", "--python", str(py_exe)] + req,
                         env=install_env, timeout=1800)
        else:
            rec.step("upgrade-pip", [str(py_exe), "-m", "pip", "install", "--upgrade", "pip"], env=install_env, timeout=600)
            r = rec.step("install-requirements", [str(py_exe), "-m", "pip", "install"] + req,
                         env=install_env, timeout=1800)
        if r["result"] != "PASS":
            return None
    return py_exe


def probe_browser(py_exe: Path):
    code, text = run_capture([str(py_exe), "-c", BROWSER_PROBE], timeout=120)
    for line in text.splitlines():
        if line.startswith("PROBE_JSON "):
            try:
                return json.loads(line[len("PROBE_JSON "):])
            except ValueError:
                break
    return {"launch": "fail", "error": "probe produced no result: " + text[-200:]}


def browser_roots():
    roots = []
    for key in ("PLAYWRIGHT_BROWSERS_PATH",):
        if os.environ.get(key) and os.environ[key] != "0":
            roots.append(Path(os.environ[key]))
    home = Path.home()
    roots += [home / ".cache" / "ms-playwright", Path("/opt/pw-browsers"),
              home / "Library" / "Caches" / "ms-playwright"]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
    return [r for r in roots if r.is_dir()]


def installed_chromium_revisions():
    revs = set()
    for root in browser_roots():
        for child in root.iterdir():
            m = re.match(r"chromium(?:_headless_shell)?-(\d+)$", child.name)
            if m:
                revs.add(int(m.group(1)))
    return sorted(revs, reverse=True)


def resolve_browser(rec: Recorder, py_exe: Path, args):
    """Make a Chromium launch work, in the least invasive order. Returns the probe dict."""
    uv = shutil.which("uv")
    info = probe_browser(py_exe)
    if info.get("launch") == "ok":
        return info
    first_error = info.get("error", "")
    # 1. A Chromium is already on disk: install the Playwright release that matches it.
    wanted = [args.playwright_version] if args.playwright_version else \
        [KNOWN_PLAYWRIGHT_FOR_CHROMIUM[r] for r in installed_chromium_revisions() if r in KNOWN_PLAYWRIGHT_FOR_CHROMIUM]
    for version in wanted:
        cmd = ([uv, "pip", "install", "--python", str(py_exe)] if uv else [str(py_exe), "-m", "pip", "install"]) + ["playwright==" + version]
        rec.step("match-playwright-" + version, cmd, timeout=600)
        info = probe_browser(py_exe)
        if info.get("launch") == "ok":
            rec.notes.append("Playwright %s was installed to match the Chromium already on this machine." % version)
            return info
    # 2. Optional download, only when explicitly allowed.
    if args.allow_browser_download:
        rec.step("playwright-install-chromium", [str(py_exe), "-m", "playwright", "install", "chromium"], timeout=1800)
        info = probe_browser(py_exe)
        if info.get("launch") == "ok":
            rec.notes.append("Chromium was downloaded with Playwright (explicitly allowed).")
            return info
    info["error"] = info.get("error") or first_error
    rec.notes.append("No usable Chromium. Browser tests will be skipped and reported as UNVERIFIED. "
                     "Rerun with --allow-browser-download, or --playwright-version X to match an installed browser.")
    return info


def system_capabilities():
    caps = {
        "os": "%s %s" % (platform.system(), platform.release()),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "node": tool_version("node"), "npm": tool_version("npm"),
        "uv": tool_version("uv"), "git": tool_version("git"),
        "ffmpeg": (tool_version("ffmpeg", "-version") or None),
        "rustc": tool_version("rustc"), "blender": tool_version("blender"),
        "xvfb": "present" if shutil.which("Xvfb") else None,
        "docker_client": "present" if shutil.which("docker") else None,
        "gpu_device": os.path.exists("/dev/dri") or None,
        "audio_device": os.path.exists("/dev/snd") or None,
    }
    try:
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names:
            caps["ram_mb"] = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1048576)
    except (ValueError, OSError):
        pass
    return caps


def repo_state():
    code, head = run_capture(["git", "rev-parse", "HEAD"])
    _, branch = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    _, dirty = run_capture(["git", "status", "--porcelain", "--", ".", ":(exclude).sandbox"])
    return {"commit": head if code == 0 else "unknown", "branch": branch if code == 0 else "unknown",
            "uncommitted_files": len([l for l in dirty.splitlines() if l.strip()]) if code == 0 else None}


# ---------------------------------------------------------------- the run
def build_env():
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PUBCAST_JWT_SECRET"] = secrets.token_urlsafe(48)
    env.pop("PUBCAST_DATA_DIR", None)  # tests build their own disposable data directories
    return env


def run_tier(args, spec: str, label: str):
    stamp = now_stamp()
    report_dir = SANDBOX / "reports" / ("%s-%s" % (stamp, label))
    rec = Recorder(report_dir)
    rec.data_baseline = rec.data_state()
    if rec.data_baseline:
        rec.notes.append("data/ already had %d uncommitted change(s) before this run; only NEW changes are attributed to steps." % len(rec.data_baseline))
    started = time.monotonic()
    print("\n== PubCast sandbox | tier=%s | python=%s | %s | report: %s" %
          (args.tier, spec, "warm" if args.reuse else "clean-room", report_dir.relative_to(ROOT)), flush=True)
    env = build_env()
    venv = SANDBOX / ("venv-" + spec if args.reuse else "venv-%s-%s" % (spec, stamp))
    py_exe = create_environment(rec, spec, venv, args.reuse, args)
    environment = {"python_requested": spec, "mode": "warm" if args.reuse else "clean-room"}
    browser = {"launch": "not attempted"}
    if py_exe:
        pkg_probe = ("import sys,importlib.metadata as m;print(sys.version.split()[0]);"
                     "print(' '.join('%s=%s' % (n, m.version(n)) for n in ('fastapi','starlette','pydantic','httpx','pytest','playwright')))")
        if args.tier != "fast" or args.capture or args.browser_probe:
            browser = resolve_browser(rec, py_exe, args)
        else:
            browser = {"launch": "not needed for the fast tier"}
        # Read package versions AFTER any Playwright matching, so the report names what the tests really used.
        code, text = run_capture([str(py_exe), "-c", pkg_probe])
        lines = text.splitlines()
        if code == 0 and len(lines) >= 2:
            environment["python"], environment["packages"] = lines[0], lines[1]
        run_steps(rec, args, py_exe, env, browser)
    else:
        rec.notes.append("Environment setup failed, so no tests were run. See the logs.")
    summary = finish_report(rec, args, spec, environment, browser, time.monotonic() - started)
    if not args.reuse and not args.keep_venv and venv.exists():
        shutil.rmtree(venv, ignore_errors=True)
    return summary


def pytest_with_rerun(rec: Recorder, args, exe, name, targets, env_factory, timeout):
    """Run pytest; rerun ONLY the failed tests up to --retries times.

    A test that fails and then passes is reported FLAKY, never PASS: it is real
    evidence of instability (first seen in the recorder tests, which do not wait
    for the first video data). A test that keeps failing stays FAIL."""
    base = [exe, "-m", "pytest", "-q", "-rfEs", "-p", "no:cacheprovider"]
    r = rec.step(name, base + list(targets), env=env_factory(), timeout=timeout, kind="pytest")
    pending = list(r.get("failed_tests", []))
    attempt = 0
    flaky = []
    while (r["result"] == "FAIL" and pending and attempt < args.retries
           and r.get("counts", {}).get("error", 0) == 0):
        attempt += 1
        rr = rec.step("%s-rerun-%d" % (name, attempt), base + pending, env=env_factory(), timeout=timeout, kind="pytest")
        still = list(rr.get("failed_tests", []))
        flaky += [t for t in pending if t not in still]
        pending = still if rr["result"] != "PASS" else []
        if rr["result"] == "PASS":
            break
    if flaky and not pending:
        r["result"] = "FLAKY"
        r["flaky_tests"] = sorted(set(flaky))
        r["summary"] = "%s; passed only on rerun: %d" % (r.get("summary", ""), len(set(flaky)))
        print("  [FLAKY  ] %-24s %s" % (name, r["summary"]), flush=True)
    elif r["result"] == "FAIL" and attempt:
        r["summary"] = "%s; still failing after %d rerun(s)" % (r.get("summary", ""), attempt)
    return r


def run_steps(rec: Recorder, args, py: Path, env, browser):
    exe = str(py)
    rec.step("python-syntax", [exe, "-I", "-c", SYNTAX_CHECK], env=env, timeout=300)
    node = shutil.which("node")
    if node:
        failures = []
        count = 0
        for f in sorted((ROOT / "static").glob("*.js")):
            count += 1
            code, text = run_capture([node, "--check", str(f)], timeout=30)
            if code != 0:
                failures.append("%s: %s" % (f.name, text.splitlines()[0] if text else code))
        (rec.logs / "node-syntax.log").write_text("checked %d files\n%s\n" % (count, "\n".join(failures)), encoding="utf-8")
        rec.steps.append({"name": "node-syntax", "result": "FAIL" if failures else "PASS", "exit": 1 if failures else 0,
                          "seconds": 0, "summary": "%d static scripts checked, %d failed" % (count, len(failures)),
                          "log": "logs/node-syntax.log", "kind": "generic"})
        print("  [%-7s] %-24s %s" % (rec.steps[-1]["result"], "node-syntax", rec.steps[-1]["summary"]), flush=True)
        rec.step("node-tests", [node, "--test"] + NODE_TESTS, env=env, timeout=600, kind="node")
    else:
        rec.skip("node-syntax", "Node.js not installed")
        rec.skip("node-tests", "Node.js not installed")
    rec.step("preflight", [exe, "tools/workbench_preflight.py"], env=rec.disposable_env(env), timeout=300)
    pytest_with_rerun(rec, args, exe, "backend-tests", FAST_PY_TESTS, lambda: rec.disposable_env(env), 900)
    browser_ok = browser.get("launch") == "ok"
    if args.tier in ("standard", "full"):
        rec.step("launcher-audit", [exe, "tools/foresight_checks/audit_launcher.py"], env=rec.disposable_env(env), timeout=600)
        if browser_ok:
            pytest_with_rerun(rec, args, exe, "browser-tests", BROWSER_PY_TESTS, lambda: rec.disposable_env(env), 2400)
        else:
            rec.skip("browser-tests", "UNVERIFIED: no usable Chromium (%s)" % browser.get("error", "unknown reason"))
    if args.tier == "full":
        if shutil.which("npm"):
            rec.step("npm-ci", ["npm", "ci"], env=env, timeout=1200)
            rec.step("npm-test-node", ["npm", "run", "test:node"], env=env, timeout=900, kind="node")
        else:
            rec.skip("npm-test-node", "npm not installed")
        pytest_with_rerun(rec, args, exe, "full-pytest", [], lambda: rec.disposable_env(env), 3600)
    if args.capture:
        if browser_ok:
            capture_motion(rec, args, py, env)
        else:
            rec.skip("capture-motion", "UNVERIFIED: no usable Chromium")


def capture_motion(rec: Recorder, args, py: Path, env):
    """Run the existing real-browser capture, then build a contact sheet if ffmpeg exists."""
    out_dir = ROOT / "artifacts" / "bella_live"
    shutil.rmtree(out_dir, ignore_errors=True)
    r = rec.step("capture-motion", [str(py), "tools/capture_bella_live.py"], env=rec.disposable_env(env), timeout=600)
    dest = rec.dir / "capture"
    if out_dir.is_dir():
        shutil.copytree(out_dir, dest, dirs_exist_ok=True)
        shutil.rmtree(out_dir, ignore_errors=True)
    videos = sorted(dest.glob("*.webm")) if dest.is_dir() else []
    ffmpeg = shutil.which("ffmpeg")
    if r["result"] == "PASS" and videos and ffmpeg:
        sheet = dest / "motion_strip.jpg"
        code, text = run_capture([ffmpeg, "-v", "error", "-y", "-ss", "6", "-t", "9", "-i", str(videos[0]),
                                  "-vf", "fps=1.35,crop=1260:540:0:180,scale=640:-1,tile=3x4",
                                  "-frames:v", "1", "-q:v", "4", str(sheet)], timeout=180)
        r["summary"] = ("motion strip written: capture/motion_strip.jpg" if code == 0 and sheet.exists()
                        else "frames captured, strip failed: " + text[-100:])
    elif r["result"] == "PASS" and not ffmpeg:
        r["summary"] = "captured; ffmpeg missing so no contact sheet"


def finish_report(rec: Recorder, args, spec, environment, browser, seconds):
    if rec.data_baseline is not None:
        polluted = rec.pollution
        rec.steps.append({
            "name": "repo-data-clean", "kind": "generic", "seconds": 0, "exit": 1 if polluted else 0,
            "result": "FAIL" if polluted else "PASS",
            "summary": ("%d file(s) under data/ were changed by: %s" % (len(polluted), ", ".join(sorted(set(polluted.values())))))
                       if polluted else "no step changed anything under data/ (tracked, new or ignored files)",
            "touched_repo_data": sorted(polluted)})
        print("  [%-7s] %-24s %s" % (rec.steps[-1]["result"], "repo-data-clean", rec.steps[-1]["summary"]), flush=True)
        if polluted:
            rec.notes.append("Repo data/ was modified. To undo: git checkout -- data && git clean -fdx -- data "
                             "(only if data/ held no work you want to keep). Never commit these files.")
    for d in rec.tmpdirs:
        shutil.rmtree(d, ignore_errors=True)
    steps = rec.steps
    failed = [s for s in steps if s["result"] in ("FAIL", "TIMEOUT")]
    unverified = [s for s in steps if s.get("unverified_browser_skipped") or s.get("skipped_tests") or
                  (s["result"] == "SKIPPED" and "UNVERIFIED" in s.get("summary", ""))]
    flaky_steps = [s for s in steps if s["result"] == "FLAKY"]
    if failed:
        overall = "FAIL"
    elif flaky_steps or unverified:
        parts = (["FLAKY TESTS"] if flaky_steps else []) + (["UNVERIFIED PARTS"] if unverified else [])
        overall = "PASS WITH " + " AND ".join(parts)
    else:
        overall = "PASS"
    probe = browser.get("probe") or {}
    not_tested = list(NOT_TESTED_ALWAYS)
    if not IS_WINDOWS:
        not_tested.insert(0, "Windows and PowerShell 5 launch (this run is not on Windows).")
    if probe.get("webgl2") and re.search(r"swiftshader|llvmpipe|software", str(probe["webgl2"]), re.I):
        not_tested.append("Hardware GL: WebGL2 here is software-rendered (%s)." % probe["webgl2"])
    data = {
        "schema": 1, "tier": args.tier, "label": rec.dir.name, "overall": overall,
        "seconds": round(seconds, 1), "repo": repo_state(), "environment": environment,
        "capabilities": system_capabilities(), "browser": browser, "steps": steps,
        "notes": rec.notes, "not_tested": not_tested,
    }
    (rec.dir / "report.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    md = ["# PubCast sandbox report", "",
          "**Result: %s**  |  tier `%s`  |  %s  |  %.0f s" % (overall, args.tier, environment.get("mode"), seconds),
          "Repository `%s` at `%s`, %s uncommitted file(s)." % (data["repo"]["branch"], data["repo"]["commit"][:10],
                                                                data["repo"]["uncommitted_files"]), "",
          "## Steps", "", "| Step | Result | Seconds | Detail |", "| --- | --- | ---: | --- |"]
    for s in steps:
        md.append("| %s | %s | %s | %s |" % (s["name"], s["result"], s.get("seconds", ""), (s.get("summary") or "").replace("|", "/")))
    fails = sorted({t for s in steps if s["result"] != "FLAKY" for t in s.get("failed_tests", [])})
    if fails:
        md += ["", "## Failing tests", ""] + ["- `%s`" % t for t in fails]
    flaky_names = sorted({t for s in steps for t in s.get("flaky_tests", [])})
    if flaky_names:
        md += ["", "## Flaky tests (failed, then passed when rerun alone)", ""] + ["- `%s`" % t for t in flaky_names]
    touched = sorted({t for s in steps for t in s.get("touched_repo_data", [])})
    if touched:
        md += ["", "## Files changed under data/ (should be none)", ""] + ["- `%s`" % t for t in touched]
    md += ["", "## Environment", "",
           "- Python: %s (requested %s)" % (environment.get("python", "unknown"), spec),
           "- Packages: %s" % environment.get("packages", "unknown"),
           "- Browser launch: %s%s" % (browser.get("launch"), (" | Chromium " + browser["browser_version"]) if browser.get("browser_version") else ""),
           "- Browser probe: %s" % json.dumps(probe) if probe else "- Browser probe: not run"]
    caps = data["capabilities"]
    md += ["- Machine: %s, %s CPUs, %s MB RAM" % (caps.get("os"), caps.get("cpus"), caps.get("ram_mb", "?")),
           "- Tools: " + ", ".join("%s=%s" % (k, v) for k, v in caps.items()
                                   if k in ("node", "npm", "uv", "ffmpeg", "rustc", "blender") and v)]
    if rec.notes:
        md += ["", "## Notes", ""] + ["- " + n for n in rec.notes]
    md += ["", "## What this run could NOT test", ""] + ["- " + n for n in not_tested]
    (rec.dir / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n  RESULT: %s  (%.0f s)\n  report: %s\n" % (overall, seconds, (rec.dir / "REPORT.md").relative_to(ROOT)), flush=True)
    return {"dir": rec.dir, "overall": overall, "data": data}


# ---------------------------------------------------------------- comparison
def load_report(path_text: str):
    p = Path(path_text)
    if p.is_dir():
        p = p / "report.json"
    return json.loads(p.read_text(encoding="utf-8")), p.parent


SETUP_STEP_PREFIXES = ("create-venv", "install-requirements", "upgrade-pip", "match-playwright", "playwright-install")


def is_setup_step(name: str) -> bool:
    """Setup and rerun steps legitimately differ between a clean-room and a warm run."""
    return name.startswith(SETUP_STEP_PREFIXES) or "-rerun-" in name


def normalize_result(result: str) -> str:
    """FLAKY means the step passed once failures were rerun alone, so for comparison it counts as ok."""
    return "PASS" if result == "FLAKY" else result


def normalize_overall(overall: str) -> str:
    return "PASS" if overall in ("PASS", "PASS WITH FLAKY TESTS") else overall


def compare_reports(a_path: str, b_path: str):
    a, a_dir = load_report(a_path)
    b, b_dir = load_report(b_path)
    lines = ["# Sandbox comparison", "", "A = `%s`  (%s, %s)" % (a["label"], a["environment"].get("mode"), a["capabilities"].get("os")),
             "B = `%s`  (%s, %s)" % (b["label"], b["environment"].get("mode"), b["capabilities"].get("os")), ""]
    differences = 0
    inventory_differs = []

    def row(name, x, y, kind="result"):
        """kind=result: a difference is a finding. kind=inventory (python, packages, browser) and
        kind=setup (venv creation, installs, reruns) are expected to differ and are only noted."""
        nonlocal differences
        same = x == y
        if kind == "result":
            differences += 0 if same else 1
            verdict = "same" if same else "**DIFFERENT**"
        elif kind == "inventory":
            if not same:
                inventory_differs.append(name)
            verdict = "same" if same else "differs (inventory)"
        else:
            verdict = "setup step, not compared"
        lines.append("| %s | %s | %s | %s |" % (name, str(x).replace("|", "/"), str(y).replace("|", "/"), verdict))

    lines += ["## Environment", "", "| Item | A | B | |", "| --- | --- | --- | --- |"]
    row("overall result", normalize_overall(a["overall"]), normalize_overall(b["overall"]))
    row("repository commit", a["repo"]["commit"][:10], b["repo"]["commit"][:10])
    row("python", a["environment"].get("python"), b["environment"].get("python"), "inventory")
    row("packages", a["environment"].get("packages"), b["environment"].get("packages"), "inventory")
    row("browser", a["browser"].get("browser_version"), b["browser"].get("browser_version"), "inventory")
    row("webgl2", (a["browser"].get("probe") or {}).get("webgl2"), (b["browser"].get("probe") or {}).get("webgl2"), "inventory")
    steps_a = {s["name"]: s for s in a["steps"]}
    steps_b = {s["name"]: s for s in b["steps"]}
    lines += ["", "## Steps", "", "| Step | A | B | |", "| --- | --- | --- | --- |"]
    for name in sorted(set(steps_a) | set(steps_b)):
        sa, sb = steps_a.get(name), steps_b.get(name)
        ra = "%s (%s)" % (sa["result"], (sa.get("summary") or "")[:70]) if sa else "not run"
        rb = "%s (%s)" % (sb["result"], (sb.get("summary") or "")[:70]) if sb else "not run"
        if is_setup_step(name):
            row(name, ra, rb, "setup")
        elif sa and sb and normalize_result(sa["result"]) == normalize_result(sb["result"]):
            lines.append("| %s | %s | %s | same result |" % (name, ra.replace("|", "/"), rb.replace("|", "/")))
        else:
            row(name, ra, rb)

    def failing(report):
        return {t for s in report["steps"] if s["result"] != "FLAKY" for t in s.get("failed_tests", [])}

    def flaky(report):
        return {t for s in report["steps"] for t in s.get("flaky_tests", [])}
    fa, fb = failing(a), failing(b)
    ka, kb = flaky(a), flaky(b)
    lines += ["", "## Failing tests", "",
              "- only in A: %s" % (", ".join("`%s`" % t for t in sorted(fa - fb)) or "none"),
              "- only in B: %s" % (", ".join("`%s`" % t for t in sorted(fb - fa)) or "none"),
              "- in both: %s" % (", ".join("`%s`" % t for t in sorted(fa & fb)) or "none"),
              "", "## Flaky tests (failed, then passed when rerun alone; noise, not a verdict)", "",
              "- in A: %s" % (", ".join("`%s`" % t for t in sorted(ka)) or "none"),
              "- in B: %s" % (", ".join("`%s`" % t for t in sorted(kb)) or "none")]
    only = bool(fa ^ fb)
    note = (" Inventory that differs (expected when comparing machines or versions): %s." % ", ".join(inventory_differs)) if inventory_differs else ""
    verdict = ("The two runs agree on every result." + note) if (differences == 0 and not only) else \
        "The two runs DIFFER. A result that differs between environments is a bug that exists in only one of them. Start with the DIFFERENT rows and the 'only in' lists." + note
    lines += ["", "**" + verdict + "**"]
    text = "\n".join(lines) + "\n"
    out = SANDBOX / "reports" / ("compare-%s-vs-%s.md" % (a_dir.name, b_dir.name))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print("comparison saved: %s" % out.relative_to(ROOT))
    return 0 if (differences == 0 and not only) else 3


# ---------------------------------------------------------------- entry point
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PubCast test sandbox: build, test, report, compare.")
    ap.add_argument("--tier", choices=("fast", "standard", "full"), default="fast")
    ap.add_argument("--python", default="3.12", help="Python to test with, e.g. 3.12 (the project's target) or a path")
    ap.add_argument("--reuse", action="store_true", help="warm run: reuse .sandbox/venv-<version> instead of a clean room")
    ap.add_argument("--keep-venv", action="store_true", help="keep the clean-room environment afterwards")
    ap.add_argument("--cold-cache", action="store_true", help="clean-room install that also bypasses the package cache")
    ap.add_argument("--capture", action="store_true", help="also capture the 3D walker in motion (needs a usable Chromium)")
    ap.add_argument("--browser-probe", action="store_true", help="probe the browser even on the fast tier")
    ap.add_argument("--playwright-version", help="force this Playwright release (to match an installed Chromium)")
    ap.add_argument("--allow-browser-download", action="store_true", help="let Playwright download Chromium if none matches")
    ap.add_argument("--retries", type=int, default=2, help="rerun failed pytest tests alone up to N times; a pass on rerun is reported FLAKY, not PASS (0 disables)")
    ap.add_argument("--strict", action="store_true", help="treat flaky tests as failures (exit code 1)")
    ap.add_argument("--matrix", help="comma-separated Python versions; runs the chosen tier once for each")
    ap.add_argument("--label", default="", help="label added to the report folder name")
    ap.add_argument("--compare", nargs=2, metavar=("REPORT_A", "REPORT_B"), help="compare two report folders or report.json files")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    if args.compare:
        return compare_reports(*args.compare)
    SANDBOX.mkdir(exist_ok=True)
    specs = [s.strip() for s in args.matrix.split(",") if s.strip()] if args.matrix else [args.python]
    results = []
    for spec in specs:
        label = (args.label + "-" if args.label else "") + "py" + spec.replace(os.sep, "_")
        results.append(run_tier(args, spec, label))
    if len(results) > 1:
        print("== Matrix summary ==")
        for spec, r in zip(specs, results):
            print("  python %-6s %s   %s" % (spec, r["overall"], r["dir"].relative_to(ROOT)))
        for r in results[1:]:
            compare_reports(str(results[0]["dir"]), str(r["dir"]))
    worst = [r["overall"] for r in results]
    if any(o == "FAIL" for o in worst):
        return 1
    if args.strict and any("FLAKY" in o for o in worst):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
