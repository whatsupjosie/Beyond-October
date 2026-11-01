# Whole-code work-list review — November 1, 2026

Signed: **Codex / ChatGPT Work / recovery-floor-2026-11-01**.
Canonical work and progress: [master list](https://github.com/whatsupjosie/Beyond-October/issues/1).

## What was actually reviewed

Base source commit: `bfbdcf0676c11163063ef369cd419b5667792cfe`.
Its root Git tree: `1395b56de4e20eda1c10b17dfdfec720da8ce2c0`.
Enumerated the complete, non-truncated inventory of **1,702 file blobs** across
the host, modules, frontend, 2i, PubPartner, Iteration Wallet, Blackbox, runtime,
renderer/camera packages, tests, assets, archives and engineering documents.

Compared each current file's Git blob identity with the saved November 1
participant-audio package: **1,661 match exactly; 41 differ or are absent locally**.
Those include deliberate public-repository document/workflow changes and real
recording/media/source differences. Retrieved the current differing `main.py`,
recording/production/media routes and studio recording/storage/render/audio JS
separately for review, rather than treating the later archive as this repository.
The inventory comparison is recorded in the evidence folder.

Read the repository's governing documents and targeted code around startup,
health, persistence, backups, source custody, live/recorded media, 2i/PubPartner,
avatar/set entrypoints, distributed workers, vault integrity and Wallet authority.
Python syntax parsing was performed on available source and the current differing
backend files. This is a **structural and targeted code review**, not a line-by-line
review of every file, a completed security audit, a full runtime acceptance run or
proof that every legacy module is mounted.

## Changes to the shared list

Added PC-020 through PC-034, with source findings, explicit acceptance outcomes
and conditional status where appropriate. Their full descriptions stay in the
canonical issue so two copies cannot drift. Areas covered:

- All data roots, external dependencies, key custody and relocation.
- Cold offline operation of selectable pages and correct licensed dependencies.
- Exact backup isolation; truthful vault damage versus actual byte restoration.
- Resource lifecycles, capability readiness and real degraded-state feedback.
- Independent 2i, PubPartner, Iteration Wallet, waiting-room and avatar acceptance.
- Actual media-worker behavior before offering that optional capability.
- Measured budgets, provenance/installation closure and one complete creative
  workflow from first setup to restored work.

Existing source-master, real native 4K, clacker, shared switcher/mixer and export
requirements stay in the required backlog. They were not moved into optional
ideas. Added eight separately labeled moonshots: federated studios, rehearsal
branches, director coverage assistance, an opt-in render cooperative, long-lived
production capsules, adaptive controls, a painted-set workshop and private
technical failure replay. These are suggestions only, with no commitment.

## Specific source findings and their limits

| Finding | Actual source | Interpretation |
| --- | --- | --- |
| A selectable Set page uses remote Three.js | `static/foresight_programs.js`, `static/pubworld_stage.html` | Offline closure needs an active-entrypoint audit and a cold offline test. Do not relabel every archived demo as broken production. |
| Integrity result can infer restoration from verification failure | `modules/integrity_checker.py::_check_file`, `modules/vault_engine.py::_verify_vault_integrity` | The code sets `restored=not ok`, while the inspected missing/corrupt paths log/reapply protection. Record a runtime reproduction before claiming a repair. |
| Friend backups have best-effort filters | `modules/pubpartner_backup.py::create_friend_backup` | Verify exact two-owner/two-friend scope. Do not call a backup isolated merely because a filename names one person. |
| Wallet has an independent storage/authority boundary | `iteration_wallet/server.py`, `iteration_wallet/gatekeeper.py`, `iteration_wallet/identity.py` | Commission intended local deployment and human-intent checks. No remote exploit has been demonstrated. |
| Worker processors return constant bytes | `modules/evo/distributed_engine.py::_do_voxel_render` and neighboring processors | Offering those job capabilities requires real output and lifecycle proof. This does not erase the narrower preview-pool work. EVO remains owner-gated. |
| Status includes both manager state and import flags | current `main.py`, `/health` system status | Commission configured/available/initialized/working distinctions; import is not runtime readiness. |
| Host-data backup cannot cover independent roots automatically | `run_reach.py`, `run_pubpartner.py`, `iteration_wallet/server.py` | PC-003 is a deliberately explicit offline root checkpoint; PC-020 tracks broader closure. |

## Work delivered alongside the review

PC-003 adds an offline host-data checkpoint, full verification and restore to a
new directory. It preserves existing formats, keys and available source bytes;
it does not change the mixer, switcher, character canon, UI or live host state.
The tested scope and precise failure behavior are in [DATA_CHECKPOINT.md](DATA_CHECKPOINT.md).

**RAN:** 31 focused standard-library checks on Linux/Python 3.12.14, including real
file/SQLite operations, subprocess CLI execution and existing-store reopen.
**Not run:** complete host/browser startup from a restored root, Windows, physical
devices, actual production archives, the full suite or either Claude environment.
No product release/merge is implied by this report.
