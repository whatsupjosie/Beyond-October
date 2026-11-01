# Foresight — tonight's working milestone

This is real and verified, not a mockup. I booted all three of your services in a
sandbox tonight, deployed this shell into the live PubCast tree, and drove it with an
actual browser — opening real trays, dragging them, watching live status data update
over time. Screenshots of that run are in this conversation if you want to see them
again.

## What's actually working

- **A real tray engine**: drag, resize, z-order, open, hide, close (with the
  card-fall close animation), all built on top of the physics already proven in
  `foresight_ui_v18`.
- **Real portals into PubCast**: Stage, 360° Panoramic, Control Room, Director
  Switcher, World, Dressing Room, Teleprompter, Map, Gallery, Analytics, Doctor —
  eleven of your real rooms, each one a genuine `<iframe>` onto the actual running
  page, not a stand-in.
- **Real live status trays for PubPartner and 2i.** Neither of those two has a
  front-end page in your bundle — they're API-only — so rather than fake up an
  editor UI that doesn't exist yet, I built honest live status panels that poll
  their real `/health` endpoints every 4 seconds and show real fields (role, node
  ID, uptime, message count, etc).
- **The blank-blade picker**: click the lantern, click the blank blade, pick a
  program, it opens as a labeled tray, a fresh blank blade appears behind it — per
  your spec's blade lifecycle.
- **Layout persistence**: tray positions/sizes/open-state save to localStorage and
  restore on reload.

## One real bug I found and fixed in PubPartner itself

`pubpartner_federation/service.py` had no CORS headers, so a browser-side page on a
different port (Foresight, served from PubCast on :8000) was blocked from fetching
its `/health` endpoint — this is a real browser security restriction, not something
I could fake around. I added a proper `CORSMiddleware` block scoped to local dev
origins. That file is included here (`service.py`) — replace your copy with it, or
diff it in. Nothing else in that file was touched.

## How to run it yourself

Three processes, three terminals, from your project root:

```bash
# 1. PubCast (FastAPI) — port 8000
cd pubcast
pip install -r requirements.txt
python3 main.py

# 2. PubPartner federation (FastAPI) — port 8001
cd pubpartner
pip install -e .
PP_PORT=8001 PP_ROLE=resident python3 -m pubpartner_federation.service

# 3. 2i backend (Express) — port 8787
cd 2i-backend
npm install
node server.js
```

Then:

1. Drop `foresight.html` into `pubcast/static/foresight.html`.
2. Replace `pubpartner/pubpartner_federation/service.py` with the patched copy here.
3. Open **http://localhost:8000/static/foresight.html**.

If your ports differ, edit the `CONFIG` block at the top of `foresight.html`'s
`<script>` — it's the only place ports are hardcoded.

## What's deliberately NOT in this pass

Being upfront about scope, per your own "no placeholders" rule — I didn't fake any
of this, I just didn't build it yet:

- **Visual ornamentation** — the two-layer safe-rect/frame split, outward-only
  bulge constraint, vessel silhouettes, single global light-angle variable, and the
  full Neo Art Deco Nouveau material treatment. Trays are functional rounded
  rectangles right now, styled in your existing dark-gold palette, not yet shaped
  objects with drop-shadow silhouettes.
- **The Sprite** — no lantern presence, no voice, no pointing/guidance behavior yet.
- **The multi-countertop carousel** — everything lives on one countertop tonight.
- **The Chat Slot** — there's no Foresight assistant wired up yet, so I didn't
  build a chat box that talks to nothing. Real feature, not started.
- **Document viewers** (md/html/xml/PDF) and **3D viewers** (GLB/OBJ/FBX) — not
  started. These are genuinely straightforward to add as new portal kinds once you
  want them (browser-native for text/PDF, three.js loaders for the 3D formats).
- **Google Docs** — will need real Drive API + OAuth wiring, not a quick add.
- **Native `.blend` files** — can't be rendered in a browser directly; the real
  path is a server-side Blender export step to glTF/GLB first. Flagging this now
  so it's not a surprise later.

## Files in this delivery

- `foresight.html` — the shell itself.
- `service.py` — PubPartner's federation service with the CORS fix applied.
- `RUN_GUIDE.md` — this file.
