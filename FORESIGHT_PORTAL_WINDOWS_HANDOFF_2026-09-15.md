# Foresight Portal Windows — Handoff
Date: 2026-09-15

## Scope
This increment makes Foresight trays behave as portals rather than mutually exclusive pages.
It intentionally prioritizes function over final visual styling. Robot arms, wall claws, hanging wire,
and final quartz/ivory materials remain presentation work; the state/mechanics they will animate now exist.

## Pinned interaction rules
- Every room/program has an authored default position/size.
- Users can freely drag and resize every tray in Counter mode.
- Reset returns one tray to its authored default.
- Enter/fullscreen expands the same live tray; Return restores its prior Counter geometry.
- Enter/Return does not recreate or replace the iframe, so room/app state stays alive.
- Multiple portals remain mounted simultaneously. A user can keep PubWorld, Control Room, and a writers/chat meeting open together.
- Direct room/program opening is permanent and equal to immersive Map/Walk navigation. Walking is optional theater, not a work requirement.
- World Chat is a persistent singleton fan blade. Closing its window hides the surface; it does not destroy the conversation surface.
- `+ new chat` creates a separate chat conversation/tray/blade.
- In embedded General Chat, opening another archived conversation asks Foresight to open/focus a sibling tray rather than replacing the current conversation window.
- Window/tray state is stored in `foresight.counter.v2`; the v1 layout is read as a migration fallback.

## Current direct room list
Stage; 360° Panoramic; Control Room; Studio Control Room; Director Switcher; World; PubWorld Set;
Bar; Dressing Room; Waiting Room; Map / Walk; Teleprompter; Gallery; Analytics; Doctor; PubPartner Chat;
2i Writer's Room; PubPartner Status.

Future rooms (Monument, Parking Lot, Vortex Bar, Pit, Green Room, Fixed Set, Palace Theater, etc.) can be added
by adding one PROGRAMS registry entry when their actual room page/portal target exists. No new window manager is required.

## Service seam correction
The stale Foresight copy in the Sep-15 Main Event archive still pointed PubPartner at localhost:8001.
This increment restores the verified Sep-13 seam contract:
- PubPartner bridge: http://localhost:8787
- 2i Writer's Room bridge/root: http://localhost:8787
`static/foresight.config.js` remains the local override seam.

## Chat integration
- `static/general_chat.html?role=world` bootstraps/reopens the persistent `World Chat` conversation.
- `static/general_chat.html?conversation=<id>` opens a specific archived conversation.
- General Chat uses browser spellcheck/autocorrect UI while the conversation API still receives the exact final text the user submits.
- General Chat posts portal identity/new-chat/open-conversation events to Foresight when embedded; standalone behavior remains available.

## Verification performed
- JavaScript syntax: `node --check` passes for Foresight and General Chat inline scripts.
- All local iframe targets registered in Foresight exist in this build.
- Browser-isolated window-manager acceptance: 15/15 passed:
  World Chat autostart/blade, detached new chat, direct Control Room open, fullscreen enter/return,
  simultaneous tray retention, iframe browsing-context retention, drag, resize, reset, persistent World Chat close/reopen,
  and multi-portal layout persistence state.
- The execution environment blocks localhost/file navigation in the full browser, so live PubCast/8787 HTTP round-trip was not claimed from this environment.

## Files changed
- `static/foresight.html`
- `static/general_chat.html`
- `static/foresight.config.js` (safe empty/default override file)
