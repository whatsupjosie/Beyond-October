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
