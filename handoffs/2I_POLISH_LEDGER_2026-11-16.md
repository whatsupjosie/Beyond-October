# 2i polish — ledger (2026-11-16, Claude Fable 5.2)

Branch `fable/2i-polish-2026-11-16`, started from `gpt/2i-professional-completion-2026-11-15` at `aaa14b0`.
`main` (`c82069b`), GPT's branch and `fable/integration-2026-11-13` (`764874a`) are untouched.

Source of the work order: Josie's handoff "2i POLISH HANDOFF FOR FABLE 5.2" (prepared 2026-11-16 by Claude Sonnet 5.5),
Phase A1, plus what she said in chat on 2026-11-16. Her words are quoted exactly where they are relied on.

Environment for every result below: Linux sandbox, Python 3.13 in a throwaway venv built from `requirements.txt`
(FastAPI 0.115.14, Starlette 0.41.3), Playwright 1.63.0 with its bundled headless Chromium, Node 22.23.4.
"Real host" means `run_reach.py --data-dir <throwaway> --no-browser --no-legacy-2i`, owner created through
`/api/auth/setup`, sign-in through the real `/login` page. Nothing under `data/` was changed.

## What Josie approved, and what she asked for

- Phase A1 repairs R1 to R6, the launch-test title fix, and reading the existing phone edition before fixing the
  phone: "That sounds like a plan. Proceed."
- Phone: "it has to work on the phone. Even if the design has to be altered. The slide out menus might be the best
  way."
- Drawer tabs, menus, Save: "especially the tabs at the sides of the screen, I want to shrink those so they look
  like a, you know, smaller tab, you know, with an arrow, you know, indicating that they can slide out, and just
  scoot them up so they're just a tiny bit underneath the main menu, just a little tiny gap between them, so you can
  see that they're separate. And then below that, just the rest of the page." / "for file, I think we can use the
  image, the traditional file button" / "we can have a standard save button as well, somewhere up top. And let the
  bottom of the screen just be the bottom of the screen."

## What changed

| Item | Paths | What and why |
| --- | --- | --- |
| R1 | `2i/writers-room-v22.html` | The page script called `TwoiFormatCore.fresh()` with no check (commit `8ab7945`). From disk `/2i-assets/format-core.js` does not resolve, so the whole script stopped. Formatting is now on only when the core loaded. Without it, formatting saved in a document is carried through a save unchanged (anchors hold their paragraph text, so the core re-checks them when it next loads). |
| R1, same shape | `2i/writers-room-v22.html` | Found by searching for other host-only names used by the page's own script: `ppHealthCheck`, `ppCommit`, `ppLoadIntelligence` read `documentId` and `initializing` (created by `reach.js`) and threw from disk. They now read them through `ppDocumentId()` / `ppStartingUp()` and report "offline" there. Hosted behaviour unchanged. |
| R1, same shape | `2i/writers-room-v22.html` | From disk the solo writing box was two lines tall inside a full page: the rule that makes its zone a column existed only in `reach.css`. The rule is now in the page. |
| R2 | `.github/workflows/2i-professional-regression.yml` (deleted) | Josie's no-Actions rule. The file still exists on GPT's branch and would run on a push to that branch. |
| R3 | `2i/2i-assets/narrative-room.js`, `2i/writers-room-v22.html` | `#narrativeBudget` and `#narrativeStatus` got their style only inside `makePanel()`, when the Scene intelligence dialog first opened; until then they were 16 px body serif drawn over the Reference Archive. Their style is now added when the controls are created. The left panel scrolls instead of squeezing its sections. `#addRefBtn` no longer takes the reference list's height. |
| R4 | `2i/2i-assets/format-menu.css`, `format-menu.js` | Menus are as wide as their names (`field-sizing:content`) and wrap on a wide screen. Below 850 px they stay on one swipeable row; the edge with more menus beyond it fades. File shows a document icon in place of the word (name kept as tooltip and for screen readers). |
| R5 | `2i/writers-room-v22.html` | Below 850 px the page takes the screen; the left panel and (inside the host) the conversation are drawers opened from small arrow tabs just under the menus. Root cause of the sliver: the page's `<style>` comes after the `reach.css` link, so `reach.css`'s narrow rules lost to the page's own `.main-area`/`.app-shell` rules. One owner for drawer state: `body[data-twoi-drawer]`. |
| Top bar | `2i/writers-room-v22.html` | `#saveBtn` and `#saveIndicator` moved from the bottom bar to the top bar (same elements, same ids). "My manuscripts" is a text button and no longer spills over the button beside it. |
| Launch test | `tests/test_bella_faux_pas_launch_acceptance.py` | Expected "Writer" in the 2i tray title; GPT's version code titles it "<marks> · <document title> — 2i". The assertion now matches that format. |
| R6 | none | `static/foley_manifest.json` still names `/assets/audio/foley/typewriter_click_01.wav`, which is not in the repository. The synthesized click remains the working sound. Nothing was faked. |

Reused from the September phone edition (`2i/2i-assets/phone.js`, `PHONE_EDITION.md`): panels are moved or
restyled, never cloned; a reference picked from a panel returns the writer to the page; large touch targets. Its
code could not be loaded as it is: it is written against the older `2i/index.html` artwork page (`photoRoot`,
`reachArtworkReady`, `photo*` controls), none of which exist in `writers-room-v22.html`.

## RAN (real output)

- Node: `node --test tests/test_2i_*_node.js tests/test_twoi_rich_browser_contract_node.js tests/test_foresight_file_close_node.js tests/test_foresight_file_navigation_node.js` → 59 passed, 0 failed.
- The 13 tests that failed on `aaa14b0` (`tests/test_2i_speech_wiring.py`, `tests/test_2i_reload_restores_solo_text.py`) → 13 passed.
- New `tests/test_2i_standalone_without_format_core.py` (7, from disk, network blocked). Against the previous page source all 7 fail.
- New `tests/test_2i_narrow_screen_drawers.py` (13, from disk, 390×844 with touch).
- New `tests/test_2i_hosted_layout.py` (2, real host, 1280×800 and 390×844 with touch; includes a real save from the top bar).
- `tests/test_bella_faux_pas_launch_acceptance.py` (real host) → passes again. It failed on `aaa14b0` and passed on `764874a`.
- The exact totals of the last full 2i Python run are in the commit message of the commit that added this file.
- Layout probe on the real host at 1280×800, 1000×700, 1280×600, 768×1024, 390×844, 320×568, 844×390 and from disk at 1280×800 and 390×844: no page errors, no menu clipped at the three wide sizes, no overlap of the scene line or Manuscript Control with the Reference Archive, typed text and a half-typed chat message kept through every drawer movement, panels back in place after widening.

## Did not match the inherited handoff

- It said `tests/test_reach_writers_room.py::test_fiction_never_becomes_a_personal_lesson` fails on both branches. Here it passes on both (8 of 8 in that file). Cause of the earlier failure: UNKNOWN.
- It said only `format-core.js` fails to load from disk. All 16 `/2i-assets/…` and `/static/…` references fail from disk (7 on `764874a`); the page's own script and style are all that run there.

## UNKNOWN / not tested

- Windows, PowerShell 5, Josie's laptop and phones, any real GPU browser, a real on-screen keyboard (the layout uses `100dvh`; behaviour with the keyboard open is untested), iPhone Safari (`field-sizing` support there is not confirmed; without it the menus are wider and the row is swiped further).
- The Horizon copy of 2i, the Foresight file shelf screen, images in the 2i chat.
- 2i inside a Foresight Counter tray at tray sizes below 850 px wide: the drawer layout will apply there; not looked at.

## Unfixed, found on the way

- Inside the host the app shell is 16 px taller than the window (the page's `height:100vh` plus `reach.css`'s 8 px margin), so the bottom border is cut off at laptop width. Present before this work.
- From disk, modes, the menu bar, versions and narrative tools do not load at all (absolute paths). The single-page notebook must work "outside the program", so Phase A2/A3 has to decide how those parts reach a disk-opened page. Not changed here: loading the host scripts from disk would also load host-bound code and would break the standalone speech behaviour the 13 tests protect.
- At 1280×800 the Reference Archive is below the fold of the left panel (Manuscript Control is 572 px tall with GPT's added buttons); the panel scrolls to it.
- Typewriter click and bell default to on (`studio-desk.js` line 68). Josie: "the audio effects should be optional." Phase A4.
- `My manuscripts` does nothing from disk (its handler is set by `reach.js`).

## Decisions needed from Josie

1. The bottom bar still holds the status dot and word ("idle"), the document title (tap to rename), the word count, the PubPartner pill and the read-aloud controls. Where each goes once the bottom is "just the bottom of the screen".
2. The spiral image on a phone: dropped, or a thin strip of rings.
3. Whether the same small arrow tabs should replace the side-by-side panels on a laptop now, or with the single-page notebook in Phase A3.
4. Section 4 of the inherited handoff, items 1 to 10, unchanged.

## Next step

Phase A2 (modes and the menu) after Josie answers item 1 and says go.

---

# Update, later on 2026-11-16 (same branch)

This section supersedes three lines above: "Decisions needed" item 1 (answered, see below), the note that the app
shell is 16 px taller than the window (fixed), and the R4 line's `field-sizing:content` (replaced).

## What Josie said

- To the proposed homes for the bottom bar's items: "That's all great."
- "why don't we just go through and look for everywhere that we may have been in a rush and cut corners or
  accidentally overlooked. Check our work. Look for weak code and strengthen that up, and then do 2 full rounds of
  troubleshooting and debugging"
- About 2i opened from disk having no menu bar: "If it has no menus, we need to add those menus, because otherwise
  they're just words at the top of the page taking up space. Yeah, the menus have to work."
  (Clarified to her: inside the host the menus are wired; from disk the bar is not drawn at all.)

## Changed

| Item | Paths | What and why |
| --- | --- | --- |
| Bottom bar removed | `2i/writers-room-v22.html`, `2i/2i-assets/reach.css` | Title (tap to rename), word count and save state are one line in the top bar beside Save. The status word shows only while reading or generating. Read-aloud controls are at the top, in Collab only, as before. The model pill is in the conversation panel. Same elements and ids. The shell is a flex column ending at the bottom of the window (`--shell-margin`, `--top-bar-height` set by `reach.css`). |
| Menu widths, one method | `2i/2i-assets/format-menu.css`, `format-menu.js` | Each menu's width comes from the length of its name (`--face-ch`). `field-sizing:content` was dropped because it could not be confirmed on iPhone Safari; there is now one path, and `tests/test_2i_hosted_layout.py` checks every name fits without a long empty box. |
| File icon in forced colours | `2i/2i-assets/format-menu.css` | In Windows high-contrast mode the File menu shows its name again (background pictures are removed there). WROTE, NOT RUN: no forced-colours browser here. |
| Unseen messages on a phone | `2i/writers-room-v22.html` | Menu commands report failures as a line in the conversation. In a closed drawer that was silent. The tab of the drawer holding the conversation shows a dot until that drawer is opened. |
| Checks kept in the repository | `tools/twoi_checks/host.py`, `layout_probe.py`, `menu_smoke.py` | The layout probe and a new menu click-through, both against the real host on a throwaway data folder. |

## Debugging round one — RAN

- Python, fourteen 2i test files: 91 passed, 0 failed. Node: 59 passed, 0 failed.
- `python tools/twoi_checks/menu_smoke.py` (real host, 1280×800 and 390×844 with touch): 65 commands in 13 menus.
  0 script errors. No dialog larger than the window at either size. 54 ran with an effect seen by the check or
  confirmed by hand (Save saves; Lock all locks; Write note and Place sticky note open their screens after a
  short on-demand load). 2 skipped (system file chooser, system print dialog). 9 were unavailable in the state the
  check sets up and were NOT exercised: Export screenplay FDX exchange, Undo, Redo, Dialogue and scene review,
  Generate draft, Commit presented draft, Archive presented draft, Read / pause presented draft, Stop reading /
  generation. They need a screenplay profile, an undo history, a presented AI draft or a live model.
- `python tools/twoi_checks/layout_probe.py`: no script errors, nothing below the window, nothing overlapping, at
  seven hosted sizes and two disk sizes.
- Found and fixed in this round: the first drawer-closing hook lived inside `viewReferenceRecord` and broke GPT's
  `tests/test_2i_reference_safety_node.js`, which runs that function alone; a short phone screen cut the message
  box off below the chat drawer and focusing it dragged the page; the read-aloud controls belong to Collab, not to
  "while reading" as first proposed to Josie.

## Still open

1. **Menus and modes from disk (Josie: "the menus have to work").** Analysis done, nothing built. `format-menu.js`
   needs these names that only `reach.js` creates: `initializing`, `documentId` (26 uses, as a stale-document
   guard), `serverReady`, `networked`, `revision`, `uuid`, `downloadFile`, `writeRecovery`. `studio-desk.js` needs
   `initializing`, `serverReady`, `networked`, `reachFileMode`, `preserveBeforeSwitch`, `rememberStudioResume`,
   `TwoiStudioBridge`. All three host routes that serve the page (`/writers-room`, `/2i`, `/2i-v22`) are at the
   root, so a relative `2i-assets/…` address resolves both from disk and on the host. Two approaches to weigh
   before writing anything: (a) a small standalone script, loaded only when `reach.js` is absent, that gives those
   names honest offline values, with host-only commands left unavailable by GPT's own availability checks;
   (b) loading `reach.js` itself from disk and relying on its `networked === false` path, as the older
   `2i/index.html` did. (b) changes what Save does from disk and must be read line by line first. Do not load
   `speech_client.js` from disk: thirteen tests protect the browser-speech fallback there.
2. Debugging round two (repeat of round one after item 1, plus break-it checks on the new tests).
3. The nine commands listed above, in the states that enable them.
4. The word count refreshes only when the page re-renders, not on every keystroke in Write mode (as it did in the
   bottom bar).
5. Real devices: Windows, Josie's phones, an on-screen keyboard, iPhone Safari, forced colours.
6. Decisions from Josie: the spiral on a phone (dropped, or a thin strip); the same arrow tabs on a laptop now or
   in Phase A3; Section 4 of the inherited handoff.

---

# Update 2, 2026-11-16 (same branch): menus from disk, debugging round two

Supersedes "Still open" items 1 and 2 in the update above, and the earlier line "From disk, modes, the menu bar,
versions and narrative tools do not load at all".

## Changed

| Item | Paths | What and why |
| --- | --- | --- |
| Companion files load from disk | `2i/writers-room-v22.html`, `2i/2i-assets/studio-desk.css` | The eleven `2i-assets/…` addresses and `../static/2i_studio_bridge.js` are relative to the page. From disk the menu bar, views, version bar and narrative tools now load. On the host the same addresses resolve because `/writers-room`, `/2i` and `/2i-v22` are all top-level routes (tested on all three). `reach_auth.js`, `speech_client.js`, `program_audio_runtime.js` and `foresight_files.js` keep host-only addresses and stay absent from disk. |
| Which approach, and why | — | Three were weighed: a new standalone script defining the host's names (rejected: a second owner for document identity and save state); loading `reach.js` as it is; loading `reach.js` and giving Save a real file. `reach.js` already had a complete path for `networked === false` (the older `2i/index.html` loaded it from disk): browser recovery copy, `serverReady` false, so GPT's availability checks switch host-only commands off by themselves. That path was adapted, not rebuilt. |
| Save from disk writes the file | `2i/2i-assets/reach.js`, `2i/writers-room-v22.html` | New `saveToFile()` and `saveNow()`. With no host, the Save button, File › Save and Ctrl+S write the manuscript file: the same file again when one was opened or chosen, else a picked file, else a downloaded copy where the browser has no file picker. Automatic saves keep only the browser recovery copy and the status line says so ("Kept in this browser · Save to update <file>"). `openDocument()` keeps the opened file's handle. Closing the picker no longer falls through to a download. On the host `saveNow()` is `saveDocument()`, unchanged. |

## What changed for someone opening 2i from disk (tell Josie plainly)

- It now looks and behaves like 2i inside the host: three panels on a laptop, drawers on a phone, all thirteen menus.
- Unavailable there, and shown as unavailable: Revision history, Story versions, Studio Inbox, Write note, Place
  sticky note, My manuscripts' host shelf.
- The conversation partner needs the host. Before this change the bare page could talk to a model address typed
  into its settings; with `reach.js` loaded, chat goes through the host. Not tested either way with a real model.
- The page file copied somewhere completely on its own (no `2i-assets` folder beside it) still opens and writes,
  without menus, as before (`tests/test_2i_standalone_without_format_core.py`, `test_2i_narrow_screen_drawers.py`).

## Debugging round two — RAN

- Python, fifteen 2i test files: 104 passed, 0 failed; run again after the check described below was added to an existing test: 104 passed, 0 failed. Node: 59 passed, 0 failed.
- `menu_smoke.py` on the host and `menu_smoke.py --disk`, each at 1280×800 and 390×844: 65 commands, 0 script
  errors, no dialog larger than the window. From disk 14 are unavailable: the same 9 that depend on editor state,
  plus the 5 that need the host.
- `layout_probe.py`: no problems at seven hosted and two disk sizes.
- Break-it check: ten deliberate breaks, one at a time, each restored afterwards. Nine were caught by the tests on
  the first pass. The tenth (the shell ignoring the host's margin, which cuts its bottom edge off) was not; a check
  for it was added to `tests/test_2i_hosted_layout.py` and the same break is now caught. Breaks used: Save taking
  the host path with no host; a cancelled picker downloading; `reach.js` addressed for the host only; the narrow
  main-area rule removed; the drawer not closing for a reference; the unseen dot never set; the partner check
  reading `initializing` directly; the scene-line style added only with the dialog; menu widths left to the
  browser; the shell ignoring the host margin.

## WROTE, NOT RUN

- Real file pickers. The tests replace `showSaveFilePicker` / `showOpenFilePicker` with a recording stand-in; the
  page and `reach.js` under test are real. A real picker on Windows Chrome or Edge has not been used.
- Browsers that treat each `file://` page as its own private storage (Firefox does) and Safari from disk: the
  browser recovery copy may not persist there. Chromium only was run.

## Still open

1. The nine state-dependent commands (Undo, Redo, FDX export, Dialogue and scene review, Generate, Commit, Archive,
   Read/pause, Stop) in the states that enable them.
2. Real devices: Windows, Josie's phones, an on-screen keyboard, iPhone Safari, forced colours, real file pickers.
3. The word count refreshes only when the page re-renders.
4. Decisions from Josie: whether chat from disk should be able to use a model address without the host; the spiral
   on a phone; the same arrow tabs on a laptop now or in Phase A3; Section 4 of the inherited handoff.
5. Next phase: A2 (the three looks selectable anywhere, and the single-page notebook as the default outside the
   studio). Not started.
