# PubCast Security Foundation — 2026-10-02

This checkpoint formalizes the security architecture developed alongside Limited Exposure.

## Authority
- The **Owner** is the license owner/root administrative and custodial authority of the PubCast instance in which an event originates.
- The **Host** is distinct. Host authority is delegated by the Owner and carries only the delegated operations/permissions.
- Running an event does not itself grant Owner authority.
- Origin instance and Owner authority travel with protected resources so federation does not silently transfer root access.
- External legal obligations or verified superior claims are policy/legal inputs; the runtime does not invent them.

## Classified access
- STANDARD data does not incur classified-access auditing.
- LIMITED/classified payload access is fail-closed through SecurityGate.
- Every classified access attempt is audited before payload release.
- Audit events contain metadata, never the protected payload.
- Owner has universal retrieval authority for protected information belonging to the Owner's origin instance, but must receive and acknowledge a warning before disclosure.
- Owner access does not declassify information.
- Host has no implicit Owner override.

## Limited conversations
- Deliberately restricted-audience conversations are LIMITED by construction, independent of semantic sensitivity.
- Participants receive direct-conversation access; unrelated people/systems do not receive the conversation merely because it might be useful.
- Derived information remains LIMITED under the existing inheritance rule.

## Existing complementary controls
The existing build already contains authentication/password hashing, room/socket authority, BlackBox, Waiting Room/governance, and other security-related components. This checkpoint adds the common classified-data authority boundary; it does not falsely claim those older systems have all been migrated behind this gate yet.

## Next integration/hardening targets
Wire SecurityGate into all classified payload resolution points, BlackBox classified retrieval, room/IM retrieval, exports, AI-assist, persistence, and future PubCast-window Incident Capture. Add centralized delegation storage/revocation and signed/audited Owner→Host grants. Then perform adversarial bypass tests across every protected-data path.
