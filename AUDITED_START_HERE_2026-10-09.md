# PubCast / Foresight — audited source (October 9 build)

This folder contains **one launchable Reach source tree**, not separate programs to install. Foresight is its primary graphical front door.

## Start

- Windows: extract the **whole folder**, then double-click `OPEN_REACH_WINDOWS.bat`. Keep the batch file next to `main.py`, `run_reach.py`, and `start_reach.py`.
- Linux/macOS: after installing `requirements.txt` in a supported Python environment, run `python3 run_reach.py`.
- Open `http://127.0.0.1:8000/foresight` (or the port reported by the launcher). Create the first owner account; thereafter log in.
- Use Foresight’s fan menu for PubPartner/Alex, direct Character Chat, 2i Writer’s Room, CARE, and original studio/room portals.
- For core-program testing without optional Node utilities: `python3 run_reach.py --no-legacy-2i`. The Node sidecar is supervised by the normal launcher if dependencies can be installed.

**Keep the entire extracted folder intact**, use the launcher rather than bare `uvicorn main:app`, and back up `reach_userdata` separately: the private direct-character transcripts are stored there. Save All Raw/ZIP now includes owner-scoped private character transcripts, but those exports are plaintext, and the separate Alex Google Drive backup does not cover these transcripts.

## What this audit means

The complete `FORESIGHT_COMMISSIONING_AUDIT_2026-10-09.md` names the corrected bugs, tests, remaining security/archival and UI limitations, and unverified external systems. **Tests passing does not mean live AI providers, Google Drive API, Windows hardware, optional 2i Node utilities, or studio camera/voxel/Rust execution have been commissioned.**

The original user-supplied ZIP is unchanged. This is a hardened derivative with one authoritative source copy per active module and one canonical PubPartner federation package.

## Four-round follow-up

The new `FOUR_ROUND_TROUBLESHOOTING_2026-10-09.md` supersedes the prior audit for the specific character identity, transcript-export, concurrency and UI issues. The prior report remains as historical evidence; its statement that private transcripts are not exported is no longer current.
