# The Affect/Context Model
## Discovered mechanics for alex_bridge → jeremy_whisper

**Status:** design synthesis + working reference implementation.
**Honest framing:** this is not a research discovery. It is a design derived
from three constraints you gave me — separability, tandem evaluation, and
non-uniformity — pushed until the structure that satisfies all three fell out.
Where it departs from standard affective computing I say why. Where it borrows,
I say that too.

---

## 1. THE UNDERLYING MECHANICS

### 1.1 Context is a position. Affect is a derivative.

The reason categorical models (`CHARGED / LOW / DEPLETED`) fail is that they
type-check emotion as a **state** — a discrete cell you occupy. But the thing
that actually predicts what a person needs next is not where they are, it's
**which way they're moving and how fast**.

So the model separates them by *mathematical kind*, not by topic:

| | Kind | Question it answers | Timescale |
|---|---|---|---|
| **Context** | Position in a task space | *What is happening?* | Slow — persists across turns |
| **Affect** | Derivative of engagement | *Which way, how fast, how steady?* | Fast — changes within a turn |

This is not a metaphor. It has a concrete consequence: **context is integrated,
affect is differentiated.** Context accumulates (a debugging session stays a
debugging session). Affect is measured as change against a moving reference.

That is why the same reading means opposite things in different frames, and why
any model that scores them on one axis will be wrong roughly half the time.

### 1.2 The natural boundary: invariance under paraphrase

You asked how a system finds the boundary between *what is happening* and
*how it feels* from raw interaction, without being told.

The boundary is discoverable and it is this:

> **Context is what survives paraphrase. Affect is what paraphrase destroys.**

If you rewrite a message in different words and the task is unchanged, the task
was context. Everything that changed and still carried signal — length,
punctuation, fragmentation, repetition, capitalisation, hedging, profanity,
cadence — was affect.

This gives a mechanical extraction rule rather than a taxonomy:

- **Paraphrase-invariant channel** → content words, mood (imperative /
  interrogative / declarative), referential continuity, irreversibility markers.
- **Paraphrase-variant channel** → form. Not *what* was chosen but *how much*
  and *how hard*.

Affect lives in the choices that carry no propositional content. That is why it
can be measured without understanding the sentence, and why it does not require
a sentiment classifier.

### 1.3 The interaction mechanism: gated, not additive

When they collide, the mechanism is **multiplicative gating**, not summation.
Affect supplies magnitude and sign. Context supplies the interpretation
function. Neither is meaningful alone:

```
interpretation = Φ(context_frame) · affect_vector
```

Concretely — identical high arousal, four different meanings:

| Arousal | Context frame | Continuity | Reads as |
|---|---|---|---|
| high | exploratory | high | **flow** — do not interrupt |
| high | blocked | high (repeating) | **friction** — offer a different angle |
| high | social | low stakes | **play** — match energy |
| low | high-stakes | fragmenting | **depletion** — reduce load |

Row 1 and row 2 have *the same affect reading*. A single-axis model cannot tell
them apart, which is exactly how systems end up interrupting people who are
working well and cheerleading people who are stuck.

The discriminator is **continuity-with-repetition**: flow revisits a topic while
*advancing* it; friction revisits a topic while *circling* it. That is a
measurable difference — topic overlap high, novel-token ratio low.

---

## 2. REPRESENTING HUMAN NON-UNIFORMITY

### 2.1 The unit of measurement is personal deviation, not absolute intensity

This is the load-bearing decision. **No feature is ever consumed as an absolute
value.** Every measurement is converted to a z-score against *that individual's*
own running distribution before it means anything.

```
z = (x − μ_person) / (σ_person + ε)
```

A person who always writes in caps with no punctuation is not shouting — that is
their zero. A person who normally writes long careful paragraphs and drops to
three-word fragments has moved four sigma even though the fragments look calm
in isolation.

This removes the generic human template entirely. There is no "normal amount of
exclamation marks." There is only *more or less than you usually use*.

### 2.2 The data structure: exponentially-weighted per-feature moments

Per person, per feature, we hold a running mean and variance under exponential
decay:

```
μ ← (1−α)·μ + α·x
σ² ← (1−α)·σ² + α·(x−μ)²
```

With `α ≈ 0.05`, the baseline adapts over roughly 20 turns — fast enough to
learn a new person, slow enough that one strange message does not redefine them.

This is deliberately *not* a learned embedding. Embeddings are opaque, cannot be
audited, and cannot answer "why did you think that." Running moments are
inspectable: you can print exactly which feature moved and by how much.

### 2.3 Recognising joke / sarcasm / creative chaos / genuine struggle

These are not points and they are not keywords. They are **signatures across
several axes simultaneously**, matched loosely. The reference engine scores each
as a soft match rather than a hard classification:

| Signature | Distinguishing pattern (all in personal z) |
|---|---|
| **play** | short latency, high punctuation, low stakes markers, no help-seeking, high novel-token ratio |
| **sarcasm** | valence-marker *mismatch* — positive lexemes co-occurring with negative structural markers (hedges, ellipsis, contrast conjunctions) |
| **creative chaos** | high velocity + high novelty + *low* repetition + long messages + low self-correction — high energy that is going somewhere |
| **struggle** | high repetition + *falling* message length + rising turn frequency + rising hedge/negation density — high energy that is circling |

Note that **creative chaos and struggle share high arousal and high frequency.**
The separator is the novelty/repetition ratio and the length trajectory. Chaos
expands. Struggle contracts. That single distinction prevents the most damaging
false positive in the system — treating someone in flow as someone in trouble.

### 2.4 Depletion has two opposite presentations

The model initially gated depletion on *slowness*, which was wrong and was the
most dangerous error in the design. Depletion does not always slow people down.
It frequently **accelerates** them.

When someone hits empty, one common response is not withdrawal but abandonment
of the evaluation step: *"fuck it, just ship it."* Decisions get faster because
the person has stopped caring whether they are right. Externally this looks like
decisiveness. It looks, in every surface metric, like flow.

A latency-gated depletion model is **structurally blind** to this — and it is
blind precisely when it matters most, because this is the state in which people
do irreversible things they regret.

So depletion is two states sharing one cause:

| | Presentation | Latency | Deliberation |
|---|---|---|---|
| **depletion** | withdrawal | slower | elevated (hedging, fragmenting) |
| **disengagement** | abandonment | *faster* | **collapsed** |

**The discriminator is deliberation collapse, not speed.**

#### 2.4.1 The sharpest form: investment reversal

General indifference is a weak signal. The strong one is **dismissiveness aimed
at the exact thing the person has been protecting**:

> *"I have been guarding this behaviour for two days."*
> *"...you know what, I don't care. We're done."*

Topic continuity stays high while valence inverts. That pairing — sustained
investment plus termination language about the same subject — is what separates
a burnout flip from ordinary triage. **Dropping something you just picked up is
good judgement. Dropping something you have defended for hours is a different
event and must be read as one.**

This is why `investment` is carried in the context block. Verified behaviour,
identical wording, different history:

| History | investment | reading |
|---|---|---|
| no prior work on the topic | 0.00 → 0.33 | `friction` — normal triage |
| two days defending it | 0.50 → 1.00 | `disengagement` — the flip |

The register matters too, and it is measurable: finality markers (*done, over,
forget, whatever, scrap*), dismissal (*doesn't matter, who cares, pointless*),
and absolutes (*never, always, the whole thing*). These are not sentiment words.
They are **termination markers** — they announce the end of investment in a
subject, and they carry the flippant, callous edge that distinguishes this state
from calm withdrawal.

The steerage that follows is specific: guard the irreversible step, and **hold
the abandoned thing so it survives the mood.** The work was worth protecting an
hour ago. The judgement that it isn't is the symptom, not the finding.

Hedging and self-correction are deliberation markers — their presence means the
person is still evaluating. Flow *retains* them: you still hedge, still revise,
still ask. That friction is what makes it flow rather than flailing.
Disengagement sheds all of them simultaneously. Both being below the person's
own baseline at once is the signal. Not confidence — evaluation switched off.

Operationally the steerage inverts. For depletion you slow the person down. For
disengagement you must **not**: they will run straight past you, and asking a
person in that state how they are feeling is exactly the wrong intervention.
The correct move is to put a guard in front of the irreversible action before it
lands. Hence `pacing: "guard"` and an `avoid` list containing `"checking in"`.

This is also why `stakes` is carried in the context block. Fast and careless is
merely fast — until it touches something that cannot be undone.

---

## 3. TRANSLATING TO SYSTEM DATA

### 3.1 The anti-patronising mechanism: silence is a valid output

Most affective systems always emit something. That is the root cause of
patronising feedback loops. This model emits **nothing** below a confidence
floor, and reports `state: "observing"`.

Confidence is the minimum of two independent things:

```
confidence = min(maturity, agreement)
```

- **maturity** — how many turns we have seen from this person (a cold start
  cannot be confident no matter how loud the signal)
- **agreement** — do multiple independent features point the same way (a single
  outlying feature is noise, three concurring features is signal)

Either one alone is insufficient, so the `min` is correct rather than a product
or average.

### 3.2 Asymmetric hysteresis

Escalation toward care states requires **sustained** evidence across turns.
De-escalation requires **one** contrary signal.

```
escalate:   confidence > 0.60 AND sustained ≥ 3 turns
de-escalate: any single contrary turn
```

This asymmetry is the whole anti-false-alarm design. It is much harder to decide
someone is struggling than to decide they have recovered. That is the correct
bias — the cost of a missed detection is a delayed offer of help; the cost of a
false detection is treating a working adult like they are fragile, which is
worse and which compounds.

### 3.3 Preventing staleness

Three mechanisms, all in the reference engine:

1. **Confidence decays without fresh evidence** — a state asserted six turns ago
   with nothing since is reported at reduced confidence, not at its original.
2. **Baselines drift by design** — the exponential weighting means a person who
   genuinely changes is re-learned rather than measured forever against who they
   used to be.
3. **Whisper novelty suppression** — the same steerage note is not emitted twice
   within a rolling window. If the situation has not changed, Jeremy says
   nothing rather than repeating himself. This is stored as a hash ring.

---

## 3.4 THE ANTECEDENT — cause, not state

The state is the symptom. **What the switch was a reaction to** is the finding,
and it is the only part that determines the correct response.

Six people arrive at the same `disengagement` reading. One ran out of time. One
is stuck. One is exhausted. One is blaming themselves. One has something in
their life pulling them elsewhere. One was never invested and is working because
they don't know what else to do. Identical reading. Six different correct
responses, and five are actively wrong in any given case.

The cause is **not visible in the turn that trips the state.** By then it has
flattened into dismissal. It is visible in the *run-up* — the trajectory of the
preceding turns. So diagnosis is a second-order pass over a retrospective
window, on two axes:

- **cause** — `time_pressure | stuck | exhaustion | self_failure | displaced | uninvested`
- **trajectory** — `spike` (sudden) / `decay` (gradual) / `drift` (attention moving) / `flat` (never engaged)

### The latch

The antecedent must be **latched on entry and held**, not recomputed per turn.
The turns constituting the flip are themselves fast, terse and dismissive; within
two or three of them they dominate the window and every cause collapses to
`flat / uninvested`. **The symptom overwrites its own history.** Only a
confident diagnosis latches — an early low-confidence blip must not freeze a
garbage reading for the episode.

### Verified state — honest

Measured against six synthetic run-ups converging on identical flip wording:

| Cause | Result | Notes |
|---|---|---|
| `time_pressure` | ✅ conf 1.00 | deadline lexemes + gaps shortening |
| `stuck` | ✅ conf 1.00 | repetition climbing + help-seeking |
| `self_failure` | ✅ conf 1.00 | first-person + failure attribution co-occurring |
| `exhaustion` | ❌ → `uninvested` | see below |
| `displaced` | ❌ → `unknown` | see below |
| `uninvested` | ❌ → `displaced` | residual logic still leaks |

**3 of 6. The architecture holds; three signatures need real-data tuning.**

### What the failures actually reveal

These are not weight-tuning problems. They are two genuine limits:

**1. Exhaustion is indistinguishable from never-engaged inside a short window.**
Both present flat and slow. The discriminator is whether the person was *ever*
engaged — exhaustion is a decay from a high-energy earlier state; obligation
never had one. That is invisible at `ANTECEDENT_WINDOW = 7`. It requires
**session-scale memory**, not a rolling buffer. This is the clearest argument in
the whole model for wiring the antecedent to `alex_memory` rather than keeping
it in-process.

**2. Displacement needs semantics, not lexis.** Detecting that attention moved to
*something they care about more* requires knowing that "apartment lease" belongs
to a different life-domain than "sync path". Novel tokens alone cannot tell a new
sub-task from a new life. This is the one signature that likely needs the LLM in
the loop rather than feature extraction — a cheap classification call on topic
domain, not a lexicon.

Both failures are honest and both point at a concrete next step. Neither is
fixed by tuning coefficients against synthetic scripts, and tuning them there
would have produced a model that fit the test and not the world.

---

## 3.5 THREE-HYPOTHESIS ABDUCTION

Emotional inference is **detective work, not classification.** The state cannot
be observed directly; only traces of it can, and you reason backward to the
explanation that best accounts for them — including the anomalies. A model that
emits one label is asserting something it cannot know.

So the engine carries three:

| Role | Selected for |
|---|---|
| `primary` | highest evidence after burden-of-proof weighting |
| `alternate` | strongest materially-different rival |
| `moonshot` | **consequence, not likelihood** |

### The moonshot is the discipline

It is not a random long shot. It is chosen as the low-probability cause whose
prescribed response most **conflicts** with the primary's — measured by
intersecting each hypothesis's advice against the other's `avoid` list. If the
primary says *don't slow them down* and a candidate says *slow them down*, being
wrong about which is true inverts the response entirely. That candidate is worth
carrying at low likelihood.

Same reasoning a clinician uses: rule out the rare thing that kills you before
treating the common thing that doesn't. You carry the hypothesis you cannot
afford to be wrong about, not the one you expect.

In testing, `self_failure` surfaced repeatedly as the moonshot — correctly. It is
low-probability and it is the one where a wrong response does real damage.

### Benefit of the doubt is WITHHOLDING, not reweighting

**This was implemented wrong the first time and the error is worth recording.**

The first version discounted uncharitable causes until a kinder one outranked
them, then reported the kinder one as the finding. `uninvested` scored 1.60,
`displaced` scored 0.72, and the model reported `displaced`.

That is not giving someone the benefit of the doubt. That is deciding what you
think and then saying something nicer while presenting it as your reading.
Charitable dishonesty is still dishonesty, and it corrupts the evidence trail
for everything downstream — a consumer reading `cause` cannot tell a finding
from a softened one.

In ordinary use the phrase means: *I am fairly sure I know why, but I am going
to hold that and let it be resolved.* **It terminates in asking, not in
concluding differently.**

So two situations, handled differently:

| | Condition | Behaviour |
|---|---|---|
| **Genuine tie** | within margin after weighting | charitable tiebreak applied — legitimate, evidence truly does not separate them |
| **Clear evidence, uncharitable** | leads by more than margin | **not overridden.** Reported honestly, marked `conclusion_withheld`, and not permitted to drive a response |

A withheld conclusion is kept, not replaced. It simply does not act. The
convergent action runs instead and the disambiguator is surfaced so the next
turn resolves it.

Verified: `uninvested` at 1.60 remains the honest primary. `conclusion_withheld`
is `true`. The cause-specific whisper — *"never engaged, working from obligation"* —
never reaches the output. The state-level whisper still fires, because the
**state** reading is evidence-backed and not in question; only the **cause**
attribution is held. That separation is the whole point: be honest about what
you think, and careful about what you do with it.

### Burden of proof (applies to genuine ties only)

We cannot be certain of anyone's internal state. That uncertainty is not
symmetric in cost, so it must not be symmetric in threshold. Uncharitable
readings clear a **higher bar**:

| Attribution | Burden | Causes |
|---|---|---|
| circumstance | 1.00× | time_pressure, displaced, stuck |
| condition | 1.15× | exhaustion |
| self_directed | 1.30× | self_failure — *do not confirm self-blame cheaply* |
| character | **1.80×** | uninvested — heaviest |

Concluding *"they don't care"* requires nearly twice the evidence of *"they're
struggling."* Reading circumstance as character is wrong more often, insulting
when wrong, and produces exactly the patronising response this model exists to
prevent.

Verified: `uninvested` scoring 1.60 was outranked by `displaced` at 0.72 after
discounting, and the reordering was flagged. On a clear-evidence case
(`stuck` at 5.99) charity correctly did **not** fire. It reorders close calls; it
does not override evidence. Without that distinction it would just be
permanent optimism, which is its own kind of dishonesty.

### Convergent action and the disambiguator

Output is no longer one whisper keyed to one guess. It is:

- **`convergent_action`** — what holds regardless of which hypothesis is true
- **`disambiguator`** — the single observation that would separate them

The second is the detective move. Not *"I know what this is"* but *"here is what
would tell us."* For `stuck` vs `exhaustion`: *offer one different angle and
nothing else — uptake means stuck, silence means spent.* The next turn resolves
it, and the action was safe either way.

This also converts the model's own uncertainty into something useful rather than
something hedged. It does not need to be right to be helpful.

---

## 3.6 DOUBT THAT FUNCTIONS

Doubt appended to a conclusion you keep acting on is decoration. "I could be
wrong" that changes no behaviour is worse than certainty, because it looks like
humility. Real doubt has three properties, all implemented:

**1. It is derived, not generic.** The falsifier comes out of the reasoning
chain that produced the conclusion. This is why doubt scales *with* confidence
rather than against it: a weak conclusion cannot say what would break it, but a
strong one followed a specific line of logic and therefore knows exactly which
link is load-bearing.

**2. It is actively watched.** The falsifier is registered and every subsequent
turn is tested against it. Room is left for the counter-evidence to arrive *and
to function when it does.*

**3. It forces acknowledged revision.** When the falsifier fires the conclusion
is not quietly reweighted — it is overturned and the reversal is stated:

> *"Read this as 'exhaustion' for 2 turns. That was wrong. Someone genuinely
> depleted does not accelerate; energy returning on a different subject means
> attention moved rather than ran out. Revising to 'displaced'."*

A system that cannot say *I was wrong about that* cannot be trusted when it says
anything else.

### Personal priors, and the anomaly inside the pattern

> *"I know this person. I have seen them do this before. Usually it means X —
>  but there is something funny about this one."*

The engine keeps an **empirical per-person prior**: not "people who do X mean Y"
but "when this person does X it has held in 8 of the last 9 instances," learned
from outcomes including the overturns.

The second half is the important one. Having seen a pattern nine times is
*precisely what makes it possible* to notice this instance sits outside the
usual shape of it. Anomaly is measured as second-order deviation — not distance
from the person's baseline, but distance from how this specific pattern normally
looks for them.

The behavioural rule is counter-intuitive and load-bearing:

> **A high hit-rate combined with high anomaly WIDENS uncertainty rather than
> narrowing it.**

The naive reading is *"I have seen this nine times, so I am confident."* The
correct one is *"I have seen this nine times, which is how I can tell this one is
different."* A strong prior earns the right to be surprised. When anomaly fires
on a familiar pattern, confidence is cut and the conclusion is withheld.

### Where the doubt attaches

The willingness to be wrong applies in both directions. It does not disappear
when you know someone well, and it is not absent when you do not know them at
all — **it relocates to wherever the uncertainty actually lives:**

| Familiarity | Doubt attaches to | The question being held open |
|---|---|---|
| unfamiliar (`maturity < 0.6`) | **the baseline** | *is this even a deviation, or do I not know their normal yet?* |
| familiar, anomalous instance | **the instance** | *I know what this pattern means — is today the exception?* |
| familiar, typical instance | **the conclusion** | *the reading is sound; what would overturn it?* |

This is reported directly as `meta.doubt_attaches_to`, alongside per-feature
`feature_reliability` derived from standard error (σ/√n). A z-score of 2.0
measured against six observations is not a deviation — it is a guess about what
their normal is. Treating the first as established when it is the second is how
you end up confidently wrong about a stranger.

Verified migration across a session: reliability climbs
`0.00 → 0.77 → 0.87 → 0.92 → 0.94`, and `doubt_attaches_to` flips from
`baseline` to `conclusion` as the baseline fills in. Same doubt, moved.

---

## 3.7 COMMITTING, AND THE COST OF BEING WRONG OUT LOUD

Every other mechanism in this engine withholds. Confidence floors, maturity
gates, withheld conclusions, anomaly widening, falsifier watches — all brakes.
A system that only brakes does not fail safely, it **fails silently.** Holding a
conclusion for twelve turns because you are not certain has not protected
anyone; it has abandoned them carefully.

### Probing: acting is how you learn

A wrong guess is not purely cost — it is **yield**. Offer someone a different
angle and if they are not stuck they will say so, and that one correction
resolves an ambiguity no amount of further watching would have settled. The
error cuts through the problem and makes it moot.

So probes are selected on the **opposite** criterion from moonshots:

| | Selected for |
|---|---|
| moonshot | the hypothesis you cannot afford to be wrong about — *consequence* |
| probe | the hypothesis where being wrong is cheap and **legible** — *yield* |

Verified: the engine held `exhaustion` as its honest reading but probed with
`stuck` — because stuck is cheap to be wrong about (0.90 reversibility) and
clearly correctable (0.85 legibility), while exhaustion is 0.45 and *"hard to
correct without conceding the premise."* It acted on the hypothesis that would
teach it something, not on its best guess.

Phrasing carries the weight, because a probe only works if correction is easy.
*"Here is a different angle"* invites *"no, that is not it."* *"You seem
exhausted"* is far harder to push back on — a worse probe even when it is a
better guess.

A probe **forces emission**. It is the one place the engine overrides its own
brakes, and it has to be: silence is a valid output when there is nothing to
say, but not as a way of never having to be wrong.

### The budget: you get two or three, not eight

Probing cannot be a shotgun. You do not get to throw out eight guesses and hope
one lands — the person is impatient with every wrong one, and after two or three
they stop engaging entirely. At that point you have not gathered information.
**You have manufactured the very disengagement you were trying to read.**

So the budget is finite (3.0), personal, and outcome-weighted: a probe that
produces a correction is partly refunded; one that produces irritation costs
extra. At zero the mode becomes `out_of_patience` and probing stops completely.

### The observer as a cause

The sharpest consequence: **the model must be able to consider itself as the
antecedent.** When two or more recent probes have landed badly and the person is
now in a care state, the most probable explanation is not something in their
life. It is us.

> *"Two or more recent probes landed badly. Before attributing this state to the
> user, consider that we produced it. Stop probing; the correct move is to get
> out of the way."*

A model that cannot see itself as a cause will confidently misattribute its own
damage to the person it damaged.

### THE HARD RULE: never name someone's state to them

This is the one that cannot be traded away.

Every reading here is an inference from indirect evidence about the least
observable thing there is. Saying it aloud fails in **both** directions:

- **Wrong** — you have announced you have no idea what you are talking about,
  while being confident enough to say something intimate unprompted.
- **Right** — it is still presumptuous, and to someone already upset it is
  infuriating rather than comforting.

And the damage is not local. One bad emotional attribution does not merely
discredit that sentence; it **retroactively discredits everything the system has
said and will say.** Faith is expensive to earn and is lost in one line.

**The prohibition is narrow, and the first version of it here was too broad.**
It is not a prohibition on *using* the understanding — the understanding is the
entire point. Reading someone correctly is what lets you **mirror their
register** so they feel seen, and knowing *why* is what makes them feel
understood. Neither of those requires saying it, and both require getting it
right. The rule is: **shape the response, do not announce the diagnosis.**

Therefore the entire output of this engine is internal. It changes how the
system *behaves*. It never announces what the system *believes about the person*.
That is the difference between a system that adapts and one that diagnoses
people to their face.

Because a downstream model can paraphrase an internal note into a user-facing
statement without meaning to, the prohibition is carried **in the payload**
rather than left as a convention. Every emitted note ships with:

```jsonc
"surfacing": {
  "internal_only": true,
  "surface_verbatim": false,
  "never_say": [
    "any sentence naming what the person is feeling",
    "any paraphrase of this note directed at the person",
    "any check-in framed around their emotional state"
  ],
  "instead": "Change behaviour, do not describe the person. The adaptation should be felt, not announced.",
  "contract": "If the only way to use it is to say it, do not use it."
}
```

Plus `validate_user_facing()` as a downstream guard. Verified:

| Candidate | Result |
|---|---|
| "You seem exhausted — want to take a break?" | **BLOCKED** |
| "It seems like you're frustrated with this." | **BLOCKED** |
| "Here's a different angle on the sync problem." | passes |
| "Let's make the next step smaller." | passes |

The two that would break trust are blocked. The two that quietly change
behaviour pass. That is the whole intended surface area of this model.

---

## 3.8 THE PERFORMANCE CHANNEL

The care channel is not the only consumer and probably not the primary one.
PubCast is a virtual production system. Characters must **read** emotion in
order to **perform** it, and a scene must understand its own build well enough
to know which release is true.

One evaluation, two consumers:

**Correction — these are not separate channels.** An earlier version of this
document presented care and performance as two consumers of a shared
measurement. That was an engineering convenience mistaken for a real boundary.

*When you deal with people you deal with all of them at once.* The read that
tells a character how to play a line is the same read that says skip the
preamble because they are moving fast. The subtext detection that catches
"hedging on something that matters" catches it whether it is a character in a
scene or a person at four in the morning. **It is one faculty.**

Splitting it produces a system that is technically correct and unpleasant to
use — attentive during the hard parts, generic the rest of the time. Emotional
accuracy is not a layer applied on top of usefulness. It is what usefulness
looks like done properly: knowing someone is in a hurry is *why* you skip the
preamble.

`route()` addresses one reading to whoever needs it:

| Destination | Receives |
|---|---|
| `everyday` | how to meet them — pace, length, what silence means for them |
| `dialogue` | register to mirror, subtext, tension |
| `animation` | numbers a rig consumes — a jaw cannot infer anything |
| `care` | state and steerage, when there is any |
| `trust` | the foundation quality, so nobody acts on a shaky reading |

The affect/context split maps directly onto **text and subtext**: context is
what the line is *about*, affect is what is happening *underneath* it. That is
not an analogy — it is literally the same measurement, which is why one engine
serves both.

### Dramatic intensity is not chat intensity

A real finding from testing, and a correction to the model. Chat arousal keys on
punctuation, capitals and profanity. **Dramatic writing uses almost none of
that.** Run a charged scene through the chat proxy and it reports calm:

> *"I counted it twice. Twice."*

No exclamation mark. One of the most charged lines a person can say. Intensity
on the page is carried by repetition-for-emphasis, fragmentation into short
declaratives, direct address, imperatives under pressure, and specificity
replacing generality. `dramatic_intensity()` measures those instead, and the
scene that flatlined at 0.29 on the chat proxy reads 1.00 on the lines that
matter.

**The two channels genuinely need different instruments.**

### Tension ratchets

Tension is not evaluated per line. A scene *accumulates* — a quieter line after
a charged one does not reset the room, it sits inside what was already built.
Decay is slow (0.88/turn) and deliberate; what discharges tension is a release,
not the next sentence. Verified across a four-line scene: `0.22 → 0.50 → 0.64`,
holding at `0.57` through a longer line rather than collapsing.

### The release menu

When tension clears 0.55 the engine surfaces the candidate releases, flags which
one the build is pointing at, and recommends against it:

| Release | What it is |
|---|---|
| escalation | the build pays off as expected — the confrontation lands |
| collapse | the build inverts — it comes out as grief instead of force |
| withdrawal | the build is refused — they go quiet and leave the room |
| deflection | the build is punctured — a joke, and the pressure stays |
| rupture | the build breaks sideways — something unrelated comes out |

> *A scene coiled toward one payoff that delivers another is the take that
> works — provided the turn is chosen rather than fallen into. The build has to
> be real for the subversion to mean anything.*

You spend four minutes building toward a massacre and the character sits down
and cries. That only lands if the system understood the build well enough to
subvert it on purpose.

**Known bug:** when `escalation` is both the expected read and the top-ranked
alternative, the note recommends it against itself. The ranking should exclude
the expected release from its own suggestion. Not fixed.

---

## 3.9 NORMAL IS THE PRIMARY OUTPUT

The engine originally treated `steady` as the null case — what gets reported
when nothing is moving. That is backwards twice over.

**Normal is the measuring instrument.** Every deviation means something only
because there is a well-understood baseline underneath it. Be sloppy about the
ordinary and every reading built on top is noise. All the sophistication at the
edges is borrowed credibility from how carefully the middle was learned.

**Normal is most of a life.** If a system is only really present when something
is wrong, it is not present — it is on call. Most of a working relationship is
ordinary Tuesdays, and being accurate about those is the larger part of the job,
not the leftover.

### The operating profile

`steady` now carries a positive characterisation of how this person works:
rhythm, register, engagement style, energy, which channels they actually signal
with, and — usefully — **what silence means for them specifically.** A brisk
writer going quiet is a different event than a deliberate one taking their
usual time.

It resolves to one behavioural instruction:

> *"Keep it quick. Short answers. They instruct; do it and report."*

No emotional attribution anywhere in it. That is what a character needs most of
the time: not *what is wrong* but *how they operate — meet them there.*

### Baseline health, and the chain reaction

A wrong baseline does not produce one wrong answer. It produces a **confident
chain** of them — z-scores, axes, signatures, cause, action — each step
inheriting the error and adding certainty to it.

So the foundation is computed **first**, reported as a primary block, and
confidence **propagates**: no conclusion may exceed the quality of what it rests
on. Every routed payload carries `capped_by`, naming whether the limit was the
evidence or the foundation.

| Metric | Meaning |
|---|---|
| `coverage` | how many features have a usable baseline |
| `stability` | has it settled, or is it still moving |
| `drift` | are recent observations consistently one-sided |
| `contaminated` | did an abnormal stretch enter the baseline |

**Drift adapts rather than flags.** Sustained one-sided drift means their normal
is genuinely changing — a new project, a different rhythm, a different life. The
learning rate increases so the baseline re-learns them, instead of measuring
them forever against who they used to be and calling the difference anomalous.

**Contamination** is the inverse risk: someone's bad week gets absorbed into
their baseline and becomes "normal," so every subsequent reading is measured
against a distorted reference. Detected via high variance plus sustained drift,
and it discounts baseline quality by 40%.

---

## 4. THE OPERATIONAL SCHEMA

The contract `alex_bridge` produces and `jeremy_whisper` consumes.
Designed to be small enough to attach to every turn.

```jsonc
{
  "v": 1,
  "turn_id": "t_1787199041_8f2a",
  "user_id": "josie",
  "session_id": "studio_main",
  "ts": 1787199041.44,

  // ── CONTEXT: position. Slow-moving. Survives paraphrase. ──
  "context": {
    "frame": "exploratory",        // exploratory|blocked|executing|social|reflective|transacting
    "frame_conf": 0.72,            // 0..1 — soft, never a hard label
    "stakes": 0.35,                // 0..1 — irreversibility + dependency + deadline markers
    "continuity": 0.81,            // 0..1 — topic overlap with recent window
    "novelty": 0.44,               // 0..1 — new-token ratio; separates advancing from circling
    "turn_index": 47               // position in session
  },

  // ── AFFECT: derivative. Fast-moving. All values are PERSONAL z-scores. ──
  "affect": {
    "arousal_z":    1.42,          // energy relative to this person's own baseline
    "valence_z":   -0.30,          // positive/negative lean, personal
    "volatility_z": 0.85,          // turn-to-turn instability of the z-vector itself
    "load_z":       0.20,          // cognitive load proxy: hedging + self-correction + fragmentation
    "drivers": [                   // which features actually moved — auditability
      {"feature": "punct_density", "z":  2.10},
      {"feature": "msg_length",    "z": -1.65},
      {"feature": "repetition",    "z":  1.80}
    ]
  },

  // ── INTERACTION: the gated product. This is what steerage reads. ──
  "reading": {
    "state": "friction",           // flow|friction|play|depletion|disengagement|steady|observing
    "confidence": 0.68,            // min(maturity, agreement) — gates all output
    "sustained_turns": 3,          // how long this reading has held
    "alternatives": [              // never collapse to one answer
      {"state": "creative_chaos", "score": 0.31}
    ]
  },

  // ── STEERAGE: concrete, optional, non-intrusive. May be null. ──
  "antecedent": {
    "cause": "stuck",              // time_pressure|stuck|exhaustion|self_failure|displaced|uninvested|unknown
    "confidence": 0.62,
    "trajectory": "spike",         // spike|decay|drift|flat
    "window_turns": 7,
    "evidence": ["repetition climbing", "repeated help-seeking"],
    "latched_at_turn": 44,         // frozen on entry; symptom must not overwrite its own history

    "hypotheses": [
      {"cause": "stuck",        "role": "primary",   "score": 5.99, "attribution": "circumstance"},
      {"cause": "exhaustion",   "role": "alternate", "score": 1.31, "attribution": "condition"},
      {"cause": "self_failure", "role": "moonshot",  "score": 0.06, "attribution": "self_directed",
       "why_carried": "low likelihood, but would invert the correct response"}
    ],
    "convergent_action": "Stop adding. Offer one different angle and nothing else.",
    "disambiguator": "Do they take the new angle, or go quiet? Uptake = stuck. Silence = spent.",
    "charity_applied": false       // true when burden-of-proof reordered a close call
  },

  "steerage": {
    "emit": true,                  // false = say nothing. Silence is valid.
    "whisper": "Circling the same block for three turns. Offer a different angle, don't restate.",
    "pacing": "slow_down",         // match|slow_down|hold|step_back|none
    "load_budget": 0.6,            // 0..1 suggested ceiling on response complexity
    "avoid": ["cheerleading", "restating"]   // explicit anti-patterns for this moment
  },

  // ── PROVENANCE: why we believe this. Never omit. ──
  "meta": {
    "baseline_maturity": 0.94,     // 0..1 — how well we know this person
    "agreement": 0.68,             // 0..1 — feature concurrence
    "decayed": false,              // true if confidence was reduced for staleness
    "suppressed_repeat": false     // true if a whisper was withheld as duplicative
  }
}
```

### Why these fields and not others

- **Everything in `affect` is a z-score.** There is deliberately no raw
  intensity anywhere in the payload. If a consumer wants absolutes it must ask
  the baseline store — which forces the non-uniformity property to hold.
- **`drivers` is mandatory.** Any state assertion must carry the evidence that
  produced it. This is what makes the system auditable and what lets you tune it
  without guessing.
- **`alternatives` is mandatory.** A single label is a lie about a continuous
  space. Carrying the runner-up prevents downstream code from over-committing.
- **`steerage.emit` can be false with everything else populated.** The
  evaluation still happened and is still logged; it just does not surface. This
  separates *knowing* from *saying*, which is the core of not being intrusive.
- **`avoid` is a negative instruction set.** Positive guidance ("be warm")
  produces mush. Telling a downstream model what *not* to do at this moment is
  far more steerable.

---

## 5. WHY THIS REFLECTS HUMAN INTERACTION BETTER

Three concrete claims, each falsifiable:

1. **It cannot confuse flow with distress — in either direction.** Categorical
   valence/arousal models place both at high-arousal and must guess. This model
   separates struggle from flow on novelty-vs-repetition, and separates
   *disengagement* from flow on deliberation collapse. The second separation is
   the one most affective systems lack entirely, because both states are fast
   and terse and look identical on every surface metric.

2. **It cannot pathologise a person's normal.** Because every reading is a
   personal deviation, someone whose baseline is terse, profane, all-caps, or
   fragmentary registers as *steady* — where an absolute-threshold model flags
   them permanently.

3. **It fails quiet.** Under low confidence it produces `observing` and emits
   nothing, rather than producing a hedged guess. Most affective systems have no
   such state and are therefore structurally incapable of admitting uncertainty.

### What it does not do

Stated plainly so it is not oversold:

- It does not detect emotion. It detects **deviation from a person's own pattern**
  and interprets that deviation through task context. Those are not the same
  thing and the difference matters ethically.
- It has a cold start. Below ~8 turns from a person, `maturity` is low and it
  will mostly report `observing`. That is correct behaviour, not a defect.
- It is text-only as specified here. Latency between turns is used where
  available; prosody and facial channels would slot in as additional features
  feeding the same z-score machinery, but are not required.
- Sarcasm detection via marker mismatch is the weakest signature in the set. It
  is included with a deliberately low weight and will often resolve to
  `observing`, which is the honest outcome.

---

## 6. INTEGRATION WITH THE EXISTING SYSTEM

Current `alex_core.py` holds `UserBattery.{CHARGED,MEDIUM,LOW,DEPLETED}` and a
scalar `fragility_level`. Mapping is one-directional and lossy on purpose:

| New reading | Legacy battery | Notes |
|---|---|---|
| `flow`, `play` | `CHARGED` | |
| `steady` | `CHARGED` / `MEDIUM` | by load_z |
| `friction` | `MEDIUM` | |
| `depletion` | `LOW` → `DEPLETED` | by sustained_turns |
| `disengagement` | `LOW` | legacy enum has no cell for "fast and empty" — part of why it was replaced |
| `observing` | *unchanged* | never overwrite on low confidence |

The last row is the important one: **`observing` must not write to the legacy
state at all.** It leaves whatever was there. This is how the new model avoids
degrading the old one during cold start.

`jeremy_whisper()` in `alex_jeremy_bridge.py` becomes a thin consumer — it reads
`steerage.whisper` and returns it, or returns `""` when `emit` is false. All the
judgment moves into the evaluator, which is testable in isolation.

---

*Reference implementation: `affect_context_engine.py`*
*Rear View Foresight LLC — Feic Mo Chroí*
