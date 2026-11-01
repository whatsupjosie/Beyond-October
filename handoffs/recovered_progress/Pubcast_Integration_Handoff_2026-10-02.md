# Pubcast recovery and integration handoff

Audit date: 2026-10-02. Work window: August–September 2026, with older donors retained where recent work refers to them.

## The result

There is substantial saved progress, and much of it is already inside the latest sealed release. There are also concrete gaps between saved handoffs and that release. This audit preserves the source bytes and separates those cases so the next engineering session can integrate specific work rather than restart archaeology.

The latest sealed build located is the September 28 Round9 Corner Audited release, copied unchanged as `01_Current_Build.zip`.

SHA-256: `9c847322844b9f0269e4022f68741b4ed2c5e5792380e18f5ebfa38bdb368951`.

933 ZIP entries, 12,235,556 bytes. Its ZIP CRC check passed. This is the best evidenced release baseline found, **not proof that every earlier repair made it into the release or that it matches a machine currently running Pubcast**. The September 29 GitHub updates are sparse source/reference and Spark staging updates; they do not establish a newer complete, accepted build.

The three recovery files are:

1. `01_Current_Build.zip`: the exact sealed baseline. Do not modify this rollback artifact.
2. `02_Recent_Progress_To_Integrate.zip`: this handoff, a 62-item progress register, copied design/implementation candidates, and integration evidence. Start here for engineering.
3. `03_Sources_Still_To_Review.tar.zst`: the expanded copied source collection, original builds, branch/source metadata, hash comparisons, and the explicit remaining review/acquisition queue. This is a recovery archive, not a runnable release.

The handoff is also supplied separately for immediate reading. No Pubcast source was changed, merged, or deployed by this audit.

## What was checked and collected

Discovery checked the connected GitHub repository inventory: 20 repositories, branch/head metadata for 19 nonempty repositories, and complete recursive trees for 18 August–September branch heads across six recently active repositories. Branch histories since August 1 and pull-request/issue collections for those six repositories were checked; those collection responses did not reach their page limits. The one substantive PR found is NowCurtsey #2; its author claims are preserved separately from the independent readiness HOLD audit.

The recent branch coverage includes:

| Repository | Relevant work recovered |
|---|---|
| The-Prime | Assembled/flat source generations, donor UI/bridge/memory material |
| The-Counter-and-2i | August backend and September notebook-dominant Writer’s Room iterations |
| Pubcaast-Breaking-Dawn | Hubcast assembly, PEQ/CRE-EQ, take-manager and BOM corrections |
| NowCurtsey-Build | LMStudio/source uploads, PR2 assembly, role slots, Spark/UI staging |
| Pub-Partner-Base-Horizon | Portable/resident runtime, federation/sync/concurrency/manuscript changes |
| Pubcast-Reach | Canonical-program/Conversation Ownership references and September 29 working-file uploads |

Additional collection copied 510 distinct GitHub payloads not byte-identical to baseline source: 508 UTF-8 blobs verified against their Git blob SHA, plus two non-UTF-8 JavaScript files recovered exactly from already copied archives by matching Git blob SHA. Exact-current references are recorded separately; a different blob is a comparison candidate, not automatically a missing feature.

The saved-file inventory pass paged through 496 August–September nonmedia records and selected 213 additional code/design records beyond the first recovery collection. All 213 selected downloads were checked against their reported byte sizes. Original account/file identities and dates are retained in the source indices.

Drive discovery checked recent project documents and relevant project folders, including Pubcast source/build folders, PubPartner code/tests/cartridge folders, and 2i material. The expanded archive retains 56 project-related Drive records: original ZIPs, loose Python, actual handoffs, PowerShell stack helpers, UI prototypes, exported design documents and saved conversation PDFs. Identical copies retain separate provenance but need not be treated as separate accomplishments. Unrelated material from a mixed Downloads folder is excluded from the recovery package.

The archive/member comparison contains 24,053 source/member references. 17,549 references match current file bytes, covering **892 distinct current-build files**. Repeated build ZIPs explain the much larger reference count. This is preservation evidence, not a count of fixes or proof that each matched file has a live caller. The other 41 current files are not thereby proven wrong or unpreserved.

2,136 unique nonmatching collected payloads are indexed for review. Many are older versions, reports, examples or superseded designs. Do not bulk-merge this queue.

All selected outer source ZIPs passed CRC checking. Nested ZIPs remain preserved inside their original packages; the member comparison is not a claim that every nested binary/vendor artifact was recursively understood. Machine inventories and hash matches are broader than the function-level review.

## The material integration gap found tonight

The September 13 camera handoff and accepted `CAMERA_RENDERER_CONTRACT_V1.md` describe a camera-authority repair. The September 28 sealed build does **not** contain that repaired shape.

| Saved September 13 claim | Observed sealed September 28 source | Required action |
|---|---|---|
| TwinEngine receives canonical CameraManager in full-host mode | `TwinEngineService.__init__` has no `camera_manager` argument; it seeds its own main/wide/closeup/overhead registry | Reconcile one full-host camera authority |
| AdvancedCameraManager is preserved but not booted | `main.py` still constructs it and stores it in application state | Establish consumers/registry contract, then quarantine the duplicate authority as intended |
| Canonical camera changes emit CameraSwitchEvent | Current `modules/cameras.py` setters do not contain the documented event contract | Restore or explicitly reconstruct event behavior with idempotent/invalid-switch tests |
| Supported REGISTER_CAMERA / SWITCH_PROGRAM / SWITCH_PREVIEW / PTZ commands are used | TwinEngine still sends ACTIVATE_CAMERA / UPDATE_CAMERA; its send helper ignores a false return | Adapt vocabulary and propagate actual rejection |
| Pete distinguishes avatar-motion WebSocket connection from real voxel rendering | `get_twin_engine_status()` still permits `voxel_renderer_connected` plus FPS to imply `voxel_renderer_operational` | Report transport connectivity and pixel-render evidence separately |
| Authenticated Rust camera transport, CameraFleet and Windows gate are prepared | Named transport/script/CameraFleet implementation was not found in the seal or collected source/member census | Recover original implementation or explicitly reconstruct from preserved contracts; never call it recovered original code |

Evidence locations in the sealed build: `main.py` advanced-camera startup; `modules/cameras.py` program/preview setters; `modules/twin_engine_service.py` constructor/startup/activate/update/send helpers; `modules/pete_enhanced.py` renderer status calculation. Preserved documentary evidence: `PUBCAST_REACH_BUILD_HANDOFF_LATEST.md` within the earlier handoff packages, September 13 handoff copies, `CAMERA_RENDERER_CONTRACT_V1.md`, `RUST_CAMERA_CONTROL_RUNBOOK_2026-09-13.md`, and `GPU_CAMERA_STAGE2_ASSESSMENT_2026-09-13.md`.

**Conclusion:** the documented repair is absent from this release. This audit cannot establish whether it was deliberately superseded, accidentally dropped, or never saved into an updated distributable. It can establish the source mismatch. The implementation must not be reported as integrated based on the handoff alone.

The copied September 13 snapshot and its hash record are retained; they do not supply the later named Rust transport files. Existing preserved camera-brain reconstruction is a separate system and cannot be substituted for CameraFleet by name.

## Progress that is already preserved

The detailed register is `PROGRESS_REGISTER.md`, with CSV and JSON versions. The JSON associates work items with copied source paths, original GitHub paths/commits and content hashes. Status `IN_CURRENT` means the relevant source/caller was located; it does not certify a live production deployment.

Major preserved work includes:

- The consolidated Reach host and actual module tree; no need to replace it with a donor main.py.
- Alex affect evaluation, personal baseline/prior persistence through MemoryCore, low-confidence battery guards and response operating notes. `modules/affect_wiring.py` is expressly deprecated duplicate wiring; reactivating it would double-evaluate and introduce competing persistence.
- Universal character memory, Thinking Context, runtime spine, Bubble Stack routes and Room Conductor’s bubble provider.
- Jeremy text/content fallback, Hub identity/presence tracking and live chat callbacks.
- Pete compatibility repair, shared bridge activation, voxel asset preload/sync and graceful degradation.
- Avatar performer background connection, Rust avatar-motion transport, GLB retargeter/browser consumer and Sheila asset. A visible complete avatar/world path still needs acceptance.
- Recording artifact registration, real ffmpeg transcode/export, BlackBox witness wiring and conversation archive/search/export.
- PubPartner cartridges/portable runtime sequencing, federation source and tests, per-role model slots, provider/routing scaffolding and Writer’s Room namespace isolation.
- Foresight/2i bridge source, World Chat convergence, manuscript ownership, explicit commit behavior and Conversation Ownership work.
- September 23–24 chat/privacy work and system-Purfluous retirement while retaining the character.
- Round5 fresh-owner/auth setup, built-in character seeding, actual-port/doctor checks; Rounds6–8 entrypoint/dependency/auth cleanup; Round9 Ollama contract, false IRM FPS fix, EVO/IRM integration, UDP receive correction, controller checks and exact recovered launchers.

The preserved federation is a separate runnable service tree; source presence is not evidence that the current host invokes the intended deployed service. The role-slot implementation similarly does not prove that all real provider credentials/models are configured and accepted.

## Copied work requiring integration or a deliberate donor decision

| Work | What is actually available | Integration boundary |
|---|---|---|
| EQ evaluation recorder | September 28 complete design handoff; existing BlackBox and archive source | Instrument current message/evaluation path before extended EQ trials |
| PEQ + CRE-EQ | Exact September 7 donor modules, registry/retrieval/broker/tests and import correction | Isolated comparison against active Affect/Alex; preserve thin signal isolation |
| Take manager | September 7 source candidate and its surrounding routes/tests | Compare canonical recording/take authority, then port missing behavior |
| Camera authority/control work | Accepted contracts, detailed handoffs, old implementations; later named Rust implementation not recovered | Fix source divergence, then compile/control/frame gates |
| GPU/scene/capture | Real renderer donors, CPU rasterizer, camera brain, PubWorld/MediaRecorder candidates | Prove real scene + camera revision -> pixels -> recording artifact |
| Sheila/animation | Assets, rig audit/mapping, retarget scripts and standalone moving-rig/walk viewers | Bind to live stage/performer path; standalone proof is not final UI integration |
| 2.5D stage | Original spec and extensive corrective review | Build reviewed V1 slice, not the uncorrected pasted implementation |
| Conversation Core v2 / Sheer | September 28–29 research/decision documents, historical Wired sources | Minimal contracts + selective reconstruction in a disposable lab |
| Personal Cricket Corps | September 22 revised addendum and original discussion/design packet | Session-bound liaison scope, explicit authorization and current identity services |
| Conversation vault | Staged plan claiming synthetic-tested Stage1; named offline source was not recovered | Recover/reconstruct source, test real account export, then add raw capture at current archive write point |
| RVF supervisor | Actual PowerShell secret/setup/stack scripts and README | Adapt paths, credentials and health probes to sealed release |
| UI refinements | Sprite/Cricket notes, 2i prototypes, collaborative editor and Spark assignment copies | Compare current UI, produce visible reviewable improvements |
| Theory/Evidence bridge | Preserved incubating implementation and underlying graph/evidence/contradiction source | Review invented weighting policy and current EVO caller before promotion |
| Wired companion mechanisms | Preserved pacing/acceptance/meaning/avatar donors | Extract justified behavior; whole branch contains stub/default-mock and package-import problems |

PEQ’s presence in a donor does not make its clinical labels validated truth or a current Pubcast authority. The NowCurtsey PR2 import/BOM repair is real recovery work; its pinned revision’s readiness audit remains HOLD and describes room disclosure, authorization, lifecycle and false-effect issues. Do not carry those problems into Reach along with the useful code. Do not automatically relabel donor-specific findings as current Reach defects either.

Spark is staged assignment material, not evidence that Spark finished the assignment. Saved prompts and selected source copies are explicitly separated from integrated runtime work.

## Integration order and definitions of done

### Task 0 — Establish a reproducible branch from the seal

Create an isolated working checkout from `01_Current_Build.zip`. Record the baseline SHA above, the current source tree hash and the environment. Do not overlay an entire old ZIP. Preserve the source-safe release policy and keep user data outside the source tree.

Install the declared Python development requirements and root/2i Node manifests in an environment with those dependencies available. Establish test results on the exact baseline before modifying it. Pin the actual deployment’s current build identity when deployment work begins; this audit only selected a saved release.

Done: reproducible dependency installation, baseline test report, recorded route inventory and rollback snapshot. A suite failure must be compared by test name and behavior, not just total count.

### Task 1 — Add the EQ evidence recorder to current authorities

Read the preserved `PUBCAST_EQ_DEV_MONITORING_HANDOFF_2026-09-28.md` in full. Use `modules/conversation_archive.py`/routes, the finalized Hub/provider turn path, `modules/alex_core.py` affect evaluation and `modules/blackbox_runtime.py` witness seam. BlackBox remains independent evidence, not conversation/UI authority.

Implement session manifest, exact two-sided messages, observed telemetry, affect mathematical trace, interpretation/intervention trace, provider pipeline and outcomes/reviews. Preserve build/model/schema versions, event IDs and hashes. Views should index immutable evidence rather than mutable copies. Missing typing start/end means typing rate is unknown; elapsed time between messages is not typing speed.

Keep observation, inference and intervention distinct. Full internal evidence belongs in the authorized development recorder; it must not leak into ordinary room broadcasts or character prompts. Match collection scope to the original design and current authorization boundaries.

Done: a real session reconstructs both speakers’ exact text, recomputes baseline/features/score, joins intervention/outcome by stable IDs and reports missing telemetry honestly. Restart/retry/interruption/disk-full cases cannot silently lose an acknowledged turn. Record the test and exact source revision.

### Task 2 — Reconcile the camera repairs that did not survive into the seal

Use the discrepancy table above as the initial failing acceptance checklist. Establish canonical CameraManager ownership, camera-change events and a full-host TwinEngine adapter. Retain standalone compatibility intentionally rather than running its registry beside the host registry. Quarantine the advanced manager only after proving its consumers and synchronization needs. Preserve useful donor fixes.

Use supported bridge commands and record false/rejected sends. Separate avatar transport health from real voxel-render evidence. Add tests on real state changes and command effects: invalid/idempotent switches, one event per change, Program/Preview, active pose/FOV, bridge rejection and lifecycle restart.

The later Rust transport implementation is an **acquisition/reconstruction task**, not a copy/paste available in this packet. Start by seeking the original session workspace/export/package. If it cannot be acquired, reconstruct explicitly from the preserved authenticated protocol/revision/ACK contracts, preserving the distinction between original and new code. Do not overwrite the packaged binary before source build/control acceptance.

Done: UI/API/vision/studio mutations converge on one camera state, unsupported commands cannot report success, the actual Rust source builds and an authenticated two-camera control run verifies matching IDs/revisions. That proves control, not pixels.

### Task 3 — Prove one visible world/avatar/recording slice

Use existing `runtime/spine`, avatar performer, `modules/glb_motion_retargeter.py`, browser motion consumer, stage UI and preserved Sheila rig material. Select one avatar, one scene and one camera before widening scope.

For native GPU camera work, preserve the Stage-2 assessment’s seam: one real scene/mesh ingestion path, camera state derived from the accepted canonical revision, GPU view uniform applied, offscreen frame/readback, and telemetry tied to that frame/revision. The preserved window/surface renderer lacks the matching historical Camera types; the headless avatar server has no established window owner. Do not bulk-copy that donor or return an ACK pretending to render.

For browser-first 2.5D work, first prove real composited canvas output and capture. Feed the actual captured media into existing `RecordingService.register_artifact()`, then transcode/export. A marker/event log is not source media.

Done: a user can see the avatar respond/move in the current UI, a camera/pose change visibly changes the produced frame, and the saved recording reopens with the expected image/audio and provenance. Screenshots or video and real artifact checks accompany tests.

### Task 4 — Complete the real 2i/Foresight/provider acceptance gate

Use the current `2i-backend` and root Node manifests; do not replace manuscript authority with a prototype. Run the actual Express listener, root DOM/editor harness and authenticated Reach bridge against fresh data. Preserve no-silent-commit mode switching and the shared World Chat room `world`.

Compare the August prototypes, September notebook-dominant layout and collaborative-editor material against current features. Port only missing useful behavior. Verify actual two-node federation manuscript edits/conflicts and real provider/model slot routing with configured services; a health response alone is insufficient.

Done: editor state survives explicit save/load, mode switch does not commit, stale peer edits produce visible conflicts, identity-scoped messages do not leak, and the browser action reaches the intended live backend.

### Task 5 — Advance Conversation Core v2 through the chosen comparison method

The September 29 revised document’s next artifact is a minimal contract set, not immediate production code or a new third core. Durable personal evidence/multiscale baselines sit underneath existing working state, observation/EQ/pacing, Director and ResponseComposer. The speaking model still owns final language. BlackBox records observation, inference, choice, speech and outcome.

Define minimal contracts/invariants first. Put selectively reconstructed historical components behind those contracts in a disposable lab. Replay the same authorized historical interactions through old and proposed paths. Compare state estimates, evidence retrieval, novelty/anti-parroting, strategy selection and outcomes. Promote demonstrated mechanisms, not entire old files. Keep typed/spoken baselines and observation/inference/user statements separate.

Done: a documented vertical slice improves a concrete replay case, retains provenance and state ownership, and has regression evidence. No mock/default-stub path may be presented as provider-backed execution.

### Task 6 — Evaluate PEQ and the incubating theory bridge

Use copied PEQ/CRE-EQ/broker/retrieval and donor tests in the same isolated comparison approach. Reproduce correct parent import/BOM handling and verify actual room-scoped signal delivery, current subject authorization and lifecycle cleanup. Compare care/advice output against active Alex/Affect before selecting authority. Raw clinical hypotheses must remain behind the broker boundary. Do not use retrieval keyword matches as proof of a person’s state.

Review the Theory/Evidence bridge’s documented invented instability weights and current EVO signature before any runtime hook. Existing graph/evidence/contradiction source is already preserved; no source recovery is required for those three files.

Done: justified responsibility map, reviewed data/weight provenance, real integration tests and an explicit promote/defer verdict. A package-import fix alone is not the gate.

### Task 7 — Implement Cricket only against the revised role specification

September 22’s revised addendum governs earlier proposals. Eligible independent humans/full AI participants receive personal liaisons; subordinate Mannies/Sheilas do not trigger their own Crickets. A Cricket can read authorized status, open/navigation views and relay/escalate. It cannot change volume/settings/cameras, restart/install, operate equipment or inherit a participant’s execution power.

Privileges are requested directly from central Jeremy, independently verified, session-bound and enforced/revoked by Pubcast. Jeremy Cricket coordinates ordinary Corps reports and is distinct from central Jeremy and owner Cricket. Personal Crickets have no direct E-Pete path. Owner/host direct contact with central Jeremy remains available. Cartridge/protocol/permission-vocabulary details identified as open in the spec need a concrete reviewable proposal before implementation; do not silently invent them.

Done: actual owner/guest/AI/background-cast/role-change/denial scenarios pass; navigation works without granting operational execution; each eligible participant has private scoped continuity and no cross-participant memory leakage.

### Task 8 — Implement the reviewed 2.5D stage V1

Read both the original spec and the corrective review. Fixed-perspective painted sets do not support arbitrary orbit shots. Separate authored-view/plate-preserving shots from genuinely 3D shots. Calibration must address world scale, signed pitch, invalid/degenerate vanishing points and consistent FOV. Keep screen/world coordinates explicit. Enforce bundle path containment and portability; the draft importer and draft tests have documented defects.

Define one authoritative stage state and canonical Program output. Local video focus differs from broadcast focus; audio/screen/director ownership must remain clear. Begin with one plate, walkable floor, one holdout, one visible test actor and one interactive screen, then prove save/reload and Program capture.

Done: the reviewed first scene works visibly and portably, the actor respects floor/holdouts, local focus does not unexpectedly change the broadcast, and stage state/recording share the intended authorities.

### Task 9 — Adapt launch supervision and close every item visibly

Compare Drive `Start-RVFStack.ps1` / `Set-RVFSecrets.ps1` / README to current release layout, current credentials and actual health routes. Their original layout assumes Pubcast/PubPartner/2i sibling service folders. Verify supported Windows behavior, process ownership, stop/restart limits, logs and health failures before using them as the standard launcher.

For every promoted item update the progress register with exact source origin, modified paths, integration commit/release hash, authoritative caller, state owner, tests and visible acceptance evidence. Preserve rejected/superseded mechanisms with the reason. Mark an item integrated only after its actual product path passes; copying code or passing isolated tests is insufficient.

## Checks performed tonight

- Exact current ZIP SHA/CRC verified; baseline release bytes were not changed.
- 213 supplementary saved files matched declared sizes; 56 retained Drive records have hashes and download size checks.
- 508 copied GitHub text blobs matched their Git blob SHA after preserving original newline bytes; two additional JavaScript payloads were recovered by exact archival blob hash.
- Selected outer ZIP CRC census passed; source/member/current hash comparison and the 62-item register were generated.
- Source tracing confirmed active affect/BlackBox/archive/Bubble/performer seams and exposed the camera source/document divergence.
- Small stdlib checks passed: exact UTF-8 archive text/message IDs survive reopening, and retarget aliases/finite rotation clamps behave as expected.
- Attempted focused pytest verification stopped **before test collection** because pytest is not installed in this execution environment. No Python suite result is claimed tonight. Historical Round9 `1,042 passed / 2 skipped` and bridge `7/7` results are saved provenance, not reruns. The earlier documented Node/npm DOM gate also remains an environment/acceptance obligation.

## Remaining coverage and acquisition limits

The three requested recovery passes are complete within the bounded searches and source collection described above. This is not a claim of complete access to every account/chat, every old Drive subtree, every historical Git commit or every binary artifact.

Remaining work is explicit:

1. Other ChatGPT accounts and original chat exports were not available. Saved PDFs and reconstructed summaries are not substitutes for every original chat or its exact boundaries.
2. Later named Rust-camera source files could not be located among the queried saved files, inspected branch trees or copied archive/member records. Their documentation is copied; their implementation remains acquisition/reconstruction work. The offline export-vault plan likewise claims an implemented synthetic-tested Stage1, but its named `conversation_vault.py` was not located in the copied census or targeted saved-file search. Keep that as a source acquisition/reconstruction gap, not copied code.
3. Sixteen attempted non-UTF-8 GitHub payloads remain unavailable through this text connector: Prime image/bundle artifacts and Dawn runtime database/WAL/temp payloads. Paths/blob hashes are retained in `UNRESOLVED_ACQUISITIONS.json`. Larger/excluded repository binary archives/assets are inventoried in branch trees; only those with an actual copied alternate source should be treated as acquired. Database residue is not release source.
4. Old donor branches/folders remain historical sources; all their metadata/source bytes were not recursively fetched. Large model/tool installations are not part of the progress package merely because a folder references them.
5. The 2,136 nonmatching payloads are a finite evidence queue, not 2,136 approved tasks. The major work streams are triaged; remaining function-level questions and uninspected nested artifacts stay in file 03.
6. Real provider services, browser rendering, Windows launcher/Rust promotion and GPU/media production have not been newly accepted in this audit.

## How to find and verify copied material

File 02 supplies human-readable candidate paths and a copy manifest. File 03 preserves the original recovery folder under `audit_collected/`, new branch/Drive data under `audit_new/`, and supplementary saved files under `audit_additional_library/`.

Key indices in file 03:

- `audit_collected/SOURCE_PROVENANCE.json` and `COPIED_FILES_MANIFEST.json`: first-pass sources and identical-payload aliases.
- `audit_new/GitHub/DISCOVERY_SNAPSHOTS.json`: repository/branch/commit/tree/log evidence and exact-current matches.
- `audit_new/GitHub/COPY_INDEX.json`, `RECOVERED_BINARY_INDEX.json`: copied blob bytes and original source paths/commits.
- `audit_new/GitHub/PR_ISSUE_RECORDS.json`: source PR/issue assertions, not engineering acceptance.
- `audit_new/Drive/COPY_INDEX.json`: original Drive IDs/URLs/dates and copied hashes.
- `audit_new/review/ADDITIONAL_LIBRARY_INDEX.json`: supplementary saved-file identities/dates/paths.
- `audit_new/review/ARCHIVE_MEMBER_COMPARISON.json`: source/member hashes, exact-current matches and same-filename candidates.
- `audit_new/review/NON_MATCHING_SOURCE_REVIEW_QUEUE.json`: deduplicated payload comparison queue.
- `audit_new/review/PROGRESS_REGISTER.json` and `TONIGHT_VERIFICATION.json`: work verdicts, evidence and actual check scope.

An identical-payload alias points to retained complete bytes. A hash proves what was copied, not that an unseen account/export supplied every source. Carry these packages and the updated register into the next session so this recovery itself does not become another forgotten chat.
