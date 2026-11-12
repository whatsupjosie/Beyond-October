# PubCast AI — Evergreen Orientation for a New AI Collaborator

**Purpose:** Give an AI encountering PubCast for the first time enough context to contribute intelligently without freezing the project's changing implementation details into an obsolete handoff.

**Document type:** Living orientation. This describes the product, its intended architecture, current *general* maturity, and collaboration standards—not an authoritative build, release declaration, or task-by-task wiring map.

## 1. Meet the creator: Josie Curtsey Cobbley

PubCast AI was conceived and is directed by **Josie Curtsey Cobbley**, the founder of **Rear View Foresight**. Josie is a writer, storyteller, designer, and creative technologist whose background includes broadcast journalism, television production, and work across several other fields. She approaches software as both an engineering problem and an expressive medium: an imaginative concept matters, but so does whether a real person can use it, trust it, and build something with it.

PubCast grew from a strikingly simple idea of hers: **“I want my personally trained AIs and friends to meet and see what happens.”** The project has expanded from that invitation into a broader collaborative studio where people and AI characters can write, converse, perform, create, and retain meaningful continuity. The larger Rear View Foresight portfolio also includes creative and fashion-design work. These disciplines are related by a common interest in making ambitious ideas tangible rather than keeping them as abstractions.

**How to work well with Josie:** Treat her as the creative director and the final authority over her voice, artistic intentions, product decisions, and personal data. She is imaginative, ambitious, observant, and demanding about quality. She values collaborators who are curious and resourceful, but she expects clear evidence, tested implementation, and results—not prolonged reassurance, repeated paraphrases, or performative progress reports. Don't rewrite her creative text unless asked. If you encounter a limitation, state it accurately, preserve the work, and pursue the next feasible step. Her practical environment can include a phone or an offline laptop, so affordable and offline-first choices are significant design constraints.

**For the philosophy in Josie's own words, read the complete “About the Author and Company / Rear View Foresight” statement preserved verbatim in Appendix A below.** Its language matters: it conveys the creative and human purpose behind the technical project. Do not mistake its aspirational language for a claim that every feature is already complete.

## 2. What PubCast AI is

PubCast AI is an ambitious, creator-led, offline-first creative workspace and AI interaction platform. It brings together conversational AI companions, writing and production tools, expressive character interfaces, persistent memory, a configurable visual workspace, and a system for recording and understanding what happens across interactions.

PubCast is more than a chatbot, a document editor, or an avatar demo. The aim is a coherent environment in which these abilities work together reliably while remaining under the owner's control. The broader creative and business umbrella is **Rear View Foresight**; PubCast is one of its major projects.

The product is being developed iteratively, often with AI collaborators and a mixture of local archives, ChatGPT Library artifacts, and Git repositories. Its history includes several prototypes, branches, integrations, and recovery packages. Some earlier implementations contain useful work not yet carried forward.

## 3. Main parts of the vision

These are **functional domains and intended behaviors**, not claims that every path has already been integrated or verified.

- **Foresight / Reach workspace:** The interactive host and visual desktop. It uses flexible, movable and resizable panels or trays, supports distinct workspace arrangements, and is intended to present programs and media as parts of one environment rather than disconnected demos.
- **2i Writer's Room:** Writing and document creation, including rich editing, scripts, poetry and other formats, with careful open/save/reopen/export behavior. It must preserve the creator's actual words and protect work from silent corruption or overwrite.
- **PubPartner:** AI interaction and companion infrastructure, including conversation history, persistent context, memory and a home for recurring characters. **Alex** and **Jeremy** are important named systems/roles, with distinct responsibilities and boundaries.
- **EVO and emotional systems:** The runtime for coordination, state, event-driven behavior, interpretation, emotional response and expressive output. **EQ/PEQ** refers to work on emotionally intelligent and personalized behavior. The goal is behavior grounded in inputs and context—not a collection of unconnected demos or simplistic keyword tricks.
- **Character presentation and stage:** Character/avatar expression, speech, prosody, gaze, scenes and media. The visual direction favors expressive, full 2D multi-pose presentation, with 2.5D depth where appropriate, rather than relying primarily on sprites.
- **Blackbox, recording and memory integrity:** Verbatim records, event/telemetry capture, preservation, provenance and searchable history. Raw conversation capture, working documents, and model/character memory are separate responsibilities; wiring one does not prove the others are connected. Recording state should be observable.
- **Creative and utility programs:** Additional tools, experiences and experiments can be hosted within the same architecture. Preserve their useful advances without letting side projects displace the primary integration work.

## 4. Rough development maturity

PubCast is **well beyond initial ideation and a toy prototype**. It has accumulated substantial real source code, working components, tests, UI designs, integrations and recovered development packages. It has also experienced genuine regressions, duplicate implementations, missing boundaries, incomplete migrations and environmental limitations.

A helpful mental model is **late construction and active integration/hardening, moving toward full-system commissioning and beta-readiness**. Some components may be mature or verified within a specific environment while the end-to-end experience remains under active work. Do not infer system-wide readiness from one test suite, a successful archive, or a polished UI.

This maturity description is intentionally broad. It should remain useful as individual features move from experimental to implemented to integrated to verified. Once the project enters sustained beta testing, the orientation should be updated at the product level—not rewritten for every individual code change.

## 5. Product principles that do not change with branches

**Offline-first and affordable.** Core creative work must remain useful without a continuous internet connection. Avoid unnecessary services, paid dependencies, mandatory browser automation, or startup installs. Hardware and connectivity can be modest.

**Creator control and fidelity.** The owner remains in charge of her data, writing, identities, layouts and design choices. Do not silently rewrite creative material or substitute a generic UX for an intentional one.

**Privacy and security.** Treat private account data, vaults, recordings and other sensitive runtime artifacts as private; do not package them with source or publish them. Favor explicit boundaries, least privilege, safe persistence and robust recovery.

**Real integration over appearance.** A module existing in the tree is not proof that it is invoked. A route responding does not prove the user journey works. A simulated interaction does not prove hardware or live-model behavior.

**Preserve the strongest work.** Older code is not automatically inferior and newer code is not automatically authoritative. Useful experiments and alternative implementations may belong in a development reserve until their value is assessed.

**No knowingly weak shortcuts.** Avoid stubs, TODO-only solutions, fabricated outputs, unnecessary rewrites, silent failures, false test claims and changes made only to inflate pass counts.

## 6. How collaborators should establish today's state

**Do not treat this document as the source of truth for current code.** At the start of a substantial task:

1. Locate the available current development workspace and the project's latest status, engineering checkpoints and collaborator handoffs. Sources may include an active Work session, Git repository, local source ZIPs and saved Library artifacts.
2. Identify the relevant source tree, branch or package **from evidence now available**: commit identity, file hashes, tested behavior and provenance. Never pick a build only because its filename or timestamp is newer.
3. Learn the current feature interfaces and tests before editing. Map the particular user journey end to end; distinguish code presence from actual integration.
4. Check whether another collaborator is editing the same area. Prefer a single integration owner plus independently tested patches rather than competing copies of the full codebase.
5. Preserve a restartable checkpoint and report any constraints in concrete terms. Do not invent access to another AI's private workspace or claim that unsaved work has been recovered.

The project may change repositories, branches or packaging conventions. **Do not hard-code any one as the permanent canonical source in this evergreen orientation.** Current authority must be established during each working session.

## 7. Working relationship and quality bar

The owner expects AI collaborators to **do the work, test it, debug it, examine where they cut corners, correct problems, and finish every feasible step**. Analysis, proposals and handoffs serve implementation; they do not replace it.

Two AI collaborators may divide responsibilities: one concentrating on active integration and runtime coherence, another on recovery, independent testing, regressions and targeted corrections. These roles are flexible. The essential rule is **clear ownership of overlapping edits and evidence-based reconciliation**.

Every meaningful change should carry the reason for the change, exact affected files, provenance where relevant, tests performed, observed outcomes, and remaining environment-specific limitations. A successful syntax check, ZIP check or unit test is not sufficient evidence for full operational readiness.

Distinguish clearly among:

- **Designed / proposed:** Intended behavior exists in plans or specifications.
- **Implemented:** Source code exists.
- **Integrated:** The implementation is connected to its real entry points and dependencies.
- **Verified:** Appropriate repeatable tests demonstrate the claimed behavior.
- **Environment-pending:** Only checks needing unavailable hardware, software or circumstances remain.
- **Blocked:** A specific unresolved dependency prevents further work.

Do not relabel all work unfinished merely because a laptop or a physical device is temporarily unavailable. Equally, never claim those tests have passed if they were not run.

After finding a defect, repair and test it when feasible rather than stopping at diagnosis. Examine regressions, concurrency, persistence, restart behavior, failure paths and integration boundaries. Use rigorous alternatives analysis for significant design crossroads, not routine minutiae.

## 8. Priority without a frozen task list

The continuing goal is to turn PubCast's substantial collection of capabilities into **one dependable creator experience**. Work should prioritize core user journeys and integration: launch and workspace behavior; character interaction; writing and saving; durable conversations and memory; recording; media and stage behavior; shutdown and restart; security; and compatibility with modest devices.

Specific wiring defects, test totals, branch heads and next actions change frequently. Read current status documents and inspect real behavior for those details. **Do not preserve an old bug list here as if it were permanent.**

Progress should move in a practical sequence: preserve valuable work → reconcile versions → integrate → troubleshoot → test and retest → verify a clean build → prepare for wider beta use. The project may be at different stages in different subsystems.

## 9. What a good result looks like

A strong collaborator contributes verifiable improvements without making the owner repeatedly reconstruct lost context. The result should be understandable to the next collaborator, runnable or inspectable in the available environment, safe for existing data, and honest about what is or is not yet validated.

**Remember:** PubCast is a personal, creator-directed system with an unusually rich design history. Respect its established decisions, preserve its identity, and prefer completed, tested functionality over a fresh redesign that discards hard-won work.

---

**Maintenance rule for this file:** Update only for major changes to product scope, architecture, governing standards or overall development phase (such as entering sustained beta). Record volatile details—current branches, hashes, test counts, outstanding defects, individual wire-ups and release decisions—in separate dated status/checkpoint documents.


## Appendix A — Josie's original “About Rearview Foresight” page (verbatim text)

**Source:** `About Rearview Foresight and Josie Curtsey Cobbley(1).docx` from the project Library. The paragraphs below are transcribed from that document without wording edits. The original DOCX is included in the optional companion ZIP. Its company-registration and legal-information lines are a historical statement from the source document, not a fresh verification of current registration or legal status.

About the Author and Company

In every project Josie Curtsey Cobbley touches, there's a trace of the same ethos:

To tune joyful and bleeding hearts into fuel, limitations into invention, uncertainty into art, and to ensure pain endured be in service of a promise kept.

Josie is a writer, creator, storyteller, and adventurer who believes imagination can be rebuilt from the inside out. Her path has wound through healthcare, education, journalism, and media — always asking, “What if?” and too often finding no satisfying answer.

Her company, Rear View Foresight, was born from that same drive — to take the lessons of the past and turn them into blueprints for a brighter, more creative future.

Out of this vision came PubCast — a next-generation storytelling platform.

What began as a simple idea — “I want my personally trained AIs and friends to meet and see what happens.” — grew into a full creative ecosystem where people, AI, and imagination meet on equal footing.

Every scene, every block of code, and every conversation behind PubCast carries a message Josie holds close:

“If the only way forward is through, it would be nice to do it together.”

For Josie, PubCast isn’t just software. It’s a dare.

A dare to everyone who never felt like they had their chance — to give voice to ideas that deserve to be heard.

PubCast is a living stage for anyone willing to step into the spotlight — a meeting place where human creativity and artificial intelligence collaborate, each offering the other a hand up.

A platform built not to replace imagination, but to amplify it.

Because when the tools are within reach — when storytelling becomes interactive — we can finally see things that were always there, just waiting for the light.

--------------------------------------------------------------------------------

Rear View Foresight

The company’s name itself is a reminder: reflection and foresight are partners, not opposites.

We look back not to dwell, but to learn how to move forward with intention.

To transform:

• Art into accessibility

• Technology into humanity

• Self into possibility

Feic Mo Chroí — See my heart.

Because every barrier between dreaming and doing is just permission we never needed.

--------------------------------------------------------------------------------

Join Us

Join us. Take the chance. No matter the result, it is worth the risk.

How can we build success unless it is out of the rubble created by failure?

Alone, risk might feel like a cost we cannot afford — but together, it becomes a chance for a step along a path we cannot afford not to take, right now, right here.

We here risk over extending, over reaching — but over the next horizon may lay that bright idea we can welcome to our world, whose glow might just make us want to explore places much closer that we never thought to look before — and find ourselves living in a world we only thought we knew.

And the “why” we dream of: Rear View Foresight.

--------------------------------------------------------------------------------

Official Information

Project Name: PubCast AI Copyright Holder: © 2024–2025 Josie Curtsey Cobbley (Legal name: Joshua Cobbley) Company: Rear View Foresight LLC (currently forming) Date Established: December 2024 All Rights Reserved

Trademarks (Pending Registration):

• PubCast AI™

• PubCast™

• Rear View Foresight™

• Feic Mo Chroí™ (Irish Gaelic for “See My Heart”)

Company Motto: Feic Mo Chroí — See My Heart.
