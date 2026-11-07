# The Dremel: sanding and grinding tool, with a bit kit

Status: **design proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are at the end.

## What it is

A digital rotary tool (think Dremel) with a kit of interchangeable bits. It removes material to sharpen or soften an angle, change how a surface projects or recedes, clean up a silhouette, or reach into deep recesses. It works on raw voxel blocks, on Filler Cream, or on both together, the way a real sander cuts filler and wood alike.

Finishing order: **carve** (voxel blueprint) → **cream** (fill flush) → **Dremel** (grind and sand) → **paint and polish**.

## Rules (same spirit as Filler Cream)

1. **The blueprint is never edited.** Grinding is saved as its own layer of strokes, kept apart from the blocks. Remove any stroke, or all of them, and the original is back exactly.
2. **Tape protects.** Masking tape (marks) blocks the Dremel the same way it blocks cream: a taped nail edge, lip line or door moulding can't be ground unless the user lifts the tape.
3. **Never breaks through by accident.** Grinding stops at a minimum wall thickness above the hollow inside of the shell. Cutting a real opening (a nostril, a keyhole) is carving, a deliberate separate action, not sanding.
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
- Each column's surface is lowered to where the swept shape cuts it, but never below the depth stop, the angle-guide plane, or the minimum wall thickness, and never inside taped parts.
- **Reach:** a bit can only go as deep as its shaft clears. If the rim around the hole is narrower than the shaft, the cut stops at the depth where the shaft would touch the rim. Long-reach bits have slim shafts, so they get deeper.
- The Dremel layer is a list of strokes; the result is recomputed from the original blocks plus cream plus strokes. Deterministic, removable, and stale-aware, like cream layers.
- Works **without cream** too: grinding raw blocks cuts into them directly (the cut block is re-meshed as columns at bake).

## How it works on meshes (phase 2)

Two kinds of mesh:
1. **Meshes made from voxels plus cream** (the finished smooth surface from the single-volume plan). The Dremel cuts the volume, and the mesh is re-extracted. Nothing extra is needed: voxel and mesh stay one system.
2. **Imported meshes** (a GLB avatar, a scanned prop). The bit's solid shape pushes surface points inward wherever it overlaps them, with local remeshing so the surface doesn't tear or fold. This is the harder part, which is why it comes second.

## Build order

1. Voxel phase: square, ball, cone and needle bits; grit; depth stop; tape; minimum wall; strokes as a reversible layer; tests (taped edge untouched, never breaks through, removing strokes restores the original, reach stops at a narrow rim).
2. Angle guide, barrel, bullnose and long-reach bits.
3. Cutting the single volume and re-extracting the mesh (needs the smooth-surface plan from the Filler Cream handoff).
4. Imported meshes.

## Decisions for Josie

1. **Name:** "the Dremel" as the working name? It's a brand name; for a shipped product you may want your own ("the Rotary", "the Grinder", something in PubCast's voice).
2. **Passes:** should passes deepen with each stroke, like real sanding, or should each stroke cut only to its depth stop or guide plane, so going over the same spot twice does nothing extra? Real feel versus safety.
3. **Minimum wall thickness:** a fixed value (for example 1/64 block) or set per part?
4. **Tape:** does one tape protect from both cream and the Dremel, or should there be separate tapes?
5. **Bit kit:** anything missing from the list? Some real-world bits that could come later: wire brush (texture), engraving cutter, polishing felt (gloss).
