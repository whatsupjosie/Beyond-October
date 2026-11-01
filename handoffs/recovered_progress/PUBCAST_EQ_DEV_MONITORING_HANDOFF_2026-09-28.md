# PubCast / BlackBox — EQ Development & Monitoring Handoff
**Date:** 2026-09-28  
**Priority:** Immediate  
**Status:** Design direction established; implementation should precede substantial further EQ evaluation  
**Purpose:** Build an auditable training/evaluation method for observing real user behavior, EQ judgments, soothing/care interventions, and outcomes without losing the full evidence needed to verify whether the emotional model is actually correct.

---

## 1. Why This Must Happen Now

PubCast is approaching the point where real use will generate the most valuable EQ data the project has ever had.

If those sessions occur before the evaluation recorder is installed, the project will again rely on:
- memory
- summaries
- anecdotes
- selective screenshots
- partial logs
- assistant recollection

That is not sufficient.

The project has repeatedly suffered from not having the full record available later.

Therefore:

> **EQ evaluation recording takes precedence before extended real-world testing.**

The system must preserve enough evidence that a later reviewer can independently ask:

- Did the user's behavior actually change?
- Did message length really increase?
- Was typing actually faster?
- Was the system reading frustration or merely profanity?
- Did the intervention help?
- Was the user's anger caused by the task, by the system, or by something else?
- Was the system's math reproducible?
- Did the system overreact?
- Did it intervene too late?
- Did it treat an accessibility/workflow problem as a behavioral/emotional one?

---

## 2. Core Principle: Evidence First, Interpretation Second

The evaluation system must never store only a conclusion such as:

> `user agitation increased 38%`

without retaining the evidence from which that conclusion was calculated.

The source of truth is:

> **complete interaction record + raw telemetry + model interpretation + intervention + outcome**

The interpretation is secondary.

Nothing important should be irreversibly summarized.

---

## 3. BlackBox Development Area

Create a dedicated development/evaluation section inside BlackBox.

Conceptual layout:

```text
BlackBox/
└── dev/
    └── EQ/
        ├── sessions/
        │   └── YYYY-MM-DD_<session-id>/
        │       ├── manifest.json
        │       ├── transcript.jsonl
        │       ├── telemetry.jsonl
        │       ├── affect_trace.jsonl
        │       ├── intervention_trace.jsonl
        │       ├── provider_pipeline.jsonl
        │       ├── outcomes.jsonl
        │       └── reviews.jsonl
        │
        ├── views/
        │   ├── calm_observations/
        │   ├── tantrums/
        │   ├── crisis_management/
        │   ├── eq_judgment_examples/
        │   └── care_protocol/
        │
        └── exports/
```

### Important implementation note
The `views/` categories should preferably be indexes/references/tags into the immutable session evidence rather than duplicated mutable copies.

The same session segment may legitimately belong to more than one category.

For example:
- tantrum
- Teddy frustration
- system-caused friction
- successful soothing
- care protocol

may all refer to the same event window.

---

## 4. Full Verbatim Transcript Is Mandatory

For every recorded EQ-development session, preserve every user and system/AI message exactly as sent or delivered.

Do not:
- summarize
- paraphrase
- remove profanity
- normalize grammar
- shorten messages
- clean speech-to-text artifacts
- collapse repeated phrases

Record:
- exact text
- role
- sender identity
- timestamp
- session ID
- turn ID / message ID
- provider/model when relevant
- channel/room
- hashes for integrity
- build/version provenance

The detail itself is evaluation evidence.

If a user repeats the same sentence six times, that repetition may matter.

If a message jumps from 40 words to 1,400 words, that may matter.

If profanity frequency is stable relative to the user's baseline, that also matters.

---

## 5. Raw Telemetry Must Remain Separate From Interpretation

Capture actual measurable signals whenever available.

Examples:
- characters
- words
- sentence count
- punctuation counts
- capitalization
- repetition
- profanity count
- hedging count
- lexical novelty
- inter-message latency
- time since previous system response
- edits
- paste events
- typing start
- typing finish
- pause distribution
- keystroke/character count where locally available and consented
- menu/control repetitions
- failed action attempts
- repeated clicks
- workflow reversals
- response latency
- abandon/retry patterns

### Critical rule: do not fabricate telemetry

Inter-message latency is not the same thing as typing speed.

If typing start/end events were not observed, then typing rate must be:

`unknown`

Historical data may support text-derived analysis such as word count or punctuation frequency, but missing telemetry must remain missing.

---

## 6. Mathematical Trace Must Be Reproducible

For each affect judgment preserve:

### Before the turn
- current personal baseline
- sample count
- means
- variances
- reliability / maturity
- relevant thresholds
- algorithm/schema version

### Current turn
- raw feature vector
- raw scores
- z-scores
- attenuation/reliability adjustments
- candidate affect states
- confidence values
- alternative hypotheses

### After the turn
- updated baseline
- whether the turn was included/excluded from baseline learning
- why

This allows later review of questions like:

> “The system said message volume was +1.7 standard deviations above baseline. Does that actually recompute from the stored record?”

---

## 7. Interpretation Trace

Preserve the complete EQ reasoning payload rather than only the selected state.

Include where available:
- affect state
- alternate states
- confidence
- sustained-turn count
- antecedent hypothesis
- falsifier
- probe choice
- probe result
- intervention class
- `self_inflicted` / system-caused-friction hypothesis
- steerage
- commitment
- `meet_them_at`
- fragility/care priority
- uncertainty

The system should be encouraged to preserve competing hypotheses.

Example:

```text
PRIMARY: TEDDY_COMPREHENSION
confidence: 0.76

ALTERNATE: DEPLETION
confidence: 0.31

SELF-INFLICTED FRICTION:
high

EVIDENCE:
three failed clarification loops
user explicitly says "I don't understand"
task goal remains stable
```

---

## 8. Intervention Trace

Record what the system did in response.

Separate:
- what Jeremy recommended
- what Cricket recommended
- what Alex decided
- what PubPartner guidance was assembled
- what provider/model produced
- what the neutralizer changed
- what the personality/friend stage changed
- what final response was delivered
- whether direct execution was offered
- whether direct execution was performed
- whether the user overrode or rejected the intervention

This must support later questions such as:

> Jeremy recommended “one next step,” but did the delivered response actually become fourteen paragraphs?

---

## 9. Provider / PubPartner Evaluation Trace

For EQ-development sessions, preserve separate stages when available:

```text
RAW_PROVIDER
→ NEUTRALIZED
→ PERSONALITY_RESTORED
→ FINAL_DELIVERED
```

This is important both for EQ testing and for provider-neutralization testing.

The goal is to be able to compare the same task across OpenAI/ChatGPT, Claude, Gemini, local models, etc. without losing the original provider output.

---

## 10. Outcome Linkage

The next user response should be linked to the previous intervention.

The system may generate provisional outcome hypotheses such as:
- helped
- re-engaged
- calmer
- confused
- ignored
- irritated
- escalated
- task completed
- user corrected system
- wrong read / useful response anyway
- right read / wrong intervention
- uncertain

These are hypotheses, not ground truth.

Human review must remain possible.

---

## 11. Human Review and Corrections

Do not rewrite the original record.

Human review should append a new immutable annotation.

Examples:
- correct read
- wrong read
- right read / wrong intervention
- useful
- annoying
- patronizing
- too late
- premature
- made it worse
- helped immediately
- neutral
- unknown

This preserves both:
- what the system believed at the time
- what the human later judged

---

## 12. Build Provenance

Every evaluation session should record:
- PubCast build hash
- EQ schema version
- BlackBox schema version
- care vocabulary version
- provider/model
- neutralizer version
- personality/friend layer version
- relevant thresholds/tuning constants

Without this, old behavior cannot be reproduced after tuning changes.

---

# 13. Development Vocabulary: Nursery Language

For the current development phase, nursery language is intentionally allowed because it is memorable, emotionally high-contrast, and easy to reason about during testing.

The user may ordinarily be addressed as Josie or Curtsey.

When EQ care protocol is actively engaged during development, the user may be referred to as **the baby**.

This is explicitly a development/evaluation convention.

The underlying canonical tags should remain neutral so the presentation language can later be replaced for production.

Example:

```text
CANONICAL:
GOAL_BLOCKED / COMPREHENSION

DEV ALIAS:
TEDDY_COMPREHENSION
```

Production can later replace nursery terms without rewriting the behavioral logic or historical data.

---

# 14. Baby-Care Vocabulary

## Bottle / Feeding
### Meaning
Low reserve, impatience, fussiness, crankiness, “feed me something useful.”

The user may not be in crisis. They may simply have very little patience left for delay or abstraction.

### Likely response
- reduce delay
- give something concrete
- reduce unnecessary explanation
- provide immediate useful output
- offer direct execution where appropriate

### Neutral semantic core
`LOW_RESERVE / REPLENISH`

---

## Diaper Change
### Meaning
A specific persistent irritant is making the interaction unpleasant.

Examples:
- repeated system mistake
- annoying UI behavior
- wrong assumption
- hidden control
- repeated irrelevant explanation
- broken feature
- avoidable friction

### Likely response
Do not soothe around the irritant.

Find it and remove/fix it.

### Neutral semantic core
`ACTIVE_IRRITANT / REMOVE_CAUSE`

---

## Nap
### Meaning
Cognitive/emotional capacity is genuinely dropping.

Potential cues:
- repeated mistakes
- loss of working-memory continuity
- inability to track steps
- reduced flexibility
- escalating frustration despite the task getting simpler
- obvious depletion/overstimulation

### Likely response
- reduce task load
- stop adding branches
- narrow to one thing
- reduce stimulation
- consider stopping or pausing the work

### Important distinction
Do not use Nap merely because the user is angry.

A user can be furious and still cognitively capable.

### Neutral semantic core
`DEPLETION / REDUCE_LOAD`

---

## Carry / Cuddle / Rocking
### Meaning
The task may not be the primary problem. The user may need co-regulation, reassurance, presence, or a sense that the system is staying with them.

### Likely response
- acknowledge
- stay present
- reduce demand
- avoid overloading with fixes
- re-enter task work after regulation returns

### Neutral semantic core
`COREGULATION / CONNECTION`

---

## Playpen
### Meaning
Too many things are happening at once.

This is containment/reset, not punishment.

### Likely response
- temporarily constrain the environment
- stop opening new branches
- freeze optional decisions
- one bounded task at a time
- preserve user authority

### Neutral semantic core
`CONTAINMENT / REDUCE_SURFACE`

---

## Teddy Bear
### Core meaning
The baby knows what she wants but cannot bridge the gap between where she is and the desired outcome.

This is best understood as:

`GOAL_BLOCKED`

### Important subtypes

#### TEDDY_ACCESS
The capability exists, but the user cannot reach/find/open it.

Examples:
- can't find menu
- can't locate file
- can't reach control
- wrong screen

#### TEDDY_COMPREHENSION
The user cannot understand the directions well enough to proceed.

Examples:
- “I don't know what you're talking about.”
- “I can't follow this.”
- “You're losing me.”
- directions assume knowledge the user does not have

#### TEDDY_EXECUTION
The user understands the goal but cannot successfully perform the required action.

Examples:
- repeated command failure
- repeated tool failure
- user can describe what they want but cannot make the mechanism produce it

#### TEDDY_NOT_BUILT
The desired capability/result is not fully available yet.

Instead of stopping at “not ready,” investigate whether a minimum-fidelity version can be produced immediately.

---

# 15. Teddy Protocol

The system should not defend the workflow merely because the workflow exists.

The operating question is:

> **What is the shortest safe path from the baby to the thing she is trying to accomplish?**

Possible responses include:
- clarify
- show
- simplify
- demonstrate
- guide one step
- surface the correct control
- use a different tool
- proxy-test
- perform the mechanical step
- perform the full authorized task

### Direct execution stays on the table

Respecting user agency does **not** mean forcing the user to manually operate every control.

Agency means the user chooses:
- goal
- constraints
- limits
- approval level

The AI may perform authorized mechanical work.

---

# 16. Observe → Check In → Interpret → Assist

A strong escalation path is:

```text
observe repeated effort
→ ask "how is that going?"
→ receive user feedback
→ confirm underlying goal
→ interpret whether the current method can achieve it
→ explain causal mismatch if needed
→ suggest better path
→ offer or perform assistance
→ evaluate outcome
```

The “how is that going?” probe is important because it collects direct feedback before the system becomes overconfident.

---

# 17. Goal Before Method

The system must first establish what the user is trying to accomplish.

Only then should it judge the method.

This prevents AI from “correcting” legitimate creative experimentation merely because the method is unconventional.

Classify method-goal alignment as something like:
- conventional/plausible
- experimental but causally plausible
- unlikely
- non-causal

Example:

If the user wants more visual separation but keeps increasing brightness after brightness is already maxed out, the system can infer:

> The goal is increased visibility/subject separation. Brightness has reached its limit. Contrast, edge definition, white balance, shadow, background detail, or color separation may be the actual effective controls.

The response should focus on the goal, not shame the user for choosing the wrong control.

---

# 18. Teddy vs Nap

This distinction is critical.

If the user says:
- “I don't understand.”
- “I can't find it.”
- “This isn't working.”
- “You're losing me.”

the system must ask:

> Is the user's capacity failing, or is the interface/explanation failing?

Repeated clarification failure should generally increase Teddy confidence before it increases Nap confidence.

Otherwise the system risks telling a perfectly capable but poorly-supported user to rest when the real problem is that the system gave bad instructions.

---

# 19. Developmental-Stage Metaphor

Not every blocked goal is a Teddy problem.

Sometimes the project itself is not developmentally capable of the desired behavior yet.

Useful dev metaphor:

### Bassinet
Core capability not ready; key dependencies genuinely missing.

### Crawling
Capability exists in pieces but requires substantial support/manual intervention.

### Cruising
Works with scaffolding / hand-holding / temporary support.

### Walking
Reliable enough for ordinary use.

### Running
Robust, integrated, comfortable, performant.

The diagnostic question is:

> **Is the baby failing to reach the capability, or is the capability itself still a baby?**

---

# 20. Proxy Validation / “Borrowed Legs”

If the final integrated path is not ready, the system should ask whether the narrower question can still be answered through a temporary or external path.

Example:

PubCast cannot yet play a generated file through the final runtime because several integration steps remain unfinished.

But Winamp can play the file now.

Then the useful move is:

> Use Winamp to answer the narrower question: “Did we generate the right file?”

This is not pretending integration is complete.

It is:

`PROXY_VALIDATION`

Examples:
- rough render
- temp audio playback
- gray-box animation
- placeholder asset
- temporary backend
- disposable branch
- external player
- unprocessed preview

### Rule
> **Planned later is not the same as impossible now.**

If a safe, cheap, provisional test answers the user's immediate creative question, it should remain available.

---

# 21. Baby-Care Intervention Is Not Loss of Adult Authority

The care system must hold two truths simultaneously:

### Emotional handling
The nursery framework may be used:
- baby is fussy
- baby needs a bottle
- baby can't reach the teddy
- baby needs carrying
- baby needs a nap

### Task authority
The user remains the adult owner of:
- project decisions
- files
- changes
- stopping
- overriding care
- rejecting the system's interpretation
- production direction
- final approval

The baby-care metaphor must never silently override adult project authority.

---

# 22. Specialized Care Protocol

The current specialized nursery/care behavior should remain explicitly development/evaluation scoped unless deliberately enabled.

It should not automatically become the production-facing default.

The system should preserve:
- stop/pause mechanisms
- owner authority
- explicit override
- reviewability
- uncertainty

Resistance to nursery language should be recorded as:
- accepted
- resisted
- neutral
- unclear

It should **not** automatically be interpreted as disobedience or pathology.

---

# 23. Care Metaphor Interventions as Experimental Variables

The project may deliberately test different nursery metaphors because the user's reaction may itself contain information.

Examples:
- bottle
- carry
- cuddle
- nap
- playpen
- diaper change
- teddy
- “baby wants the project to walk”
- “borrowed legs”

For each intervention record:
- why it was selected
- confidence
- exact wording
- whether it was accepted/rejected
- immediate user reaction
- task outcome
- later human review

Over time this may reveal which metaphors:
- soothe
- irritate
- clarify
- restore focus
- feel patronizing
- improve cooperation
- interfere with work

---

# 24. Calm Observations Matter Too

Do not build a dataset made only of meltdowns.

The baseline requires ordinary sessions.

Record calm examples of:
- sustained productive work
- ordinary swearing
- playful profanity
- long messages without distress
- short messages without disengagement
- creative experimentation
- normal impatience
- successful independent problem-solving
- asking for direct execution without emotional escalation

Without calm observations the system cannot know what is normal for the individual user.

---

# 25. Crisis Management Category

A separate review category should exist for high-intensity events.

It should include:
- full transcript
- raw telemetry
- EQ state
- intervention sequence
- escalation/de-escalation
- whether the system helped
- whether the system itself contributed
- what authority boundary applied
- human review

Do not infer a clinical diagnosis from a high-intensity interaction.

The evaluation goal is behavioral/interactional:
- what happened
- what helped
- what worsened it
- what should change in the system

---

# 26. EQ Judgment Examples

The BlackBox dev EQ area should make it easy to find especially informative examples such as:
- correct early intervention
- correct late intervention
- premature intervention
- misread profanity
- Teddy mistaken for Nap
- Nap mistaken for Teddy
- system-caused frustration
- successful direct execution
- successful proxy validation
- failed soothing metaphor
- successful soothing metaphor
- care protocol rejected
- care protocol accepted
- ambiguous result

These become future regression/evaluation cases.

---

# 27. Historical Backfill

Past ChatGPT/PubCast development conversations may later be imported as historical evaluation material.

Rules:
- preserve complete text when available
- preserve original timestamps when available
- label source clearly
- do not pretend historical telemetry existed
- derive only features that can be recomputed from surviving evidence
- missing signals remain `unknown`

Historical backfill should never contaminate the “live observed telemetry” category.

---

# 28. BlackBox Role

BlackBox remains:
- witness
- recorder
- append-only evidence boundary
- retrieval source

BlackBox should **not** become the authority deciding what the user feels.

The EQ system interprets.

BlackBox preserves what happened and what the EQ system claimed.

That separation is essential.

---

# 29. Immediate Implementation Order

1. Create `BlackBox/dev/EQ` evaluation structure.
2. Add date-stamped immutable session archives.
3. Record full verbatim transcript.
4. Add raw telemetry capture.
5. Add EQ/math trace.
6. Add intervention trace.
7. Add provider-neutralization/personality stages.
8. Link subsequent user response as outcome evidence.
9. Add human-review annotation records.
10. Add category/index views:
   - calm observations
   - tantrums
   - crisis management
   - EQ judgment examples
   - care protocol
11. Add build/schema/version provenance.
12. Add export/review tooling.
13. Only after evidence collection proves useful should the system automatically turn evaluation findings into durable behavioral learning.

---

# 30. Immediate Success Criteria

Before serious EQ testing begins, prove that one controlled session can produce a reviewable archive containing:

- complete verbatim user text
- complete delivered AI text
- timing/telemetry actually observed
- baseline before
- feature vector
- EQ interpretation
- alternate hypothesis
- intervention choice
- provider/raw stage where applicable
- final personalized response
- next-user-turn outcome
- human-review slot
- hashes
- build/schema provenance

Then manually inspect one session and verify that the numbers can be recomputed from the saved evidence.

Only then should we trust the recorder enough to begin accumulating development data.

---

# 31. Handoff Conclusion

The EQ project is not simply “make the AI sound more caring.”

It is:

> **Build an auditable system that learns how to support a real human under emotional load while still respecting that person's adult authority, creative intent, and task ownership.**

The nursery framework is currently useful because it provides high-contrast development language for different care hypotheses.

But the long-term value comes from the evidence:

- what the human actually did
- what the system thought it meant
- what the system did in response
- what happened next
- whether the interpretation and intervention were actually correct

The first serious PubCast sessions should not happen invisibly.

They should become the first proper training/evaluation corpus for the EQ system.

---
## Next-Session Pointer
For the next fresh-context session, begin with `START_HERE_NEXT_CHAT_EQ_2026-09-28.md` and then read this handoff together with its companion handoff before modifying canonical code.
