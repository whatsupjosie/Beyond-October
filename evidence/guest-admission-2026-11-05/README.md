# Admission durability prerequisite

Codex / ChatGPT Work, 2026-11-05. This does not implement visiting identity yet.

Reproduced: a new GovernanceEngine on the same data directory cannot read an
existing waiting request. Before: one failed, one passed. The full-host adapter
called those records durable; they existed only in a process dictionary.

Compared three approaches: process snapshots still diverge between workers;
an extra JSON admission store duplicates governance authority and has concurrent
update races; an additive table in the existing governance SQLite database gives
one durable source and atomic status transitions. Chose the existing database.

Requests, decisions, pending listings and entered state now read the shared
database. Approval/denial uses compare-and-set so concurrent operators cannot
both decide a request. Only approved entries may transition to entered.
No owner identity, consent policy or standalone waiting-room API is replaced.

RAN `python -m pytest -q tests/test_governance_admission_persistence.py tests/test_full_host_route_authority.py tests/test_pubcast.py tests/test_module_router_parity_guards.py`:
**46 passed, one deprecation warning, 4.46 seconds**. Actual before/after output
and final JUnit are adjacent. Includes restart, cross-worker reads, concurrent
decision and denied-entry protection. Not a full-codebase debugging round.

Next: independent visiting identities, invite/challenge verification, owner
approval, host-issued guest sessions, revocation, profile/notes integration and
real multi-host browser/recording acceptance. Existing legacy account fixture
tests remain regression coverage only.
