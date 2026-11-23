# PubPartner unification: authority map and integration boundaries

Status: **integration branch, not merged or runtime qualified**

## Decisions carried forward from the November 22 design session

1. **PubPartner is a separate installable product.** PubCast hosts its control plane; the host must not own the friend identity. Portable runtime remains a separate client of the same identity/data contracts.
2. **Cartridge = packaged character definition, not the entire partner.** Profile and vessel supply identity; provider/model is replaceable.
3. **VerbatimVault = original immutable user messages.** Blackbox Light is the readily searchable full-dialogue projection. Neither is the Iteration Wallet.
4. **Iteration Wallet = independent custody and recovery.** Birth snapshot, last verified good, and quarantine require Wallet's verified gatekeeper/ceremony and paired installation authority. This branch does NOT create a competing Wallet, claim pairing, or silently restore a damaged character.
5. **Calibration = verified feedback to existing systems.** User Calibration teaches PubPartner's model of the person; System Calibration adjusts partner behavior/voice. Original audio can be retained by consent for comparative EQ, but a recording alone is not an emotional label.
6. **Emotion learning must start with evidence.** The partner listens, compares actual voice samples against a personal baseline, forms tentative hypotheses, asks short direct questions, and stores uncertainty/corrections. Do not ask users to explain unconscious vocal tells. The existing canonical affect system lives in AlexCore, not the deprecated affect_wiring path.
7. **Interview contract.** Aim three main questions, hard ceiling five, maximum one optional follow-up per main question. Follow-up questions and free continuation are distinct from main question count. Partner owns question selection; no clinical questionnaire.
8. **Future recording controls.** Per-voice-message 60-second capture ceiling is not retention expiration. Three studio recording modes (normal camcorder, data-only, main-camera-only) belong to PubCast recording and should not be conflated with PubPartner private conversation archive.

## Existing code and responsibilities

| Responsibility | Authority |
| --- | --- |
| Turn pipeline, provider dispatch and receipts | `PubPartnerSpine.run_turn` |
| Identity/personality | existing friend profile and vessel |
| Original user text | `VerbatimVault` |
| Searchable complete user + partner exchanges | `ConversationArchive` through `PubPartnerBlackboxLight` adapter |
| Relationship corrections | `RelationshipEngine` confirmed lessons |
| EQ inference and personal baseline | AlexCore canonical affect engine; audio integration NOT wired |
| Structured interview/voice sample custody | `CalibrationStore` |
| Portable runtime & synchronization | existing `PortableRuntime` and `DockingNode` (not newly packaged here) |
| Verified friend ZIP backup | `pubpartner_backup` scoped export; independent of Wallet |
| Protected restoration/quarantine | existing standalone Iteration Wallet (adapter NOT wired) |

## Wiring added on this branch

- `PubPartnerSpine.run_turn` archives successful *private* dialogue after restoring the actual model reply, and exposes a visible `blackbox_light` status in its result. Failures do not erase the primary VerbatimVault record.
- Authenticated endpoints `/api/pubpartner/blackbox-light/conversations`, `/conversations/{conversation_id}` and `/search` use user AND partner scope.
- The archive database reuses existing `ConversationArchive` SQL schema. Duplicate replay of the same source is idempotent. Bad source collisions fail rather than change prior text.
- Verified backup now exports only the requested user's requested partner's Blackbox Light conversations as JSON rather than copying the shared SQLite file. Session/receipt selection is strengthened to require explicit owner + partner state. Calibration source files are included for the owner.

## Still to integrate, not to mislabel as complete

- UI conversation browser and retrospective search (API exists; no phone-ready browser added yet).
- Audio timestamp alignment, EQ model comparison, consent/retention/deletion controls and voice baseline updating.
- Full private archive ingestion from *all* historical chat surfaces. Existing PubPartner live turns only are archived by the new adapter.
- Migration/backfill of old turn logs and original-source consistency checks.
- Wallet authenticated pairing, backup custody, rollback and quarantine using preexisting Wallet APIs.
- Cross-host sync and an exactly-once replica repair protocol. Federation exists but is not yet tied to the new searchable archive.
- Live Python unit/integration tests and browser tests; GitHub Actions runner allocation previously failed before tests started. Do not merge until tests pass or verified failure cause is recorded.

## Acceptance checks

1. One successful private live turn results in a VerbatimVault source, an existing receipt, and a searchable ordered Blackbox Light user/partner pair.
2. An unsuccessful provider attempt does not invent a partner message; a shared-room turn does not enter private Blackbox Light.
3. Replay of an identical source remains idempotent; conflicting source payloads are rejected.
4. Owner and partner separation hold for listing, search, read and export under HTTP authorization.
5. Owner's verified ZIP includes only their requested partner's searchable transcript projection; it never includes another owner's SQLite rows or any provider credentials.
6. No existing session file, original text, or Wallet artifact is modified by this archive adapter.
7. Existing calibration corrections continue to appear in appropriate private FCP1 guidance after restart.

The integration is incomplete until these checks run on a real host and the user can operate it on a phone.
