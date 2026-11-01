# PubCast First Prime Snapshot Note - 2026-06-18

This build folder is the source for the first canon PubCast Prime snapshot.

Snapshot rule:

- Preserve the construction build non-destructively.
- Create a zip backup outside this folder.
- If a live process locks a transient validation log during compression, skip that locked log only and record it in the snapshot manifest. Do not stop the process and do not delete the file.

Reason:

The first direct zip attempt found a locked Ollama validation stderr log in `codex_validation_outputs`. That is runtime validation output, not source code or build logic.
