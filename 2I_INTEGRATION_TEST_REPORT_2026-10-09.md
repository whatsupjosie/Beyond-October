# 2i v22 integration status — 2026-10-09

Implemented actual routes and durable SQLite backing for chapter commit, chapter hash/no-op detection, simple explicitly named entity extraction, intelligence retrieval, voice-feedback signal capture, flag resolution, and manuscript generation delegated to the existing PubPartner spine. /2i now serves v22; /2i-v22 remains an alias.

Verified: Python syntax, six FastAPI routes, HTTP chapter commit and idempotency, health, intelligence retrieval, voice-signal validation, missing-provider error, and isolation between two authenticated owners.

Not verified: live Ollama model generation, full app boot with all external dependencies, browser end-to-end interaction, and the original manuscript-intelligence package's 105 tests. This is a replacement integration for the missing package, NOT a claim of feature parity. Entity extraction is deliberately limited; continuity detection and automatic flag creation are not implemented. The original standalone manuscript-intelligence implementation is not available.

Security: manuscript API uses existing route_security.current_identity, not user_id supplied by browser. Content stored in writers_room/intelligence.sqlite3.
