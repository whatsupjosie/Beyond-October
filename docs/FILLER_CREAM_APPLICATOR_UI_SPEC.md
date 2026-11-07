# Filler Cream applicator — UI design proposal

Status: **proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are listed at the end.

## Where it is used

One applicator and one engine, used in two places:

- **Primp** (makeup app, part of PubCast): shaping avatar faces and bodies, such as cheekbones, jawlines, lips, eyelids and nails, so digital performers can get the look a role needs.
- **Set building and art design**: doors, windows, frames, tile floors, ballroom floors, trees, glass and ice sculptures, props.

Same tools and the same rules everywhere. Only the starting presets differ.

## The finishing bench: four tools, same as a woodworker

| Tool | What it does | Analogy |
|---|---|---|
| **Cream** | Fills low spots flush with the surface the blocks define | wood filler wiped flush |
| **Wipe** | Removes cream from an area (blocks are never touched) | wiping excess off |
| **Tape** | Protects a designed edge, dip or opening from cream | masking tape |
| **Sand** *(later)* | Removes material to sharpen or soften an angle | light sanding |

Paint and polish come after, in Primp's makeup tools and the set materials. Every action is reversible and kept in a named history.

## The brush

- **A ring on the surface**, sized in real units (mm or inches, the user's choice), shown live on the model.
- **A detail dial right beside it**: five named stops with plain examples, not jargon. Very fine (lips, nail edges) · fine (nose, eyes, fingers) · medium (cheeks, jaw, knees) · broad (belly, back) · very broad (floors, walls). A slider between stops for fine control.
- **Eyedropper**: hold a key and click a surface to pick up its detail setting.
- **Pen pressure** (tablets): drives size or detail, the user's choice.

## Tape (marks), the sculptor's control

- **Tape a line**: paint along an edge to keep it sharp (eye corner, lip line, nail edge, a door frame's moulding profile). It snaps to block edges, since that's where designed edges live.
- **Name a region**: paint regions as parts (skin, nail, lip, brow; glass, frame, grout) shown as soft colour overlays. Cream never crosses between differently named parts.
- **Protect a hole**: click a mouth, a nostril, a keyhole or a window opening to mark it as an opening.
- **Suggestions, never automatic**: the tool can highlight sharp creases it thinks might be designed. The sculptor confirms or ignores each one; the blueprint stays the authority.

## Selecting what to work on

Click one face · double-click a whole block · brush · grow or shrink to connected pieces · lasso · select a named part ("all nail").

## Seeing the work

- **Ghost preview**: while dragging, cream shows as a translucent gold ghost at lower detail, so it stays fast. It settles to full detail on release. Big areas, like a 20 ft floor, run in the background with a progress bar.
- **Three looks, one click each**: raw blocks · smooth neutral material (the honest check: do the shapes work before paint helps?) · painted.
- **Camera presets**: front, three-quarter and profile at the intended viewing distance.
- **Overlays**: cream on/off, before/after split, detail heat map, tape and part view.
- **Symmetry**: mirror (faces, bodies, doors) and radial (vases, ice sculptures, columns).

## Two modes

- **Quick**: pick a preset, brush, done. For makeup users and set dressers.
- **Studio**: every dial, tape and overlay exposed. For the true sculptor.

## Starting presets

| Preset | Detail | Tape / parts | Notes |
|---|---|---|---|
| Face skin | fine | eyes, mouth, nostrils taped as openings | lips "very fine" |
| Acrylic nail | very fine | nail, cuticle and skin as separate parts | length and shape are geometry; thickness at 1/64 (4 mm) only as stylised geometry, otherwise paint |
| Body | broad | joints medium | kneecap and waist from the blueprint |
| Ballroom / stage floor | very broad | level lock | fills cracks level, nothing else |
| Tile floor | medium | grout lines taped from the tile pattern automatically | cream smooths each tile, never fills the grout |
| Door / window | medium | frame profiles taped | openings protected |
| Glass / ice sculpture | fine | facet edges taped where wanted | transparency is material, not cream |
| Tree trunk | broad | bark grooves can be taped | leaves and grass are materials and scatter, not cream |

## Honest limits that shape the UI

- **Eyeshadow is paint.** Grass blades and leaves are materials and scatter. Cream shapes surfaces; it doesn't do colour or tiny strands.
- **Speed:** full-detail cream is too slow to run live under the brush today (measured: 8–23 s on a face-sized patch). The ghost preview is the plan, and the engine needs the array-math speed-up before a live brush feels right.
- **Engine additions needed:** Wipe (a mask on a layer), the Flow setting if chosen, tape lines (barrier marks along edges), symmetry, and the background job for big areas. The engine already has selections, parts, keep tags, barriers, detail and layers.

## Decisions for Josie

1. **Flow:** should cream always go fully flush in one pass, or allow thin coats (never past flush, never building up)?
2. **Crease suggestions:** on by default, off by default, or Studio mode only?
3. **Where it lives:** the Avatar Foundry in the dressing room for Primp. Where for set building?
4. **Units shown:** mm, inches, or the user's choice?
5. **Pen pressure:** drives size, detail, or the user's choice?
6. **Names:** "Cream / Wipe / Tape / Sand" and "Quick / Studio" are working names. Yours to change.
