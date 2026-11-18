# 2i sandbox verification checkpoint | November 18, 2026

**Source branch:** `codex/2i-typewriter-manuscript-bridge-2026-11-18`  
**Checked commit before saving this report:** `337c78efada8332c025f804be6b7621efe1580b0`  
**Environment:** ChatGPT temporary container, native Node.js 22 and real system Chromium via Playwright. No GitHub Actions usage and no borrowed-computer changes.

## Summary

**19 focused checks passed; 0 failed after the last correction.**

| Group | Passed | Failed | Execution |
| --- | ---: | ---: | --- |
| Typewriter input unit tests | 8 | 0 | Native Node `node:test` |
| Cursor, text insertion and undo | 7 | 0 | Real Chromium, isolated editable page |
| Protected-line input and undo | 4 | 0 | Real Chromium, source-extracted editor guard |
| **Total** | **19** | **0** | Focused tests only |

### Native Node TAP checks (8/8)

1. Touch key inserts at retained caret instead of appending.
2. Typing over selection replaces selected text exactly once.
3. Return and space insert their actual characters.
4. Backspace removes previous whole grapheme, not part of an emoji.
5. Shift, invalid controls and read-only cannot modify manuscript.
6. Native browser insertText path avoids duplicate input events.
7. Cancelled beforeinput prevents a fallback write.
8. Cancelled beforeinput stops native insertion before execCommand runs.

Test command in sandbox: `node --test tests/test_2i_typewriter_input_node.js`. Node TAP summary: 8 tests, 8 passed, 0 failed, 0 skipped, duration 93.966275 ms.

### Chromium typewriter checks (7/7)

1. Native insert preserves Chrome undo.
2. Native selected-text replacement and undo.
3. Backspace emoji grapheme and undo.
4. Return uses newline in a real textarea.
5. Backspace at the document start is a no-op.
6. Cancelled beforeinput blocks real native insertion.
7. Two consecutive native keys followed by real Ctrl+Z.

### Chromium protected-line checks (4/4)

1. Native key cannot modify a locked line (no dirty state).
2. Native key in an unlocked line succeeds and marks document dirty.
3. Adding a newline before the protected line shifts its lock index.
4. Undoing that newline retains protected text and correct lock indexing.

The browser checks used constructed pages backed by the actual GitHub input adapter and extracted 2i editor protection logic. They did **not** run the complete hosted writer application.

## Defect reproduced and fixed

The first seven Chromium checks initially produced **6 passes, 1 failure**: the native `document.execCommand('insertText', false, text)` path could bypass cancellation of `beforeinput`. A subsequent probe confirmed Chromium emitted `input` but no cancellable `beforeinput` for this path.

The adapter now dispatches a cancelable `beforeinput` **before invoking either the browser-native or fallback insertion route**, so an editor that rejects the operation is not altered. A new Node regression prevents this behavior from returning. The repair retained browser-native undo on successful edits.

- Fix: `ed32c5f5073c7d1746f3fc9bff414cb8084580de`
- Regression: `337c78efada8332c025f804be6b7621efe1580b0`
- Verified GitHub blobs: `2i/2i-assets/typewriter-input.js` = `421eb2d182b392b5f5769df409ea0a397d83241d`; `tests/test_2i_typewriter_input_node.js` = `7d61738d787bc04a9cac2f78dced2cb096e2a143`.

## Outstanding release gates

- A complete combined-branch checkout and native full Node/Python suite.
- Actual PubCast/2i host startup in Chromium.
- Save Now → close/reopen → compare → offline recovery (real storage and server).
- Integrated Claude/Fable undo, protected content, replacement, writing views, mobile, and typewriter from the actual host.
- Studio recording acceptance, 30-minute capture, packaging and final independent review.

**Environment limitations:** browser navigation to the sandbox's own HTTP server was blocked (`net::ERR_BLOCKED_BY_ADMINISTRATOR`), and GitHub's download host could not be resolved for a full checkout. An isolated successful test does not certify that the integrated application passes.

## Preservation

Original Claude and Fable branches, their exact-head backup branches, and `main` remained unchanged. Review the chain of draft PRs #9, #10 and #11. Do not merge as beta-ready on this evidence alone.
