# Why four tests in test_foresight_airgapped_ui.py failed, 2026-10-29, Claude

## Finding (observed)

The four tests that fail on clean October-24 with 30 second timeouts are not a product problem and not slow frames. Their fixture opened the Counter with `page.set_content(DOM)`, which gives the page an opaque origin. There the browser refuses `sessionStorage`, and a relative `fetch('/api/writers-room/config')` cannot be parsed. The Counter's `boot()` in `static/foresight_counter.html` asks that route who owns the workspace (`ForesightFiles.ownerScope`), so boot stopped before `counter.start()`. No frame loop ran, so a new tray stayed hidden forever. Calling `__counter.start()` by hand made the test pass.

## Changed

`tests/test_foresight_airgapped_ui.py` only: a `serve_counter(page)` helper opens the page at `http://counter.test/` through Playwright routing. It answers only `/api/writers-room/config`; everything else gets a 404, as with no host. Both fixtures use it. The iframe assertion now matches the path, because the Counter adds `?foresightSession=` to a tray's address.

## Result (Linux, Python 3.13)

Before: 4 failed. After: 2 passed, 2 failed, repeatably.

## Still failing, cause not found

- `test_real_counter_integrates_2i_hosting_and_restorable_layout`: no `iframe[src*="/writers-room"]` appears after `__programs.open('twoi')`.
- `test_real_canvas2d_can_render_five_mixed_tray_shapes`: a 30 second wait times out. It passed once in an earlier run, so it may be load-sensitive.

## Idea not applied

Tray growth in `static/foresight_counter.js` (`growStep`) eases by a fraction per frame and gives up after a fixed number of frames, so a very slow machine would take much longer. That did not explain these failures, and it is not shown to matter on real hardware, so nothing was changed. If frame rate on Josie's laptop turns out to be a problem, that is where to look.
