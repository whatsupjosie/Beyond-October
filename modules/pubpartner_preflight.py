"""PubPartner local activation preflight.

This is an advisory productization layer: it checks the boring-but-decisive
things that make the local friend loop actually runnable for a normal user.
It does not call paid providers and it does not claim external services work.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import socket
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REQUIRED = ("fastapi", "pydantic", "uvicorn")
OPTIONAL = ("httpx", "pytest", "openai")


def _available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: str = "", *, severity: str = "error", fix: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity, "fix": fix})


def _writable(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".pubpartner_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, str(path)
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, f"{path}: {exc}"


def _port_free(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, int(port))) != 0
    except OSError:
        return False


def human_summary(report: Dict[str, Any]) -> str:
    lines = [
        "PubPartner Activation Preflight",
        "================================",
        f"Overall: {'OK' if report.get('ok') else 'NEEDS ATTENTION'}",
        f"App root: {report.get('app_root')}",
        f"Data dir: {report.get('data_dir')}",
        "",
    ]
    for c in report.get("checks", []):
        tag = "OK" if c.get("ok") else ("WARN" if c.get("severity") == "warning" else "FAIL")
        lines.append(f"[{tag}] {c.get('name')}: {c.get('detail')}")
        if not c.get("ok") and c.get("fix"):
            lines.append(f"      Fix: {c.get('fix')}")
    return "\n".join(lines)


def run_preflight(*, data_dir: Path | str, app_root: Optional[Path | str] = None, host: str = "127.0.0.1", port: int = 8000) -> Dict[str, Any]:
    root = Path(data_dir).expanduser()
    app = Path(app_root or Path.cwd()).expanduser()
    checks: List[Dict[str, Any]] = []

    _check(checks, "python_version", sys.version_info >= (3, 10), sys.version.split()[0], fix="Install Python 3.10+.")
    _check(checks, "platform", True, f"{platform.system()} {platform.release()} / {platform.machine()}", severity="warning")

    for sub, label in [(root, "data_dir_writable"), (root / "pubpartner", "pubpartner_data_writable"), (root / "pubpartner" / "receipts", "receipt_dir_writable"), (root / "pubpartner" / "verbatim", "verbatim_dir_writable")]:
        ok, detail = _writable(sub)
        _check(checks, label, ok, detail, fix="Choose a writable PUBPARTNER_DATA_DIR or fix folder permissions.")

    for module in REQUIRED:
        _check(checks, f"module:{module}", _available(module), module, fix="Run: python -m pip install -r requirements.txt")
    for module in OPTIONAL:
        _check(checks, f"optional_module:{module}", _available(module), module, severity="warning", fix=f"Install optional support with: python -m pip install {module}")

    try:
        disk = shutil.disk_usage(root if root.exists() else root.parent)
        if disk.total > 16 * (1024 ** 5):
            _check(checks, "disk_space", True, "virtual filesystem capacity; writable probe passed", severity="warning")
        else:
            free_mb = int(disk.free / (1024 * 1024))
            _check(
                checks,
                "disk_space",
                free_mb >= 1024,
                f"{free_mb} MiB free",
                severity="error" if free_mb < 256 else "warning",
                fix="Free at least 1 GiB before launch; 5+ GiB is recommended for models, recordings, and backups.",
            )
    except Exception as exc:
        _check(checks, "disk_space", False, f"unavailable: {exc}", severity="warning")

    files = {
        "pubpartner_app.py": app / "pubpartner_app.py",
        "main.py": app / "main.py",
        "static/pubpartner.html": app / "static" / "pubpartner.html",
        "static/pubpartner.css": app / "static" / "pubpartner.css",
        "static/pubpartner.js": app / "static" / "pubpartner.js",
        "modules/pubpartner_core.py": app / "modules" / "pubpartner_core.py",
        "modules/pubpartner_routes.py": app / "modules" / "pubpartner_routes.py",
        "modules/pubpartner_provider.py": app / "modules" / "pubpartner_provider.py",
        "modules/provider_neutralizer.py": app / "modules" / "provider_neutralizer.py",
        "modules/provider_capabilities.py": app / "modules" / "provider_capabilities.py",
        "modules/openai_compatible_provider.py": app / "modules" / "openai_compatible_provider.py",
        "modules/pubpartner_relationship.py": app / "modules" / "pubpartner_relationship.py",
        "modules/pub_manager_authority.py": app / "modules" / "pub_manager_authority.py",
        "modules/auth.py": app / "modules" / "auth.py",
        "modules/auth_routes.py": app / "modules" / "auth_routes.py",
    }
    for name, path in files.items():
        _check(checks, f"file:{name}", path.exists(), str(path), fix="Re-extract the latest PubPartner build zip.")

    _check(checks, "port_available", _port_free(host, port), f"{host}:{port}", severity="warning", fix=f"Use another port: python run_pubpartner.py --port {port + 1}")
    _check(checks, "openai_key_optional", bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY", severity="warning", fix="Only needed for provider=openai. Local mock/offline/Ollama can run without it.")
    _check(checks, "ollama_host_configured", bool(os.environ.get("OLLAMA_HOST", "http://localhost:11434")), os.environ.get("OLLAMA_HOST", "http://localhost:11434"), severity="warning")
    jwt_secret = os.environ.get("PUBCAST_JWT_SECRET", "")
    _check(checks, "local_runtime_secret", len(jwt_secret) >= 32, "configured" if len(jwt_secret) >= 32 else "missing or too short", fix="Launch with run_pubpartner.py so a local secret is generated safely.")
    _check(checks, "auth_enforced", str(os.environ.get("PUBCAST_ENFORCE_AUTH", "0")).strip().lower() in {"1", "true", "yes", "on"}, os.environ.get("PUBCAST_ENFORCE_AUTH", "0"), severity="warning", fix="Launch with run_pubpartner.py; use --unsafe-no-auth only for isolated development.")
    origins = os.environ.get("PUBCAST_ALLOWED_ORIGINS", "")
    _check(checks, "cors_not_wildcard", bool(origins and origins.strip() != "*"), origins or "not configured", severity="warning", fix="Launch with run_pubpartner.py or set PUBCAST_ALLOWED_ORIGINS to the local app URL.")

    errors = [c for c in checks if not c["ok"] and c.get("severity") == "error"]
    warnings = [c for c in checks if not c["ok"] and c.get("severity") == "warning"]
    report: Dict[str, Any] = {
        "format": "PubPartnerPreflight.v3",
        "revision": "provider_neutralizer_multi_llm_pass_1",
        "ok": not errors,
        "app_root": str(app),
        "data_dir": str(root),
        "host": host,
        "port": port,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "next_fix": next((c.get("fix") for c in errors + warnings if c.get("fix")), ""),
    }
    report["human_summary"] = human_summary(report)
    return report


def write_report(report: Dict[str, Any], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["run_preflight", "human_summary", "write_report"]
