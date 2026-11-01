---
name: "hyperreal-webgl-rendering"
description: "Use when raising image quality in WebGL2 or canvas UI: metal, glass, stone, shadows, weight and depth, tone mapping, bloom, anti-aliasing. Techniques are labeled by how well each was verified."
---

# Hyper-real WebGL2 rendering for tray-style UI

Built from a five-thread research pass (Oct 13, 2026) for the Foresight trays. Scene model: flat polygon trays extruded with vertical walls, camera straight down, one key light, live HTML screens, a bench surface below. Target: 60 fps on an integrated laptop GPU, minimal downloads (she has severe bandwidth limits).

## Honesty rule for this skill

Most of this was written from memory of standard references, not from pages that were opened. Labels:
- [verified]: a researcher read the source. Use as stated.
- [recalled]: the source exists but the detail is from memory. Check constants and code against the source before shipping.
- [derived]: our own math or judgment for this scene. Validate visually or against a brute-force reference.
- [estimate]: arithmetic only. Nothing has been timed on any GPU. Measure.
Never present a recalled constant as confirmed. Copy exact constants (PBR Neutral curve, metal reflectance table, specular-AA constants, Quilez umbra variant) from the source.

## Pipeline fixes first (cheapest, most certain)

Problem [derived]: tone mapping (ACES) and gamma inside each tray shader, then blending into 8-bit, mixes curved signals. Result: muddy glass edges, glows that clip per object, no values above 1.0, compounding contrast.

1. Composite in linear light into a float target: R11F_G11F_B10F (4 bytes per pixel, enough for an opaque bench) or RGBA16F. EXT_color_buffer_float is on 99.95% of WebGL2 browsers [verified]. Test framebuffer status and a blend readback at startup [recalled].
2. One final pass: exposure, then Khronos PBR Neutral tone map, then exact piecewise sRGB, then triangular dither. Context: alpha false, antialias false, depth false, stencil false, powerPreference high-performance [verified]. PBR Neutral keeps gold, jewel tones and white marble true; ACES shifts hues [verified]. Take the curve constants from the Khronos ToneMapping repo.
3. Edges: native resolution with analytic coverage from the signed distance divided by its screen-space rate of change, ramped over about 1.2 px (0.5 blocky, 2.0 blurry) [verified]. Drop 2x supersampling (about 4x less pixel work). Keep 2x only for screenshot mode.
4. Dither: triangular noise from a hashed pixel coordinate, fade near pure black and white [verified].
5. Skip MSAA (useless for SDF edges), TAA (ghosts on moving UI), and WebGPU (no quality gain here) [derived].

## Bloom and backlight

Jimenez bloom [verified]: downsample pyramid with 1/(1+luma) weighting on the first step, 3x3 tent upsample, no threshold, bloom mixed at about 0.04. Author the selected tray's backlight as HDR emission above 1.0 and let bloom produce the glow, replacing analytic halos. Also add the emission as light onto the bench and neighbors [derived].

## Metal and gloss

- Metal looks like what it reflects. Build a photographer's studio as a procedural environment, generated on the GPU at startup (zero download) [derived]: near-black room (0.01 to 0.03), key strip 20 to 50x brighter (aspect 1:3 to 1:6, soft edge 5 to 10% of width), cooler kicker strip at 0.3 to 0.6x, overhead gradient scrim, explicit black bands between lights, dim floor bounce.
- Geometry rule for a straight-down camera: a rim facet tilted by angle theta reflects the direction 2*theta from vertical. Place strips at about 35 to 55 degrees to land on rim shoulders [derived].
- Lighting: split-sum IBL (prefiltered mips by roughness plus a small DFG table, or Karis's analytic fit) and nine-coefficient diffuse [recalled]. About 1 MB video memory; re-prefilter estimated about 1 ms on Iris Xe-class [estimate].
- Energy compensation (Filament one-liner) so rough and satin gold, brass, bronze are not grey [recalled].
- Measured metal reflectance (linear): gold 1.000, 0.782, 0.344; silver 0.972, 0.960, 0.915; copper 0.955, 0.638, 0.538; brass 0.910, 0.778, 0.423 [recalled, spot-check every row]. No measured data for rose gold, bronze, champagne: tune by eye.
- F82 edge tint (Hoffman) gives gold and copper colored edges [recalled].
- Brushing: take the tangent from the 2D distance-field gradient and use anisotropic GGX with bent reflection vector [recalled, derived].
- Rim profile: swept 2D profile along the distance field. Seen from above it is a height field, so no ray marching; analytic normals. Bead, cove, bead gives the multi-line highlight of a moulded frame [derived]. Do not paint bright top edges or dark bottom lines as layers; they fall out of correct normals and contradict the light when it moves.
- Specular anti-aliasing from the analytic profile curvature so thin highlights hold still when trays move [derived; constants disagree between sources, verify].
- Clear coat (second lobe, 4%, dims the base) is the biggest single win for marble, varnished wood and lacquer [recalled].
- Optional: LTC area lights for razor strips (about 64 KB tables, the only download in the plan) [recalled]. Karis representative-point is a no-table fallback.

## Weight and depth

- Vertical walls mean the exact 3D distance equals the 2D polygon distance below rim height [derived]. So soft shadows are a short 2D march (8 to 16 steps): keep min of k*h/t. Contact-hardening comes free: sharp at the wall base, soft at the tip [recalled Quilez, derived].
- Wall occlusion: 0.5*(1 - x/sqrt(x^2 + H^2)) at distance x from a wall of height H. 0.5 at the base, 0.146 at one rim height, 0.026 at three. Skirt width scales with rim height. Two nearby trays add their terms. Validate once against brute-force integration [derived].
- Sum lights, do not stack darkening layers: color = albedo * (key * keyVisibility * N.L + sky * skyVisibility + bounce). Stacking double-darkens [derived].
- Colored bounce: replace the sky a neighbor blocks with that neighbor's lit color. Polished metal wall throws a warm glow strip to the bench on the lit side out to H*(L.xy.n)/L.z [derived].
- Lift cycle drives one height h: shadow offset h*L.xy/L.z, penumbra widens, skirt widens and fades, contact line disappears, scale D/(D-h). Fast lift, slight overshoot, slower settle; heavier trays lift lower and overshoot less [derived].
- Scale rim thickness, wall height, shadow depth and highlight sharpness with tray size so big trays feel heavier [Apple WWDC25, verified, no numbers published].
- Bench reflection about 4% at normal incidence. Scale by bench darkness (strong on dark indigo stone, nearly invisible on white marble), blur growing with height [recalled, derived].

## Surfaces

- Replace value noise with gradient or simplex noise; rotate octaves about 37 degrees, lacunarity about 2.01 [recalled, derived].
- Domain warping (two-level) and ridged multifractals for veins [recalled]. Band-limit everything: fade periodic terms and octaves once finer than a pixel, or surfaces shimmer when trays move.
- Bake procedural materials once at load into textures (bench 2048 squared, rims and trays 512 to 1K), with height in R16F, normals by central differences, mipmaps on. Do not derive normals from dFdx/dFdy of procedural height (blocky) [derived]. This is the most important architecture decision for the target.
- Marble: warm-white base, ridged primary veins on a warped domain, Voronoi hairlines, a blurred desaturated deeper layer. Camera straight down means no real parallax, so blur and desaturation sell depth [derived].
- Walnut: model the tree, not the board. 3D ring field around a pith axis tilted 1 to 3 degrees gives cathedral arches; stretched Worley pores; anisotropic highlight for figure [recalled].
- Indigo stone: charoite-style swirling fibers with a highlight following the warp [derived].
- Pearl: thin-film iridescence baked into a 64 by 64 table; terraced thickness for nacre [recalled, derived].
- Jewel glass: Beer-Lambert absorption (thicker is richer), refraction by re-evaluating the procedural bench at the bent coordinate, dispersion on bevel pixels only. Glass on glass is to be avoided [verified Apple guidance].
- Translucent stone and pearl cast lighter tinted shadows (transmittance exp(-sigma*path)). Restraint: wear and smudges only as roughness variation of 0.03 to 0.08.
- Scanned textures lose: a 1K scan over a 1 m bench is about 1 mm per texel, and downloads cost bandwidth. Default fully procedural.

## Live HTML screens

- The WebGL canvas can never see screen pixels (HTML-in-Canvas is an origin trial and excludes cross-origin iframes) [verified]. Glass refracts only the bench and other trays.
- Stack: WebGL canvas below (bench, frames, rims, shadows, backlight, dark cavity), real HTML in the middle clipped with clip-path to the polygon opening (clip lands exactly on the rim's inner lip), CSS-only non-interactive gloss layer above (inner shadow, faint diagonal reflection, bright glass-metal line). One shared WebGL context, never one per tray.
- Pointer moves the viewer, not the scene: small eased shift of the view vector for specular and environment lookups; share it with the CSS gloss.
- Provide a Full / Frosted / Solid quality toggle (also the low-end tier). Never put text on refractive or animated glass; check contrast 4.5:1 and 3:1.

## Performance plan

Budget [estimate]: about 2,700 to 4,500 floating-point operations per pixel per frame at 1440p 60 fps on an Iris Xe-class GPU, so only 10 to 20 exact polygon distances per pixel. Passes: quarter-res scene field (distance, height, id), full-res bench reading it, one quad per tray, half-res bloom chain, final pass. Render on demand; cache the bench; drop to 0.67 to 0.75x resolution while dragging and sharpen (CAS) on release. Measure with EXT_disjoint_timer_query_webgl2 (about 86% of Windows browsers) with a frame-time fallback.

Degrade in this order: shadow march 16 to 8 steps or single analytic step; half-res occlusion and shadow; reflections on dark benches only; fewer bloom mips; dynamic resolution.

## Build order (each step shown to Josie as screenshots before wiring)

1. GPU timers plus frame-time governor.
2. Linear HDR target and the single final pass.
3. Native resolution, analytic 1.2 px edges, render on demand, cached bench.
4. Bloom pyramid and HDR backlight that lights the bench.
5. Procedural photo-studio environment, GPU-prefiltered, DFG table, diffuse SH.
6. Swept rim profile, GGX with measured F0, F82, energy compensation, brushing, specular AA.
7. Scene field, contact-hardening shadows, wall occlusion, summed lights, tinted shadows, lift cycle.
8. Noise upgrade and baked materials with clear coat.
9. HTML clip, CSS gloss layer, pointer specular, quality toggle.
10. Pearl, jewel glass, translucent shadows, glints.
11. Bench reflection scaled by darkness, colored bounce, metal glow strip.
12. Optional: LTC strip, procedural LUT grade, light vignette.

## Leave out

TAA, depth of field, motion blur, chromatic aberration on tray edges, full-screen sharpening at native resolution, SMAA, scanned textures, downloaded HDRIs, Basis transcoder, WebGPU backend, HTML-in-Canvas beyond experiments.

## Known gaps

Nothing timed on a real GPU. Several recalled constants unchecked. Mixed-spec notes: one thread suggested a bloom threshold near 1.0 from memory; the verified source argues for no threshold, so use none. Source notes and the full report were written to /home/claude/foresight-research (session workspace, may not persist).