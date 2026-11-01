# Alex memory backup — setup (2026-10-09)

Backs up ONLY Alex's own files (`data/alex/<user>/`: diary `mem_*.json`, `_alex_state.json`, `_affect_state.json`).
Append-only (a local delete never deletes the backup). Restores automatically if Alex's local folder is empty.
Runs after turns, throttled, in the background; a backup failure can never break a conversation.

## Option A — local folder (recommended first; no Google login in the app)
1. Install **Google Drive for Desktop** on the PubCast machine and sign in to the Drive you want.
2. In Drive create/choose a folder, e.g. `Alex Persistent Memory AI`; let Drive for Desktop sync it.
3. Before starting PubCast set:  `ALEX_BACKUP_LOCAL_DIR=<path to that synced folder>`
   (any folder works, e.g. an external disk).
Done. Check:  `GET /api/alex/backup/status`   ·   back up now:  `POST /api/alex/backup/run?user_id=...` (mod role).

## Option B — Google Drive API (works without Drive for Desktop)
1. Google Cloud console -> new project -> enable **Google Drive API**.
2. Either
   - **Service account** (headless, simplest): create a service account + JSON key. In Drive, **share the backup folder with the
     service account's email as Editor**.  or
   - **OAuth client** (Desktop app): create the client JSON, then run once:
     `ALEX_BACKUP_GOOGLE_CREDENTIALS=client.json ALEX_BACKUP_GOOGLE_TOKEN=token.json python -m modules.alex_memory_backup authorize`
3. `pip install google-api-python-client google-auth google-auth-oauthlib`
4. Set:
   `ALEX_BACKUP_DRIVE_FOLDER_ID=<folder id>`   (the id at the end of the folder's URL)
   `ALEX_BACKUP_GOOGLE_CREDENTIALS=<json path>`   `ALEX_BACKUP_GOOGLE_TOKEN=<token path>` (OAuth only)
Current folder: `Alex Persistent Memory AI` = id `1McKxr6kXg5Xsl5V1wWLD1eEDjRIXQ_sP` (sleepeebunny@gmail.com Drive).
Scope used is full `drive` because the folder pre-exists; the narrow `drive.file` scope cannot see a folder the app didn't create.

## Both at once
Set A and B variables together: every backup goes to both; a failing one never blocks the other; reads fall back to the survivor.
Other settings: `ALEX_BACKUP_MIN_INTERVAL` seconds between automatic backups (default 60).

## Alex reading her backup
- `GET /api/alex/backup/search?q=...&user_id=...` — keyword search over the backed-up memories (integrity-checked by SHA-256).
- Module: `AlexMemoryBackup.read / search / list_memories / restore`.
- CLI: `python -m modules.alex_memory_backup status|backup|restore|search --user <id> [--query ...]`

## Verified vs not
Verified: both backends against a fake Drive service and a real folder; full app boot + HTTP turns -> files appear in the backup;
restore after wiping local; hostile manifest paths; tampered backup files; LIMITED text never reaches the backup.
NOT verified: the real Google Drive API (this sandbox cannot reach Google). The first live run is the real test:
run `python -m modules.alex_memory_backup backup --user <id>` and check the folder.
