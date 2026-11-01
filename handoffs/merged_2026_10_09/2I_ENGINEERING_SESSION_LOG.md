# 2i Writer's Room — Engineering Session Log

Companion to `MANUSCRIPT_MAP_DESIGN_NOTES.md`. This covers the actual build/
verification work done on the codebase this session — what was checked, how,
and what it found. Everything here was confirmed by running real code
(Python, Node, a spec-accurate CSS resolver, a simulated DOM), not by
reading and trusting documentation.

## 1. Manuscript Intelligence Wiring Verification (v21)

Checked `V21_STARTUP.md`'s claims about the PubPartner manuscript-
intelligence integration against the actual `pubpartner-manuscript-
intelligence.zip` package and `pubcast-2i-writers-room-v21.html`.

**Confirmed real:**
- `tests/test_manuscript.py`: 105 passed, 0 failed, on real Python 3.12.
  Covers hashing, authority chain, continuity, voice training,
  model-failure resilience, concurrency.
- `demo_end_to_end.py` runs with no model, no network — indexes
  chapters, catches a real name-collision continuity flag, builds a
  voice profile, produces a generation prompt.
- `tests/test_http_live.py`: had to install `fastapi`/`httpx` and fix a
  hardcoded path in the test file to get it running at all. Once fixed:
  all 8 routes respond, hash gate works over HTTP, all 6 error-path
  checks return correct status codes.
- The v21 HTML wiring claims are exactly true. Diffed v20's script
  block against v21 line-by-line — the only changes are the 5 call
  sites the doc names (`approveBuffer`, `generateMore`, reject button,
  line-edit-save, one added script block). `ppWordCount()` bug fix is
  real (v20 has zero `countWords` references anywhere). Provenance
  gating (`PP_GEN`) genuinely checks "was this line model-generated"
  before firing a rewrite training signal.

**One inflated claim found:** the README says the hash function is
"byte-verified against 2i's JavaScript across eight cases including
emoji and CJK." The actual test has 6 checks, and only one (the empty-
string case) pins a real expected value — the rest only confirm it
doesn't crash on unicode, not that it matches real JS output. Turns out
not to matter functionally (the server hashes chapters itself from raw
text; the client never computes or sends a hash), but the sentence
overstates what was tested.

**What's not actually done, despite reading like it's close:** "drop
`modules/manuscript/` into PubPartner" is still an instruction, not a
witnessed event. Nothing in the uploaded files — including
`NowCurtsey-Build-main.zip`, which predates this package by 11 days —
shows it actually living inside a running PubPartner Horizon `main.py`.

## 2. Per-Pane Text Zoom (v21 → v22)

Built three independent zoom controls (manuscript, chat, reference
viewer) — font-size only, buttons never resize, persisted via
`localStorage`.

**Bug #1 — caught by running it, not reading it:** first draft called
`loadZoom()` from inside `init()`, but `init()` lives in the *first*
`<script>` block and runs to completion before the *second* block
(where `loadZoom` was defined) even executes. Real `ReferenceError` on
every page load — and because it was the first line of `init()`, the
crash would have silently skipped everything else `init()` does: mode
UI, the initial render, spine drawing, the autosave-recovery check.
Fixed by moving the call to where it's actually defined.

**Bug #2 — caught by installing a spec-accurate CSS resolver, not by
trusting memory of the CSS spec:** the line-numbers gutter fix used
`calc(... / 12px)` to keep the gutter's line-height in sync with the
textarea's. Installed `@csstools/css-calc` (a real implementation of
the CSS calc() type-checking algorithm) and fed it the exact
expression — it came back unresolved. CSS `calc()` division only
allows dividing by a plain `<number>`, never by another length. Fixed
by precomputing the ratio as a literal number (`2.00208`) multiplied by
the zoom variable instead.

**Side effect fix:** the line-number gutter in Solo mode never actually
lined up with the text even before this session's changes (18.6px line
pitch on the gutter vs. the textarea's real 24px) — fixed as part of
the zoom work rather than built on top of.

**Verification method:** installed `jsdom`, loaded the real HTML file,
clicked the real buttons via `dispatchEvent`, read the real computed
CSS variables and `localStorage` writes, simulated a page reload against
the same storage, hammered the +button 30x to confirm clamping at 200%,
and fed it deliberately corrupted `localStorage` to confirm it falls
back cleanly instead of crashing boot.

## 3. Full Button Audit (v22)

Enumerated all 60 `<button>` elements in the file and clicked every one
in a live simulated DOM.

- **58 wired and confirmed executing cleanly** — every handler function
  referenced by an inline `onclick=` or a `.onclick =` assignment
  actually exists, and every one ran without throwing.
- **1 false alarm, confirmed as an environment gap, not an app bug:**
  `exportBtn` throws `URL.createObjectURL is not a function` — but a
  completely blank jsdom instance with *none* of this app's code loaded
  shows the same `undefined`. `exportManuscript()` itself is the
  textbook-correct Blob → object-URL → trigger-download pattern, which
  every real browser has supported for over a decade.
- **1 genuinely dead button:** the "Manuscript" tab at the top of the
  app (`<button class="top-tab active" data-tab="manuscript">`) has no
  `onclick`, no `id`, and nothing anywhere in the JS references
  `.top-tab` or `data-tab`. Clicking it does nothing — reads like
  scaffolding for a multi-tab layout that was never wired up. Harmless
  today since it's the only tab and already shows as active.

## 4. Lock Scene — Exact Mechanics

Traced the real implementation rather than going by the button's name:

- There is no separate "scene" concept in the code. "Lock Scene" means
  "everything since the last chapter marker." No chapter markers ever
  clicked → the whole manuscript is "the scene."
- Finds the most recent chapter whose start line falls within the
  currently committed text, then locks every line from there to the end
  of `committed`.
- Operates purely on array indices in the `committed` data — not
  viewport, not scroll position, not anything visible on screen.
- Only touches `committed` lines, never the active draft/buffer text.
- **Solo-mode nuance:** in Solo mode, `committed` is a live mirror of
  the textarea, updated on every keystroke — so "Lock Scene" there
  locks everything through literally your last keystroke, not a
  considered/reviewed cut point.

## 5. "New Chapter" Button — Why It Exists

Confirmed four real consumers of the `chapters[]` array, not just
decoration:
1. Visual section-break headings rendered directly in the manuscript
   view (`.chapter-heading`/`.chapter-subtitle`).
2. Markdown export headers (`## Chapter Title`) inserted at the right
   point in the exported `.md` file.
3. Lock Scene's boundary definition (see above).
4. The PubPartner manuscript-intelligence integration — `ppChapters()`
   segments content by chapter for indexing; `ppCurrentChapterIndex()`
   tags voice-training signals with which chapter they happened in.

All four degrade gracefully (not crash) if no chapter markers exist —
they collapse to treating the whole manuscript as one chapter/scene.
