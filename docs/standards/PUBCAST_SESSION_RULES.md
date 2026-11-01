# PUBCAST — Session Rules (Compact)
*Load this every session. Full rationale lives in `PUBCAST_ENGINEERING_LESSON.md` — only open that when a rule here is unclear or disputed.*

## 1. Before touching anything
- The local folder/repo as given **is** the program. Preserve it — don't reconstruct, "clean," reorganize, or produce a curated "seed" version unless explicitly asked.
- Messy ≠ broken. Odd filenames, duplicates, legacy code = assume intentional until told otherwise.
- Unsure if something's safe to change/rename/delete? **Stop and ask. Don't guess.**

## 2. Files & repo hygiene
- 3 layers: **Program** (track it) · **Generated** (`__pycache__/`, `target/`, `.venv/` — gitignore, never commit) · **Baggage/backups** (`baggage/`, `*.zip`, `*.bak` — keep on disk, exclude from git unless told otherwise).
- `.gitignore` = stop tracking. **Not** delete from disk. **Not** retroactive history erasure.
- GitHub hard limits: 100 MiB/object via git push, 25 MiB via web upload. Large files → LFS or exclude; don't force it.
- Duplicate/similar files (`file (1).py`, `_backup`, `_final2`) → check imports/refs/timestamps before touching either. Never delete on filename vibes.

## 3. Editing code
- **Never use placeholders** (`// rest unchanged`, `# ...`, `TODO: keep logic`). Full file or an exact anchored diff — a placeholder pasted in is deleted code.
- Fix the bug; don't rewrite the subsystem unless asked to rewrite.
- One state owner per piece of data — don't add a second source of truth for something a governor/session-state module already owns.
- Small, atomic, reversible commits over one giant commit.
- Any destructive/structural change (delete, move, rename, rewrite history) → say so explicitly *before* doing it. Never as a side effect.

## 4. Verification & execution honesty
- No local execution available → say so plainly. Never fabricate logs, JSON state, screenshots, or "it's running" proof.
- "Compiles/imports" ≠ "works." Real check = the actual feature behaving correctly end to end.
- If a tool ran, show real output. If it didn't run, don't imply it did.

## 5. Git / shell safety
- Destructive commands (`git clean`, `git reset`, `rm`) → dry-run first (`-n` / `--dry-run`), show the result, then execute.
- Never casual `git push --force`. Use `--force-with-lease`; if that fails, `git fetch` and reassess before anything stronger.
- After `add` / `commit` / `push` → verify with `status` / `log` / `fetch`. No crash ≠ success.
- PowerShell ≠ Bash: backtick line-continuation, not `\`. One clean copy-pasteable block per command.

## 6. When genuinely ambiguous
Default: **don't act — ask, or flag it and stop.** Never "pick whichever seems cleaner."

---
### Handoff block — paste/fill at the start of a new session or past ~50 turns
```
Branch:
Authoritative dir:
Excluded (local-only): baggage/, .venv/, target/, __pycache__/
Do-not-touch files:
Current task:
```
