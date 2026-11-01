# Host control of characters ("like The Sims"): spec and map to existing code, 2026-10-29, Claude

Status: the server half and the walker panel are built and tested; see `HOST_CONTROL_SERVER_2026-10-29.md` for what is done and not. This file keeps the spec and Josie's words.

## Josie's words, 2026-10-29, exactly as she gave them (not edited)

> I guess it should work like The Sims there's our characters on screen you can as the host as the owner rather as the owner you can select them you can select their Avatar and you know a little group of options is listed you know you know I am you can I am them you can track them you know so like you could put a tracker on them meaning that you'll see everywhere they go and you'll automatically record specifically every interaction that they have so any conversation that they are party to you know you you'll be recording that automatically like somewhere in an MD file or whatever it doesn't have to be like full a video or audio but a record of it'll be kept just the point or you can open their profile and their profile have you know their name their you know just like their brief history you know who they are you know what they do what they're like how they behaved it previous sessions if this isn't their first whether or not there's a disciplinary record with them privileges and authorities that you can grant or revoke. And of course, you know, under a separate tab of security, you know, just like, you know, a possession button where you can take control of them and automatically a background message is sent to them and only to them in private IM. Just like, just to let you know, you know, the host has found it necessary to take control of your avatar. You can speak to them momentarily about why this was necessary. I apologize for the intrusion. And hope to resolve this situation very quickly.

## What it asks for, in the order she said it

1. Characters are on screen. The owner (host) can select one.
2. Selecting one lists a few options, including "I am them".
3. Tracker: the owner sees everywhere they go, and every interaction they are party to is recorded automatically as a text record (an MD file or similar). Not video or audio.
4. Profile: name, brief history, who they are, what they do, what they are like, how they behaved in earlier sessions, whether there is a disciplinary record, and privileges and authorities the owner can grant or revoke.
5. A Security tab with a Possession button. Pressing it takes control of the avatar and automatically sends that person, and only that person, a private IM. The message is the last sentences of her passage above. The exact wording to send is for Josie to confirm; it must not be reworded by anyone else.

## What already exists (read, not run)

- `modules/governance.py` and `modules/governance_routes.py` (`/api/governance/...`): bans, mute, kick, consent records including recording consent, a waiting room with approve and deny, and a tamper-evident audit log. Actions need `require_role("mod")`.
- Avatar freeze is already there: `POST /api/governance/freeze` and `/unfreeze`. A `FreezeState` records who froze whom, when, why, and an optional `pose_override`. It supports a duration with automatic release, and broadcasts `avatar_frozen` to everyone. Its own description is "the host controls their movement".
- `modules/governance_waiting_room.py` and `modules/sir_purfluous_waiting_room.py`: entry requests and approval.
- `modules/blackbox_*.py`: the Black Box recorder, with its own operator boundary.
- `modules/pubworld*.py` and the walker's live link (`static/world_walk_live.js`): rooms, presence, hotspots.

## What looks missing (check before building)

- A host panel where characters are on screen and selectable, with an options list.
- Possession as such: freeze stops them, it does not hand the owner their avatar. It also sends no private message that I could find; it broadcasts `avatar_frozen` to everyone.
- The automatic private IM to only the possessed person.
- The tracker: a per-person running text record of where they went and every conversation they were in.
- The profile: history, behaviour in earlier sessions, disciplinary record, and grantable and revocable privileges. Bans and consent records exist, but I found no profile or privilege store.
- The walker does not show other people. The host does not broadcast presence between walkers yet (see `handoffs/SAVING_2026-10-28.md`, Untested).

## Suggested build order (each step stands alone and can be tested)

1. Possession on top of freeze: same permission check and audit entry, plus the one private message, sent to that person only, and a release path. This is the smallest piece and the most sensitive, so it goes first with tests that prove nobody else receives the message.
2. The per-person interaction record: an append-only text file per person, written by the code that already carries conversations, under `data/`, never in a public artifact.
3. The profile store and the grant and revoke of privileges, with every change written to the existing audit log.
4. The host panel in the walker: select a character, options list, profile tab, security tab.
5. Presence between walkers, so there are other characters on screen to select.

## Questions only Josie can answer

- The exact possession message, and whether there is a matching "control returned" message.
- Which privileges exist, and what each one allows.
- Who besides the owner may possess (a moderator, the AI manager), and whether the owner can see who did.
- Whether a tracked person is told they are tracked. Her earlier entry rule has them sign a waiver that already consents to recording; confirm this covers the tracker.
- How long the record is kept and who can read it.

## Addition, 2026-10-29 20:24, Josie's words exactly as she gave them (not edited)

> You should probably be able to see the complexity of their avatar, their refresh rate, their connection speed, and any other statistics or resources that they're using. You should be able to see their title and position, and you should be able to change their title and position. Not their name, but their title and position. And of course, you could give them gifts. You know, like access to the control room, which is going to be locked most of the time. But to certain people will be unlocked for, you know, access. Or avatar accessory gifts, I don't know, something like that.

### What it adds

6. Resource view on the profile: avatar complexity, refresh rate, connection speed, and other statistics or resources they are using.
7. Title and position: shown, and changeable by the owner. Never the name.
8. Gifts: access to the control room (locked by default, unlocked for certain people), and avatar accessories.

### How it fits

- Control room access is a privilege in the same store as the other grantable and revocable privileges (step 3 of the build order). The walker's control room consoles are still marked "not wired yet", so the lock has nothing to guard until Josie decides what they do.
- Avatar accessories belong with the avatar library and PubPartner's Wardrobe, where an avatar is already chosen per character. A gift would be an entry the person is allowed to wear, recorded in their profile.
- Title and position are plain profile fields. Name is read-only. Each change goes to the existing audit log.
- Statistics: connection speed and delay can be measured by the host from the socket it already holds. Refresh rate and avatar complexity (polygon count, bone count) can only be reported by the person's own browser, so treat them as reported, not proven.

### More questions only Josie can answer

- Which titles and positions exist, or are they free text?
- Does the person see a gift as a message, and can they decline or return it?
- Can a gift be taken back? (The revoke in item 4 suggests yes.)
- Should the resource numbers be visible only to the owner, or also to the person themselves?

## Addition, 2026-10-29 20:27, Josie's words exactly as she gave them (not edited)

> You should be able to get into an open voice chat with them, or the private one-on-one IM chat. You should be able to have a button that can eject them into the waiting room, or boot them from the server. And if you boot them from the server, then an option to permanently ban pops up. And, yeah, just because you boot them from one event doesn't mean you need to permanently ban them, but maybe. And, that doesn't mean their profile disappears from the records. Yet, I mean, you're actually going to maintain a banned list, so you have the option to unban somebody. And also find somebody who was banned and, you know, is maybe operating under a slightly different name or an alias or whatever.

### What it adds

9. From a person's panel: join an open voice chat with them, or the private one-on-one IM.
10. Two buttons: eject them into the waiting room, or boot them from the server.
11. Booting offers "permanently ban". A boot alone is not a ban.
12. A ban never deletes the profile or its record.
13. A banned list the owner can read, with unban.
14. Find someone who was banned and is back under a slightly different name or an alias.

### How it fits (read, not run)

- Boot is the existing `POST /api/governance/kick`. Ban and unban exist as `/ban` and `/unban`, with ban types temporary, permanent and session, and a reason. `is_banned` exists. Consent records and a ban record already keep an `ip_hash` field.
- The waiting room exists for entry (`modules/governance_waiting_room.py`). Ejecting someone already inside into it is new; it is the same room your 2026-10-27 entry design uses as a timeout and detention space.
- The private one-on-one IM is what the possession message (item 5) will also use, so build it once.
- Voice: I found WebRTC code only in the voxel and Pete modules (`modules/voxel_webrtc_bridge.py`, `modules/pete_enhanced.py`) and a microphone picker. I did not find a voice chat between people that the host can join. Treat voice as not built.
- Banned list: individual bans exist; a listing screen and keeping the profile after a ban need to be checked and built.
- Alias matching: I found no code for it. The only signal stored today is the hashed network address.

### Care needed on alias matching

Matching by name similarity, avatar, writing style or network address will produce false matches. An address is shared by households, cafes and shelters, and a name can be close to a stranger's. So the design should show the owner a ranked list of possible matches with the reasons, never ban or block automatically, and write every decision to the audit log. Which signals to use is for Josie to decide.

### More questions only Josie can answer

- Is the boot reason required? Does the person see it?
- Does a temporary ban have a time the owner picks?
- Which signals may be used for alias matching (name, avatar, device, address, writing)? Who can run a search?
- Is voice always on the open channel, or can the owner whisper to one person?

## Correction, 2026-10-29 20:29, Josie's words exactly as she gave them (not edited)

> Oh, yeah, I think, you need to be able to, I think I may have said boot when I meant, you know, put on timeout, you know, eject to the waiting room, you know, and that would automatically teleport them to the disciplinary side of the waiting room where it's, you know, somebody's put there because, you know, just like, I don't know what's going on with you, but it can't continue. Are you glitching? Is there an issue? Or are you, if you're doing this on purpose, it's not fucking okay.

### How this is read (Josie to confirm)

- Timeout is the button: it ejects the person into the waiting room and automatically teleports them to the disciplinary side of it. This is the detention side of your 2026-10-27 entry design, where everything said or thought is recorded because the waiver is already signed.
- The passage from "I don't know what's going on with you" to the end reads as what is said to the person there. Treat it as a message she has not yet approved for sending; it must be used exactly as written or not at all, and not softened or shortened by anyone else. It contains strong language, and whether it is sent as is, or as a gentler first message with this one held back, is her decision.
- Not settled: whether a separate "boot from the server" button (item 10) and the "permanently ban" offer (item 11) still exist as well, or whether the ban offer now follows a timeout. Left as written in items 10 and 11 until she says.

### Question only Josie can answer

- Is the timeout message the first thing the person sees on arrival, or is it sent by the owner in the private IM once they are there? Does it show before the owner has said anything themselves?

## Program design (Claude's proposal from reading the code, not Josie's words; Josie to approve or change)

One principle: every host action goes through a single dispatcher on the server. The panel never changes anything itself. The dispatcher checks the role (`require_role`), calls the governance engine, writes the audit entry, then sends events: a private one to the target, and a roster update to the host.

### Pieces, with where they attach

1. Roster (everything else needs it). Today the walker tells the host only its room, once per room change (`enterView` in `static/world_walk_live.js`, message `room_change`). Add to the walker's socket messages: `pos` (view and feet position, about four a second while moving), `char`, and `stats` every five seconds (frames per second, polygon and bone count of the loaded avatar). The host keeps a roster per signed-in person in the pubworld hub and sends changes to the owner's page. Connection delay is measured by the host from ping and pong, not reported by the person.
2. Private message primitive. One function, `send_private(user_id, text)`, that reaches only that person, using the DM and conversation code that already exists. The possession notice, timeout notice and gift notice all use it.
3. Possession. Extend `FreezeState` in `modules/governance.py` with `controlled_by` and a mode ("freeze" or "possession"), plus an expiry. The owner's page shows the target's room. Clicks on the owner's page go to the target's walker as `drive` commands, which sets its `S.target`. The target's own input is off, its screen shows a banner, and everyone else sees the avatar marked as host-controlled. Release always works, and the expiry releases it automatically (the existing freeze route already has a timed release to copy).
4. Timeout. The dispatcher sends `teleport` to the detention room, sets the recording flag for that room, starts a countdown and shows it to both sides. On the walker, the target can only move inside that room until released.
5. Person record. One JSON file per person under `data/`, written the way `modules/studio_progress.py` writes (temp file, then replace, with a revision): name (read-only), title, position, notes, history, privileges (control room, gifts), discipline entries, and the tracked flag. Every edit goes through one function that also writes the audit entry, so nothing changes without a trail.
6. Tracker log. An append-only text file per tracked person per day, `data/people_log/<user_id>/<date>.md`, written by one function `log_event(user_id, kind, text, with=[...])`. Called from room changes, chat and DM messages, hotspot use, voice start and stop (only the fact and the length), and every host action on that person. Capped in size, rotated by day.
7. Panel. Owner only, in the walker: the roster as portraits like The Sims, click one for the menu (I am them, Profile, Track, Private IM, Voice, Timeout, Boot, Gift), then the tabs Profile, Stats, Security. Hidden from everyone else, and every button is also checked on the server.

### Build order (changed from the first list, because nothing can be selected without a roster)

1. Roster with position and stats.
2. Private message primitive.
3. Possession and release.
4. Timeout and the detention teleport.
5. Person record, then the tracker log.
6. Panel, built last on top of the pieces that already work and are tested.

### How each step is tested

Server tests with the test client and a fake hub. One browser test with two separate sign-ins: the private message arrives only in the target's page, possession moves only the target, release returns control, and a person without the role gets refused on the server even if the panel is forced open.
