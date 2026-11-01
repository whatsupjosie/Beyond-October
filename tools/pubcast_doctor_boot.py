"""
PubCast boot verifier.

Runs a practical GO/NO-GO preflight without deleting or mutating project files.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _print(title: str, value: str) -> None:
    print(f"[{title}] {value}")


def check_required_files(base: Path) -> Tuple[bool, List[str]]:
    required = [
        base / "main.py",
        base / "modules" / "doctor.py",
        base / "modules" / "inference.py",
        base / "modules" / "llm_orchestrator.py",
        base / "static" / "stage.html",
        base / "static" / "stage_panoramic.html",
    ]
    missing = [str(p.relative_to(base)) for p in required if not p.exists()]
    return (len(missing) == 0, missing)


def check_doctor(base: Path) -> Dict[str, Any]:
    try:
        from modules.doctor import run_doctor, run_launch_gate
    except Exception as exc:
        return {"ok": False, "error": f"doctor import failed: {exc}"}
    report = run_doctor(base)
    gate = run_launch_gate(base)
    return {"ok": True, "report": report, "gate": gate}


async def check_inference_smoke() -> Dict[str, Any]:
    try:
        from modules.inference import InferenceManager
    except Exception as exc:
        return {"ok": False, "error": f"inference import failed: {exc}"}

    mgr = InferenceManager()
    await mgr.startup()
    out = await mgr.generate_text(
        prompt="Say hello in one short sentence.",
        role="studio",
        temperature=0.2,
        max_tokens=64,
    )
    healthy_shape = isinstance(out, dict) and "text" in out and "role_used" in out
    return {
        "ok": healthy_shape,
        "worker_alive": bool(mgr._worker_alive),
        "result": out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PubCast boot preflight verifier")
    parser.add_argument("--base", default=".", help="Project root path")
    args = parser.parse_args()

    base = Path(args.base).resolve()
    _print("BASE", str(base))

    files_ok, missing = check_required_files(base)
    if files_ok:
        _print("FILES", "PASS")
    else:
        _print("FILES", f"FAIL missing={missing}")

    doctor = check_doctor(base)
    if not doctor.get("ok"):
        _print("DOCTOR", f"FAIL {doctor.get('error')}")
        gate_ok = False
    else:
        report = doctor["report"]
        gate = doctor["gate"]
        _print(
            "DOCTOR",
            f"status={report.get('status')} passed={report.get('summary', {}).get('passed')} "
            f"warn={report.get('summary', {}).get('warnings')} fail={report.get('summary', {}).get('failed')}",
        )
        _print("LAUNCH_GATE", f"allowed={gate.get('allowed')} reason={gate.get('reason')}")
        gate_ok = bool(gate.get("allowed"))

    try:
        inference = asyncio.run(check_inference_smoke())
    except Exception as exc:
        inference = {"ok": False, "error": str(exc)}

    if inference.get("ok"):
        out = inference.get("result", {})
        _print(
            "INFERENCE",
            f"PASS worker_alive={inference.get('worker_alive')} role_used={out.get('role_used')} "
            f"fallback={out.get('fallback_occurred')}",
        )
    else:
        _print("INFERENCE", f"FAIL {inference.get('error', 'shape invalid')}")

    final_ok = files_ok and gate_ok and inference.get("ok", False)
    _print("GO_NO_GO", "GO" if final_ok else "NO_GO")

    summary = {
        "files_ok": files_ok,
        "missing_files": missing,
        "doctor_ok": doctor.get("ok", False),
        "launch_gate_ok": gate_ok,
        "inference_ok": inference.get("ok", False),
        "go": final_ok,
    }
    print(json.dumps(summary, indent=2))
    return 0 if final_ok else 1


if __name__ == "__main__":
    sys.exit(main())
