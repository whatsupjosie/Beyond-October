# PubCast Foresight — four additional commissioning/debug rounds

**Release label:** 2026-10-09. **Input:** the user-provided `PubCast_Foresight_AUDITED_HARDENED_2026-10-09.zip`. **Approach:** patch only the audited single-source tree; preserve Alex's emotional, memory, CARE, and manuscript behavior; do not substitute a second character engine. The earlier commissioning report is historical, not a description of this build.

## Round 1 — Alternate routes, identities and information disclosure

**Findings:** `modules/route_security.py` could map an authenticated bearer user to a shared `anon` identity when authentication enforcement was relaxed and `X-Client-Id` was missing; explicit user selection could also contradict a valid token. The older `/api/characters/{id}` and `/context` routes exposed character internals without enforcing production authentication; `/api/bots/{id}/status` revealed internal key environment names in a public diagnostic response. The legacy `/api/characters/speak` route used a separate inference shortcut that ignored the BotManager character prompt/profile.

**Fixes:** authenticated JWT claims now take priority regardless of developer-mode configuration; contradictory actor headers and fields are rejected. Legacy character routes require authentication when deployed, reveal only public profile metadata to ordinary users, and reserve internal context for moderator/admin/owner. Bot diagnostics are reduced for ordinary clients. The legacy speaking entry now delegates to the same `speak_to_character` private-transcript+BotManager service as Foresight, with caller identity fixed at the HTTP boundary. It no longer treats untrusted request context as a user or room selection.

## Round 2 — Direct conversation ordering and archive ownership

**Findings:** simultaneous requests to one direct character thread could interleave user texts and assistant replies in the model prompt and in the saved history. The SQLite messages table stored only hashed thread IDs, so owner-scoped Save All could not enumerate private character conversations.

**Fixes:** an asyncio lock keyed by data directory+thread serializes model generation and append order **within one server process**. The same SQLite database gains a `threads` table with owner, bot, and conversation label; existing message rows remain intact. Each authenticated read/write registers its thread mapping. A checked owner export enumerates only that owner's threads. An adversarial seven-turn concurrency test measured a maximum of one simultaneous provider invocation for the same thread and verified ordered user/reply pairs.

**Limit:** this is **not** a cross-process lock. Older hashed threads with unfamiliar custom labels cannot be discovered for export until opened by the owner; no unverifiable reconstruction of old metadata has been attempted.

## Round 3 — Private transcripts in Save All and checksum inventory

**Finding:** the existing general-chat Save All Raw/ZIP excluded private direct-character conversations, creating an unannounced backup hole.

**Fixes:** the canonical `PackageService` now accepts a tightly allowlisted export attachment, `PrivateCharacters/transcripts.json`, supplied by the owner-scoped character store. Both Save All Raw and ZIP include it in the existing manifest, SHA-256 checksums and archive verification. No unscoped database dump or new competing backup engine was added. Tests checked separate Alice/Bob exports for zero cross-owner content, exact UTF-8 and markup fidelity, manifest length/hash, ZIP integrity, and authentication rejection.

**Privacy:** these exported ZIP/raw files are **plaintext**. Existing export staging/storage remains in the host's `exports` tree. Do not assume encryption, automatic Google Drive syncing, retention policy or verified import/restore. The records are now portable and checksummed; secure transport, restore and retention remain separate work.

## Round 4 — Browser display, live routes, and regressions

**Findings:** the Character Chat info panel interpolated moderator-configured provider/model labels into `innerHTML` even after prior hardening of message bubbles. The DM selector still includes static names and does not open a fully managed DM conversation; this is recorded, not represented as fixed.

**Fixes:** the panel builds DOM nodes and inserts provider/model text via `textContent`. Removed an unnecessary legacy development-role header from the DM request. Confirmed the canonical character backend and normal Foresight navigation are served from the same live Reach host.

### Evidence from this pass

- New focused/adversarial tests + existing privacy, packaging, Writer's Room/Foresight, CARE/Alex memory and emotional integration: **63 passed** in one selection.
- Separate broader authentication, websocket, real host routing, security and World Chat integration selection: **95 passed**.
- The smaller hardening + original conversation/package selection: **35 passed**. Counts overlap across selections; they are **not** 193 unique tests.
- Static JavaScript for `static/pub_partner_chat.html`: Node `--check` passed. Python module compilation passed.
- Fresh process launch of `run_reach.py --no-browser --no-legacy-2i`, clean data dir, auth forced on: `/foresight`, `/pubpartner`, `/writers-room`, `/pub-partner-chat` all HTTP 200; anonymous legacy character profile/bot-status requests HTTP 401; real owner creation HTTP 201; owner character list HTTP 200 with four bundled characters; owner Save All ZIP HTTP 200 and verified to contain the character-transcript file and pass ZIP integrity. Legacy character speak returned **HTTP 503** because the Anthropic key was absent, proving error handling but **not live inference**. Host exited cleanly.
- **Important suite qualification:** a single whole-repository pytest invocation did **not** complete in this execution environment. It reached about 44–47% before hitting execution time limits around the Alex bridge tests. The high-urgency Alex bridge test passed in isolation (2.55s), and a wider isolated authentication/route set passed (95 tests). The earlier audited release's 964-pass number does **not** certify this modified build; no full-suite green claim is made for this version.

## Open constraints / honest status

1. No UI click-through on an actual Windows/Android browser or phone hardware; static JavaScript and live HTTP checks are not substitutes.
2. External model providers, owner API keys, real Google Drive and optional 2i Node sidecar were not available for live integration here.
3. The new private-transcript ordering lock is per process. True multi-worker turn ordering and request idempotency remain to be implemented.
4. Save All exports are checksummed but plaintext and currently have no verified restore/import or automated retention cleanup. Historical custom-label threads must be reopened to register export metadata.
5. Character Chat's accepted DM requests still lack a complete DM conversation viewer and presence-driven participant selection. PubChat's core consent and socket authority remain the real gate.
6. Studio hardware/voxel/cameras/recording physical devices, GGUF performance and Windows/offline startup are still not commissioned.
7. The general auth-off behavior for direct `uvicorn main:app` is unchanged: production operation must use `run_reach.py` or explicitly enforce auth.

**Result:** four concrete debug rounds delivered as one patched authoritative source tree, with tests and an accurate boundary between proven behavior and unfinished commissioning.
