# 2i beta polish pass - 2026-11-17

Branch `2i-beta-polish` (from `main` at c82069b). Not merged.

Josie asked for a polish pass toward the 2i beta, run as a marathon. Her stated design for 2i (spiral notebook look, phone support, two documents open, slide-out drawers) is in her memory notes, not repeated here. This pass fixed what was broken in the page the host actually serves, `2i/writers-room-v22.html` (`/2i` and `/writers-room`). It did not build new features.

## Decision asked of Josie, not yet answered
The repository holds two editions of 2i:
- `2i/writers-room-v22.html`: served. Newer working parts (sign-in, PubPartner manuscript features, file workspace, speech, per-pane zoom). Plain look.
- `2i/index.html`: not served by any route. The September painted spiral-notebook desk (`2i/2i-assets/writers-room-art.webp`, `artwork.js`, `desk-controls.js`, `reader.js`) with a phone edition (`phone.js`, `phone.css`, see `PHONE_EDITION.md`). It is kept for `tools/phone_local/build.py` and its tests (`UNIFIED_INTEGRATION_HANDOFF_2026-10-09.md`). It lacks v22's newer parts.

Recommendation given to Josie: bring the notebook artwork and phone edition into v22. The layers call page functions that v22 also has (`approveBuffer`, `closeMenu`, `coWriting`, `draftArea`, `viewRef`); `showShelf` comes from `reach.js`. v22 adds controls the art does not place (`ppStatus`, `ppFlags`, `ppCast`, zoom controls, `partnerNote`, `speedSlider`), so the port needs placement work, not just script tags. **Do not start it without her answer.**

## Found and fixed (each with a browser check that fails on the previous code)
1. **The Reach desk layer was half applied.** `reach.css` is designed to load after the page's own styles (as in `index.html`); v22 loaded it before, so the page's base rules beat it. On a phone the sidebar took the screen and the chat was a sliver; at 1366 x 768 the status bar and Save ran off the bottom. Moved the link after `</style>`. Because the layer then wins, its fixed text sizes now multiply v22's zoom variables (`--zoom-manuscript`, `--zoom-chat`; default 1, so `index.html` is unchanged), and line numbers follow the same zoom. Narrow screens: one column, wrapping top bar, Save pinned to the bottom, tighter phone spacing. "My manuscripts" is a pill that fits its label. Spiral coils and the lantern light are redrawn whenever their box changes size.
2. **Ctrl+Z in a text box rolled back the manuscript.** Reproduced: write, Lock scene, keep writing, open Find, type, Ctrl+Z: everything written after the lock was gone. Undo and redo now stay native in every text box (a collab line being edited in place keeps the manuscript undo, as before). Ctrl+Shift+Z is redo; shortcuts work with Caps Lock on.
3. **Locks did nothing in Write mode.** A locked line could be typed over, cut or pasted over, and adding a line above it moved the lock onto another line. Every Write-mode edit is now compared line by line with the text before it: an edit that would change a locked line is put back with a note; locks move with their lines. Locked line numbers are marked. Unlock in Write mode unlocks the line with the cursor.
4. **Replace all** counted each match twice in Write mode and replaced inside locked lines. Fixed; it reports how many it left in locked lines.
5. **Undo of a lock in Write mode** put back that moment's words, discarding later typing, and left the page showing different words from the ones saved. It now steps back locks and chapters only.
6. **Interface messages spoke as the partner.** "Unlock the line first", "Generation failed", "Loaded: ..." appeared as said by Alex. They now come from the Writer's Room; only real partner replies carry the partner's name.
7. A cancelled New chapter left an empty undo step.

Files: `2i/writers-room-v22.html`, `2i/2i-assets/reach.css`, `2i/2i-assets/reach.js` (undo guard widened), `tests/test_2i_polish_browser.py` (new, 33 checks).

## Verified (RAN)
- `tests/test_2i_polish_browser.py`: 33 passed. Layout checks at 11 sizes, 320 x 568 to 1920 x 1080: nothing off the side, Save, menu, settings and My manuscripts on screen, the writing page on the first screen. 16 of the layout checks fail on the previous files; every keyboard and lock check fails on the previous code.
- Related suite (`-k "2i or writers or foresight or reach or phone or workbench or pubpartner"`): 399 passed, 2 skipped.
- Full suite on the branch (commit 9759547, Python 3.13 sandbox): 2283 passed, 6 skipped (optional model/research tests), 0 failed, 724 s. Working tree clean afterwards; Alex vessel blob still 96fa66a728d07d5ff43b0d3d7fc17a466765cec1.
- Clicked through on the real app (`run_reach.py`, disposable data dir): every menu item opens its dialog; Find & Replace, Rename, Export (`.md`), shelf, Collab commit, line lock, edit, insert, delete and undo all work. Chat and Generate with no model report "Ollama is not reachable" in the chat as a Writer's Room note.

## Not verified / not done
- Not tried on a real phone, iPad or Safari.
- New chapter and the word goal still use the browser's prompt boxes.
- Opening a new document replaces the open one (the old one is kept on the shelf). Josie wants two documents open at once; not built.
- Typewriter Collab skin, slide-out drawers, read-aloud of a selected line, reference preview box, sharing: not built (her design notes).
- On first load a new document asks the host for itself and gets a 404 (handled; shows only as a red line in the browser console).
- `static/program_audio_runtime.js` polls `/api/program-audio/events?after=0` about twice a second and never advances `after`. Noticed, not investigated.
