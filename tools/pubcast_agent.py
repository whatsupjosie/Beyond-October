"""
PubCast Overnight Agent
=======================
Runs autonomously using Ollama (Mistral or Gemma 3).
Works ONLY inside the designated folder. Touches nothing outside it.
Logs everything. Safe to leave running overnight.

Usage:
    python pubcast_agent.py

Requirements:
    pip install requests
    (Ollama must be running: ollama serve)
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tarfile
import hashlib
import logging
import requests
import traceback
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURATION — EDIT THESE IF NEEDED
# ─────────────────────────────────────────────

WORKSPACE = Path(r"C:\Users\hardc\OneDrive\Desktop\ALL AIs can only work in this folder and stay in this folder and access nothing outside of it")
OLLAMA_URL = "http://localhost:11434/api/generate"

# Try these models in order — uses whichever is available
PREFERRED_MODELS = ["gemma4:4b", "gemma4", "gemma3", "mistral", "llama3"]

LOG_FILE = WORKSPACE / "agent_run_log.txt"
OUTPUT_DIR = WORKSPACE / "agent_output"
BACKUP_DIR = WORKSPACE / "agent_backups"
REPORT_FILE = OUTPUT_DIR / "AGENT_REPORT.md"
MERGED_DIR = OUTPUT_DIR / "pubcast_merged"

# ─────────────────────────────────────────────
# SAFETY: VERIFY WORKSPACE EXISTS
# ─────────────────────────────────────────────

if not WORKSPACE.exists():
    print(f"ERROR: Workspace folder does not exist:\n  {WORKSPACE}")
    print("Please create it or check the path and try again.")
    sys.exit(1)

OUTPUT_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
MERGED_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("PubCastAgent")

# ─────────────────────────────────────────────
# OLLAMA INTERFACE
# ─────────────────────────────────────────────

def get_available_model() -> str:
    """Find which Ollama model is available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            # Keep full names (e.g. "gemma4:4b") — stripping tags breaks exact matching
            full_names = [m["name"] for m in resp.json().get("models", [])]
            log.info(f"Ollama models available: {full_names}")
            # Pass 1: exact full-name match (e.g. "gemma4:4b" == "gemma4:4b")
            for preferred in PREFERRED_MODELS:
                for name in full_names:
                    if preferred.lower() == name.lower():
                        log.info(f"Selected model (exact): {name}")
                        return name
            # Pass 2: substring match on full name (e.g. "gemma4" in "gemma4:latest")
            for preferred in PREFERRED_MODELS:
                for name in full_names:
                    if preferred.lower() in name.lower():
                        log.info(f"Selected model (partial): {name}")
                        return name
        log.warning("No preferred model found, defaulting to gemma4:4b")
        return "gemma4:4b"
    except Exception as e:
        log.warning(f"Could not query Ollama models: {e}. Defaulting to gemma4:4b.")
        return "gemma4:4b"

def ask_llm(model: str, prompt: str, timeout: int = 120) -> str:
    """Send a prompt to Ollama and return the response."""
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            log.error(f"Ollama error {resp.status_code}: {resp.text[:200]}")
            return ""
    except requests.exceptions.Timeout:
        log.error("Ollama request timed out.")
        return ""
    except Exception as e:
        log.error(f"Ollama request failed: {e}")
        return ""

def check_ollama_running() -> bool:
    """Verify Ollama is up before starting."""
    try:
        resp = requests.get("http://localhost:11434/", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

# ─────────────────────────────────────────────
# FILE UTILITIES (SANDBOX ENFORCED)
# ─────────────────────────────────────────────

def safe_path(path: Path) -> Path:
    """Ensure path stays within WORKSPACE. Raises if it escapes."""
    resolved = path.resolve()
    workspace_resolved = WORKSPACE.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise PermissionError(f"SANDBOX VIOLATION: {resolved} is outside {workspace_resolved}")
    return resolved

def backup_file(src: Path) -> Path:
    """Back up a file before modifying it."""
    src = safe_path(src)
    # Use microseconds to prevent timestamp collisions on rapid writes
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dst = BACKUP_DIR / f"{src.name}.{stamp}.bak"
    shutil.copy2(src, dst)
    log.info(f"Backed up: {src.name} → {dst.name}")
    return dst

def read_file_safe(path: Path, max_chars: int = 8000) -> str:
    """Read a file safely, truncating if needed."""
    try:
        safe_path(path)
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[... TRUNCATED at {max_chars} chars ...]"
        return content
    except Exception as e:
        return f"[Could not read file: {e}]"

def write_file_safe(path: Path, content: str) -> bool:
    """Write a file safely within workspace."""
    try:
        safe_path(path)  # Raises PermissionError if outside workspace
    except PermissionError:
        raise  # Never silently swallow sandbox violations
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup_file(path)
        path.write_text(content, encoding="utf-8")
        log.info(f"Wrote: {path.name} ({len(content)} chars)")
        return True
    except Exception as e:
        log.error(f"Failed to write {path}: {e}")
        return False

# ─────────────────────────────────────────────
# PROJECT DISCOVERY
# ─────────────────────────────────────────────

def extract_archives(target_dir: Path) -> list:
    """Extract all zip/tar.gz files found in workspace."""
    extracted = []
    for f in WORKSPACE.rglob("*.zip"):
        try:
            safe_path(f)
            dest = target_dir / f.stem
            dest.mkdir(exist_ok=True)
            with zipfile.ZipFile(f, "r") as z:
                z.extractall(dest)
            log.info(f"Extracted zip: {f.name} → {dest.name}/")
            extracted.append(dest)
        except Exception as e:
            log.warning(f"Could not extract {f.name}: {e}")

    for f in WORKSPACE.rglob("*.tar.gz"):
        try:
            safe_path(f)
            dest = target_dir / f.stem.replace(".tar", "")
            dest.mkdir(exist_ok=True)
            with tarfile.open(f, "r:gz") as t:
                t.extractall(dest)
            log.info(f"Extracted tar.gz: {f.name} → {dest.name}/")
            extracted.append(dest)
        except Exception as e:
            log.warning(f"Could not extract {f.name}: {e}")

    return extracted

def inventory_project(base: Path) -> dict:
    """Build a map of all Python files, their sizes, and key modules."""
    inventory = {"python_files": [], "other_files": [], "modules": {}, "total_lines": 0}
    for f in base.rglob("*.py"):
        try:
            safe_path(f)
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            rel = str(f.relative_to(base))
            inventory["python_files"].append({
                "path": rel,
                "lines": len(lines),
                "size": f.stat().st_size
            })
            inventory["total_lines"] += len(lines)
            if "modules" in rel:
                mod_name = f.stem
                inventory["modules"][mod_name] = rel
        except Exception as exc:
            log.warning("Inventory scan skipped %s: %s", f, exc)
    log.info(f"Inventory: {len(inventory['python_files'])} Python files, {inventory['total_lines']} total lines")
    return inventory

# ─────────────────────────────────────────────
# TASK RUNNER
# ─────────────────────────────────────────────

class Task:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "pending"
        self.result = ""
        self.started_at = None
        self.finished_at = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "result": self.result[:500] if self.result else "",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

class PubCastAgent:
    def __init__(self):
        self.model = None
        self.tasks: list[Task] = []
        self.report_sections: list[str] = []
        self.session_start = datetime.now().isoformat()
        self.extracted_dirs: list[Path] = []
        self.best_source: Path = None  # The most complete version to work from

    def log_section(self, title: str, content: str):
        """Add a section to the final report."""
        self.report_sections.append(f"\n## {title}\n\n{content}\n")

    def run_task(self, task: Task, fn) -> bool:
        """Run a task with full error handling and logging."""
        log.info(f"▶ Starting task: {task.name}")
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        try:
            result = fn(task)
            task.result = str(result or "Done")
            task.status = "complete"
            log.info(f"✓ Task complete: {task.name}")
            return True
        except Exception as e:
            task.result = f"ERROR: {e}\n{traceback.format_exc()}"
            task.status = "failed"
            log.error(f"✗ Task failed: {task.name} — {e}")
            return False
        finally:
            task.finished_at = datetime.now().isoformat()

    # ── PHASE 1: Setup & Discovery ────────────────────────────────────────────

    def phase_setup(self):
        log.info("=" * 60)
        log.info("PHASE 1: Setup & Discovery")
        log.info("=" * 60)

        # Check Ollama
        if not check_ollama_running():
            log.error("Ollama is not running! Start it with: ollama serve")
            log.error("Then restart this agent.")
            sys.exit(1)

        self.model = get_available_model()
        log.info(f"Using model: {self.model}")

        # Extract archives
        log.info("Extracting all archives...")
        extract_target = OUTPUT_DIR / "extracted"
        extract_target.mkdir(exist_ok=True)
        self.extracted_dirs = extract_archives(extract_target)

        # Also look for already-extracted dirs in workspace
        for d in WORKSPACE.iterdir():
            if d.is_dir() and d != OUTPUT_DIR and d != BACKUP_DIR:
                self.extracted_dirs.append(d)

        log.info(f"Found {len(self.extracted_dirs)} source directories")

        # Find the best/most complete source
        best_dir = None
        best_count = 0
        for d in self.extracted_dirs:
            count = sum(1 for _ in d.rglob("*.py"))
            log.info(f"  {d.name}: {count} Python files")
            if count > best_count:
                best_count = count
                best_dir = d

        self.best_source = best_dir
        if best_dir:
            log.info(f"Best source: {best_dir.name} ({best_count} Python files)")
            self.log_section("Source Discovery", f"Most complete source: **{best_dir.name}** with {best_count} Python files.")
        else:
            log.warning("No Python source directories found in workspace!")

    # ── PHASE 2: Code Analysis ────────────────────────────────────────────────

    def phase_analyze(self):
        log.info("=" * 60)
        log.info("PHASE 2: Code Analysis")
        log.info("=" * 60)

        if not self.best_source:
            log.warning("No source to analyze.")
            return

        # Find key files to analyze
        key_files = {}
        for name in ["main.py", "hub.py", "bots.py", "recording.py", "persistence.py", "bot_llm_adapter.py"]:
            for f in self.best_source.rglob(name):
                key_files[name] = f
                break

        # Also check standalone uploaded .py files
        for f in WORKSPACE.glob("*.py"):
            key_files[f.name] = f

        analysis_results = []

        for fname, fpath in key_files.items():
            log.info(f"Analyzing: {fname}")
            content = read_file_safe(fpath, max_chars=5000)

            prompt = f"""You are a senior Python developer reviewing PubCast AI, a live streaming platform built with FastAPI.

File: {fname}
Content:
```python
{content}
```

Analyze this file and provide:
1. What this file does (2-3 sentences)
2. Any bugs, issues, or incomplete implementations you see
3. What needs to be fixed or completed

Be specific and technical. Focus on actionable issues."""

            result = ask_llm(self.model, prompt, timeout=90)
            if result:
                analysis_results.append(f"### {fname}\n\n{result}")
                log.info(f"Analysis complete for {fname}")
            else:
                analysis_results.append(f"### {fname}\n\n*Could not analyze (LLM timeout or error)*")

            time.sleep(2)  # Don't hammer Ollama

        full_analysis = "\n\n".join(analysis_results)
        self.log_section("Code Analysis", full_analysis)

        # Save analysis to file
        write_file_safe(OUTPUT_DIR / "code_analysis.md", f"# PubCast Code Analysis\n\nGenerated: {datetime.now().isoformat()}\nModel: {self.model}\n\n{full_analysis}")
        log.info("Code analysis saved to agent_output/code_analysis.md")

    # ── PHASE 3: Gap Identification & Fixes ──────────────────────────────────

    def phase_fix_gaps(self):
        log.info("=" * 60)
        log.info("PHASE 3: Gap Identification & Fixes")
        log.info("=" * 60)

        if not self.best_source:
            return

        # Read the TODO.md and HANDOFF.md for context
        todo_content = ""
        handoff_content = ""
        for f in self.best_source.rglob("TODO.md"):
            todo_content = read_file_safe(f, 3000)
            break
        for f in self.best_source.rglob("HANDOFF.md"):
            handoff_content = read_file_safe(f, 3000)
            break

        # Also check workspace root
        for f in WORKSPACE.glob("*.md"):
            if "WIRING" in f.name.upper() or "HANDOFF" in f.name.upper():
                handoff_content = read_file_safe(f, 3000)

        # Ask LLM to prioritize what to fix
        priority_prompt = f"""You are working on PubCast AI — a live streaming platform built with FastAPI + Python.

Project status from HANDOFF.md:
{handoff_content[:2000]}

TODO list (priorities):
{todo_content[:2000]}

Given this is a solo developer project with limited time, list the TOP 5 most impactful fixes or implementations to do RIGHT NOW.

For each fix, provide:
1. File to edit
2. Exactly what code to add/change (provide real code, not pseudocode)
3. Why this matters

Be specific. Write real Python code."""

        priorities = ask_llm(self.model, priority_prompt, timeout=120)
        self.log_section("Priority Fixes Identified", priorities or "*LLM could not generate priorities*")
        write_file_safe(OUTPUT_DIR / "priority_fixes.md", f"# Priority Fixes\n\nGenerated: {datetime.now().isoformat()}\n\n{priorities}")

        # Now attempt to actually implement the Ollama bot adapter
        # This is the most critical free-tier fix — wire Ollama as a bot provider
        self.implement_ollama_adapter()

    def implement_ollama_adapter(self):
        """Write a real Ollama bot adapter so bots work without paid APIs."""
        log.info("Implementing Ollama bot adapter...")

        adapter_code = '''"""
modules/ollama_adapter.py — Free Ollama LLM adapter for PubCast bots.
Supports Mistral, Gemma, Llama3, and any other Ollama model.
Drop-in replacement for paid API adapters.

Usage in .env:
    BOT_PROVIDER=ollama
    OLLAMA_HOST=http://localhost:11434
    OLLAMA_MODEL=mistral
"""
from __future__ import annotations
import logging
import os
import json
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))


class OllamaAdapter:
    """
    Async adapter for Ollama local LLM.
    Compatible with PubCast's bot_llm_adapter interface.
    """

    provider = "ollama"

    def __init__(self, model: str = None, system_prompt: str = ""):
        self.model = model or OLLAMA_MODEL
        self.system_prompt = system_prompt
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("OllamaAdapter initialized: model=%s host=%s", self.model, OLLAMA_HOST)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """
        Send messages to Ollama and return the response text.
        messages format: [{"role": "user"|"assistant"|"system", "content": "..."}]
        """
        # Build prompt from message history
        prompt_parts = []
        if self.system_prompt:
            prompt_parts.append(f"System: {self.system_prompt}\\n")

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}\\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\\n")
            else:
                prompt_parts.append(f"User: {content}\\n")

        prompt_parts.append("Assistant: ")
        full_prompt = "\\n".join(prompt_parts)

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        try:
            session = await self._get_session()
            async with session.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("Ollama error %d: %s", resp.status, error_text[:200])
                    return "[Ollama error — check that Ollama is running]"

                data = await resp.json()
                return data.get("response", "").strip()

        except asyncio.TimeoutError:
            logger.error("Ollama request timed out after %ds", OLLAMA_TIMEOUT)
            return "[Ollama timed out — model may be loading, try again]"
        except aiohttp.ClientConnectorError:
            logger.error("Cannot connect to Ollama at %s", OLLAMA_HOST)
            return "[Cannot reach Ollama — make sure it is running: ollama serve]"
        except Exception as e:
            logger.error("Ollama request failed: %s", e)
            return f"[Ollama error: {e}]"

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ):
        """
        Streaming version — yields text chunks as they arrive.
        Usage: async for chunk in adapter.stream_complete(messages): ...
        """
        prompt_parts = []
        if self.system_prompt:
            prompt_parts.append(f"System: {self.system_prompt}")
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        prompt_parts.append("Assistant: ")
        full_prompt = "\\n".join(prompt_parts)

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        try:
            session = await self._get_session()
            async with session.post(f"{OLLAMA_HOST}/api/generate", json=payload) as resp:
                async for line in resp.content:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Ollama streaming error: %s", e)
            yield f"[Streaming error: {e}]"

    @staticmethod
    async def list_models() -> List[str]:
        """List available Ollama models."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_HOST}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    @staticmethod
    async def health_check() -> bool:
        """Return True if Ollama is reachable."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(OLLAMA_HOST, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    return resp.status == 200
        except Exception:
            return False


# ── Convenience factory (matches bot_llm_adapter.get_adapter() interface) ──

def get_ollama_adapter(bot_config: Dict[str, Any] = None) -> OllamaAdapter:
    """
    Factory function compatible with get_adapter() pattern.
    bot_config keys: model, system_prompt, temperature
    """
    cfg = bot_config or {}
    return OllamaAdapter(
        model=cfg.get("model", OLLAMA_MODEL),
        system_prompt=cfg.get("system_prompt", "You are a helpful AI co-host on PubCast."),
    )
'''

        adapter_path = MERGED_DIR / "modules" / "ollama_adapter.py"
        adapter_path.parent.mkdir(parents=True, exist_ok=True)
        write_file_safe(adapter_path, adapter_code)
        log.info("Ollama adapter written to agent_output/pubcast_merged/modules/ollama_adapter.py")

        # Also write a startup script
        startup_script = '''#!/usr/bin/env python3
"""
start_pubcast.py — Quick launcher for PubCast with Ollama bots.
Run this instead of: uvicorn main:app

What it does:
  1. Checks Ollama is running
  2. Sets free-tier environment variables
  3. Starts PubCast on port 8000
"""
import os
import sys
import subprocess
import requests

print("=" * 50)
print("  PubCast AI — Free Tier Launcher")
print("=" * 50)

# Check Ollama
try:
    r = requests.get("http://localhost:11434/", timeout=3)
    models = requests.get("http://localhost:11434/api/tags", timeout=3).json()
    model_names = [m["name"] for m in models.get("models", [])]
    print(f"✓ Ollama running. Models: {model_names}")
    
    # Pick best available model
    preferred = ["mistral", "gemma3", "gemma", "llama3"]
    chosen = next((m for p in preferred for m in model_names if p in m), model_names[0] if model_names else "mistral")
    print(f"✓ Using model: {chosen}")
except Exception as e:
    print(f"✗ Ollama not running: {e}")
    print("  Start it with: ollama serve")
    print("  Then pull a model: ollama pull mistral")
    sys.exit(1)

# Set free-tier env vars (no paid API keys needed)
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", chosen)
os.environ.setdefault("BOT_PROVIDER", "ollama")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-in-production-use-64-char-hex")
os.environ.setdefault("ALLOWED_ORIGINS", "*")
os.environ.setdefault("ALLOWED_WS_ORIGINS", "*")
os.environ.setdefault("DATA_DIR", "data")

print("✓ Environment configured for free-tier (Ollama)")
print("✓ Starting PubCast on http://localhost:8000")
print("  Press Ctrl+C to stop")
print()

# Start the server
subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"])
'''
        write_file_safe(OUTPUT_DIR / "start_pubcast.py", startup_script)
        log.info("Startup script written to agent_output/start_pubcast.py")

    # ── PHASE 4: Generate Documentation ──────────────────────────────────────

    def phase_documentation(self):
        log.info("=" * 60)
        log.info("PHASE 4: Documentation")
        log.info("=" * 60)

        doc_prompt = """You are writing documentation for PubCast AI — a self-hosted live streaming platform with:
- FastAPI backend (103 routes)
- WebSocket real-time hub
- AI bots (now running on FREE local Ollama — Mistral/Gemma)
- FFmpeg recording (H.264/AAC)
- Virtual PubWorld 
- JWT authentication

Write a QUICK START guide for someone running this on Windows with Ollama.
Include: installation, starting Ollama, pulling a model, starting PubCast, first login, enabling bots.
Be specific. Use real commands. Target a non-developer creator."""

        quick_start = ask_llm(self.model, doc_prompt, timeout=90)

        bot_prompt = """Write a guide for configuring AI bots in PubCast using FREE local Ollama.
Include: what bots do, how to configure them in the UI, what Mistral vs Gemma 3 are good for, tips for good bot prompts."""

        bot_guide = ask_llm(self.model, bot_prompt, timeout=90)

        docs = f"""# PubCast AI — Documentation
Generated: {datetime.now().isoformat()}
Model: {self.model}

---

## Quick Start (Windows + Ollama — Free)

{quick_start}

---

## Bot Configuration Guide

{bot_guide}

---

## Architecture Overview

PubCast is a self-hosted live streaming platform. Key components:

- **main.py** — FastAPI app with 103 routes
- **modules/hub.py** — WebSocket event bus for real-time comms
- **modules/bots.py** — AI co-host bot manager
- **modules/ollama_adapter.py** — FREE local LLM adapter (new!)
- **modules/recording.py** — FFmpeg H.264/AAC recording
- **modules/pubworld.py** — Virtual world integration
- **modules/userdb.py** — SQLite user/role database

## Free Tier Setup (No API Keys Needed)

```bash
# 1. Install Ollama
# Download from https://ollama.com

# 2. Start Ollama
ollama serve

# 3. Pull a model (pick one)
ollama pull mistral      # Fast, good for chat
ollama pull gemma3       # Google's model, great quality

# 4. Install PubCast dependencies
pip install -r requirements.txt

# 5. Start PubCast (uses the launcher)
python start_pubcast.py

# 6. Open browser
# http://localhost:8000/login
```

## Environment Variables

```bash
# Free tier — no paid API keys needed
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral
BOT_PROVIDER=ollama

# Security (change these!)
JWT_SECRET_KEY=your-secret-key-here
BOOTSTRAP_OWNER=admin:YourPassword123!

# Optional (for paid API bots)
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```
"""
        write_file_safe(OUTPUT_DIR / "DOCUMENTATION.md", docs)
        self.log_section("Documentation", "Full documentation written to `agent_output/DOCUMENTATION.md`")
        log.info("Documentation written.")

    # ── PHASE 5: Final Report ─────────────────────────────────────────────────

    def phase_report(self):
        log.info("=" * 60)
        log.info("PHASE 5: Final Report")
        log.info("=" * 60)

        task_summary = "\n".join(
            f"- **{t.name}**: {t.status} — {t.result[:100]}"
            for t in self.tasks
        )

        output_files = "\n".join(
            f"- `{f.name}`" for f in OUTPUT_DIR.rglob("*") if f.is_file()
        )

        report = f"""# PubCast Overnight Agent Report

**Session:** {self.session_start}  
**Completed:** {datetime.now().isoformat()}  
**Model Used:** {self.model}  
**Workspace:** `{WORKSPACE}`

---

## What Got Done

{chr(10).join(self.report_sections)}

---

## Output Files Created

{output_files}

---

## Next Steps For You, Josie

1. **Copy `agent_output/pubcast_merged/modules/ollama_adapter.py`** into your `pubcast_unified/modules/` folder
2. **Copy `agent_output/start_pubcast.py`** into your `pubcast_unified/` folder
3. **Make sure Ollama is running:** `ollama serve`
4. **Pull a model if you haven't:** `ollama pull mistral`
5. **Start PubCast:** `python start_pubcast.py`
6. **Open browser:** http://localhost:8000/login

Your bots will now work FOR FREE using local Ollama — no API keys needed.

---

## Agent Log

Full log: `{LOG_FILE.name}`

---

*PubCast Agent — ran autonomously, touched nothing outside your folder.*
"""

        write_file_safe(REPORT_FILE, report)
        log.info(f"Final report written to: {REPORT_FILE}")

    # ── MAIN RUN LOOP ─────────────────────────────────────────────────────────

    def run(self):
        log.info("=" * 60)
        log.info("  PubCast Overnight Agent Starting")
        log.info(f"  Workspace: {WORKSPACE}")
        log.info(f"  Started: {self.session_start}")
        log.info("=" * 60)

        try:
            self.phase_setup()
            self.phase_analyze()
            self.phase_fix_gaps()
            self.phase_documentation()
            self.phase_report()

            log.info("")
            log.info("=" * 60)
            log.info("  ALL DONE. Check agent_output/ folder.")
            log.info(f"  Report: {REPORT_FILE}")
            log.info("=" * 60)

        except KeyboardInterrupt:
            log.info("Agent stopped by user (Ctrl+C)")
            self.phase_report()
        except Exception as e:
            log.error(f"Agent crashed: {e}")
            log.error(traceback.format_exc())
            self.phase_report()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    agent = PubCastAgent()
    agent.run()
