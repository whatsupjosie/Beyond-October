# PubCast Limited Exposure Data Handling

Implemented 2026-10-02.

`LIMITED` is a propagation classification. It is not an importance or priority instruction.

## Contract
- BlackBox remains the authoritative exception and receives the complete event plus its handling label.
- Shared context, indexes, intermediate files and broad system packets must not receive LIMITED payloads.
- Derived information inherits LIMITED handling.
- Access is default-deny and separately scoped by consumer and purpose.
- Shared paths receive opaque `LimitedContextRef` values rather than the protected payload.
- Credentials/secrets can use the `CREDENTIAL` category and remain subject to the same default-deny contract.

## Initial categories
IDENTITY, CONTACT_LOCATION, HEALTH, FINANCIAL, CREDENTIAL, PERSONAL_HISTORY, EMOTIONAL, RELATIONSHIP, LEGAL, USER_DESIGNATED.

## Runtime integration in this checkpoint
- `modules/limited_exposure.py`: classification, categories, explicit allow-list policy, inheritance, opaque refs, strict parsing, BlackBox envelope.
- `modules/alex_jeremy_bridge.py`: LIMITED turns may be processed in the authorised Alex path, but emotional coordination is replaced with an opaque reference and the bridge does not persist the shared packet. The full labelled turn is supplied to BlackBox.
- `modules/emotional_orchestrator.py`: provenance for LIMITED evidence is withheld from shared coordination snapshots.
- `blackbox_recorder/pubcast_event_adapter.py`: LIMITED events preserve a canonical complete event representation rather than losing nested/private fields through the compact scalar projection.

This is deliberately separate from System Alex emotional authority. Data classification controls propagation; it does not decide emotional meaning.
