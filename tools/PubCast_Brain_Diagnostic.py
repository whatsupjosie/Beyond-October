"""
pubcast_brain_diagnostic.py - v1.0 - 2026-03-28 17:00 UTC
Rear View Foresight LLC / Feic Mo Chroi

PURPOSE
-------
Run this BEFORE using PubcastBrain to understand exactly why the engine
isn't responding. Each check produces a clear PASS/FAIL/WARN with a
human explanation and a concrete fix.

Run it:
python pubcast_brain_diagnostic.py
python pubcast_brain_diagnostic.py --models-dir /path/to/your/models
"""

from __future__ import annotations

import gc
import platform
import struct
import subprocess
import sys
from pathlib import Path


_RESULTS: list[tuple[str, str, str]] = []


def _record(status: str, label: str, message: str) -> None:
    _RESULTS.append((status, label, message))
    icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "INFO": "INFO"}.get(status, "?")
    print(f"[{icon}] {label}: {message}")


def _section(title: str) -> None:
    print(f"\n-- {title} " + "-" * max(0, 56 - len(title)))


def check_python() -> None:
    _section("Python environment")
    v = sys.version_info
    label = f"Python {v.major}.{v.minor}.{v.micro}"
    if v < (3, 9):
        _record("FAIL", label, "llama_cpp requires Python >= 3.9. Upgrade Python.")
    else:
        _record("PASS", label, "version OK")
    bits = struct.calcsize("P") * 8
    if bits != 64:
        _record("FAIL", "Architecture", f"{bits}-bit. llama_cpp requires 64-bit Python.")
    else:
        _record("PASS", "Architecture", "64-bit")
    _record("PASS", "Platform", platform.system())


def check_llama_cpp() -> bool:
    _section("llama_cpp package")
    try:
        import llama_cpp  # type: ignore

        version = getattr(llama_cpp, "__version__", "unknown")
        _record("PASS", "import llama_cpp", f"version {version}")
        return True
    except ImportError as exc:
        _record(
            "FAIL",
            "import llama_cpp",
            "Not installed or broken: "
            f"{exc}\nFix: pip install llama-cpp-python\n"
            'GPU build: CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python',
        )
        return False
    except Exception as exc:
        _record(
            "FAIL",
            "import llama_cpp",
            f"Import raised {type(exc).__name__}: {exc}\n"
            "Fix: pip uninstall llama-cpp-python && pip install llama-cpp-python --no-cache-dir",
        )
        return False


def check_llama_class() -> bool:
    _section("Llama class")
    try:
        from llama_cpp import Llama  # type: ignore
        import inspect

        _record("PASS", "from llama_cpp import Llama", "class found")
        sig = inspect.signature(Llama.__init__)
        params = list(sig.parameters.keys())
        for required in ("model_path", "n_ctx", "n_gpu_layers"):
            if required in params:
                _record("PASS", f"param: {required}", "present")
            else:
                _record(
                    "WARN",
                    f"param: {required}",
                    "not found in signature. Try: pip install --upgrade llama-cpp-python",
                )
        return True
    except Exception as exc:
        _record("FAIL", "Llama class", str(exc))
        return False


def check_model_files(models_dir: Path) -> dict[str, Path]:
    _section(f"Model files in {models_dir}")
    found: dict[str, Path] = {}
    if not models_dir.exists():
        _record("FAIL", "models/ directory", f"Does not exist: {models_dir.resolve()}")
        return found

    gguf_files = list(models_dir.glob("*.gguf"))
    if not gguf_files:
        _record("FAIL", "*.gguf files", "None found. Download a GGUF first.")
        return found

    for file_path in gguf_files:
        size_mb = file_path.stat().st_size / (1024 ** 2)
        if size_mb < 10:
            _record("WARN", file_path.name, f"{size_mb:.1f} MB. Suspiciously small.")
        else:
            _record("PASS", file_path.name, f"{size_mb:.0f} MB")
        found[file_path.stem] = file_path

    for expected in ("studio", "architect"):
        expected_path = models_dir / f"{expected}.gguf"
        if expected_path.exists():
            _record("PASS", f"{expected}.gguf", "present")
        else:
            _record(
                "WARN",
                f"{expected}.gguf",
                f"Not found at {expected_path}. Rename the GGUF or register the explicit path in code.",
            )
    return found


def check_gpu() -> None:
    _section("GPU / VRAM")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 3:
                    name, total_mb, free_mb = parts[0], parts[1], parts[2]
                    total_gb = float(total_mb) / 1024
                    free_gb = float(free_mb) / 1024
                    _record("PASS", "NVIDIA GPU", f"{name} {total_gb:.1f} GB total {free_gb:.1f} GB free")
                    if free_gb < 1.0:
                        _record("WARN", "VRAM free", "Less than 1 GB free. Model may not fit.")
        else:
            _record("WARN", "nvidia-smi", "Not found or returned no GPUs. CPU-only mode will be used.")
    except FileNotFoundError:
        _record("WARN", "nvidia-smi", "Not in PATH. Assuming CPU-only or non-NVIDIA GPU.")
    except Exception as exc:
        _record("WARN", "GPU probe", str(exc))

    try:
        import llama_cpp  # type: ignore

        supports_cuda = getattr(llama_cpp, "llama_supports_gpu_offload", None)
        if callable(supports_cuda):
            if supports_cuda():
                _record("PASS", "llama_cpp CUDA", "GPU offload compiled in")
            else:
                _record(
                    "WARN",
                    "llama_cpp CUDA",
                    'GPU offload NOT compiled in. For CUDA: CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python --force-reinstall',
                )
        else:
            _record("WARN", "llama_cpp CUDA", "Cannot detect GPU offload support.")
    except Exception:
        pass


def check_live_load(model_path: Path) -> None:
    _section(f"Live load smoke test: {model_path.name}")
    print(f"Loading {model_path.name}. This may take 15-60 seconds...")
    try:
        from llama_cpp import Llama  # type: ignore

        llm = Llama(
            model_path=str(model_path.resolve()),
            n_ctx=128,
            n_gpu_layers=0,
            verbose=True,
        )
        _record("PASS", "Llama() constructor", "model loaded with n_gpu_layers=0")
        output = llm("Hello", max_tokens=1, temperature=0.0, echo=False)
        text = output["choices"][0]["text"]
        _record("PASS", "Single token generation", f"returned: {text!r}")
        del llm
        gc.collect()
    except FileNotFoundError as exc:
        _record("FAIL", "Llama() constructor", f"File not found: {exc}")
    except Exception as exc:
        _record(
            "FAIL",
            "Llama() constructor",
            f"{type(exc).__name__}: {exc}\n"
            "Common causes:\n"
            "1. GGUF file is corrupt\n"
            "2. llama_cpp version is too old for this GGUF format\n"
            "3. GGUF was quantized with a newer llama.cpp than your Python binding\n"
            "4. The model requires more RAM than available\n"
            "5. On Windows, the Visual C++ Redistributable may be missing",
        )


def check_output_suppression() -> None:
    _section("Output / logging check")
    print(
        "NOTE: llama_cpp writes progress to stderr, not stdout.\n"
        "If the process looks silent, it may still be loading.\n"
        "Redirect stderr if needed: python script.py 2>&1 | tee run.log"
    )
    _record("INFO", "stderr vs stdout", "llama_cpp progress goes to stderr")


def run_all(models_dir: Path) -> None:
    print("\n" + "=" * 65)
    print("PubcastBrain Diagnostic - v1.0 - 2026-03-28")
    print("=" * 65)
    check_python()
    llama_ok = check_llama_cpp()
    if llama_ok:
        check_llama_class()
    check_gpu()
    found_models = check_model_files(models_dir)
    if llama_ok and found_models:
        smallest = min(found_models.values(), key=lambda path: path.stat().st_size)
        check_live_load(smallest)
    elif llama_ok:
        _section("Live load smoke test")
        print("SKIPPED - no .gguf files found.")
    check_output_suppression()
    print("\n" + "=" * 65)
    fails = [row for row in _RESULTS if row[0] == "FAIL"]
    warns = [row for row in _RESULTS if row[0] == "WARN"]
    passes = [row for row in _RESULTS if row[0] == "PASS"]
    print(f"RESULTS: {len(passes)} passed {len(warns)} warnings {len(fails)} failed")
    if fails:
        print("\n-- FAILED CHECKS --")
        for _, label, _ in fails:
            print(f"FAIL {label}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="PubcastBrain diagnostic - finds why the engine isn't running"
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "models",
        help="Path to directory containing .gguf files (default: ./models/)",
    )
    args = parser.parse_args()
    run_all(args.models_dir)
