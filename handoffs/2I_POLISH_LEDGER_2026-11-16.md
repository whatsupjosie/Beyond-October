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

---

# Update 3, 2026-11-16 afternoon: branch `fable/2i-beta-polish-2026-11-16` (Claude Fable 5.2)

Started from GPT's `codex/2i-ui-readability-2026-11-16` at `f47b11b`, which itself sits on `fable/2i-polish-2026-11-16`
(`51a34ca`) plus GPT's five commits of 2026-11-16 (offline save bound to the manuscript snapshot, file conflict
protection, narrow-tray save test, menu label width, readability pass). One line of history; nothing diverged.
`main`, GPT's branches and the earlier Fable branches are untouched.

## What Josie said (2026-11-16, her words)

- "I want you to go over it, and by the time we're done, I want it to be full-on polished and ready for a beta.
  The official beta."
- With the notebook picture (`2i/2i-assets/writers-room-art.webp`, the same image she sent): "this is closer to
  what I wish it would look like."
- With the Rearview Foresight monument and four Pub Partner screens: "what I hope will get Foresight to look like".
- "Please make sure that this is good and complete and perfect. This is my entire weekly limit you're about to
  spend."

Reading used, told to her and not objected to: the picture is the direction for the notebook's LOOK; where the
picture and her later instructions differ (bottom bar, top tabs, always-open side panels), her later instructions
stand. NOT CONFIRMED in so many words.

## Found by opening `f47b11b` and looking (all tests were green at the time)

1. Collab: a blank line between paragraphs collapsed to 2 px and its number printed over the next number.
2. Write: numbers counted paragraphs at a fixed row height, so each wrapped paragraph pushed later numbers off
   their lines (five numbers beside six rows at 1280 px, beside seven at 390 px).
3. Switching to Notebook view from the standard page left the spiral blank until the window was resized (the
   canvas was sized only on window load/resize, while hidden: 0 × 0).
4. The word count stayed at "0 words" while typing in Write (only `render()` refreshed it).
5. Phone: the bars take about the top third of the screen before the page starts. NOT CHANGED, see below.
6. A "404" in the browser console on the host. Identified: `GET /api/writers-room/documents/<new id>` and
   `.../versions` for a brand-new document that has not been saved yet. The host is right to answer "not found";
   nothing is missing and nothing breaks. NOT A BUG; no change.

## Changed

| Item | Paths | What and why |
| --- | --- | --- |
| Paragraph numbers | `2i/writers-room-v22.html` (`updateLineNumbers`, `.line-numbers`, `#lineMeasure`) | Each number is as tall as its own paragraph, measured in a hidden copy that has the writing box's font and width. Only changed paragraphs are re-measured. Numbers move with the text by transform (the old scrolled column stopped short at the end). Re-laid out on width change, look change, text-size change and when the page's lettering finishes loading. |
| One owner for the row height | `2i/2i-assets/reach.css`, `2i/2i-assets/studio-desk.css`, page | Four hard-coded copies of the number row height (36.3 px, 35.65 px, 25.6 px, 28.05 px, and the page's own `2.00208`) are removed. The row height and top padding are read from the writing box (`--solo-row`, `--solo-pad-top`). |
| Blank lines in Collab | page (`.m-line`) | A committed line is at least one row tall. The number is now the line's first flex item, on the baseline of its first row (it used to hang from the top), and an invisible first character gives blank lines that baseline too. Hover/selection set `background-color` only. |
| Spiral | page (`drawSpine`, `.spiral-spine`) | Drawn as one brass coil through holes in the paper's edge; the canvas reaches `--ring-overhang` over the paper. Redrawn by a `ResizeObserver` whenever the binding changes size, including coming back on screen. |
| Notebook page | page (new section "THE NOTEBOOK PAGE") | Ruled lines (`1lh` per row, scrolling with the text, running on under the numbers), the red margin line as the page's own part, a strip for the holes, the draft box filling the lower page in Collab, whole-pixel rows. Applies to every look except standard and typewriter. Inside `@supports`, so a browser without `lh` gets an unruled page, not a broken one. |
| Focus on the page | page | In the notebook the full-sheet focus box from `f47b11b` is replaced by the margin line darkening (the caret is in the text). Forced-colours mode keeps the system outline. Every other control keeps GPT's outline. CHANGES A CHOICE GPT MADE; told to Josie. |
| Word count | page (`updateWordCount`, `countWordsSoon`) | One function, used by `render()` and, once per painted frame, by typing in the writing box and in the draft. |
| Tests | `tests/test_2i_notebook_page.py` (new, 14 cases at laptop and phone size), `tests/test_2i_narrow_screen_drawers.py` (the word-count check no longer calls `render()` first) | See RAN. |

Three approaches were weighed for the numbers: (a) number every visual row, as the picture does; (b) keep one
number per paragraph and measure each paragraph's height; (c) replace the textarea with a rich editor. (b) was
chosen: a number keeps meaning the same paragraph in Write and Collab (lock, select and comments use that index),
and nothing about how text is stored or typed changes. (a) differs from the picture's row-by-row numbering; Josie
has been told.

## RAN (real output, Linux sandbox, Python 3.13, Playwright 1.63.0 headless Chromium 153, Node 22)

- Node: `node --test tests/test_2i_*_node.js tests/test_twoi_rich_browser_contract_node.js tests/test_foresight_file_close_node.js tests/test_foresight_file_navigation_node.js` → 70 passed, 0 failed (same on `f47b11b`).
- Python, fourteen 2i files (the thirteen run on `f47b11b`, 97 passed there, plus the new one) → 111 passed, 0 failed.
- `tests/test_2i_notebook_page.py` against the page as it was on `f47b11b` → 14 failed. Against this branch → 14 passed.
- The existing phone tests caught one mistake of mine on the way (the draft box showing in Write on the bare page); fixed before commit.
- `tools/twoi_checks/menu_smoke.py`, host and `--disk`: exit 0, 65 commands each, same available/unavailable counts as before.
- `tools/twoi_checks/layout_probe.py`: exit 0, nine scenarios, no page errors, no failed requests.
- Measured on the real host: the numbers' heights add up to the text's height (216 = 216 px notebook; 168.29 vs 168 px standard); Collab rows 28, 28, 56, 28, 28 px.

## UNKNOWN / not tested

- Windows, Josie's laptop and phones, a real on-screen keyboard, Safari and Firefox (`lh`, `round()`, `:has()` each
  have a fallback or are progressive, but only Chromium was run), a real GPU browser, forced colours, a live model.
- A very long manuscript's typing speed was not measured; the design re-measures only changed paragraphs.
- The typewriter look was photographed after the change and looks as before; it has no new tests.
- Opening 2i from the writers room (`/2i?studio_room=writers_room&studio_view=...`): the check was interrupted and
  not rerun.

## Not built: Josie's page design (read against her stated design; none of this was started here)

- Standard page: tinted paper, faint blue lines, centred with adjustable margins, spiral image at the side, only
  the top menu and the writing showing.
- Typewriter selectable from any window (today only when opened at a studio typewriter); clicks and bell off
  unless turned on (today on by default, `studio-desk.js`); the key-bar row; letter-by-letter AI text (not checked).
- Collab as the open two-page notebook; panels as slide-out drawers on a laptop; several documents open at once;
  the amber main-document tab; the file drawer and preview in the message box; sharing.
- The picture's brass frames and ornaments on the panels, its Scene Ideas box and AI suggestion card.

## Decisions needed from Josie

1. Phone header: what gives way so the page starts higher (the version bar's second row, the name line, or the
   menus behind one button).
2. In Collab, committed text is set in a print face and the draft in handwriting (GPT, `f47b11b`). The picture
   shows handwriting throughout. Keep, or handwriting for both.
3. Numbers: one per paragraph (now) or one per row (the picture).
4. The logo's sign reads "Rear View"; the company name in use is "Rearview".
5. Still open from before: the spiral on a phone, arrow tabs on a laptop, Section 4 of the inherited handoff.

## Next step

Josie's answers to 1 to 3, then the standard page (her single-page notebook), which is the default wherever 2i
opens outside the studio.

---

# Update 4, 2026-11-16 evening: the single-page notebook and the typewriter from any window (Claude Fable 5.2)

Same branch, `fable/2i-beta-polish-2026-11-16`, on top of `53af0a3`. Josie, 9:16 pm: "we've made no progress.
Please, take us over the finish line ... Functionally, practically, beautifully." She did not answer the three
questions at the end of Update 3; they are still open and nothing here depends on them.

## Built (each against her stated design, quoted in `tests/test_2i_single_page.py`)

| Item | Paths | What |
| --- | --- | --- |
| Single-page notebook | `2i/2i-assets/studio-desk.css` | The standard look is now her single page: warm off-white paper (`#fbf6e6`, was `#fffefa`), faint blue rules the writing sits on, the brass binding at the left edge (hidden on a phone), the red margin line, centred. Focus is the margin line darkening, not a box round the sheet. |
| Adjustable margins | `2i/writers-room-v22.html` (`#twoiMarginSelect`), `studio-desk.css` (`--page-margin`) | Narrow / Normal / Wide / Extra wide in the page's header row, single page only, remembered (`localStorage` key `twoi.page.margin.v1`). A phone never gets more than 14 px. |
| Only the writing shows | page, new block "THE SINGLE PAGE ON A WIDE SCREEN" | At laptop width, on the single page in Write, both side panels are put away. Small arrow tabs sit just under the menus. Left tab: tools out beside the page, and away again. Right tab: opens the AI side, which starts Collab; in Collab the panels are where they were. The ☰ button does the same as the left tab there. |
| Messages are not lost | page (`conversationAway`, `markUnseen`) | A line arriving in the conversation while it is put away (a reply, or an error such as "Speech stopped") puts the amber dot on its tab at laptop width too. Before this change the dot existed only on narrow screens. |
| Typewriter from any window | `2i/2i-assets/studio-desk.js` (`canPresent`) | The View menu offers Typewriter view everywhere. A studio seat still decides which look 2i opens in. |
| Typewriter sound off by default | `studio-desk.js` | `click` and `bell` start `false`; a stored choice is kept. |
| Tests | `tests/test_2i_single_page.py` (new, 6), `tests/test_2i_hosted_layout.py`, `tests/test_2i_speech_wiring.py`, `tests/test_2i_professional_ui_node.js` | Three existing tests assumed the panels always show at laptop width, or that the typewriter is seat-only; they now state the new design. |

## RAN (same sandbox as Update 3)

- Node: 70 passed, 0 failed.
- Python, fifteen 2i files: 117 passed, 0 failed.
- `menu_smoke.py`: host and `--disk`, exit 0; 66 commands each (one more than before: Typewriter view).
- Looked at on the real host at 1280 and 390 px: single page, tools out, Collab by the right tab, typewriter.

## UNKNOWN / not done

- Not run on Windows, Josie's devices, Safari or Firefox.
- The typewriter chosen from an ordinary window has the typewriter paper and type, but the typewriter picture and
  its sound switches are still built only at a studio seat (`studio-desk.js`, the `config.seated` branch). The
  key-bar row and letter-by-letter AI text are not built or not checked.
- The single page in Collab is the old one-page layout with panels beside it, not the open two-page notebook.
- On the single page in Write there is no conversation on screen at all; a message shows as a dot on the tab, not
  as words. If she reads aloud from Write and the voice fails, she sees the dot, then the words after opening the side.
- Phone header height: unchanged. Several documents at once, the amber main tab, the file drawer, sharing, and the
  brass frames from her picture: not started.

## Next step

The open two-page Collab notebook, then the phone header (needs her choice from Update 3, question 1).
