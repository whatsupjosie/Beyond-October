# PubCast EQ & Conversational Intelligence — AI Development Handoff

**Date:** 2026-11-10  
**Purpose:** Preserve the discussion's actionable findings and guide an AI developer toward evidence-backed integration, testing, and incremental improvements.

## Evidence classification — read first

- **Discussed design:** Conversation describes contextual disambiguation, EQ response cards, a Director, profiles, and an EQ orchestrator.
- **Prior assistant's reported inspection, not reverified in this handoff:** `eq_disambiguation_engine.py` reportedly extracts actor, subject, domain, intensity, valence; `main.py` reportedly initializes `EQOrchestrator()` but WebSocket dispatch may call `orchestrator.handle_message(...)` rather than `eq_orchestrator.process_message(...)`.
- **Unverified:** Whether live user messages actually traverse the EQ engine, whether conversational state is persisted and consulted, quality of EQ output, and test coverage. Prior numerical rating (8/10) was subjective, not a measured score.
- **Proposals, not existing capabilities:** trajectory engine, contradiction/curiosity/belief tracking, feedback learning, model routing, monorepo migration, cross-user vector indexing, automated escalation, and explainability query engine.
- **Do not assume** the earlier assistant's code observations are accurate for the latest branch. Reproduce them against the supplied ZIP and active repository, recording branch, commit, environment, and exact evidence.

## What is promising and worth preserving

1. **Context-first disambiguation.** Actor, subject, situation domain, intensity, and valence can distinguish similar words with very different implications: “I took a shot” versus “I was shot.” Test ambiguity and negation rather than relying on keyword sentiment.
2. **Structured response-card selection.** Matching contextual attributes to response approaches is more maintainable and auditable than a simplistic emotion-to-canned-response mapping.
3. **Director coordination.** A central contribution policy can coordinate agent styles such as PRESENCE versus CHALLENGE, provided decisions are inspectable and evaluated.
4. **Profiles and narrative intent.** Persistent context offers a route toward continuity across sessions, rather than isolated-turn emotional labels.
5. **Modality-neutral core.** A semantic EQ/narrative pipeline can later accept STT text and output expressive TTS/prosody without binding its reasoning to one interface.
6. **Recognition that outcomes matter.** Feedback and evaluation are more important than simply multiplying model sizes or code modules.

## Most important shortcomings and risks

### P0 — Verify the actual live integration

Trace WebSocket input through routing, observation, disambiguation, Director, response selection, generation, safety, persistence, and outbound payload. Confirm whether `eq_orchestrator.process_message(...)` is invoked, bypassed, or integrated through another route. Trace `follow_up_questions`, `resources`, `response_type`, and `confidence` from producer to client. Add an end-to-end test that fails if EQ is silently bypassed. Do not claim this is broken until reproduced.

### P1 — Message-centric vs conversation-centric reasoning

A good single-turn classifier may miss temporal context, emotional transitions, changing interpretations, user corrections, and ongoing story arcs. Build a bounded, provenance-aware conversation-state representation, not a permanent psychological label. Differentiate observation, interpretation, user-confirmed fact, and uncertainty.

### P1 — No demonstrated quality feedback loop

Collect optional, explicit feedback: helpful / unhelpful / misunderstood / too much / good question, with turn and Director-decision context. **Do not automatically adjust safety-critical weights based solely on thumbs.** Feedback is sparse, biased, and confounded; offline evaluation and controlled rollouts should precede policy changes. The claim that improvements compound by 1% per 1,000 sessions is aspirational, not an empirical guarantee.

### P1 — Safety, privacy, and epistemic humility

Do not equate grief, intensity, or contradictions with pathology or danger. Do not infer a user's beliefs as certain; allow review, correction, and deletion. Crisis escalation to SMS/email requires explicit consent, vetted recipients, human oversight, false-positive and false-negative evaluation, and data minimization. A blanket forced break after N intense sessions could be harmful; assess alternatives and user control. Cross-user embeddings of sensitive narratives should not be built by default: require privacy analysis, consent, access controls, retention limits, and ideally privacy-preserving aggregate evaluation.

### P2 — Architecture and maintainability

Potential flat-file coupling merits a dependency graph and import-cycle audit before migration. A candidate package structure is `pubcast/engine`, `server`, `agents`, `storage`, `training`, `tools`, each with typed interfaces and tests. **Do not perform a wholesale rewrite merely for folder aesthetics.** Extract stable boundaries incrementally, preserve behavior with characterization tests, and keep existing agents/plugins interoperable.

## Proposed improvements, in order

1. **Baseline and reproduce.** Inventory files, imports, entry points, existing tests, recent commits, and known behavior. Run focused tests and an end-to-end WebSocket EQ probe. Mark each claim verified, failed, blocked, or needs rerun.
2. **Turn-level audit trace.** With privacy safeguards, record input identifier, model/version, disambiguation output, Director choice, selected card, response metadata, latency, and confidence/uncertainty. Separate observable facts from inferred emotion.
3. **Human evaluation harness.** Assemble consented, anonymized cases for ambiguous phrasing, metaphor, simile, literal meaning, humor, sarcasm, grief, achievement, mixed feelings, and corrections. Evaluate interpretations and response helpfulness against human judgments; measure calibration and disagreement.
4. **Conversation-state and trajectory layer.** Track changes over turns, with timestamps, evidence, confidence, and explicit user corrections. Avoid claiming objective “progress” or “regression” from emotion alone.
5. **Curiosity and clarification.** When meaning is ambiguous, ask a relevant question rather than imposing a confident interpretation. Measure unnecessary-question rate as well as useful clarification.
6. **Belief/hypothesis tracking.** If implemented, represent beliefs as revisable hypotheses with evidence for/against, provenance, and user confirmation. Never treat model-inferred beliefs as immutable facts.
7. **Feedback loop, safely staged.** First log feedback and perform offline analysis; then evaluate candidate Director policy adjustments on holdout conversations and opt-in controlled experiments. Protect safety rules from uncontrolled optimization.
8. **Explanation/query interface.** Support questions like “Why did Pete say that?” or “What evidence made the Director choose PRESENCE?” Expose the actual recorded decision trail, not invented post-hoc rationalizations.
9. **Voice integration.** Use STT/TTS adapters and pass expressive intent into the existing prosody/viseme pipeline; evaluate timing, turn-taking, emotion overstatement, and accessibility.
10. **Operational hardening.** Add schema versions/migrations, transactional audit storage (SQLite WAL can be appropriate for single-node use), snapshots, access controls, rate limits, CI, fuzz/property tests, and realistic load tests. Add Redis/PostgreSQL/vector services only when requirements justify them.

## Three-solution decision tests

For each major change compare (A) reuse/extend current code, (B) add a narrow adapter/service, and (C) restructure the subsystem. Score correctness, integration risk, latency, resource footprint, maintenance, testability, and reversibility. Select using measured evidence, not novelty. This is especially important for routing, profile storage, narrative state, and agent plugins.

## Suggested minimum acceptance suite

- Ambiguous statement pairs resolve by actor/context rather than keyword alone.
- Negation, sarcasm, quotation, metaphor, and literal statements do not silently collapse into one emotion label.
- A follow-up turn changes interpretation when new information arrives.
- User correction updates state and prevents repetition of a disproven inference.
- Director decisions and card selections have traceable evidence and can be reproduced in a deterministic test fixture.
- End-to-end WebSocket traffic demonstrably invokes the intended EQ pipeline and returns the expected metadata.
- Invalid strings and malformed profiles fail safely without server crashes or corrupting stored state.
- Consent, data retention, and deletion behavior are tested before storing sensitive narratives or feedback.
- New bugs receive regression tests; claims of browser, unit, integration, or hardware testing are explicitly distinguished.

## Long-range architecture vision (not immediate backlog)

- Typed monorepo packages with agent plugin contracts.
- Model router for resource-aware local/cloud selection, with transparent privacy and cost rules.
- Optional fine-tuning using licensed, consented, appropriately reviewed data; avoid unvalidated therapeutic claims.
- Observability for policy distribution, false-positive interpretations, anti-parroting rates, uncertainty calibration, and user-reported outcomes.
- Explainable, privacy-aware narrative memory and state migration.
- Deployment automation, semantic releases, and load testing matched to actual user scale.

## Instructions to the next AI

**Do not rebuild already-working features.** First identify exact duplicates, partial overlaps, integration gaps, and truly missing functions. Preserve existing PubCast/Alex/Director/agent interfaces when possible. Prioritize the smallest demonstrably useful improvement, document the three options considered, write regression tests, run them, and report exact results. If a test cannot run, say **blocked** or **untested**; never substitute a design claim for runtime evidence. Record branch, commit, files changed, command output, and remaining risks in the session handoff.

**North-star question:** Can the system accurately interpret what the person means *in context*, respond appropriately and respectfully, update its understanding when corrected, and produce evidence that its response helped—without overclaiming emotional certainty?
