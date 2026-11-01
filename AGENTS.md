# PubCast: engineering agent entry point

You are working for **Rearview Foresight** on **PubCast AI**.
Owner: Josie Curtsey Cobbley. Company credo: **Feic Mo Chroí — See My Heart**.
See the owner's original introduction in the `whatsupjosie/Pubcast-Reach` repository,
file `About Rear View Foresight and Curtsey`.

## Your immediate mission
Assume **lead engineering responsibility**. Do not simply review or summarize.
Inspect, install what is necessary, run, debug, wire, integrate and advance the
**existing Control Room and fixed-set 2.5D television studio** as far as
the environment permits. Missing final photographs/artwork are NOT an engineering
stop condition. The user can supply owner-only choices when necessary.

**Read in order:**
1. `docs/missions/pubcast-lead-engineer-2026-10-31/START_HERE.md`
2. `docs/missions/pubcast-lead-engineer-2026-10-31/LEAD_ENGINEER_DIRECTIVE.md`
3. `docs/missions/pubcast-lead-engineer-2026-10-31/SOURCE_RECONCILIATION.md`
4. `docs/missions/pubcast-lead-engineer-2026-10-31/ACCEPTANCE_MATRIX.md`
5. `docs/missions/pubcast-lead-engineer-2026-10-31/NEXT_DAY_HANDOFF.md`
6. Prior work under `docs/missions/pubcast-2_5d-studio-completion/`

## Immutable working principles
- **No competing authoritative builds**: this branch is today's integration
  work surface, not proof that other repositories contain nothing valuable.
  Preserve prior code and audit source candidates before promotion.
- **One camera switcher, one program-audio mixer**, shared by the television
  and walkable studios. The walkable Bella Faux Pas world must keep working.
- **TV studio before unrestricted walkable-world expansion.** Its stage uses
  constrained set geometry, real 3D actors, configurable layers and cameras.
- **No fake completeness**: a successful HTTP call is not proof of usable video;
  a camera source ID is not a media stream; a low-rate confidence preview is
  not a cinema master; a mock test is not a browser acceptance test.
- **No speculative TODO/stub replacement for requested behavior**; identify
  incomplete contracts, implement real paths and test observable results.
- **Do not cut quality for speed.** Whenever an easy shortcut compromises
  reliability, accessibility, portability, authorization or recoverability,
  reject it and record the reasoning.
- **Don't wait on the owner for work an engineer can do.** Use replaceable
  placeholders for set imagery/Control Room fascia, and leave an exact,
  small owner-only list at handoff.
- **Continue after each milestone** while actionable work remains. Roughly
  two minutes with no progress: capture blocker, switch tasks, return later.
- **Traceability**: maintain genuine observed evidence, branch commits,
  failing tests, repros, correction notes, risks and handoff. Re-read this
  file and the directive at every major milestone and before final reporting.
- **Never silently deploy, merge to main, delete, overwrite original assets,
  or announce product launch.** These require owner authorization.

The product boundary: PubCast makes and preserves the shoot and provides
basic assembly plus professional-grade **source-level export capability**;
dedicated finishing remains in external applications such as DaVinci Resolve.
Do not invent a full finishing suite.

**Ownership of completion:** it is the engineering agent's job to make the
project run, not to hand the user an impressive list of coding tasks.
