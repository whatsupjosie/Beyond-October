# Foresight Hardening — 2026-08-20

This pass intentionally did not replace or merge any existing subsystem. It hardened the current Foresight shell in place.

## Changes

- Fixed the lantern/blade initial-state behavior: the blade manager now starts closed, so the first lantern click opens it.
- Added `aria-expanded` state to the lantern control.
- Added explicit tray cleanup for status polling when a tray closes, instead of relying on the deprecated `DOMNodeRemoved` event.
- Made the status polling interval configurable through `CONFIG.pollMs`.
- Escaped all five HTML-significant characters in status-panel error text.
- Fixed the empty-counter hint so it reflects whether any tray is actually visible, including after restoring a saved layout containing only hidden trays.
- Clamped restored tray sizes to the current viewport.
- Added viewport-resize clamping so trays do not become stranded off-screen after a window resize.
- Prevented duplicate tray IDs after restoring saved trays and then opening new trays.
- Made the two cross-origin service URLs overridable through `window.FORESIGHT_CONFIG`, while preserving the existing localhost defaults.

## Verification

- Foresight embedded JavaScript: syntax check PASS (`node --check`).
- All 11 configured PubCast iframe target files exist in the bundle.
- No application subsystem was renamed, deleted, merged, or replaced.

## Not claimed

The original sandbox's live browser run is not reproduced by this offline ZIP inspection. In particular, the actual three-process browser integration still needs to be run in the environment where PubCast, PubPartner, and 2i are installed and running.

The ZIP does not include `node_modules`; a clean `npm install`/`npm ci` remains part of the live verification step.
