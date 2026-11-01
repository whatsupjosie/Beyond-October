PUBCAST CONSOLIDATION PLAN — 2026-10-13

Status: planning document plus a first merge already done and tested in a scratch copy (pf-merge). Nothing here has been run against a real AI model. Original archives are untouched.


1. WHAT EXISTS (all 14 archives unpacked and indexed file by file)

Full-program trees, newest first:
- BASE: Pete Provider-First (Oct 10-11). 1,009 files. Canonical starting point, as the Oct 11 handoff also says.
- SMOLLM: the five-part audited backup (Oct 10). 1,135 files. Same program plus local SmolLM2 model support, hosted-adapter fixes, a 1.06 GB GGUF model and llama.cpp runtimes for Linux and Windows.
- MERGED Alex-V22 (Oct 10), COHESIVE Foresight (Oct 9), 2I V22 CONNECTED (Oct 9): older steps on the same line as BASE. BASE already contains their work.
- UNIFIED CARE + Little Mode (Oct 8), CARE evaluation (Oct 8), ROOM RECORDING (Oct 8): a separate fork built on the Oct 3 source. Not merged into BASE.
- WorldChat 2i (Sep 23): oldest. Contains runtime data with private keys and databases (never ship), build backups, and two things later trees dropped (see section 4).

Small packages: Alex changes-only (two), CARE/EQ reference, Baby Ambiguator activation test, CARE patches, OmniVault Phase 1, recovery catalog, standalone Sir Purfluous bot (7 KB version).

Across all trees there are 1,412 distinct file paths. BASE has 1,009 of them.


2. THE SHAPE OF THE PROBLEM

There are three forks, not one line:

- Fork A (BASE): Foresight + Alex memory/personality + 2i V22 + Pete provider-first. Plus this session's fixes (character_service guard, honest offline labels, offline Sir Purfluous/Pete/RePete, clip analysis).
- Fork B (SMOLLM): split from Fork A on Oct 10. Adds the local model launcher and fixes the hosted OpenAI/Claude/Gemini adapters.
- Fork C (Oct 8 CARE): CARE coordinator with Little Mode learning, explicit-language masking, conversation policy, room evidence sync, room-recording reliability. Fork A only took the small CARE/EQ reference seam (care_eq.py), not this.

Everything older is either already inside Fork A or is history.


3. STEP 1 — DONE: Fork B merged into Fork A (in pf-merge)

Three-way merge against COHESIVE as the common ancestor:
- 10 files taken from SMOLLM (only it changed them): bot_llm_adapter, llm_framework, manuscript_intelligence, openai_compatible_provider, provider_neutralizer, pubpartner_knowledge, pubpartner_routes, pubpartner_voice, writers_room, requirements.txt.
- 8 files kept from BASE (only it changed them): pete.json, alex_jeremy_bridge, bots, character_cast, character_profiles, models, ollama_provider, pubpartner_vessel/runtime.
- 1 merged cleanly: pubpartner_core.
- 4 real conflicts resolved by hand:
  - character_service: kept BASE + this session's honest offline labelling.
  - pubpartner_provider: kept SMOLLM's local-model path; kept BASE's shared friend-voice contract as the system prompt.
  - pubpartner.html: kept BASE (Ollama default, "diagnostics only" labels, fallback unchecked).
  - pubpartner.js: took SMOLLM's safer send logic (duplicate-send guard, stale-reply isolation, draft recovery). Kept BASE's honest "No live reply" and "Diagnostic response (not a real AI)" wording.
- Added SMOLLM's new files: local_model_config, openai_responses_provider, smollm_prompt, turn_serialization, run_smollm/setup_smollm, launchers, 5 test files, live-check tool, validation docs.
- NOT added to the source tree: the 1.06 GB model and the runtime binaries. They belong in a separate release/download, not in the code repo.

Verified here:
- The full suite runs file by file: 1,106 passed, 1 failed, 1 skipped. The one failure is the voxel test that fails only because this Linux sandbox has posix_ipc.
- SMOLLM's 56 adapter tests pass on the merged tree.
- The PubPartner browser DOM test passes all 8 checks. It ran under jsdom 26 in a DOM simulation, not a real browser.
- The app boots with auth on. All main pages return 200, anonymous API requests get 401, and an offline character reply is labelled offline.

Not verified: a real reply from SmolLM, Ollama or any hosted provider. The model and runtime were not loaded in this sandbox.


4. STEP 2 — Restore what later trees dropped

a) Sir Purfluous scene director (modules/purfluous.py, 559 lines, Sep 23). It watches rooms and nudges bots through BotManager.nudge(), which still exists in BASE. The Sep 23 main.py wired it in; every later tree dropped it. Plan: bring it in behind a feature flag, re-wire it, write tests, check it can't speak for other bots or bypass room rules.
b) bot canonical-prompt test (tests/test_bot_canonical_prompt.py from MERGED). BASE has the code but not the test. Plan: add it and run it.
c) Bubble Stack dossier zips (Sep 23 run6_bubble_stack). Reference material, not code. Plan: archive with docs.
Not restoring: pubpartner_verified/ (a byte-identical duplicate that was removed on purpose), legacy modules/care_profile.py (marked legacy), modules/main.py duplicate entrypoint, the Sep 23 data/ folder (private keys, user DBs).


5. STEP 3 — Merge Fork C (the Oct 8 CARE work). Biggest job, and needs your decisions.

BASE has one CARE design: care_eq.py (7.6 KB). It's owner-activated, with the Baby Ambiguator masking and a parachute exit.
Fork C has a fuller CARE design: care_coordinator.py (14.8 KB) plus littlemode_protocol changes, explicit_language.py, conversation_policy.py and room_evidence_sync.py. It also hooks into hub, alex_core, alex_jeremy_bridge, pubpartner_core/provider/routes, pubpartner_app and main.py. Its 102 targeted tests passed on Oct 8 and its 9 test files are not in BASE.

The two designs overlap: both call themselves the single CARE coordinator. They can't both be live. Three ways forward:
- Option 1: make Fork C's coordinator the one CARE engine and re-point BASE's /api/alex/care routes and foresight_care.html at it. Most capable, most work.
- Option 2: keep BASE's care_eq as the engine and port only Fork C's pieces it lacks (outcome learning, explicit-language masking, room evidence sync). Less churn, but the risk is a hybrid nobody designed.
- Option 3: keep both behind one switch for a trial period. Not recommended; that's how duplicate engines happen.
Recommendation: Option 1, done as a reviewed port module by module, with Fork C's tests brought over first so they define what "working" means.
Also in Fork C: bigger versions of affect_context_engine, emotional_orchestrator and eq_monitoring_recorder. BASE's emotional_orchestrator is the newer V22 System-Alex adjudicator, so size doesn't mean newer. Each needs a line-by-line review, not a copy.


6. STEP 4 — Loose files

- body.py (procedural Sir Purfluous rig): keep as an asset tool. It builds geometry only and has no exporter yet.
- Standalone sir_purfluous_bot (7 KB): superseded for chat by the in-app offline Sir Purfluous. Its search bug is documented. The 23 KB version is still missing.
- OmniVault: separate browser-extension product. Keep in its own repo, not inside PubCast.
- memory_index_uai_v1.1.py: UAI product, separate.
- memory_api.py, pubcast_agent.py: do not merge. They have a hard-coded secret, open CORS with credentials, an unsafe zip extract, and a hard-coded Windows path.
- conversation_state.py: depends on five modules nobody has sent. Park it.
- 2i V22 page: BASE's copy is the newest. The uploaded v223 html and MERGED's copy are older.


7. STEP 5 — Make it shippable

- One repo, one entrypoint (root main.py via run_reach.py), one BotManager, one CARE engine.
- requirements: declare scikit-learn. Pin the jsdom version for the DOM test.
- Model and runtimes: a separate download with checksum. The launcher checks it, as SMOLLM's already does.
- Lock or justify the anonymous /api/doctor and /api/studio/status.
- Clean distributable: no secrets, caches, DBs, private conversations or model. Include a SHA-256 manifest, a change log and an honest "what was actually run" report.
- Backup: GitHub (private repo) plus Drive, recorded only with real receipts (commit SHA, file ID).


8. STILL MISSING (named in the recovery catalog, never recovered)

Foresight_PubPartner_2I_BOOTABLE (Oct 9), Foresight_Alex_Cartridge_2I_Trays (Oct 9), 2I_V22_BACKEND_WIRED and SAFE_INTEGRATION (Oct 9), BABY_AMBIGUATOR (Oct 3), COMBINED_EMPATHY_EQ (Oct 2), PubPartner_FORWARD_INTEGRATION (Oct 6), the 2I V22 independent audit, the two Alex historical-source zips, the manuscript-intelligence package (modules/manuscript/, 105 tests), and the larger Sir Purfluous bot. The "Trays" build matters most: the Foresight trays UI may only exist there.


9. DECISIONS NEEDED FROM JOSIE

1. CARE: Option 1, 2 or 3 (section 5).
2. Restore the Sir Purfluous scene director (section 4a): yes or no.
3. Where the canonical repo lives: a new private GitHub repo, or the existing NowCurtsey-Build.
