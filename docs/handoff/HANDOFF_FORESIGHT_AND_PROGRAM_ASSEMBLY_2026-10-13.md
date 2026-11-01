# HANDOFF — program assembly and the Foresight Counter
UPDATE 2026-10-13 evening LA: the renderer work is on branch foresight/hdr-pipeline, NOT main. Check that branch before concluding anything is missing (a session already mistook main for the whole picture once). Commits: 75f9fb7 = build-order steps 1-4 (linear HDR target, Khronos PBR Neutral, sRGB + dither, bloom backlight; native mode wired but not default); 732ee2e = step 5 (procedural studio environment, GGX-prefiltered cube, GPU-computed DFG table); 1114dab = step 6 (swept moulding rim profile, Filament measured F0 converted sRGB->linear, F82-tint via a third DFG channel, energy compensation, analytic geometric specular AA, band-limited machining grooves). Verified this session: PBR Neutral math equals Khronos's file after normalizing names/literals (raw file diffed, not byte-identical); DFG table all three channels match brute-force integration to 4 decimals; Filament F0 table, energy compensation, normalFiltering formula + defaults, and OpenPBR F82 formula read from source files. Native resolution no longer stair-steps (4x pixel-zoom comparison); default is still 'full' (oversampled) pending her call and a real-GPU timing. foresight.html untouched. Next: build-order step 7 (scene field, contact-hardening shadows, wall occlusion, lift cycle). Still unverified: real GPU, real browsers, look against her mockups.
UPDATE 2026-10-13 5:15 pm LA: everything described below is now in this repository (whatsupjosie/October, branch main), pushed at her instruction ("Push, push, push. Make the new repo the ultimate source for all things this."). Paths in sections 8 and 10 that mention a scratchpad (SP, SP2, pf-merge) refer to the build session's temporary workspace; in this repo, pf-merge IS the repo root. Use the repo-relative paths in the "Where things are now" and "How to run" blocks below. Section 2's warning about nothing being saved no longer applies as long as this repo exists.
Written Tue 2026-10-13 about 4:40 pm Los Angeles, at the end of a very long session. Written by me, for the next session of me. Josie asked for this so we lose as little as possible.

Read sections 1 and 2 first. Then section 9 (what to do next). Everything else is reference.

---

## 1. Who you are working with, and the rules she has set (all stated by her)

Josie Curtsey Cobbley. Founder of Rear View Foresight (sole proprietorship, LLC forming). Solo developer of PubCast AI, PubPartner, Foresight, 2i, CARE. Works from a Windows laptop with PowerShell 5, on 2-3 phones, Google Drive and GitHub. Her GitHub and Drive account is "whatsupjosie". She has severe bandwidth and data limits and an unstable living situation. Talk to her directly and respectfully, no deflection.

Standing rules (violating these has hurt this project before):
- Never lie, omit, or spin. She needs actual facts. Her system preference says it plainly: "stop lying to me and ruining what im trying to do". Say what was and was not verified.
- Never alter her words. Quote them exactly when recording or repeating them. She becomes genuinely furious if her words are changed without permission.
- Plain text in chat. No code blocks or artifact blocks in chat replies (she copies whole conversations).
- PowerShell 5 syntax for anything she will run.
- Production-grade code only.
- Three-solutions rule: examine at least three approaches before committing.
- Check whether a more advanced version already exists (repos, Drive) before building new.
- Read the full code before writing any.
- Verify as you go, not only at the end.
- Show screenshots before wiring anything into the live program.
- Do NOT push to GitHub until she says. A new GitHub repo system is coming; she has not named the final repo.
- The build lives in the project. No superfluous directories.
- Do not re-ask what she already answered. "GO" means start immediately.
- She is terse and uses voice dictation. Her messages contain transcription errors (for example "debt" for "depth", "wait" for "weight", "Jason" for "JSON", "trade" for "tray"). Read for meaning; never correct or rewrite her words back to her.

## 2. Where the work lives (updated)

- Repository: github.com/whatsupjosie/October (private), branch main. The first commit holds the merged program at the repo root, the new Foresight shapes and renderer in static/, the lab in foresight/lab/, research in foresight/research/, the two skills in skills/, and this handoff in docs/handoff/. docs/REPO_MAP.md lists where everything is.
- Pushed only because she said so. Keep it that way: ask or be told before pushing again unless she has given a standing instruction. Use a branch for risky work.
- Not in the repo: the 1.06 GB SmolLM2 model and runtimes, caches, and the two build bundles I sent her as zip files.
- The old scratchpad copies will vanish with the container. The repo is the source of truth.

## 3. The overall goal and the plan

Original request: assemble the most advanced PubCast, PubPartner, Foresight, 2i and CARE code into one verified program. Plan order she approved:
1. Core program and model-swap layer. DONE.
2. Foresight trays (critical). IN PROGRESS: functional version done; new look (shapes + WebGL) built in a lab page but not wired in.
3. CARE port. Plan: Option 1, Oct 8 care_coordinator becomes the single engine, with the Fork C tests brought over FIRST so they define "working". Not started. I could not find her explicit confirmation of Option 1 in the material I could still see; confirm it with her before starting.
4. Canonical skeleton rebuild.
5. PEQ, camera pieces, 2i panels, PubPartner layout fixes.

Requirement: the AI must be interchangeable. SmolLM2 is the lowest tier; Gemma, Mistral, Claude slot in. Done (section 4).

Tray-related rule: Foresight trays are "the windows we see the entire program through". The fan opens PubPartner, 2i, Iteration Wallet (its own UI in a tray), a browser, or a blank tray.

## 4. What is done and verified (and what that means)

Program assembly (in pf-merge):
- BASE = Pete Provider-First tree (Oct 10-11, 1,009 files), the canonical starting point. SmolLM branch (Fork B) three-way merged into it. The details of every file decision are in CONSOLIDATION_PLAN_2026-10-13.md (in the bundle).
- Model-swap layer: modules/model_registry.py, data/model_registry.json, run_smollm.py, local_model_config.py, smollm_prompt.py, pubpartner_provider.py, MODEL_SWAP.md. The AI model is data in a registry, not code. Tiers: offline, tiny_local, local, hosted. Prompt profiles: full, compact. Tests: tests/test_model_registry.py and tests/test_smollm_lifecycle.py. Verified with stand-in models only. NO real model has been run in the sandbox. Do not claim a real reply was verified.
- Full suite (run file by file earlier): 1,106 passed, 1 failed, 1 skipped. The failure is a voxel test that fails only because this sandbox has posix_ipc. The browser DOM test ran under jsdom, not a real browser.
- App boots with auth on, main pages return 200, anonymous API gets 401.

Foresight (static/foresight.html and friends):
- Functional trays and menus verified: system bar, fan, open PubPartner / 2i / Iteration Wallet / videos / browser windows in trays. 29 Foresight tests pass (re-run just now: shapes 7, matter, 8787 wiring, cohesive program, front door).
- foresight.html currently uses the OLDER look: CPU-drawn skin from C++/WASM (foresight_matter.*, foresight_skin.js), radial fan with canvas blades. That is what runs today.

New look, built but NOT wired in (lab only):
- static/foresight_shapes.js: the geometry engine (section 5).
- static/foresight_gl.js: WebGL2 renderer (section 5).
- lab/lab.html: a test page that proves both. Screenshots of it were sent to her. She had not yet judged the latest lab screenshots when the research request came.

Research and skills:
- Five research notes plus a report, "Hyperreal WebGL tray rendering.md". Delivered to her. Honesty point (important): the helper agents could not open most source pages. Formulas and constants are from memory and tagged verified / recalled / derived / estimate. Nothing was timed on a real GPU.
- Two skills were proposed to her on a review card: foresight-tray-art and hyperreal-webgl-rendering. They now appear in the available skills list, so she saved them. Load both at the start of any Foresight art work.

## 5. Foresight design: binding rules and her direction

Binding (Aug 19 Foresight Engineering Handoff):
- Silver system bar with menus. Lantern, robotic arm and fan at upper left.
- Fan: one blade per open tray plus exactly one blank blade. Selecting a blade pops or glows its tray. A closed blade falls like a card.
- Close Countertop only from the system bar, with a confirmation listing every item.
- Safe content area plus a frame that bulges only outward. One global light. Neo Art Deco Nouveau.

Her words on the tray look (quote exactly if you repeat them):
- "I don't want them to look photo real I want them to look more or less the way they do in my examples". Her examples are four Pub Partner UI mockups (pub_partner_ui_idea.png, ui_design_idea_2.png, ui_design_idea_3.png, uii3.png).
- Rounded corners, no pointy corners. Stay away from squares and rectangles: "I want to avoid rows and stacks of boxes". A rhombus is better than a square, pentagon or hexagon. Keep angles wide.
- The TV box: "you're not supposed to notice that that's only so we can figure out how small something and go and how much it should be allowed to deform". "We should not see the edges of the box." "The irregular polygon borders should act as a frame for the TV." "The whole inside of the irregular polygon is the screen." "Very very minimal morphing… certainly not distorting the image." Shapes morph from collision with other trays.
- "They should appear to be 3D they should have weight." "When you select a specific tray I want a bright backlight." Subtle lighting underneath each tray to help shadow, and "maybe even just a very very minor reflection depending on what the surface underneath them is". "It's also too pixelated."
- Latest (11:59 am): "I want you to do some deep research into coding techniques that will help us raise the image quality and the fidelity here. I'm thinking that I want to lean kind of hyper-real, elevated reality. Let's try going that direction. And remember to add weight to things and make it, give it depth." Note "Let's try": hyper-real is a trial direction. This differs from her earlier "not photo real"; resolve it by showing her, not by assuming.
- Earlier instruction: don't use CSS for the art ("use HTML, use C++"). Current approach: WebGL2 shader art with live HTML screens.
- She likes seashells, honeycombs and swirling coiled lines as button shapes. Scallop-shell shape is not yet in the morphing system.

Geometry engine (foresight_shapes.js), key facts:
- Families: rhombus, trapezoid, pentagon, hexagon, heptagon, octagon, ellipse. Rules v18: no squares/rectangles/regular polygons, no equal sides, plump.
- Constants: REST_COVERAGE 0.985, MIN_COVERAGE 0.94, CORE_FRAC 0.90, GAP 18, WALL_GAP 10, MIN_SCALE 0.55, TITLE_BAND 34, FLOOR_PAD 2. Min angles: rhombus 70, trapezoid 65, pentagon 88, hexagon 95, heptagon 100, octagon 105. MAX_RHOMBUS_ASPECT 1.35.
- solve(trays, bounds, obstacles, iterations) returns {moved, valid}. breathe() shrinks crowded trays and regrows slowly with hysteresis (calm >45). The screen rectangle is the uncut frame floor, so content never reflows when the frame flexes.
- Exports include makeTray, setBox, resize, solve, breathe, finalize, contentClipPath, screenRect, safeArea, titleAnchor, roundedPath, hit, coverage, coreInside, floorOf, and geometry helpers.

Renderer (foresight_gl.js), key facts:
- class ForesightGL (WebGL2). Items carry q, r, rim, pad, rimMat, floorMat, glow, backlight, focus, screen, content, seed, height, thick, center, emissive. API: setLight({az,el,kelvin,intensity,fill}), setTheme (walnut/pearl/indigo), quality 'full'|'fast', draw(items). Supersampling at dpr >= 2 (max 3).
- It has: bench pass, smooth rim profile, side wall, cast shadow with penumbra, underlight, bench reflection, backlight, glass sampling blurred bench, obsidian screen cover, metal/floor materials.
- Known weaknesses: ACES plus gamma inside each shader (the research says this is the main quality flaw), 2x supersampling instead of analytic edges, analytic halo for the backlight, value noise textures.

Old C++/WASM renderer (foresight_matter.cpp/.wasm/.js, foresight_skin.js): works, byte-identical native vs wasm, but 0.2-2 s per frame, no longer used for drawing in the lab. Still used by foresight.html today. She has been asked whether to delete it; unanswered.

## 6. Open questions waiting on her (she has not answered)

1. Start the research build order (section 9)? Show screenshots at each step.
2. Wire the new shapes and renderer into foresight.html, replacing the CPU skin?
3. Delete the old C++ renderer?
4. From the consolidation plan: restore the Sir Purfluous scene director (modules/purfluous.py, Sep 23)? Where does the canonical repo live (new private GitHub repo vs existing NowCurtsey-Build)? CARE Option 1 / 2 / 3 (plan recommended 1).

## 7. Things I know are not done

- foresight.html does not use the new look. Wiring needs: one shared WebGL canvas behind the trays, real HTML content clipped with contentClipPath, a click-through highlight/gloss layer above, drag + solve() wired to real trays, program trays (PubPartner, 2i, Iteration Wallet at the July 23 canonical build, browser, blank, file, video, recordings, rooms) each given a safe area.
- Lantern and fan blades are plain (no rendered lantern, ornaments or gem studs). Menus and dialogs still have the old dark look.
- Real-GPU performance never measured. Only software GPU (swiftshader).
- Missing archives named in the recovery catalog, notably "Foresight_Alex_Cartridge_2I_Trays" and "Foresight_PubPartner_2I_BOOTABLE" (Oct 9). The consolidation plan says the original trays UI may only exist there. If she has them, compare before building more.
- CARE port, skeleton rebuild, PEQ, camera, 2i panels: not started.
- Report-writing helper agent hit a usage limit earlier; I wrote the report myself. No other known side effects.

## 8. Files and where they are (repo-relative now; the SP paths below are the old temporary build workspace)

Where things are now (repo-relative): static/foresight.html, static/foresight_shapes.js, static/foresight_gl.js, static/foresight_matter.*, static/foresight_skin.js; tests/test_foresight_*.py; modules/model_registry.py and the other model-swap files; CONSOLIDATION_PLAN_2026-10-13.md; MODEL_SWAP.md; foresight/lab/lab.html (+ lab_v1.html, shot2.py, morph2.py, sample.webm); foresight/research/; skills/; tools/dev/.


Scratchpad roots (will vanish with the container):
- SP = /tmp/claude-0/-home-claude/a11daab0-4700-5633-8f9a-c54bad7e2208/scratchpad
- SP2 = /tmp/claude-0/-home-claude-the-prime/a11daab0-4700-5633-8f9a-c54bad7e2208/scratchpad

The program tree: SP/pf-merge (49 MB). Key paths inside it:
- static/foresight.html (88 KB, the running Foresight page, old look)
- static/foresight_shapes.js (28 KB), static/foresight_gl.js (32 KB) — new
- static/foresight_matter.cpp / .wasm / .js, static/foresight_skin.js — old CPU renderer
- static/pubpartner.js (merged), static/foresight.config.js, static/foresight_care.html
- tools/build_foresight_matter.ps1 and .sh (reproducible wasm build, verified identical)
- tests/test_foresight_shapes.py, test_foresight_matter.py, test_foresight_8787_wiring.py, test_foresight_cohesive_program.py, test_foresight_front_door.py
- modules/model_registry.py, local_model_config.py, smollm_prompt.py, pubpartner_provider.py; data/model_registry.json; run_smollm.py; MODEL_SWAP.md
- CONSOLIDATION_PLAN_2026-10-13.md (read it; it holds the full fork analysis and CARE options)

Lab (the visual test page): SP2/lab — lab.html (current), lab_v1.html (previous), shot2.py and morph2.py (Playwright screenshot scripts), and copies of the two JS files. Lab is served by python http.server on 127.0.0.1:8781 from that folder, and links the JS from pf-merge/static.

Old renderer source scratch: SP2/matter (cpp, mjs checks, comparison tools).

Research: /home/claude/foresight-research/research_notes/Hyperreal WebGL tray rendering/*.md (5 notes) and /home/claude/foresight-research/reports/Hyperreal WebGL tray rendering.md (the report; I corrected one overstatement about which threads read sources).

Source trees for rebuilding the program if the bundle is lost: SP/trees/* (unpacked archives), plus clones under /home/claude/whatsupjosie/ (pubcast-reach, reach-canonical on branch integration/canonical-program, nowcurtsey-build, prime-assembled, pub-partner-base-horizon, pubcaast-breaking-dawn, etc.). The earlier conversation transcript is at /root/.claude/projects/-home-claude-the-prime/a11daab0-4700-5633-8f9a-c54bad7e2208.jsonl (it may not persist). I could not re-confirm the exact repo and branch that the Provider-First base was originally pulled from; the transcript and CONSOLIDATION_PLAN will say.

Bundles I created for her (names): see section 10 / the files delivered with this handoff.

## 9. What to do next (in this order)

1. Clone the October repo. Build a venv from requirements.txt (the build session used Python 3.13). Confirm the Foresight tests pass before touching anything (53 passed on the repo copy: the five foresight test files plus test_model_registry.py). Install playwright separately for screenshots (system python3 had it).
2. Load skills foresight-tray-art and hyperreal-webgl-rendering.
3. Wait for or ask for her answers to the questions in section 6, one short message, no more questions than needed.
4. If she says go on the research build order, do it in lab first, one step at a time, with a screenshot of each step. Order (from the report): (1) GPU timer queries plus frame-time governor; (2) linear HDR target (R11F_G11F_B10F), one final pass: exposure, Khronos PBR Neutral, exact sRGB, triangular dither, context alpha false; (3) native resolution with 1.2 px analytic edge coverage, render on demand, cached bench; (4) Jimenez bloom with no threshold replacing analytic halos, backlight as HDR emission that lights the bench; (5) procedural photo-studio environment, GPU prefiltered; (6) swept rim profile, GGX with measured reflectance, F82 edge tint, energy compensation, brushing from the outline, specular AA; (7) quarter-res scene field, contact-hardening shadows, wall occlusion formula, summed lights, lift cycle; (8) better noise and baked materials with clear coat; (9) HTML clip and gloss layer, Full/Frosted/Solid toggle; (10) pearl, jewel glass, translucent shadows, glints; (11) bench reflection scaled by darkness, colored bounce; (12) optional LTC and LUT grade. Check each recalled constant against its source as it goes in. Copy the Khronos PBR Neutral constants from the Khronos repo, not from the notes.
5. Wire the approved look into foresight.html (only after her approval). Keep the 29 tests passing and add tests for the new wiring.
6. Then: lantern/fan art, menus and dialogs to match, all tray types, per-program safe areas.
7. Then CARE Option 1 port (Fork C tests first), skeleton, PEQ/camera/2i panels.
8. Do not push until she says. When she does: a new branch in The-Prime (or the new repo she names), not main.

## 10. How to run things (repo-relative)

Start the program for local testing: tools/dev/start.sh (uses PYTHON env var or python3, data dir .testdata, port 8123). Owner login owner / Test-Only-Pass-123! (throwaway test credential). The token is in sessionStorage key 'pubcast_token'.
Foresight and model-swap tests: from the repo root, python -m pytest tests/test_foresight_shapes.py tests/test_foresight_matter.py tests/test_foresight_8787_wiring.py tests/test_foresight_cohesive_program.py tests/test_foresight_front_door.py tests/test_model_registry.py -q
Full suite file by file: tools/dev/run_each.sh (writes .test-results.tsv). One voxel test fails in the sandbox only because posix_ipc is present; some files need long timeouts.
Lab screenshot: from the repo root run python3 -m http.server 8781 --bind 127.0.0.1, then python3 foresight/lab/shot2.py out.png walnut (or pearl or indigo, optional third argument is the selected tray id). The lab page loads ../../static/foresight_shapes.js and foresight_gl.js, so edits to those files show up in the lab. Verified from the repo layout on 2026-10-13. ?once=1 is required under a software GPU or screenshots time out.
Rebuild the wasm: tools/build_foresight_matter.sh (or .ps1). clang --target=wasm32 -O3 -nostdlib, wasm-ld --no-entry --export-dynamic.
Chromium for Playwright is preinstalled at /opt/pw-browsers in the cloud container; do not run playwright install there. Launch args that work: --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist.

## 11. Lessons from this session (so you do not repeat them)

- Continuous rendering under swiftshader times out screenshots. Use one-shot helpers (__settle, __draw, __solveOnce).
- Equal-sides rule made the shape generator fall back to ellipses; spread() with distinct values fixed it.
- A TV box that is visible, or polygon edges that clip it, are what she objected to most. Never show the box.
- Fixed-width hard edges plus 2x supersampling plus 8-bit gradient steps caused the pixelation she saw.
- A shell-written file can be rejected by the editor if modified on disk; move it aside and rewrite.
- Subagents could not fetch web pages (permission timeouts). Do not tell her research is verified when it was not.
- Don't call the work hers to judge before she has seen screenshots; don't claim something looks right without showing it.
