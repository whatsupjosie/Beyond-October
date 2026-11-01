# Source Reconciliation and Provenance — 2026-10-31
**Branch:** `lead-engineering-control-room-tv-studio-2026-10-31`
**Status:** Structural inventory, not a fully verified file-level byte audit.

## Objective
Locate work and assets that are genuinely absent from `October-24`.
Consolidate useful, compatible work in controlled commits, preserving the
authoritative existing implementation and every project's source provenance.
Do not indiscriminately merge old snapshots or archives.

## Evidence recorded October 31
- The connected GitHub account lists 22 accessible repositories, including
  PubCast source history, 2i, PubPartner, Reach and unrelated creative work.
  They should NOT all be merged into one monorepo.
- The `October-24` integration branch was 130 commits ahead of its own `main`
  and zero behind when compared at mission setup; `main` is not today's work.
- Compared `whatsupjosie/October` main vs the NEW `October-24` branch:
  **210 vs 212 root items**; **zero missing root items** from October.
- Compared the first level of eight differing root directories:
  `.github`, `data`, `docs`, `handoffs`, `modules`, `static`,
  `tests`, `tools`. **Zero missing direct children** of these directories
  in October-24. SHA differences are real and require content review, not
  automatic overwrite.
- Changes were concentrated in newer October-24 implementations:
  24 differing `static` names (19 additional), 12 differing `modules`
  (10 additional), four differing `tests` (30 additional),
  plus new camera/control/2.5D assets, editor and tests.
  These numbers are directory-level GitHub API observations, not a byte audit.
- One more nested level found a concrete path discrepancy:
  `October/static/vendor/three` vs
  `October-24/static/vendor/three-0.160.0`.
  **Action:** inspect JS import URLs and vendored license/version before
  deciding whether a compatibility alias is needed. Do NOT copy older
  Three.js blindly over the versioned runtime.
- `data/avatars`: October-24 additionally has
  `canonical_heights.json`; no October direct children missing.
- `.github/workflows`: October-24 additionally has three
  workflows including `pubcast-25d-integrity.yml`.
- `static/js/avatar` and `static/world/test_avatars` directory
  hashes differ; recursively compare implementation and assets.
- This inventory does **not** prove all nested files and binary assets
  match; run recursive tree/sha checks on every differing directory.

## Potential source repositories requiring selective audit
| Repository | Observed latest push (UTC) | Why consider it | Promotion rule |
|---|---|---|---|
| `whatsupjosie/October` | 2026-10-28 | closest recent older source tree | compare nested paths/hashes and code behavior before copying |
| `whatsupjosie/The-Prime` | 2026-10-27 | design images, room maps, extensive earlier assets/archives, architecture | verify licenses, compare existing assets, avoid older-code regression |
| `whatsupjosie/Wednesday-` | 2026-10-10 | historical integrated Python application and extensive handoff | inspect unique modules and tests, do not replace newer services |
| `whatsupjosie/Pubcast-Reach` | 2026-09-29 | company manifesto, Reach concepts, session rules | use for provenance and only missing compatible code |
| `whatsupjosie/Pub-Partner-Base-Horizon` | 2026-09-07 | cartridge/system source and recent handoff | review against consolidated PubPartner implementation |
| `whatsupjosie/The-Counter-and-2i` | 2026-09-07 | standalone editor/counter concepts/archives | prefer verified current 2i/counter; compare unmerged capabilities |
| `whatsupjosie/Pubcaast-Breaking-Dawn` | 2026-09-07 | older studio brand/video/source bundle | identify original artwork/assets only where needed |
| `whatsupjosie/6.0-` | 2026-07-29 | earlier architecture/code | recover only unique, tested functionality |
| `whatsupjosie/friday` | 2026-06-15 | previous production snapshot | archival comparison only unless gap proven |
| `whatsupjosie/Just-The-Pubcast` | 2026-05-14 | animation and early runtime modules | compare only missing animation assets/capabilities |
| `whatsupjosie/Storage` | 2026-05-15 | historical artifacts | checksum/provenance; no bulk import |
| `whatsupjosie/Pubcast-Phase-2-` and others | earlier | context/ideas | do not promote stale code without a gap |

Observed dates describe repository pushes, **not** the authority or
freshness of every individual file. Some repos may be private or contain
assets restricted to internal use. Do not redistribute protected material.

## Reconciliation protocol for the engineer
1. Clone or otherwise enumerate all accessible relevant roots in a working
   environment; capture commit SHA and revision for each.
2. Compare paths, byte hashes and meaningful module exports, using recursive
   inventories and Git's history rather than file names alone.
3. Classify each candidate: **already present exact**, **present modified**,
   **unique useful**, **unique obsolete**, **asset/license pending**,
   **possible breaking conflict**, or **unknown**.
4. For each `unique useful` item: record repository/path/SHA, destination,
   reason, runtime dependency, licensing status, conflicting live subsystem,
   tests, and rollback plan.
5. Promote in small commits on the new branch; create explicit integrations
   rather than overwrite or duplicate runtime owners.
6. Run tests and interactive acceptance on the promoted functionality.
7. Write to this ledger with real results and unresolved candidates.
8. If access to external files is unavailable, carry on local engineering and
   report the exact missing data/access. **Do not call all files gathered
   until recursive checks and binary inventories are complete.**

## Extra care points
- Existing 3D/GLB asset licenses and copied TV imagery;
  never assume an older repository gives commercial redistribution rights.
- Foresight Counter and 2i v22: preserve completed work and owner-visible saves.
- Control Room: `static/control.html`, `control_room.html`,
  `director_switcher.html`, `control_stations.js`, `control_switcher.js`,
  `camera_rig.js`, `program_audio_runtime.js`, relevant backend routes.
- TV studio: `production25d*.js`, `production25d.html`,
  `studio25d_remote_feed.js`, GLB bridge, media/camera services.
- Existing walkable Bella Faux Pas maps and the real-world studio signage:
  must be preserved, not overwritten by new placeholder artwork.
- Do not assume current text repositories contain every older binary/ZIP.
  Do not transfer a ZIP into production as executable code without inspection,
  decompression, provenance and tests.

## Current reconciliation conclusion
The new October-24 branch is the correct integration landing place.
At the scanned directory levels, `October` is not missing any direct named
items on `October-24`. There are specific differing directories and the
Three.js vendor path change to audit. **Other old repositories have NOT been
fully compared or migrated.** Continue source reconciliation alongside the
primary Control Room/TV engineering work, not instead of it.

## Follow-up inspection — Three.js vendor mismatch
`static/world_walk.html` actually uses import maps referring to the
versioned `/static/vendor/three-0.160.0/build/three.module.js`;
`static/avatar_import.html` and
`static/js/avatar/avatar_import.js` also reference that versioned path.
`static/vendor/three-0.160.0/PROVENANCE.json` records the package version
and source. Thus the renamed vendor tree appears deliberate and consistent
in the inspected entrypoints. Do **not** restore the old `static/vendor/three`
directory merely to match old path names. Continue checking any remaining
dynamic paths/imports in real browser/network tests before marking complete.

## Executed recursive blob inventory — October 31 engineering run

Compared the full, non-truncated Git trees of three donor repositories with source
commit `73ca8bba3acad765c5388ce5b8e56fe37d093a82` (1,670 current blobs).
The complete path, blob SHA, size and classification records are committed under
`evidence/2026-10-31/inventory-*.jsonl`.

| Donor | Source commit | Same path/bytes | Same path/different bytes | Other path/same bytes | Path and bytes absent |
|---|---|---:|---:|---:|---:|
| October | `1d9f48fb1c13f1ba84c7ad6b4a00c8804ae3529a` | 1,490 | 51 | 4 | 1 |
| The-Prime | `ecf01ba0918acaefa6055d0a5cbe22135732e167` | 1 | 8 | 57 | 217 |
| Wednesday- | `bad71e75121a00c0ca5590a883e968ad97483640` | 119 | 110 | 20 | 949 |

The only October file absent both by path and blob identity is
`static/vendor/three/build/three.module.min.js` (670,681 bytes). The active studio
and walker use the versioned Three.js module tree and passed real browser loading.
No older vendor distribution was imported merely to equalize paths.

The-Prime contains archives, historical source, artwork and stock-looking image
filenames whose provenance/rights are not established by a path inventory.
Wednesday- includes many compiled caches and historical backup subtrees; its
unique top-level `modules/care_profile.py` remains a candidate for semantic review.
Neither absent-blob count means that many missing runtime features. No donor code
or binary was bulk-promoted. Other repositories listed above still require review.
