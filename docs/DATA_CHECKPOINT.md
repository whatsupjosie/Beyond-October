# Offline host-data checkpoint and recovery

Shared work: [PC-003 and signed progress](https://github.com/whatsupjosie/Beyond-October/issues/1).

The existing launcher, Doctor, recording archives and PubPartner backups remain
their respective authorities. This tool adds an offline recovery copy of **one
explicit host-data directory**. It runs with Python 3.11+ and the standard library,
even when the application dependencies cannot import. It does not start a host,
contact a service, install packages or test either of Claude's environments.

## Scope

Use the exact directory passed to `run_reach.py --data-dir`; its usual default is
`reach_userdata`. Do not assume the repository's seed `data` folder contains the
owner's current work. The checkpoint preserves all regular files beneath the
selected root, including manuscript/relationship records, available media, login
and encryption-key files, SQLite database/WAL/SHM files and empty directories.
File content is preserved byte for byte. Modification times are retained for
files; original ACLs, extended attributes and directory times are not preserved.
Verification proves agreement with the captured bytes; it does not diagnose
pre-existing semantic corruption in every source application/store.

**The archive contains private runtime data and may contain keys. Keep it private;
never commit a real checkpoint to this public repository.** The archive is not
encrypted. Restore creates files with private POSIX modes; Windows ACL behavior
needs actual Windows commissioning.

Outside this scope: browser-only IndexedDB/unsaved capture chunks, files or assets
outside the chosen root, separately configured applications such as Iteration
Wallet, environment-only secrets, source code, model files and installed Python
dependencies. Relative-path portability of every existing subsystem is a separate
acceptance gate. A host-data backup is not a replayable shoot master or a whole
machine image. PC-020 tracks that broader data/dependency map.

## Why the capture is offline

Three approaches were considered:

| Approach | Decision |
| --- | --- |
| Copy a live directory | Reject: a database, its WAL, JSON saves and media could describe different instants. |
| Independently snapshot each live store | Defer: SQLite online backup is useful, but a consistent host-wide result also needs coordinated JSON/media writers and external dependencies. |
| Preserve the entire stopped data tree | Implement: preserves existing store formats and keys without introducing migrations or another runtime state owner. |

Stop **every** process that writes to the selected directory before capture.
`--offline` explicitly confirms that precondition. The tool checks inventory,
file identity/size/timestamps and content hashes again before publication, and
refuses observed changes. These checks are not a global live-writer lock and
cannot prove that an intermittently active process is stopped.

## PowerShell 5 commands

Run from the repository root after stopping the host. Choose a new filename
outside the selected data directory:

```powershell
python tools\pubcast_checkpoint.py create --data-dir .\reach_userdata --output .\PubCast-private-checkpoint.zip --offline
```

Successful output is one JSON receipt with `ok: true`, the archive path, file count,
byte count and the archive's SHA-256. Preserve that receipt separately. If the exact
application revision is known, add `--source-revision REVISION`; an omitted revision
is honestly recorded as unknown.

Verify the whole archive before relying on it:

```powershell
python tools\pubcast_checkpoint.py verify --archive .\PubCast-private-checkpoint.zip
```

For binding to a known external digest, add `--expected-sha256` with the exact
lowercase digest returned at creation. The self-contained manifest detects
accidental corruption. An independently retained trusted digest also detects an
archive whose data and manifest were both replaced; the manifest alone is not
authentication against a deliberate rewrite.

Restore into a **new** container directory:

```powershell
python tools\pubcast_checkpoint.py restore --archive .\PubCast-private-checkpoint.zip --destination .\PubCast-recovered
```

This returns `data_dir`, normally `PubCast-recovered/data`, and a successful
`PUBCAST_RESTORE.json` receipt. After inspecting that result, the existing launcher
can target the restored copy:

```powershell
python run_reach.py --data-dir .\PubCast-recovered\data
```

That final full-host launch/login/media check has **not** been executed in this
engineering environment. The tested product-store reopen uses the real document
and conversation modules, not the complete host or browser.

## Failure behavior and limits

- Output files and restore destinations must be new, including empty existing
  restore folders. Original data is never merged, deleted or overwritten.
- Capture publishes only a fully verified ZIP, using an atomic, non-replacing
  hard link in the output filesystem. Unsupported hard-link filesystems fail
  explicitly; there is no unsafe overwrite fallback.
- Restore verifies the complete inventory before staging. It hashes every file
  again during extraction, reserves the new container with exclusive `mkdir`,
  then moves the complete `data` subtree into that private container.
- A failed extraction removes its temporary staging tree. A failure after
  reserving the output container can leave `.restore-pending.json`; that is not
  a successful receipt. Keep the source archive and retry into a different new
  container after resolving the error.
- Files and supported directories are flushed. Windows directory flushing,
  hardware power loss, unusual filesystems and disk-controller durability are
  not claimed verified. A late flush failure may leave a fully written archive
  while the command still reports failure; verify it explicitly before use.
- Links/junctions/special files, ambiguous Windows names, case/Unicode collisions,
  traversal, duplicate/unlisted ZIP members and invalid hashes are refused.
- Default limits: 100,000 total files/directories, 100 GiB of uncompressed file
  content, 16 MiB manifest. `--max-files` and `--max-bytes` adjust the first two.
  Data streams in 1 MiB chunks; no entire media file is read into memory.
- CLI success returns zero with JSON on stdout. Failure returns two with an
  explicit JSON error on stderr. No data contents or keys are printed.

## Executed verification

Linux, Python 3.12.14:

```powershell
python -m unittest discover -s tests -p test_data_checkpoint.py -v
```

**RAN: 31 passed.** [Exact log](../evidence/recovery-floor-2026-11-01/unittest.log).
Coverage includes same-length corruption, trusted digest mismatch, hostile ZIP
members/paths, resource limits, source mutations, disk-full interruption, publication
failure, competing destinations, actual subprocess CLI use, a committed SQLite WAL
left by an exited process, exact key/media/manuscript bytes, and reopening existing
document/conversation stores at the restored location.

The separate [scale probe](../evidence/recovery-floor-2026-11-01/scale_probe.py)
also ran: **501 files, 67,136,254 bytes**, including a 64 MiB payload restored with
the original path unavailable. The payload hash matched exactly. The observed
3.612-second run is local evidence, not a target-device performance guarantee.

**UNKNOWN / not run:** full-host authenticated restored startup, Windows/PowerShell
execution, actual-device media, large/long-lived production commissioning, live
multi-process snapshots, external-data roots, hard power loss and Claude's two
test environments. No GitHub Actions run was requested.
