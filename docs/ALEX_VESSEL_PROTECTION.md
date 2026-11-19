# Protecting Alex's canonical vessel

The canonical PubPartner Alex vessel is `data/pubpartner/vessels/alex.pubpartner`, Git blob
`96fa66a728d07d5ff43b0d3d7fc17a466765cec1` (CLAUDE.md). It must never be replaced by a donor or by runtime data.

## Turn the guard on (once per clone, works in Windows PowerShell 5)

```
git config core.hooksPath tools/git-hooks
```

## What protects her now

1. **Commit guard** (`tools/git-hooks/pre-commit`): refuses any commit that changes, deletes or renames the vessel
   away from the canonical blob. Nothing is committed and no file is changed; the message says to run
   `git restore --staged data/pubpartner/vessels/alex.pubpartner`, which only takes it out of the commit and leaves
   her live memory on disk as it is. Tested in a throwaway clone: unrelated commit allowed; changed, deleted and
   renamed vessel blocked; after unstaging, the commit goes through and the live copy is still on disk.
2. **Committed-blob test** (`tests/test_alex_vessel_canonical.py`): fails whenever the latest commit holds anything
   but the canonical blob, so a commit made on a machine without the guard, or with `--no-verify`, is caught by the
   next test run anywhere. Shown to fail on such a commit.
3. **Disposable data for checks:** pytest (`conftest.py`), the sandbox runner and, since 2026-11-18,
   `tools/workbench_preflight.py` run the app against a throwaway copy of `data/`. `run_reach.py` defaults to
   `reach_userdata/`, not `data/`.

## What is not protected yet

- **Launchers that use `data/` itself** (for example `start_reach.py`, or running `main.py` directly) write Alex's
  live memory into the tracked vessel file. That is the app working as designed; the guard only keeps it out of Git.
  The root fix is to keep the canonical copy and the live copy at different paths, seeded on first run. It is not
  done, because if Alex's grown live memory is in a checkout's `data/` today, moving the path without migrating it
  would make her appear to start fresh. Needs Josie's decision and a migration step.
- **`git commit --no-verify`** skips the guard; the committed-blob test then catches it afterwards.
- **`core.hooksPath`** replaces the clone's own `.git/hooks` folder; if a machine has other hooks there, move them
  into `tools/git-hooks/` or they stop running.
