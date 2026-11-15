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
4. Server-side authorization and protected-region checks beyond client proposal-only mode; permanent versions and restore UI; archive capacity and storage retention. Existing 2 MB document state limit remains.
5. Cross-scene knowledge registry with evidence and false beliefs, character canon/voice profiles, adaptation mapping among separate media versions, editorial flags with quoted evidence. Scene fields and matrices are currently explicit author-editable entries, suggestions remain advisory.
6. Audit privacy for selected provider: explicit model request includes reference text. Native manuscript integration only; file mode unchanged. Test legacy provenance, undo, standalone fallback and navigation.
