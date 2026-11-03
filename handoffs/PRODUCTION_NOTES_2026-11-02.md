# Production notes (sticky notes) and the PubCast profile — 2026-11-02

Branch: `claude-work` (on top of `6509835`, which sits on `main` at `bfbdcf0`).

## What Josie asked for (her design, in order of the conversation)

- Production messages between people in a production ("rehearsal moved…", "okay, got it"), shown as sticky notes.
- When a user registers, PubCast gets their email. Sending a note can also make an email copy, sent through the
  sender's own email; replies to all could come back as sticky notes (not built yet, see below).
- Every user has a permanent user ID (and a session ID that changes each session).
- Clicking a note: the room blurs, a column of notes appears, newest on top; clicking one opens one big sticky note
  laid out like an email (From, To, CC, BCC, subject, attachments), scrollable. Save, Trash, Reply, New sticky note.
- The subject is what is handwritten on the little note. Up to three little notes show on the makeup mirror.
- A sender chooses where a note sticks in the recipient's PubCast (the mirror and, e.g., the audio mixing board).
  Notes stick only to things you can interact with.
- In a wide shot a note is visible but not clickable; you click it once you are at the closer shot. Opening a note
  from anywhere takes it off its spots. Clicking one note opens the menu with that note first; closing it lands on
  the menu.
- Notes look like her reference picture: torn edges, curl, a third smaller than the second mockup, and lying in the
  perspective of the surface they are on (the angle comes from the horizon line).
- A gold foil star on the top right corner with a subtle sparkle so a note is not missed, without making it bigger.
- A sticky note on the corkboard that opens the main menu; the menu organised by date or by project; notes to yourself.

## What was built

| Piece | Where |
| --- | --- |
| Profiles with permanent IDs (`u_` + 20 hex), display name, email; made at first-run setup, for crew, and automatically for accounts made before profiles existed | `modules/userdb.py` (`profiles` table) |
| First-run setup asks for an optional display name and email | `modules/auth_routes.py`, `static/login.html` |
| Profile routes: read/edit your profile, change your password; list the production; owner or moderator adds crew accounts (only the owner adds moderators) | `modules/production_notes.py` |
| Notes on the host: To/CC/BCC (people, `@production` = everyone but you, or yourself), subject, optional project, message, spots (the mirror always), attachments (8 × 10 MB, 25 MB per note, downloads only, served only to people on the note), read / save / trash per person, replies threaded, BCC shown only to the sender | `modules/production_notes.py`, `<data>/notes/` |
| Spots and where they are in each picture (quads measured by eye: proposed, for Josie to correct): makeup mirror (wide and close-up), audio console, director's console, Avatar Foundry mirror, studio door in the green room; the corkboard's own notes button | `static/world/note_spots.json` |
| In the studio: unread notes painted onto their surfaces in perspective, under the figures; gold star with a glint every ~5 s (none with reduced motion); wide shots show, close-ups click; hotspot bubbles offer "Read note: …"; corkboard note opens the menu; menu by date or project with Inbox / Saved / Sent; open note; writer with To/CC/BCC, project, spots, attachments and "Also send as email" (a `mailto:` link to the people's profile emails) | `static/production_notes.js`, hooks in `static/world_walk.html` |
| Fonts: Caveat (handwriting) and EB Garamond, both SIL OFL, stored locally | `static/fonts/` |
| The message board hotspot used to return two made-up messages ("Stage Manager: Rehearsal at 3pm", "Welcome to PubCast AI v5.2"); it now returns none and the board's close-up holds the real notes | `modules/pubworld_hotspots.py`, `static/world_walk_live.js` |

## Tested (Linux, Python 3.13, Chromium headless)

- `tests/test_production_notes.py` — 9 passed: IDs, profile validation, who may add crew, password change, no access
  without signing in (the dev header is refused), send/read/save/trash, BCC privacy, `@production`, notes to self,
  replies, validation, attachments (stored, private, limits, nothing left behind on refusal), survives a new store.
- `tests/test_production_notes_browser.py` — 1 passed: `run_reach.py` with a fresh data folder, real login, three real
  notes; on the mirror; inside the mirror's surface; bubble offers to read; reading removes it from every spot; corkboard
  note opens the menu; grouping; writing one to yourself + CC with the email copy; Escape; no page errors.
- Regression (together): world map, placement, world.json, walker host integration, launch acceptance, studio progress,
  auth foundation, socket cookie auth, host control and host control end to end, saves survive restart:
  201 passed, 1 failed once (`test_bella_faux_pas_progress.py` restart test, under load); that file then passed alone
  and twice more together with the studio tests (26 passed, twice). Not a full-suite run.

## Not tested / not built

- Not built: replies by email coming back as sticky notes (needs a PubCast mailbox and its login); live push (notes
  refresh every 20 s and on every room change); the user menu Josie described on 2026-11-02 (see below); the
  "place sticky note" room-and-place picker and right-click; spots for the other places she listed; close-up pictures
  for the consoles (until they exist the console bubble is how you read a note there).
- Not tested: Windows / PowerShell 5, two machines over a network, phones, a real email program opening the link.
- Spot positions are by eye. Words that are mine, for Josie to change: "Production notes" on the corkboard note,
  "Read note: …", "Stick it", "Inbox / Saved / Sent", "By date / By project", "No project", the empty-state lines.

## Josie's next design (2026-11-02, not built)

A user menu (the user's own, not a cartridge): user ID, subscriptions, transactions, history, saves, help, contact,
review, Foresight; messages; a sticky notes section that lights up when something is new, with "Place sticky note":
pick a room (where you are highlighted), then a place in it (the hotspot spots), then write. Right-clicking an
interactable object or place also offers "Place sticky note". Places she listed: control room — audio mixer, video
mixer, Chyron/VTR machine; green room — TV, one of the two back doors; makeup mirror, typewriter, avatar maker,
clothing maker; Vortex bar counter; Sir Purfluous's office — back wall, door to his office; Palace hallway — gold
statue; "the lounge" — exit door or the bar in the middle; writers' room — a future screen monitor for meetings;
the 2.5D studio later.
