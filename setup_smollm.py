"""Install/check all declared runtime requirements, then launch SmolLM.

The requirements digest avoids unnecessary online checks after installation.
A missing/broken dependency or changed requirements always forces repair.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    requirements = ROOT / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = environment / ".pubcast-requirements-sha256"
    installed = stamp.read_text().strip() if stamp.is_file() else ""
    # A real pip metadata check catches version conflicts; imports catch broken native wheels.
    check = subprocess.run([str(python), "-m", "pip", "check"], capture_output=True)
    imports = subprocess.run([str(python), "-c",
        "import fastapi,uvicorn,httpx,socksio,cryptography,numpy,psutil,structlog,websockets,jinja2,multipart,aiosqlite,bcrypt"],
        capture_output=True)
    if installed != digest or check.returncode or imports.returncode:
        print("Installing/checking PubCast dependencies. This step needs internet on first use.", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
        subprocess.run([str(python), "-c",
            "import fastapi,uvicorn,httpx,socksio,cryptography,numpy,psutil,structlog,websockets,jinja2,multipart,aiosqlite,bcrypt"], check=True)
        stamp.write_text(digest + "\n")
    os.chdir(ROOT)
    args = sys.argv[1:]
    target = "run_smollm.py"
    if "--hosted" in args:
        args.remove("--hosted")
        target = "run_reach.py"
        args = ["--no-legacy-2i", *args]
    os.execv(str(python), [str(python), str(ROOT / target), *args])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
