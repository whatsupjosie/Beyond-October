#!/usr/bin/env python3
"""Install/check Reach's private environment and retain actionable startup errors.

Only the standard library is needed to run this file. User data is never removed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
CHECK_IMPORTS = "import fastapi, uvicorn, httpx, structlog, jinja2, multipart, aiosqlite, numpy, psutil, bcrypt, cryptography"


class LaunchError(RuntimeError):
    pass


def valid_python(command: list[str]) -> bool:
    try:
        return subprocess.run(
            command + ["-c", "import sys,struct; sys.exit(0 if sys.version_info >= (3,11) and struct.calcsize('P')==8 else 1)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    os.chdir(ROOT)
    for relative in ("requirements.txt", "run_reach.py", "main.py", "modules", "2i/index.html"):
        if not (ROOT / relative).exists():
            print("Reach is missing " + relative + ". Right-click the ZIP, choose Extract All, then run OPEN_REACH_WINDOWS.bat inside the extracted folder.")
            return 2
    if sys.version_info < (3, 11) or sys.maxsize <= 2**32:
        print("Reach needs 64-bit Python 3.11 or newer. This interpreter is " + platform.python_version() + ".")
        return 2
    try:
        log = (ROOT / "reach-startup.log").open("a", encoding="utf-8")
    except OSError as error:
        print("Reach cannot write in this folder. Extract it into a folder you can edit. " + str(error))
        return 2

    with log:
        def say(message: str):
            print(message, flush=True)
            log.write(message + "\n"); log.flush()

        def run(command: list[str]) -> int:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1")
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            try:
                for line in process.stdout:
                    print(line, end="", flush=True);log.write(line);log.flush()
                return process.wait()
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=8)
                    except subprocess.TimeoutExpired: process.kill();process.wait()
                raise

        try:
            say("\nReach startup | Python " + platform.python_version() + " | " + platform.system())
            say("Folder: " + str(ROOT))
            venv = ROOT / ".reach-venv"
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if not valid_python([str(python)]):
                if venv.exists():
                    backup = venv.with_name(".reach-venv-incomplete-" + str(time.time_ns()))
                    try: venv.rename(backup)
                    except OSError as error:
                        raise LaunchError("The old Python environment cannot be moved while in use. Close other Reach terminals and retry. " + str(error)) from error
                    say("Preserved the incomplete Python environment in " + backup.name + ".")
                say("Preparing Reach's Python environment...")
                if run([sys.executable, "-m", "venv", str(venv)]):
                    raise LaunchError("Python could not create Reach's environment. The cause is printed above.")
                if not valid_python([str(python)]):
                    raise LaunchError("The newly created environment could not start. The cause is printed above.")
            requirements = ROOT / "requirements.txt"
            fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
            marker = venv / "reach-install.json"
            try: installed = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError): installed = {}
            imports_ok = subprocess.run([str(python), "-c", CHECK_IMPORTS], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0
            if installed.get("requirements_sha256") != fingerprint or not imports_ok:
                say("Installing/checking Reach dependencies. The first launch needs internet access.")
                if run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)]):
                    raise LaunchError("Dependency installation failed. The exact pip error is above and in reach-startup.log. Reopening this launcher retries installation.")
                if run([str(python), "-c", CHECK_IMPORTS]) or run([str(python), "-m", "pip", "check"]):
                    raise LaunchError("Installed dependencies failed their startup check. See reach-startup.log.")
                marker.write_text(json.dumps({"requirements_sha256": fingerprint}, indent=2) + "\n", encoding="utf-8")
            say("Reach's Python environment is ready.")
            if sys.argv[1:] == ["--check"]:
                return 0
            result = run([str(python), "-u", str(ROOT / "run_reach.py"), *sys.argv[1:]])
            if result:
                raise LaunchError("Reach stopped with exit code " + str(result) + ". Send the last error shown here, or the last lines of reach-startup.log.")
            return 0
        except KeyboardInterrupt:
            say("Reach stopped.");return 0
        except Exception as error:
            if not isinstance(error, LaunchError):
                log.write(traceback.format_exc());log.flush()
            say("\nSTARTUP FAILED: " + str(error))
            say("Error log: " + str(ROOT / "reach-startup.log"))
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
