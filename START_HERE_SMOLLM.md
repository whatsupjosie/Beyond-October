# PubCast + SmolLM2 — local live integration

This package extends **PubCast_Foresight_FOUR_ROUND_DEBUGGED_2026-10-09**.
It includes the complete SmolLM2 1.7B Instruct Q4_K_M GGUF, CPU runtimes,
the combined PubCast source, and a small-model prompt adapter.

For hosted OpenAI, Gemini or Claude testing without loading SmolLM, read
`HOSTED_ADAPTERS.md` and use the new hosted launcher.

## Start on a computer

Extract the entire ZIP first. Keep its folders together. Install 64-bit Python
3.11 or 3.12 if needed. The first dependency installation needs internet access;
Python and its packages are not bundled. Allow several GB of free disk space
for the ZIP, extracted files and Python environment. RAM and speed depend on
the computer; this has not been benchmarked on your hardware.

- **Windows x64:** double-click `START_SMOLLM_WINDOWS.bat`.
- **Linux x64:** run `bash start_smollm.sh` from a terminal in this folder.

Create your owner account on first launch. The Foresight front door opens;
open PubPartner, or visit `http://127.0.0.1:8000/pubpartner`.
The launcher selects the local model for PubPartner and Writer's Room.
Use Ctrl+C in the launcher terminal to stop both servers.

The GGUF does not need another download. After Python dependencies are installed,
these local inference routes need no cloud model key. Optional online features
remain separate. No account password or personal user conversation is included; validation uses synthetic test messages.

Linux was exercised here. Windows binaries are included but were **not** executed
on Windows. These runtimes do **not** run on Android, ARM or macOS. A phone can
download/store the ZIP, but this is not an Android app. The model file itself can
be copied into an independently compatible GGUF app.

## What the adapter does

The existing authenticated PubPartner spine still selects context, runs Alex,
applies privacy rules, preserves source text and records receipts. For the
launcher-managed SmolLM endpoint only, `modules/smollm_prompt.py` translates the
authorized FCP1 packet to a system message, conversation messages and the exact
current user text. It carries relevant guidance and memory without duplicated
packet serialization and internal numerical diagnostics. Hosted providers have separately audited transports; see HOSTED_ADAPTERS.md.

The browser supplies the last two successful exchanges in its current session.
This short window is held in page memory and resets on reload or account,
session or companion change. Existing persistent memory remains in PubCast.
This is not a new full conversation archive or cross-device history loader.

The adapter never silently truncates source/history: it rejects reference-only
requests and requests whose actual chat-template tokens plus the 512-token reply reserve
and 32-token margin exceed the 8,192-token context. A separate 256 KiB input
safety limit also applies. Use a shorter excerpt if rejected.
SmolLM is small: passing a few live checks does not establish broad reasoning,
creative quality, long-document reliability or complete behavioral compliance.

The model binds to loopback and uses a fresh private API key supplied to Reach
at each launch. The browser receives the model URL but not that key. Reach is
started through its authenticated launcher. Do not expose these ports publicly.

## Scope

Verified wiring covers PubPartner live turns and Writer's Room manuscript
generation. Character Chat's separately configured bots retain their existing
providers; this does not switch every PubCast character to SmolLM. The optional
legacy 2i Node sidecar is disabled by this launcher. Studio devices, deployment,
Windows/phone UI interaction and the original four-round report's open items
remain uncommissioned. This is a usable integration for evaluation, not a claim
that all of PubCast is finished.

## Troubleshooting

Logs: your data directory's `logs/smollm.log` plus launcher terminal output.
If a port is occupied, use `.venv/bin/python run_smollm.py --port 8002
--model-port 8083` on Linux (one line), or `.venv\Scripts\python.exe` on Windows.
The launcher verifies the model SHA-256 every time and stops on a mismatch.
If Linux cannot load a native library, inspect the terminal error; the bundled
runtime is the upstream Ubuntu x64 build, not a universal Linux binary.

Default data directory: `reach_userdata` beside the launcher. If an earlier
installation has an owner secret in `data/secure`, the local launcher reuses
that legacy directory. Keep your existing working
data backed up before pointing this build at it. Existing exports are plaintext;
the historical reports document their restore and retention limitations.

## Provenance and licenses

- Base: four-round build, following UNIFIED → COHESIVE → AUDITED_HARDENED.
- Model: https://huggingface.co/unsloth/SmolLM2-1.7B-Instruct-GGUF
- Original: https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct
- File: `models/SmolLM2-1.7B-Instruct-Q4_K_M.gguf`, 1,055,609,504 bytes.
- SHA-256: `61b6f90dd515fd3bffbd0f6ba716e87555dde77d9b0573a562c2c5e62afc4909`.
- This Hugging Face copy is the requested variant, not a byte-identical copy of
  the inaccessible Drive upload (which reported a slightly different size).
- Model license: Apache 2.0, included under `models/LICENSE-SmolLM2.txt` from
  https://github.com/huggingface/smollm/blob/main/LICENSE.
- llama.cpp CPU runtimes: https://github.com/ggml-org/llama.cpp/releases/tag/b11429
  with included upstream licenses. llama.cpp is the inference runtime; the
  model remains SmolLM2.

See `SMOLLM_VALIDATION.md` and `validation/` for this integration's evidence.
Earlier reports remain historical and do not certify these new changes.
