/* Optional local Foresight service overrides.
   Defaults:
   - PubPartner full-host status: same-origin Reach /api/pubpartner/status
   - Character bridge: same-origin /api/foresight/bridge; optional 8787 utilities remain behind Reach
   - 2i Writer's Room UI: same-origin Reach /writers-room
   Override only when deliberately hosting one of those services elsewhere. */
window.FORESIGHT_CONFIG = window.FORESIGHT_CONFIG || {};
