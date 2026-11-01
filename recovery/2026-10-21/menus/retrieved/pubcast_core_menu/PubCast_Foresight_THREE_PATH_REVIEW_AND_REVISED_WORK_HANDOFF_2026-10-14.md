# PubCast/Foresight — Three-path solution test and revised Work handoff

## Basis and limitations
Reviewed the 16 KB `PubCast_Foresight_WORK_MODE_MASTER_HANDOFF_2026-10-14.md` against files extracted directly from `PubCast_Foresight_Agent_Continued_2026-10-14.zip`: Windows launcher, application registry, preflight, integrated acceptance tests, GitHub Actions workflow, and embedded latest handoff. These are **source-contract checks**, not a fresh Windows GUI or provider-backed conversation run. The archive was not modified.

## Three candidate solutions — tested against current artifacts

### A. Work directly toward first-use on the user's computer
**Method:** use the existing Windows launcher, open Foresight, exercise 2i and Pub Partner, diagnose problems on the machine that matters.

**Checks:** Windows launcher invokes `start_reach.py` and retains visible error output (PASS); application registry targets `/writers-room` and `/pubpartner` (PASS). **Not proven:** Windows runtime dependencies, browser tray behavior, save/reopen, and provider reply.

**Advantages:** Most direct proof of usability; hardware/browser-specific issues visible. **Risks:** User becomes the test operator; debugging begins during the hoped-for first productive session; lacks unattended reproduction. **Verdict:** Necessary final acceptance, poor as the only first step.

### B. GitHub CI-first validation
**Method:** commit a protected branch and run checks on hosted runners, adding Playwright browser automation, startup smoke tests, and build artifacts.

**Checks:** Existing `.github/workflows/foresight-workbench.yml` runs pytest (PASS). It does **not** install or invoke Playwright/Chromium (GAP); does **not** call `tools/workbench_preflight.py` (GAP); does **not** upload a complete runnable build (GAP). It uploads only JUnit XML. Its trigger paths do not explicitly cover every relevant startup/registry file; verify repository layout before use.

**Advantages:** Repeatable independent browser checks; logs/artifacts; can run unattended. **Risks:** Current workflow is not an end-to-end test; repo layout and permissions unknown; CI cannot supply real provider credentials automatically and cannot fully represent the user's desktop. **Verdict:** Upgrade workflow before relying on it; do not describe current CI as browser certification.

### C. Hybrid: local integration repairs + browser CI + real-machine acceptance
**Method:** protect the latest ZIP, use local unit/in-process integration to repair application wiring, add browser E2E on a runner that permits localhost, then validate the same packaged build on the user's machine.

**Checks:** Master handoff already defines Checkpoint A (bootable) and B (first usable), and prohibits counting synthetic provider responses as real (PASS). Existing registry and preflight offer a foundation (PASS). Browser E2E and live provider acceptance are still unverified (GAP).

**Advantages:** Preserves fast engineering iteration, adds real-browser evidence, avoids pushing troubleshooting onto the user, and leaves a downloadable checkpoint. **Risks:** Requires CI/repo identification and careful isolated test data; real AI requires an authorized provider and secrets management. **Verdict: RECOMMENDED.**

## Important corrections to the master handoff
1. **Do not assume GitHub Actions already tests browser interactions.** It currently runs JS syntax and pytest, not Playwright. Add an actual browser test that starts Reach and opens `/foresight-counter`, then opens 2i and Pub Partner from the picker.
2. **Do not equate the preflight with launch success.** It uses an in-process FastAPI TestClient. Separately test the real server process, port binding, browser navigation, iframe auth, and shutdown.
3. **Do not treat source-string assertions as functional persistence.** The existing `test_foresight_workbench_acceptance.py` checks that save/conversation code strings appear. Add a real create-save-reload API round-trip with isolated temporary user data, followed by a browser-level round-trip.
4. **Provider availability is an explicit conditional gate.** Test genuine provider response only with configured credentials; otherwise test actionable unavailable status and leave real conversation uncertified.
5. **Avoid an arbitrary elapsed-time promise.** Work in substantial, recoverable sessions; finish a coherent engineering checkpoint and report actual time/work rather than announcing every defect.
6. **Protect user data and secrets.** Run tests against a disposable data directory. Verify no real manuscript or provider token enters public GitHub commits or CI artifacts.
7. **Check exact repo layout before committing.** The ZIP has `october/` at its root; the workflow paths assume the files live at repository root. Map archive to GitHub checkout explicitly.

## Revised order for the next Work session

**Gate 0 — establish exact source and safe workspace.** Obtain latest ZIP, extract without overwriting originals, check ZIP integrity, identify GitHub repository and layout only if connected. Inventory data directories and redact secrets from outputs.

**Gate 1 — actual process smoke.** Run preflight and targeted regressions; start Reach as a subprocess with isolated data and ephemeral/local port; fetch Counter, 2i, Pub Partner, and key JS/CSS; check clean shutdown. Repair anything that prevents boot. Package a bootable checkpoint if achieved.

**Gate 2 — real document persistence.** Write a temporary 2i manuscript using actual API calls, retrieve it, modify it, restart service, and retrieve again. Verify recovery behavior when service is unavailable. Never touch bundled user manuscripts.

**Gate 3 — browser integration.** Add Playwright E2E on a capable host/CI: launch Reach, open blank Counter, picker -> 2i, type/save/reopen, picker -> Pub Partner, confirm UI loaded and errors surfaced. Collect screenshots, console errors, network failures and JUnit/artifacts. Fix failures and rerun.

**Gate 4 — genuine AI path.** Exercise provider-first message delivery with configured provider. If no credentials, verify graceful status/error and record that live reply remains unverified. Do not claim a fake reply passes.

**Gate 5 — packaging and handoff.** Re-run regressions, archive complete runnable source, test ZIP integrity, include a `WORK_SESSION_HANDOFF.md` with changed files, exact commands, pass/fail evidence, launch instructions, known issues, rollback path and next actions. Report once at checkpoint, not bug-by-bug.

## Best near-term handoff point
A **bootable Counter with the actual 2i and Pub Partner pages opening inside trays**, plus a **real server-side manuscript save/reload round-trip**, even if the browser GUI and external provider remain conditional. This is a useful recovery point short of the full first-session goal. Then continue toward GUI and AI proof rather than stopping solely because a ZIP exists.

## Recommended Work prompt
Continue engineering from the attached latest PubCast source ZIP and the master handoff, using this three-path review as an amendment. Follow the **hybrid strategy**. Work in sustained checkpoints without announcing individual bugs. First prove real server startup and an isolated manuscript save/reload; then add browser-based Counter/2i/Pub Partner acceptance tests in a localhost-capable environment or GitHub CI. Repair failures and package a complete runnable build with evidence. Preserve originals and user data; never count route 200, source-string tests, or synthetic AI replies as first-use certification. Do not stop at the first successful check; make a meaningful checkpoint and continue where feasible.
