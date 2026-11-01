# Friday companion recovery — October 25, 2026

## Completed code and integration

Friday's companion capabilities are retained and connected to the existing
PubPartnerSpine. They advise the authored companion; they do not replace System
Alex, overwrite cartridges, create a second personality, or gain write authority
over the companion's emotional state. The normal provider path still owns the
response and existing memory/receipt systems own persistence.

The shared companion_support package supplies acceptance, pacing, context
disambiguation, anti-parroting, known-versus-novel checks, agency safeguards,
explicit observation and provisional statement-difference tracking. Existing
modules.wired imports remain available through compatibility exports. Acceptance,
pacing and context-disambiguation implementations match the retained versions
byte-for-byte. Anti-parroting, known-versus-novel and safeguards match the recovered
Friday donor files byte-for-byte. The missing original observation/contradiction
implementations were not located: these two are new conservative implementations
of the retained consumer APIs, not a claim of recovered original algorithms.

Each turn owns an adviser, replays at most 16 permitted private history rows,
and supplies optional guidance after existing relationship/persona guidance.
Public/shared turns cannot replay private history or receive this guidance.
Known self-knowledge stays known; explicit opposing statements remain unconfirmed
and require clarification. The output review reports echo/novelty/agency concerns
without rewriting the provider response. No old canned crisis, referral or hotline
text is emitted by this adviser. Explicit requests for practical help override the
retained heuristic's long hold. Long/protected writing bypasses new analysis.

Both the embeddable PortableRuntime and cartridge CLI use the same advisers.
PubCast's private chat route now uses its existing canonical spine, requires
authentication, and binds the turn to the caller even for owner-role accounts.
Runtime-profile dispatch respects enabled profiles, reports fallback explicitly,
and does not present an echo/test profile as a live companion. The minimal
standalone PubPartner application already uses the spine and receives the new
behavior through that existing path.

The recovered companion progress also depends on the archive's coherent provider,
relationship and vessel changes: explicit lesson admission, quoted-source
protection, full authored context, indexed scoped recall, and visible incomplete
recall. Those dependency changes and their focused regression tests are included
rather than dropping them while replacing the outdated GitHub counterparts.

## Base, Horizon, cartridges and docking

A cartridge carries authored companion identity/personality and its memory store.
Horizon is a portable running host; Base is the resident host in PubCast. Docking
exchanges records between those hosts while retaining their distinct identities.

The new owner-scoped DockingNode API uses the existing sync engine and SQLite
stores. It exchanges cartridge-memory records, attributed user/reply experiences,
and knowledge with source references. Knowledge starts as a candidate unless
explicitly confirmed; candidates are excluded from recall. Retrieval is owner-
and companion-scoped, bounded, and reports incompleteness. Shared-stage turns do
not receive docking recall or export their dialogue as private experiences.

Configure an explicit resident node on PubPartnerSpine(docking_node=base_node)
and an explicit portable node on PortableRuntime(docking_node=horizon_node,
subject_id=owner_id, friend_id=companion_id). Both nodes must belong to that owner,
have different node identities, and use the same protocol. Calling
horizon_node.dock(base_node) checks health before and after exchange. Repeated
docking is idempotent; unresolved conflicts remain visible. Retrieved records are
evidence/context, not silent rewrites of authored identity or promotions to fact.
Cartridge YAML files are unchanged by docking. The owner controls confirmation.

This is a tested in-process docking API. Automatic phone discovery, pairing UI,
and a remote transport bound to these owner-scoped nodes are NOT implemented in
this slice. Existing federation HTTP tests pass, but that does not establish a
physical phone-to-Base docking connection. The portable host's data must include
its node store as well as its cartridge to carry exchanged records offline.

## Defects found and corrected during review

- Protected writing was analyzed before the vault classified it. Advice/review
  now use the stored source classification; source bytes remain unchanged.
- Optional docking failures could discard successful provider replies. Replies
  and receipts now survive, with visible recall/capture failure metadata.
- Knowledge identifiers could collide across companions. They are now scoped.
- Recall could report completeness after its effective 20-item cap. It now
  reports incompleteness correctly.
- Repeated docking could hide pre-existing conflicts or report a successful
  post-sync health failure. Those statuses now remain explicit.
- Sync saved its clock before saving associated data. Local writes/deletes and
  entire receive batches now use transactions; disk and in-memory clocks roll
  back with interrupted writes. Three new tests reproduced failures before the
  fix; rollback and restart/retry regressions now pass.
- Received changes were acknowledged but not retained for forwarding, so Base
  could not relay experiences between portable hosts. Received changes are now
  retained atomically. Existing conflict tests still assert preserved conflicts;
  one test was updated to inspect conflicts rather than assume the new edit is
  first in an envelope that can now also contain relayed history.
- The CLI bypassed PortableRuntime, and input assembly and memory insertion
  stripped authored whitespace. It now uses the shared runtime, and validation
  rejects blank-only text without trimming accepted source text.

## What was actually verified

Final combined candidate run: **379 passed, zero failures, zero skips, one
warning** (Starlette test-client deprecation for httpx, not a runtime failure),
with asyncio debugging enabled and ResourceWarning promoted to error.
This includes 103 already-published EVO regressions and 276 companion, cartridge,
federation, vessel, host and emotional-system cases. It is one 379-case result,
not a sum of repeated runs. Earlier focused/broader runs also passed.

The actual minimal standalone PubPartner app started and served its live-turn
route with a fake provider. The actual cartridge CLI completed a turn and
persisted memory. The actual PubCast private-chat handler was mounted and invoked
in FastAPI without booting unrelated full-studio services: authenticated owner
binding, override rejection, one canonical normal dispatch, protected writing,
fallback reporting and receipt integrity passed. This is explicitly not a full
PubCast startup test.

Real SQLite stores, real cartridges and the real sync engine were used for
bidirectional memory/knowledge/experience exchange, health and role/owner checks,
same-node rejection, idempotence, restart persistence, conflict visibility,
three-node relay, interrupted batch retry and failed-delete rollback.

A wheel built offline using pubpartner_pyproject.toml as isolated build metadata
passed a separate python -I smoke check: shared advice, real cartridge persistence
and bidirectional docking worked with **zero PubCast module imports**. All 17
selected portable/shared source files matched that wheel byte-for-byte. No model
API call or paid service was used in any test.

Every imported project source/test file was hash-checked against the GitHub
parent or an explicit publication path. No tested dependency relies on an
unpublished archive modification. Source parsing and whitespace checks passed.
The existing Alex identity, personality and emotional-authority sources remain
unchanged. Six retained/recovered engines retain their actual source bytes.

Run the selection from the repository with the recorded dependencies installed:

```bash
PYTHONASYNCIODEBUG=1 python scripts/verify_companion_recovery.py
```

The script excludes unrelated full-host conftest fixtures and supplies the
existing federation import path. Actual logs, JUnit, tested-file hashes, wheel
smoke output and pre-fix sync failures accompany this handoff. Deprecations in
retained legacy engines are not claims of test failures or proof of voice quality.

## Remaining product/environment checks

No real model conversation, human evaluation of emotional quality, browser UI,
physical phone, Windows deployment, remote node pairing/discovery, or live
cross-device docking was tested. The scoped remote docking transport/UI remains
future implementation, as stated above. No phone installation or deployment is
claimed. Full PubCast studio startup, cameras, audio and GPU paths remain outside
this companion recovery. The separate October 25 EQ revamp proposal is untouched.
