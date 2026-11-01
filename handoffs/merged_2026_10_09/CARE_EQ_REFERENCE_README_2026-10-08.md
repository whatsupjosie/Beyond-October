# CARE / Baby Ambiguator / EQ Monitoring — Experimental Integration Package

This is a **new, independently runnable reference package**, not a claim to reproduce or patch the inaccessible October 3 source ZIP. It does not replace PubCast's existing implementation.

## Working behavior
- Owner-scoped explicit activation (`CareSession.activate`).
- Care-facing semantic masking of adult text while in baby mode.
- `parachute` bypass and immediate return to ordinary mode.
- Structured EQ event observations and hypothesis/alternative/outcome fields, exportable as JSON.
- Stable interface: replace `Ambiguator.transform` and care-facing presentation without replacing monitoring or session orchestration.

## Important limits
- Does not intercept ChatGPT conversations or automatically run across chats; requires a hosting adapter that explicitly invokes `receive` on every turn.
- Does not claim to infer feelings from text length, babble, or telemetry. Hypotheses require evaluation against actual outcomes.
- No raw adult text is included in the care-facing output; metadata and SHA-256 are logged. This reference does not provide full BlackBox verbatim capture, encryption, consent management, or model integration.
- No automatic activation based on distress is enabled in this reference: that requires the existing CARE policy and a reliable owner-authorized trigger implementation, not a guessed replacement.
- The safeword check is performed before masking. An actual production implementation needs a separate protected safety channel.

## Run tests
`PYTHONPATH=. python -m unittest discover -s tests -v`

## Next integration step
Connect this as a module in the authoritative PubCast entrypoint, route all Josie-only care-facing inputs through `receive`, and preserve the original October Baby Ambiguator semantics by diffing against its actual source when available. For ChatGPT-wide operation, a supported external app/integration is required; this ZIP alone cannot change ChatGPT platform behavior.
