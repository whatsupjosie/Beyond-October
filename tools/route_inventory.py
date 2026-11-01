"""
PubCast route and frontend endpoint inventory.

Non-mutating audit tool for market-prep merges. It scans backend Python files for
FastAPI route decorators and frontend files for fetch/WebSocket/EventSource endpoint
references, then reports likely mismatches before UI wiring work proceeds.

Usage:
    python tools/route_inventory.py --base . --format markdown
    python tools/route_inventory.py --base . --format json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "websocket"}
FRONTEND_SUFFIXES = {".html", ".js", ".mjs", ".ts", ".tsx"}
BACKEND_SUFFIXES = {".py"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "incoming_review",
    "visual_reference",
    "data",
}

FETCH_RE = re.compile(r"\bfetch\(\s*([`'\"])(?P<url>[^`'\"]+)\1")
XHR_OPEN_RE = re.compile(r"\.open\(\s*([`'\"])(?:GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\1\s*,\s*([`'\"])(?P<url>[^`'\"]+)\2", re.I)
WS_RE = re.compile(r"\bnew\s+WebSocket\(\s*([`'\"])(?P<url>[^`'\"]+)\1")
EVENTSOURCE_RE = re.compile(r"\bnew\s+EventSource\(\s*([`'\"])(?P<url>[^`'\"]+)\1")
LITERAL_ENDPOINT_RE = re.compile(r"([`'\"])(?P<url>/(?:api|ws|health|doctor|static)[^`'\"\s)]*)\1")


@dataclass(frozen=True)
class BackendRoute:
    method: str
    path: str
    file: str
    line: int
    router_symbol: str


@dataclass(frozen=True)
class FrontendEndpoint:
    kind: str
    url: str
    file: str
    line: int


@dataclass
class Inventory:
    backend_routes: List[BackendRoute]
    frontend_endpoints: List[FrontendEndpoint]
    likely_missing: List[FrontendEndpoint]
    notes: List[str]


def iter_files(base: Path, suffixes: Set[str]) -> Iterable[Path]:
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        rel_parts = set(path.relative_to(base).parts)
        if rel_parts & SKIP_DIRS:
            continue
        yield path


def _const_str(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _decorator_info(deco: ast.AST) -> Optional[tuple[str, str, str]]:
    if not isinstance(deco, ast.Call):
        return None
    func = deco.func
    method = None
    symbol = ""
    if isinstance(func, ast.Attribute):
        method = func.attr.lower()
        if isinstance(func.value, ast.Name):
            symbol = func.value.id
        else:
            symbol = ast.unparse(func.value) if hasattr(ast, "unparse") else "<expr>"
    if method not in HTTP_METHODS:
        return None
    if not deco.args:
        return None
    route_path = _const_str(deco.args[0])
    if not route_path:
        return None
    return method.upper(), route_path, symbol


def scan_backend_routes(base: Path) -> List[BackendRoute]:
    routes: List[BackendRoute] = []
    for path in iter_files(base, BACKEND_SUFFIXES):
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except Exception:
            continue
        rel = str(path.relative_to(base)).replace("\\", "/")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                info = _decorator_info(deco)
                if not info:
                    continue
                method, route_path, symbol = info
                routes.append(BackendRoute(method=method, path=route_path, file=rel, line=getattr(deco, "lineno", node.lineno), router_symbol=symbol))
    return sorted(routes, key=lambda r: (r.path, r.method, r.file, r.line))


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _normalize_frontend_url(url: str) -> str:
    url = url.strip()
    if url.startswith("${") or "${" in url:
        return url
    url = re.sub(r"^https?://[^/]+", "", url)
    url = re.sub(r"^wss?://[^/]+", "", url)
    if "?" in url:
        url = url.split("?", 1)[0]
    if "#" in url:
        url = url.split("#", 1)[0]
    return url or "/"


def scan_frontend_endpoints(base: Path) -> List[FrontendEndpoint]:
    endpoints: List[FrontendEndpoint] = []
    patterns: Sequence[tuple[str, re.Pattern[str]]] = [
        ("fetch", FETCH_RE),
        ("xhr", XHR_OPEN_RE),
        ("websocket", WS_RE),
        ("eventsource", EVENTSOURCE_RE),
        ("literal", LITERAL_ENDPOINT_RE),
    ]
    seen: Set[tuple[str, str, str, int]] = set()
    for path in iter_files(base, FRONTEND_SUFFIXES):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path.relative_to(base)).replace("\\", "/")
        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                raw = match.group("url")
                if not raw:
                    continue
                url = _normalize_frontend_url(raw)
                if not (url.startswith("/") or url.startswith("${")):
                    continue
                line = _line_for_offset(text, match.start())
                key = (kind, url, rel, line)
                if key in seen:
                    continue
                seen.add(key)
                endpoints.append(FrontendEndpoint(kind=kind, url=url, file=rel, line=line))
    return sorted(endpoints, key=lambda e: (e.url, e.file, e.line, e.kind))


def _route_family(path: str) -> str:
    if not path.startswith("/"):
        return path
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "/"
    if parts[0] in {"api", "ws", "static"} and len(parts) > 1:
        return "/" + "/".join(parts[:2])
    return "/" + parts[0]


def _is_dynamic_frontend_url(url: str) -> bool:
    return "${" in url or "+" in url or "`" in url or "{" in url


def find_likely_missing(frontend: List[FrontendEndpoint], backend: List[BackendRoute]) -> List[FrontendEndpoint]:
    backend_paths = {r.path for r in backend}
    backend_families = {_route_family(r.path) for r in backend}
    missing: List[FrontendEndpoint] = []
    for ep in frontend:
        if ep.url.startswith("/static"):
            continue
        if ep.url in {"/health", "/doctor"} and ep.url in backend_paths:
            continue
        if ep.url in backend_paths:
            continue
        family = _route_family(ep.url)
        if family in backend_families:
            continue
        if _is_dynamic_frontend_url(ep.url):
            missing.append(ep)
            continue
        missing.append(ep)
    return missing


def build_inventory(base: Path) -> Inventory:
    backend = scan_backend_routes(base)
    frontend = scan_frontend_endpoints(base)
    missing = find_likely_missing(frontend, backend)
    notes = [
        "This is a static inventory, not a substitute for running the FastAPI app and browser smoke tests.",
        "Family matching treats /api/cameras/123 as covered when /api/cameras exists, but exact route parameters still need manual/API testing.",
        "Dynamic template-string URLs are flagged for review because static matching cannot prove them safe.",
    ]
    return Inventory(backend_routes=backend, frontend_endpoints=frontend, likely_missing=missing, notes=notes)


def print_markdown(inv: Inventory) -> None:
    print("# PubCast Route Inventory\n")
    print("## Notes")
    for note in inv.notes:
        print(f"- {note}")
    print("\n## Backend routes")
    print("| Method | Path | File | Line | Router |")
    print("|---|---|---|---:|---|")
    for r in inv.backend_routes:
        print(f"| {r.method} | `{r.path}` | `{r.file}` | {r.line} | `{r.router_symbol}` |")
    print("\n## Frontend endpoint references")
    print("| Kind | URL | File | Line |")
    print("|---|---|---|---:|")
    for e in inv.frontend_endpoints:
        print(f"| {e.kind} | `{e.url}` | `{e.file}` | {e.line} |")
    print("\n## Likely missing or needs review")
    if not inv.likely_missing:
        print("No likely missing frontend endpoint families found by static scan.")
        return
    print("| Kind | URL | File | Line |")
    print("|---|---|---|---:|")
    for e in inv.likely_missing:
        print(f"| {e.kind} | `{e.url}` | `{e.file}` | {e.line} |")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory backend routes and frontend endpoint calls")
    parser.add_argument("--base", default=".", help="Project root")
    parser.add_argument("--format", choices={"markdown", "json"}, default="markdown")
    args = parser.parse_args()
    base = Path(args.base).resolve()
    inv = build_inventory(base)
    if args.format == "json":
        print(json.dumps(asdict(inv), indent=2))
    else:
        print_markdown(inv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
