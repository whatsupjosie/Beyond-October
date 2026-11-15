# 2i Narrative Intelligence — initial implementation (2026-11-15)

Base: Fable checkpoint 764874a; main untouched.

- Scene dossiers with stable IDs, explicit author-set line ranges, medium, cast and objectives, dramatic purpose, knowledge per recipient, subtext, ambiguity/reveal plan, choreography, emotional/dramatic change, dependencies, impact and editorial attention.
- Advisory dossier suggestions and scene review use the existing selected LLM route; neither writes manuscript text. Drafting uses full active section, up to three preceding chapter starts (or roughly three pages), recent discussions, confirmed decisions, references and latent material. Oversized requests fail rather than silently truncate locally.
- The visible AI draft satisfies a canonical two-page APPROXIMATION (500 words, 3000 Unicode code points, 50 60-column rows); overflow remains latent and must be reconsidered on a new request. No automatic generation from playback. Commit/archive explicitly before requesting more; mode switching does not approve. Stale responses are archived, not presented. Latent text follows its own scene.
- Fixed mismatched manuscript project/title identity, null instruction and pending-generation partner/document switch guard.

## Verification
Ten isolated pure-core checks actually executed in the JavaScript execution environment against the function serialized into narrative-core.js (10 passed). Not browser or repository tests. Added Node regression tests. No repository clone/runtime connectivity, real model calls, browser, Windows or full-suite verification in this session.

## Release gates
1. Browser test with scripted five-page reply; change author decision; archive and reconsider latent; verify playback cannot generate or commit; reload active draft; switch device/partner/document; deliver stale response late.
2. Run Node/editor/storage/speech focused tests and full suite. Verify model JSON compliance and provider-side context limits; no silent omission of active section.
3. Exact rendered pagination; durable paragraph anchors replacing numeric ranges guarded by fingerprint.
4. Server-side authorization and protected-region checks beyond client proposal-only mode; verify new revision history and restore UI; archive capacity and storage retention. Existing 2 MB document state limit remains.
5. Cross-scene knowledge registry with evidence and false beliefs, character canon/voice profiles, adaptation mapping among separate media versions, editorial flags with quoted evidence. Scene fields and matrices are currently explicit author-editable entries, suggestions remain advisory.
6. Audit privacy for selected provider: explicit model request includes reference text. Native manuscript integration only; file mode unchanged. Test legacy provenance, undo, standalone fallback and navigation.

## Revision preservation follow-up
- Every successful owner-scoped save now stores a compressed, SHA-256-checked revision snapshot in the same SQLite transaction as the current document. Existing databases seed the most recent pre-upgrade revision, not previously overwritten versions. A stale write cannot create a revision.
- Native editor's Revision history UI lists confirmed server revisions, pages backward, exports .2i, or imports a selected revision as a new recovered manuscript without overwriting the current one.
- Added API tests covering stale writes, pagination, owner isolation, corruption and pre-existing database migration; passed in an isolated fixture (details below). Run against the actual repository before merging. Compression/checksum detects corruption but is not tamper-proof storage, backup, or a retention policy. The existing document-size bound is unchanged.

## Additional verified evidence (isolated reproductions)
- Node v22-compatible test runner: 5/5 tests passed, 0 failed, on local file copies whose Git blob IDs exactly matched the committed narrative core (f658b7566d61c305e85b7c5617e51c7cfe704c6d) and Node tests (878dd911f9141b97abe0d4aa308acc3168cee684). This executes the pure core only, not the browser integration. These overlap with the earlier ten core checks; do not add them as a unique total.
- FastAPI/SQLite fixture: 2/2 tests passed, 0 failed, on byte-identical committed module (eb4a2af2613d808c7beb0c6aec7056570e8a4af7) and tests (f10064625acd8d57c47ce2205bb9d6efae71bf23). The identity and default provider imports were stubs and the identity dependency was overridden. Verified revision retention, conflict, pagination, owner isolation, checksum failure and latest legacy revision migration; not real host authentication or browser recovery UI.
- Review-only follow-up: validate narrative state before import/switch, and make a recovered revision start independent live conversation session IDs while retaining historical messages. Browser execution remains a release gate.

## Color-coded version identity (follow-up)
- Permanent per-story version ordinal, parent/version source, independent main and designated working references, open-here marker, departed flag and revision-specific review state. New story roots default to main/working; existing pre-feature documents are independent roots (unknown lineage is not guessed). A fork of a saved revision leaves source untouched and preserves conversation text with independent live session IDs. No automatic promotion.
- Editor strip, browser title, shelf, family dialog. Color palette cycles after 12 but ordinal is always shown. Gold needs review / green reviewed; departed text and dashed stripe. Changes to any saved payload revision conservatively invalidate review. Stale server status explicitly labelled.
- Connected native manuscripts only; offline unconfirmed copies retain existing behavior. User chooses main/working/retire/review; no model authority. Server scopes metadata to owner and compares family epoch and revision before changes. Branching a conflict recovery copy remains a separate root.
- Executed 8 focused pure JS assertions against the function serialized into version-identity.js; no browser or server execution in this turn. Added Node and API regression files, not run. Verify cross-tab focus and status refresh, recovery lineage, old database migration, concurrency, auth, keyboard/mobile, browser layout and full suite before merge.

## Second-pass audit (2026-11-15)
- Repaired legacy autosave restore so ordinary native manuscripts recover as separate copies instead of overwriting the active ID. Imported copies get independent live conversation IDs; startup prefers the selected document's own recovery and validates server state.
- Scene switching now archives unassigned legacy material instead of leaking it across scenes. Preserved last-read recovery candidate and generated-line provenance; included recent author review outcomes in the next generation packet. Confirm a commit if its original scene/decision context changed. Added explicit cancellation and unsaved-dossier warnings.
- Version manager can open another family member directly; marks departed branches with dashed editor stripe; browser title includes roles. Fork response guarded against editor changes. Added consistent server read transaction and clearer registry error.
- Corrected shared request abort cleanup, authenticated manuscript indexing fetch and stale index status guard; reset per-document manuscript intelligence on load.
- Executed 13 JS assertions/parse checks on the actual source strings to be committed, including 30 page partition cases. No execution of browser, live provider, Python API or full repository in this pass. Added Node regression test file, not run under Node. Remaining: full auth/host test, independent multi-tab conflict recovery and URL pinning, exact rendered pages, server author-vs-model permissions, long context and archive size retention, stable passage IDs, automatic cross-scene facts, adaptation and full regression.

## Further polish: parallel editors and recovery (2026-11-15)
- Native version manager can open another version in a separate tab. Its document identity is pinned in its URL; reload recovers that editor's own pending buffer when available. A new explicit-version tab does not adopt another tab's dirty copy.
- Local dirty recovery keys and IndexedDB snapshot slots are isolated per editor; old recovery copies remain readable. Ambiguous unsaved copies are offered separately. Opening a local recovery makes an independent manuscript rather than silently overwriting a version. A missing explicitly requested ID cannot be reused for an empty replacement.
- Guarded delayed manuscript intelligence and health responses against acting on a different document after switching.
- Executed 12 checks against source in this pass (8 recovery-selection assertions, 4 JavaScript syntax checks). Added persistent Node regression tests; not run in Node. No full browser or server integration run; true multi-tab recovery, storage pressure, auth and persistence remain acceptance tests. Older recovery records are deliberately not silently purged; retention management remains open.

## Editorial safety and undo follow-up
- Undo/redo restores working narrative metadata and provenance while retaining creative archives; displaced latent and draft material is archived. Generation snapshots precede latent changes. Mode changes are undoable. Protected manuscript lines remain intact during Find & Replace and solo editing; solo lock shifting is deliberately conservative for complex edits. Inline editing cannot silently cross a locked line.
- Native narrative generation isolates its model session from ordinary partner conversation and avoids supplying a second truncated manuscript packet. This is client-side routing isolation, not a certified server-side memory boundary. Existing model/provider context limits remain to be verified.
- Executed 12 source checks (7 behavioral assertions, 5 syntax checks). Added Node regression file. Full browser/provider/auth/server integration still pending; author-versus-model permission enforcement remains open.
