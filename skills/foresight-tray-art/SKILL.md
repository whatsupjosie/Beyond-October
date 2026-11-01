---
name: "foresight-tray-art"
description: "Use when designing, drawing, building or reviewing Foresight Counter trays, frames, benches, fan, lantern or menus: Josie's binding art direction, shape rules, materials and review checklist."
---

# Foresight tray art direction

Foresight trays are "the windows we see the entire program through". Every program (PubPartner, 2i, Iteration Wallet, browser, files, video, recordings, rooms, blank) lives inside a tray. This skill holds Josie's direction. Treat it as binding unless she changes it. Quote her words exactly; never reword, shorten or "clean up" her statements when recording or repeating them.

## Before any work

1. Check whether a more advanced version already exists (repos, Drive, earlier builds) and compare or adapt it before building new.
2. Examine at least three approaches before committing, and say which one was chosen and why.
3. Read the existing code first: foresight_shapes.js (geometry), foresight_gl.js (WebGL2 renderer), foresight.html (page). Do not write blind.
4. Show screenshots before wiring anything into the live page. Do not push to GitHub until she says so.
5. Verify as you go, not only at the end. State plainly what was and was not verified. No spin.

## Binding structure (Aug 19 Foresight Engineering Handoff)

- Silver system bar with menus across the top.
- Lantern, robotic arm and fan at upper left.
- The fan has one blade per open tray plus exactly one blank blade. Selecting a blade pops or glows its tray. A closed blade falls like a card.
- The fan opens PubPartner, 2i, Iteration Wallet (its own UI in a tray), a browser, or a blank tray.
- Close Countertop only from the system bar, with a confirmation that lists every item.
- Each tray has a safe content area plus a frame that bulges only outward.
- One global light for the whole scene.
- Style: Neo Art Deco Nouveau.

## Her direction on trays (verbatim where quoted)

- Shapes: rounded corners, "I don't want the pointy corners". Stay away from squares and rectangles: "one of the main purposes of choosing a system UI like this is I want to avoid rows and stacks of boxes". "A rhombus is better than a square or a pentagon or a hexagon." Keep angles wide "so we don't have an angle or a side of the rhombus getting too sharp to the point where it's useless".
- The TV box: an irregular polygon surrounds a standard content rectangle. It is only an invisible measure of how small a tray may get or how much it may deform before it is useless as a window. "We should not see the edges of the box." Most of it must stay visible; the shape may scale and morph (sides lengthen, new angles, new sides sprouting) "due to its collision with another tray", as long as the TV box never collapses.
- Frame and screen: "the irregular polygon borders should act as a frame for the TV". "The whole inside of the irregular polygon is the screen." Around the screen edges, "very very minimal morphing", "certainly not distorting the image".
- Weight and depth: "they should appear to be 3D they should have weight". Subtle lighting underneath every tray that helps give it a shadow, and "maybe even just a very very minor reflection depending on what the surface underneath them is" plus the type and direction of the lighting.
- Selection: "when you select a specific tray I want a bright backlight".
- Fidelity: "too pixelated". She wants the look of her example mockups (four Pub Partner UI images: warm pearl/silver and dark indigo/gold themes). Her first instruction was "I don't want them to look photo real". Her latest instruction was to try leaning "hyper-real, elevated reality" and to "add weight to things and make it, give it depth". Treat hyper-real as a trial direction: build it, show it, and let her judge. Do not claim it is approved.
- Technology: she said not to use CSS for the art; HTML, JSON or C++ are open. Current choice: WebGL2 fragment shaders driven by polygon signed distance fields, with live HTML for the screens.
- She likes seashells, honeycombs and swirling coiled lines as button shapes.

## Shape rules (v18 Tray Design Rules, as implemented)

- Families: rhombus, trapezoid, pentagon, hexagon, heptagon, octagon, ellipse. No squares or rectangles, no regular polygons, no equal sides, plump outlines.
- Minimum interior angles (degrees): rhombus 70, trapezoid 65, pentagon 88, hexagon 95, heptagon 100, octagon 105. Max rhombus aspect 1.35.
- Coverage: rest 0.985, minimum 0.94 of the TV box. Core fraction 0.90 must stay inside. Title band 34 px is protected. Tray gap 18, wall gap 10.
- Crowding: trays shrink under pressure down to 0.55 scale, then regrow slowly with hysteresis. A layout is invalid if overlap is unresolved.
- The screen rectangle is the uncut frame floor, so content never reflows when the frame flexes.
- The scallop-shell shape is not yet in the morphing system.

## Materials

- Canonical palette: Rearview Pearl, Sapphire Glass, Emerald Enamel, Amethyst Glass, Obsidian Lacquer, copper, bronze, brass, walnut. Metals: gold, brass, copper, silver, bronze. Stones: marble (white, rose, green, black), granite, sandstone, indigo. Woods: walnut, oak, mahogany. Also nacre/pearl, tortoise, leather.
- Themes: walnut bench, pearl, indigo/gold.
- One light only. Lighting Explorer values (Kelvin, azimuth, elevation, intensity, fill) drive it.
- Rendering techniques live in the hyperreal-webgl-rendering skill.

## Review checklist (run before showing her anything)

1. Any square, rectangle, regular polygon or pointy corner? Fix it.
2. Is the TV box visible anywhere? It must not be.
3. Does the frame cover the screen edges, with the whole polygon interior acting as the screen?
4. Does the image stay undistorted while the frame flexes and trays collide?
5. Do trays read as heavy: contact shadow, underlight, minor reflection scaled to the surface?
6. Does the selected tray have a bright backlight?
7. Any visible pixelation or stair-stepping on edges or gradients, including during drags?
8. One light direction everywhere?
9. Do menus, dialogs, fan and lantern match the new look (they currently still look old and plain)?
10. Report what was checked, what was not, and anything uncertain.

## State at time of writing (re-check before relying on it)

- The shapes engine and WebGL renderer work in a lab page but are NOT yet wired into foresight.html, which still uses the older CPU-drawn skin.
- The C++/WASM renderer is too slow for live drawing (0.2 to 2 s per frame); whether to remove it was an open question to her.
- Real-GPU performance has not been measured, only a software GPU.
- Lantern and fan blades are still plain (no ornaments or gem studs).

## Working style with Josie

- Plain text in chat, no code blocks or artifact blocks. Terse, direct, truthful.
- PowerShell 5 syntax for anything she runs. Production-grade code only.
- Do not re-ask what she has already answered. Ask only when a wrong guess is costly.