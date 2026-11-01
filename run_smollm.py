"""Launch a local CPU model and the existing authenticated Reach host.

The model is chosen by alias from the model registry (modules/model_registry.py
plus data/model_registry.json). SmolLM2 is the default. Any other model needs a
registry entry with its .gguf file name, SHA-256, context size and tier, and the
file placed in models/.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from modules.model_registry import ModelRegistryError, get_model  # noqa: E402


def resolve_model(alias):
    """Return (spec, path) for a launcher model, refusing anything unverifiable."""
    try:
        spec = get_model(alias)
    except ModelRegistryError as error:
        raise RuntimeError(str(error)) from None
    if spec.runtime != "launcher":
        raise RuntimeError(f"{spec.alias} runs through {spec.runtime}, not this launcher")
    if not spec.sha256:
        raise RuntimeError(f"{spec.alias} has no SHA-256 in the model registry; add it before running "
                           "(PowerShell: Get-FileHash -Algorithm SHA256 <file>)")
    path = ROOT / "models" / spec.file
    if not path.is_file():
        raise RuntimeError(f"Missing model file: {path}")
    return spec, path


def verify_model(path, expected_sha):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha:
        raise RuntimeError("Model checksum failed. The file is incomplete or is not the registered model.")


def stop(process):
    if process is None or process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        process.wait(timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def interrupt(signum, frame):
    raise KeyboardInterrupt


def default_data_dir():
    legacy = ROOT / "data"
    # The first integration used data/. Never silently hide an existing account.
    return legacy if (legacy / "secure" / "jwt_secret.txt").is_file() else ROOT / "reach_userdata"


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required")
    signal.signal(signal.SIGTERM, interrupt)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model-port", type=int, default=8081)
    parser.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--data-dir", default=str(default_data_dir()))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--model", default="smollm2", help="model alias from the model registry")
    args = parser.parse_args()
    if not (1 <= args.port <= 65535 and 1 <= args.model_port <= 65535) or args.threads < 1:
        parser.error("Ports must be 1–65535 and threads must be positive")
    if args.port == args.model_port:
        parser.error("Reach and the model need different ports")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        parser.error("Bundled runtimes require an x64 Windows/Linux computer, not Android or ARM")
    if sys.platform not in {"win32", "linux"}:
        parser.error("This package includes Windows and Linux runtimes only")
    runtime = ROOT / "runtime" / ("windows-x64" if os.name == "nt" else "linux-x64")
    server = runtime / ("llama-server.exe" if os.name == "nt" else "llama-server")
    if not server.is_file():
        raise RuntimeError(f"Missing runtime: {server}")
    if os.name != "nt":
        server.chmod(server.stat().st_mode | 0o100)
    for port in (args.model_port, args.port):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    spec, model_path = resolve_model(args.model)
    print(f"Checking {spec.display_name}…", flush=True)
    verify_model(model_path, spec.sha256)
    data = Path(args.data_dir).expanduser().resolve()
    logs = data / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PUBCAST_LOCAL_MODEL_URL"] = f"http://127.0.0.1:{args.model_port}/v1"
    env["PUBCAST_LOCAL_MODEL_KEY"] = secrets.token_urlsafe(32)
    env["LLAMA_API_KEY"] = env["PUBCAST_LOCAL_MODEL_KEY"]
    env["PUBCAST_LOCAL_MODEL_ALIAS"] = spec.alias
    child_options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    model = host = None
    with (logs / "smollm.log").open("a", encoding="utf-8") as logfile:
        try:
            model = subprocess.Popen([str(server), "-m", str(model_path), "--alias", spec.alias,
                "--host", "127.0.0.1", "--port", str(args.model_port), "-c", str(spec.context_tokens),
                "-np", "1", "-t", str(args.threads), "--no-context-shift", "--no-slots"], env=env, cwd=runtime,
                stdout=logfile, stderr=subprocess.STDOUT, **child_options)
            ready = False
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if model.poll() is not None:
                    raise RuntimeError(f"Model server exited; see {logs / 'smollm.log'}")
                try:
                    request = urllib.request.Request(f"http://127.0.0.1:{args.model_port}/health",
                        headers={"Authorization": "Bearer " + env["PUBCAST_LOCAL_MODEL_KEY"]})
                    with urllib.request.urlopen(request, timeout=2) as response:
                        ready = json.load(response).get("status") == "ok"
                    if ready:
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(0.5)
            if not ready:
                raise RuntimeError(f"Model did not become ready; see {logs / 'smollm.log'}")
            # A healthy endpoint is not enough: verify the required identity,
            # context and authentication before allowing the app to use it.
            request = urllib.request.Request(f"http://127.0.0.1:{args.model_port}/props",
                headers={"Authorization": "Bearer " + env["PUBCAST_LOCAL_MODEL_KEY"]})
            with urllib.request.urlopen(request, timeout=5) as response:
                props = json.load(response)
            if (props.get("model_alias") != spec.alias
                    or (props.get("default_generation_settings") or {}).get("n_ctx") != spec.context_tokens):
                raise RuntimeError("Local model identity or context size does not match this adapter")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{args.model_port}/v1/models", timeout=5)
            except urllib.error.HTTPError as error:
                if error.code != 401:
                    raise RuntimeError("Unexpected model authentication response") from None
            else:
                raise RuntimeError("Model endpoint accepted an unauthenticated API request")
            print(f"{spec.display_name} ready. Ctrl+C stops the session.", flush=True)
            command = [sys.executable, str(ROOT / "run_reach.py"), "--port", str(args.port),
                       "--data-dir", str(data), "--no-legacy-2i"]
            if args.no_browser:
                command.append("--no-browser")
            host = subprocess.Popen(command, cwd=ROOT, env=env, **child_options)
            print(f"Open http://127.0.0.1:{args.port}/pubpartner for Alex with {spec.display_name}.", flush=True)
            while host.poll() is None:
                if model.poll() is not None:
                    raise RuntimeError("Model stopped unexpectedly; shutting Reach down")
                time.sleep(0.5)
            return host.returncode
        finally:
            stop(host)
            stop(model)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped.")
    except (OSError, RuntimeError) as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
