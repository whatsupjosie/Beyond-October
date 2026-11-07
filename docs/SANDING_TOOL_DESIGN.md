# The Dremel: sanding and grinding tool, with a bit kit

Status: **design proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are at the end.

## What it is

A digital rotary tool (think Dremel) with a kit of interchangeable bits. It removes material to sharpen or soften an angle, change how a surface projects or recedes, clean up a silhouette, or reach into deep recesses. It works on raw voxel blocks, on Filler Cream, or on both together, the way a real sander cuts filler and wood alike.

Finishing order: **carve** (voxel blueprint) → **cream** (fill flush) → **Dremel** (grind and sand) → **paint and polish**.

## Layer stack (Josie, 2026-11-06)

- **Base architecture:** the pure, unedited voxel blueprint. It is never changed by finishing tools.
- **Customization layers on top:** cream, Dremel strokes, and solid decorations (an engraved emblem, a carved pattern, a raised crest), built in real 3D geometry rather than painted on.
- **Per instance:** one base design can be used many times. Most copies stay plain; a specific one gets its own customization layers (one box out of a hundred with an emblem cut into its lid). Customizations belong to the instance, not the shared base.
- **Paint** sits above all of it.

Order on bake: base → cream → Dremel strokes and decorations → paint. Every layer can be switched off, removed or regenerated without touching the base.

## Rules (same spirit as Filler Cream)

1. **The base is never edited.** Grinding is saved as its own layer of strokes on the instance, kept apart from the base blocks. Remove any stroke, or all of them, and the plain base is back exactly.
2. **Tape protects.** Masking tape (marks) blocks the Dremel the same way it blocks cream: a taped nail edge, lip line or door moulding can't be ground unless the user lifts the tape.
3. **Reshapes past the blueprint, stays closed.** The Dremel may cut as deep into the design as the artist wants: reshaping a nose, slimming a jaw, deepening an eye socket. Surface pieces are hollow shells, so when a cut goes deeper than the shell, the inside is treated as solid while carving and a new wall forms behind the cut. The object never ends up with an accidental hole. Cutting a real opening (a nostril, a keyhole) is a deliberate separate action.
4. **Local.** A bit only touches what it physically reaches.
5. **Real units.** Every bit size is in mm or inches, tied to the 10 in PubBlock (1/64 block is about 4 mm).

## The bit kit

Each bit has a **tip shape**, a **size**, and a **reach** (how far it can go down into a recess before its shaft hits the rim).

| Bit | Tip | Use |
|---|---|---|
| **Square / flat** | flat face, crisp corners | flatten a surface, square off an edge, floors and tiles |
| **Barrel / drum** | cylinder side | long, even passes along a contour (jawline, arm, door frame) |
| **Ball** | sphere | rounded hollows: eye sockets, the dip above the lip, scooped details |
| **Bullnose** | flat face with rounded edge | soften an edge without losing a flat (cheekbone plane, table edge) |
| **Cone / flame** | tapered point | creases and corners: nostril wings, the corner of the eye, grout lines |
| **Needle** | very narrow cylinder | fine lines and tight spots: nail edges, eyelid crease, engraving |
| **Long reach** (extension on any bit) | any tip on a long slim shaft | deep recesses: inside a nostril, between fingers, under a jaw, inside a cup |

Sizes: from 1/64 block (about 4 mm) up to a full block (254 mm), with named presets (fine, medium, broad) and a slider between them. The needle and cone bits default to the smallest sizes.

## Controls

- **Grit:** coarse, medium, fine, polish. How much each pass removes, from about 1/64 block (coarse) down to a fraction of that (polish). Many light passes give control, just like the real thing.
- **Speed / pressure:** pen pressure on a tablet drives depth per pass (or bit size; the user's choice).
- **Angle guide:** the purpose you named, increasing or decreasing a surface's angle of attack or retreat. Set an angle (or pick a plane by clicking two points), and the Dremel cuts down to that plane and no further within the stroke. It's the safest way to get exactly the slope you want.
- **Depth stop:** a maximum depth for the stroke, measured from the surface as it was before the stroke.
- **Follow the surface vs. hold the plane:** a stroke either rides the current contour (smoothing) or holds a fixed height or plane (flattening, chamfers).
- **Symmetry, ghost preview, before/after, named history:** shared with the cream applicator, so both tools feel like one bench.

## How it works on voxels (phase 1, voxel-only)

- The same column layout Filler Cream uses: one face direction at a time; each column has a surface height (block plus any cream).
- A bit placed at a point is a **solid shape** (flat-bottomed box, sphere, cylinder, cone) at that position and depth. A stroke is that shape swept along the path.
- Each column's surface is lowered to where the swept shape cuts it, but never below the depth stop or the angle-guide plane, and never inside taped parts. Cuts may go below the blueprint surface and past the shell; the interior counts as solid while carving and the wall re-forms behind the cut.
- **Reach:** a bit can only go as deep as its shaft clears. If the rim around the hole is narrower than the shaft, the cut stops at the depth where the shaft would touch the rim. Long-reach bits have slim shafts, so they get deeper.
- The Dremel layer is a list of strokes; the result is recomputed from the original blocks plus cream plus strokes. Deterministic, removable, and stale-aware, like cream layers.
- Works **without cream** too: grinding raw blocks cuts into them directly (the cut block is re-meshed as columns at bake).

## How it works on meshes (phase 2)

Two kinds of mesh:
1. **Meshes made from voxels plus cream** (the finished smooth surface from the single-volume plan). The Dremel cuts the volume, and the mesh is re-extracted. Nothing extra is needed: voxel and mesh stay one system.
2. **Imported meshes** (a GLB avatar, a scanned prop). The bit's solid shape pushes surface points inward wherever it overlaps them, with local remeshing so the surface doesn't tear or fold. This is the harder part, which is why it comes second.

## Build order

1. Voxel phase: square, ball, cone and needle bits; grit; depth stop; tape; cutting past the blueprint with the wall re-forming; strokes as a reversible layer; tests (reshaping a nose fixture past its blueprint, taped edge untouched, no accidental holes, removing strokes restores the original, reach stops at a narrow rim).
2. Angle guide, barrel, bullnose and long-reach bits.
3. Cutting the single volume and re-extracting the mesh (needs the smooth-surface plan from the Filler Cream handoff).
4. Imported meshes.

## Decisions for Josie

1. **Name:** "the Dremel" as the working name? It's a brand name; for a shipped product you may want your own ("the Rotary", "the Grinder", something in PubCast's voice).
2. **Passes:** should passes deepen with each stroke, like real sanding, or should each stroke cut only to its depth stop or guide plane, so going over the same spot twice does nothing extra? Real feel versus safety.
3. **Decided:** the base stays pure; reshaping and decoration are layers on the instance (no "Make permanent").
6. **Building up:** the Dremel only removes, and cream only fills up to the blueprint's surface. If a nose is too *small*, neither can make it bigger. Should cream get a "build up" mode (putty that can go past the blueprint), or should that be done by adding blocks?
4. **Tape:** does one tape protect from both cream and the Dremel, or should there be separate tapes?
5. **Stamps:** should an emblem or pattern be a reusable stamp (draw or import it once, then engrave it into, or raise it from, any surface at any size)? Raised designs need the build-up question (6) answered.
7. **Bit kit:** anything missing from the list? Some real-world bits that could come later: wire brush (texture), engraving cutter, polishing felt (gloss).
