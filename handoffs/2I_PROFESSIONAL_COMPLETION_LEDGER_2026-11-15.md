# 2i professional completion — execution ledger

Base: `84d9e27c7e74f1345d6d07401a125b54ca2c82c2`, the narrative intelligence branch; 15 commits ahead of Fable integration, zero behind. No main merge authorized.

| Workstream | State | Acceptance gate |
|---|---|---|
| Existing implementation and branch inventory | In progress | Inspect existing components and handoff; avoid duplication |
| Command discovery and menu consolidation | Partial implemented; simulated checks passed | Shared command bindings, keyboard and touch access, no fake actions |
| Standard / notebook / typewriter presentations | Partial implemented; routing checks passed | Same document identity, no edits lost on switching |
| Twenty format presets and rich document engine | Partial inherited | Real format distinctions and lossless supported round trip |
| Narrative and editorial intelligence | Partial inherited | Evidence-linked diagnostics, author decides |
| Production notes | Partial inherited | Reuse existing service, recipient/location/end-to-end verification |
| Creative provenance and session recorder | Existing archive inspected; partial disclosure implemented | Evidence separated from AI testimony; private by default; no certification claim |
| Competitive audit | Pending | Prioritize user pain points and verified existing gaps |
| Standalone and ecosystem release gates | Pending | Independent use and shared services verified separately |
| Functional, adversarial, usability passes | Pending | Actual test results recorded, browser/device evidence distinguished |

Execution constraint: GitHub connector available; direct repository clone failed DNS in the local shell. Full repository execution, engine acquisition and browser integration tests cannot be claimed from this environment. Targeted code changes and bounded tests remain possible. Do not promote inherited implementation claims to freshly verified results.

## Checkpoint 1 — command discovery
- Implemented a searchable command palette in the existing native menu module, with shared command bindings, Ctrl/Command+Shift+P and touch button, literal multi-term ranking, disabled-control filtering and active-document guard. Added Help menu; removed duplicate keyboard-help placement from Tools.
- Eight ranking logic checks executed in the available JavaScript runtime; all passed. Seven committed-source wiring checks passed. No real DOM/browser test run.

## Checkpoint 2 — standard document presentation
- Non-studio native launches and file-workspace launches default to a restrained standard editorial paper view. Studio notebook and designated seated typewriter defaults retained. Native View menu switches presentation in-place; typewriter offered only while at an authorized designated seat (UI context, not an access-control boundary). Studio entry/exit and document save code unchanged. Typewriter artwork and sound are hidden/suppressed in other presentations.
- Nine presentation routing/eligibility logic checks executed in available JS runtime; all passed. Browser, phone, actual file workspace appearance and data-preservation end-to-end not executed. This is a first presentation pass, not WYSIWYG or final design acceptance.
- Next gates: actual Node regression and browser checks; tray rich-document opening; native state invariance and seat handoff; command availability under every editor state; menu completion; provenance; actual rich engine build and offline qualification.

## Checkpoint verification — 2026-11-15
- Re-fetched committed source at `d413e98db96e75a0f9956bbde3d0355b25d628fc` and executed 21 checks in the available JavaScript runtime: 4 syntax compilations, 11 command-search and presentation checks, 5 native formatting checks, 1 seat restriction check. All passed.
- Executed the committed format-menu.js against a minimal in-memory DOM adapter: 6/6 passed (touch dispatch exactly once; disabled command omitted; stale document prevents dispatch; Enter dispatch and event isolation; Escape cancellation; standard/notebook visible while typewriter unavailable). This is a simulated DOM, not a browser. The harness was executed in-session; the committed Node test covers the pure helpers, not the full DOM harness.
- No full repository or real browser tests run; clone DNS remains blocked. Actual Node test file was added but not executed with Node. No changes to main. No claims of verification for other inherited features.
- These checks are a bounded increment, not the mandate's three full verification passes or a completion claim. Further implementation remains open, including business-document file workspace verification, menu breadth, rich editing, competitive audit, provenance and session recording.

## Checkpoint 3 — menu completeness and safety (continuation)
- Recovered the collaboration rule: every requested requirement remains open until proven; only the author changes scope. No weaker standard for AI contributions or self-authored changes. Preserve authorship and separate existing implementation from actual operation.
- Replaced imported reference metadata HTML interpolation with DOM text and event handlers; duplicate legacy identifiers cannot make a reference-row delete remove another record. Added a searchable reference archive over the existing data, Manuscript menu, exact committed-only text export, and explicit warning that Markdown includes presented draft. All twelve requested menu headings now exist; individual missing features remain open.
- Scoped manuscript keyboard shortcuts away from dialog fields, chat inputs, composition and already-handled events; added Shift+Ctrl/Command+Z and updated help. Removed unsupported Space shortcut claim. Full native undo behavior still needs real-browser tests.
- Executed 14 shortcut-policy assertions and compiled changed JavaScript plus inline script syntax. No local repository clone (DNS independently reconfirmed); real browser/full-suite still blocked.

## Checkpoint 3 adversarial follow-up
- Menu count initially misstated as eleven; comparison against the actual user mandate confirmed twelve distinct required headings, all present. Corrected above. Four simulated reference-record safety checks passed (literal hostile metadata; exact duplicate-ID open; exact delete; stale row no-op). Existing native undo capture in reach.js retained. Node test file added but not executed under Node.

## Checkpoint 4 — private contribution reporting from existing records
- Inspected the existing narrative archive, revision store, Blackbox runtime/append-only recorder and Iteration Wallet product laws. Reused the native archive; no redundant recorder or automatic private-content transfer to Blackbox or Wallet.
- Added Review > Creative contribution records, an aggregate-only disclosure export (no source text, scene/document IDs, titles, or arbitrary archive labels), plus separately confirmed private archive export with text. Distinguishes counts of archived record types from attribution and warns about imports, forks, undo, incomplete coverage and lack of independent verification. No verdict, seal, or authorship percentages. Private export uses explicit confirmation; no automatic upload or public registration.
- Twelve pure report checks passed against the new core and three scripts compiled in the available JS runtime. UI, server persistence and physical device tests not yet done. Fine-grained attribution, opt-in recording modes, author annotation/dispute workflow, evidence integrity and Blackbox/Wallet integration are still open; report is not a substitute for them.

## Checkpoint 5 — command state and committed print snapshot
- Shared command availability now drives both native dropdown options and the palette, with a fresh execution check and failure-closed predicates. Draft operations only offered in Collab, history/versions and studio messaging require connected readiness, undo/redo menu reflects manuscript-operation stacks. Version manager reachable through Review.
- Added Print committed manuscript through formatted preview. Preview, print and exported HTML use one immutable render snapshot; sandbox permits printing but not scripts. Browser-native print support and real pagination not verified. No claim of professional pagination.
- Four command-availability assertions, exact twelve-menu order check and syntax compilation passed. Real browser, menu focus behavior and print workflow remain open.

## Continuation verification checkpoint
- Re-fetched exact committed code from `35a95511676194c1c08ad7c92654239615437cf2`. 40/40 bounded assertions passed: 9 syntax compilations (including three regression files), 14 shortcut behaviors, 5 command policy/menu checks, 6 contribution disclosure behaviors, 3 simulated reference safety behaviors and 3 print/integration source checks.
- Actual committed menu script plus actual format core executed in a minimal DOM adapter: 7/7 scenarios passed, including disabled/forged command rejection, Collab commit dispatch once, palette save/stale document guards, print load gate, same immutable preview/export snapshot, no draft disclosure, and stale-document print rejection. Simulated print counts calls, not printer/browser behavior.
- Added a reproducible reference security regression file. Full Node suite, browser, hardware, API, and print tests remain unexecuted because the checkout cannot be cloned in this environment. These 47 passed rechecks are bounded, not the three full product verification passes.
- Pending in priority order: actual checkout/browser test; real tray/DOCX build and rich round trips; chapter/scene navigation and remaining high-value commands; span-level provenance and author disputes; session recording modes and consent-bound Blackbox/Wallet integration; competitive research; market-readiness and standalone verification. No task removed or redefined. No main merge.

## Checkpoint 6 — manuscript navigation and scroll stability
- Added native searchable chapter/scene/heading navigator and direct committed paragraph jump. Scene dossier navigation is read-only and flags missing/stale scene anchors rather than moving the active AI scene. Stale document/outline actions are guarded. Solo caret offsets use exact UTF-16 selection, viewport scroll is approximate; Collab selects and scrolls the actual paragraph. Preserve Collab reading position on rerender; follow only when already at the end. Multiple existing chapters at the same line are no longer silently omitted from Collab display.
- Twelve pure assertions passed; changed scripts compiled (including inline). Actual mobile scrolling, focus, large manuscript performance and full browser integration remain unverified. No new document store. Remaining work retained.

## Checkpoint 7 — revision comparison
- Reused confirmed server revisions and captured the committed working snapshot at history opening; added a read-only comparison with exact paragraph changes, stable line positions, explicit coarse-region fallback for large documents, bounded on-screen preview and separately confirmed private full JSON export. Source revision navigation and recovery remain distinct. Closed or changed document prevents late async action dispatch.
- Diff implementation passed 114 assertions (10 fixtures, 100 deterministic generated round trips, 4 method/validation checks); script/test syntax compiled in JS runtime. Comparison excludes formatting, draft, metadata and attribution; those comparisons remain open. No real browser/API test or printer test. No new storage infrastructure.

## Checkpoint 8 — CI and formatted editor connection (dependency-gated)
- Added branch-only read-permission Node regression workflow; no CI run was reported at time of check. Direct Git checkout re-attempt failed DNS; local Node v22 and Chromium are installed but cannot access the full checkout.
- Inspected the pinned EigenPal upstream contract and existing v5 archive pack/read, then connected the existing verified rich archive path to an opt-in local DOCX editor surface, using documented engine commands/events and bundled substitute fonts. Engine load failure retains source and download controls. Changed DOCX bytes recover into the existing IDB compare-and-swap record, scoped to source ID + hash. Ordinary Save is local; explicit .2i export repackages the original and current working DOCX via existing server route and verifies returned archive digest. Direct source overwrite is not the normal Save path.
- 10 static acceptance checks plus source syntax compilation passed. Real engine bundle is absent, so actual rich editing, browser save/reopen, font fidelity, external-request restrictions, recovery concurrency, and real host integration remain unverified. This is an implementation wiring checkpoint, not a claim Word-equivalent editing is operational. Raw DOCX direct rich opening remains pending; legacy text-copy behavior unchanged.

## Checkpoint 8 adversarial follow-up — exact no-op exports
- Caught and repaired a self-authored flaw: exporting after merely opening the rich editor could unnecessarily reserialize unchanged working DOCX. Now unmodified archive exports return the exact input bytes, and clean local recovery exports use saved working bytes. Metadata-only changes do not reserialize the DOCX. Added explicit original-working download for recovery cases. Added an explicit source-only DOCX → rich v5 copy command; it preserves the formatted original and does not claim to carry plain-text edits over.
- 10 targeted checks passed against the modified source (including no-op archive, recovery and edited-package dispatch), source/test syntax compiled. Two CI runs reported failure: 43775562695 and 43775775752. Each job returned no steps and logs failed with BlobNotFound; cannot classify code versus runner failure. Do not claim CI success. Actual rich runtime remains missing from checkout.

## Checkpoint 8 browser fixture and no-op recovery revision
- Copied the exact committed rich-editor.js blob (Git object 6c78360b2b54bfc52b5c1f5ad6e12676ba3d157d) into the local tool environment and verified its Git hash. Chromium with Playwright loaded that exact source in an in-memory document. Localhost navigation was initially blocked by environment policy; no external access was required for the in-memory test.
- 14/14 assertions at both 1200×900 and 390×844 viewports (28 total), plus disabled-control, actual button click, save, Ctrl+S, network-request and page-error checks. Engine contract mock: not actual DOCX rendering, real Reach, or complete app. Previous verbal progress count of 26 in-page assertions was incorrect; inspected output lists 14 per viewport. Preserved reproducible fixture and evidence. Actual local engine still missing from repository.
- Read-only unopened rich archives now avoid unnecessary local revision writes. This follow-up compiles; full IndexedDB concurrency test remains open.
