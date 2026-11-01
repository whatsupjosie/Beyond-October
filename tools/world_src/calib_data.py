"""Per-picture camera calibration (proposed, NOT approved). h = horizon row, E = eye height in inches above the floor.
conf: good / fair / low. refs: what was measured. Nothing here is stored in the app data until Josie approves."""
CAL = {
 "green_room/main": dict(kind="camera", h=180, E=66, conf="fair",
     why="Two vanishing points at rows 184-192 agree with the three doors (80 in), eye height 65-66 in. But near furniture disagrees: the kitchen counter reads about 20% smaller than this camera predicts, and the TV comes out about 36 in tall where Josie's own guess was about navel height on a 6-footer (roughly 43-48 in). So close to the sofa, avatars may be 15-20% too big. Pit floor sits lower: needs its own altitude.",
     refs=["ornate door 1.9 px/in at row 305", "Conference door 2.9 at row 370", "Control Room door 3.6 at row 420", "kitchen counter ~4.2 at row ~510 (about 20% under the camera)"]),
 "dressing_room/wide": dict(kind="camera", h=346, E=60, conf="fair",
     why="Right-wall vanishing point stable at row 346-348. Door, desk and light switch give eye height 55-65 in. Left-wall lines disagree (rows 304-531), so the picture's perspective is not perfectly consistent.",
     refs=["door 80 in: 4.3 px/in at row 594", "vanity desk 30 in: 5.5 at row 695", "light switch ~47 in: 3.6 at row 582"]),
 "palace_hallway/main": dict(kind="camera", h=350, E=62, conf="fair",
     why="Strong one-point perspective: vanishing point (920-948, 346-357) from 65 line segments. Display counter (38 in) gives eye height 62 in at its near end and 59 at the far end. The back door then reads about 10 ft tall: plausible for a grand lobby but not verified.",
     refs=["display counter 38 in near end: 4.2 px/in at row 612", "same counter far end ~2.1 at row 495"]),
 "manager_office/main": dict(kind="camera", h=313, E=87, conf="fair",
     why="Two vanishing points at rows 282 and 345 (they should match): horizon 313 +/- 30. Desk (30 in) and guest chair (34 in) agree on eye height 79-94 in for any horizon in that range (a high camera). The door's base is hidden behind the desk, so it was not used.",
     refs=["executive desk 30 in: 4.8 px/in at row 728", "guest chair 34 in: 6.1 at row 865"]),
 "lobby_upstairs/main": dict(kind="camera", h=278, E=62, conf="low",
     why="Curved architecture: the one vanishing point it found (row 348) comes from curved railings, so I did not trust it. Only the MANAGER door (80 in: 3.1 px/in at row 470) is measured. I ASSUMED eye height 62 in (what the pictures I could measure came out at); the horizon follows from that. Cross-check added 2026-10-18: the sofa arm (about 24 in) reads 4.2 px/in at row 548 against 4.35 from the camera, so the camera holds against a second object; the armchair arm reads 29% lower, so confidence stays low.",
     refs=["MANAGER door 80 in: 3.1 px/in at row 470", "sofa arm ~24 in: 4.2 at row 548 (the camera says 4.35)", "armchair arm ~24 in: 3.2 at row 534 (29% under the camera; not used)"]),
 "lobby/main": dict(kind="samples", samples=[(355, 1.1), (447, 1.67)], conf="low",
     why="Curved, fisheye-like room: its vanishing point landed on the floor row, which is impossible, and the kiosk and vault door disagree at nearly the same rows. So no camera is fitted. Two samples only: vault door (84 in) 1.1 px/in at row 355 and bar stools (30 in) 1.67 at row 447. Beyond row 447 it is extrapolated.",
     refs=["vault door 84 in: 1.1 px/in at row 355", "bar stools 30 in: 1.67 at row 447", "left bar stool 30 in: 1.5 at row 430 (the line gives 1.56)", "wall cabinet ~70 in: 1.1 at row 330 (agrees with the vault door)", "bar 42 in: 1.5 at row 440", "kiosk ~72 in: 1.6 at row 372 (conflicts with the vault door)"]),
 "control_room/main": dict(kind="camera", h=242, E=75, conf="fair",
     why="Two vanishing points agree (rows 238 and 246), with 93-134 line segments behind the stronger one. Both desks (30 in) and both chairs (36 in) give eye height 70-83 in, so the camera is fairly high.",
     refs=["left desk 30 in: 2.3 px/in at row 405", "left chair 36 in: 2.4 at row 408", "right desk 30 in: 3.0 at row 490", "right chair 36 in: 3.8 at row 540"]),
 "writers_room/main": dict(kind="samples", samples=[(620, 3.4), (905, 5.1)], conf="low",
     why="Re-done 2026-10-18 on Josie's corrections (the earlier sheets looked too small to her). The giant arched door is not used (non-standard). Back of the room: the mug on the right low table (13 px, mug about 3.5-3.75 in) gives about 3.5 px/in at row 620; the shelf mugs and coffee machine and the door handle agree within about 15% (3.0-3.8). Front of the room: Josie's check is that a conference chair comes below the bust of a 5 ft 8 in person standing beside it. The front-right chair is about 215 px tall (top row 700, base row 915). A conference chair about 42 in tall (my reading of her 'below the bust'; a bust is about 49 in on 68 in) gives about 5.1 px/in at row 905, so Pete (68 in) is about 347 px there. Cost, stated plainly: the round conference table (120 px tall, base row 835) then comes out about 26 in, not the standard 30 in (it gave 4.0 at row 835; the line gives about 4.7), so the picture does not agree with itself and the chairs are drawn large. No vanishing point and stylized art: low confidence.",
     refs=["mug on right low table (3.5-3.75 in): about 3.5 px/in at row 620 (13 px)", "mugs on wall shelf (3.5-3.75 in): about 3.0 at row 528 (11 px), farther back", "coffee machine 14-16 in: about 3.8-4.0 at row 528 (57 px)", "door handle 36-40 in above floor: about 3.5 at row 598", "front-right conference chair ~42 in (comes below the bust of a 68 in person): about 5.1 at row 905 (215 px, rows 700 to 915)", "round conference table 30 in: 4.0 at row 835 (120 px) - disagrees with the chair (line gives about 4.7, table would be about 26 in)", "arched door frame / leaf height: NOT used (giant, non-standard)"]),
 "vortex_bar/main": dict(kind="camera", h=333, E=83, conf="fair",
     why="Re-measured 2026-10-18. The first version pinned the line at the back door's MIDDLE row (485) instead of its base (532) and had no second check. Three references now agree on one line: the back door (80-84 in; top row 344, base row 532, 188 px) gives 2.3 px/in at row 532; the rear bar stool (my assumption: about 43 in to the top of its back; base row 773, back top row 533) gives about 5.6 at row 773; the front bar stool (back top row 610, base row 868) gives about 6.2 at row 868. A line through all three leaves at most 6% error and puts the horizon at row 333 and the eye at about 83 in. That fits the picture itself: the door's top (row 344) sits at eye level when the eye is about 83 in and the door is 80-84 in. The vanishing-point search still fails here (the whirlpool paint), so the horizon comes from the references, not from lines; the stool height is my assumption.",
     refs=["back door 80-84 in: 2.3 px/in at row 532 (rows 344 to 532, 188 px)", "rear bar stool, about 43 in to the back top: 5.6 at row 773", "front bar stool, about 43 in to the back top: 6.2 at row 868"]),
 "basement_bar/main": dict(kind="samples", samples=[(800, 3.5), (870, 4.4), (932, 4.5), (1024, 4.5)], conf="low",
     why="Re-measured 2026-10-18 from the tight chair cut-outs (back top to feet), all folding chairs taken as 32 in (assumed). Wide-angle, steep downward view onto a curved staircase: no usable vanishing point, so the scale is a line fitted through chair readings only. The earlier fit had the back-row reading at the wrong row (600; the back chairs actually stand at rows 773-834), which made figures at the back of the floor too big. Five back-row chairs (105-120 px, base rows 773-834) average 3.5 px/in; two middle chairs (152 and 132 px, base rows 870-872) average 4.4; two front chairs (155 and 136 px, base row 932) average 4.5; the left chair (145 px, base row 1024) gives 4.5. Foot rows are estimates (feet are hidden in places), and upright things look foreshortened from this high angle, as an upright avatar would. Stage props (mic stand, drums) were not used: the stage is raised and their real sizes are unknown.",
     refs=["5 back-row folding chairs 32 in: 105-120 px, base rows 773-834, mean 3.5 px/in at row 800", "2 middle chairs 32 in: 152 and 132 px at base rows 870-872, mean 4.4 at row 870", "2 front chairs 32 in: 155 and 136 px at base row 932, mean 4.5 at row 932", "left chair 32 in: 145 px at base row 1024, 4.5 at row 1024", "bar counter, round table, stage props not used (hidden base or raised)"]),
 "studio_overlook/main": dict(kind="camera", h=315, E=232, conf="fair",
     why="High, wide view from the overlook. The vanishing point settles at rows 308-315, and three crew members (I assumed each is 68 in) give eye height 226-240 in at that horizon, so the camera is high above the floor (about 19 ft). The assumption that the crew are 68 in is mine.",
     refs=["crew member 0.88 px/in at row 515", "crew member 1.07 at row 572", "crew member 1.15 at row 575", "all assume 68 in"]),
 "studio_fixedsets/main": dict(kind="camera", h=310, E=240, conf="low",
     why="No usable vanishing point (cables and curved set). The line comes only from three standing crew at nearby rows (assumed 68 in each), extended up to a horizon; that short baseline makes the horizon uncertain. It lands at row 310, which matches the far shot's independent vanishing point (315), and the foreground floor lamp then reads about 64 in tall, which is plausible but not verified.",
     refs=["crew by the sofas 0.81 px/in at row 503", "white-shirt crew 1.03 at row 548", "crew by the stairs 1.10 at row 572", "all assume 68 in", "floor lamp 175 px at row 965 reads ~64 in (not used to fit)"]),
 "studio_director/main": dict(kind="camera", h=380, E=62, conf="fair",
     why="Two vanishing points agree (rows 378 and 382, from 79-105 and 41-55 line segments). The laptop cart (36 in), the long table (30 in) and the studio stool then give eye height 58-68 in. The TV stand on the right comes out about 72 in tall, plausible. The floor is glossy, so reflections are not objects.",
     refs=["laptop cart 36 in: 2.9 px/in at row 562", "long table 30 in: 4.3 at row 670", "studio stool ~28-30 in: about 3.0 at row 553", "TV stand 103 px at row 468 reads ~72 in (not used to fit)"]),
 "parking_lot/main": dict(kind="samples", samples=[(285, 0.38), (706, 1.0)], conf="fair",
     why="Re-measured 2026-10-18. The first version had the Vortex Bar entrance at 0.65 px/in and that was wrong: the entrance door runs from row 622 to row 705 (84 px, about 1.0 px/in for an 80-84 in door), not 55 px. With the door corrected, the doors and the cars agree: the parked cars (57 in) read about 1.05 at row 775 where the line gives about 1.10, so the 'doors versus cars' conflict I showed before is gone. At the far end the STAGE I person door (80 in; rows 247-279, 32 px) reads 0.40 at row 279, the Palace Theater entrance doors about 0.35 at row 297, and the far car's length (about 15 ft, 63 px) about 0.35 at row 295. The line runs from 0.38 at row 285 to 1.0 at row 706. It is a high aerial view, so this is a straight-line fit with no camera.",
     refs=["line anchors: 0.38 px/in at row 285 (far doors and car), 1.0 at row 706 (Vortex Bar entrance)", "STAGE I person door 80 in: 0.40 at row 279", "Palace Theater entrance doors ~84 in: 0.35 at row 297", "far car, length 15 ft: 0.35 at row 295", "Vortex Bar entrance door 80-84 in: 1.0 at row 706 (rows 622 to 705)", "parked car 57 in: 1.05 at row 775 (agrees with the doors)"]),
 "monument/day": dict(kind="samples", samples=[(578, 1.85), (786, 2.5)], conf="low",
     why="No camera. The vanishing-point search gave two points that disagree, and the benches and the lamps cannot both be right. The park benches (34 in) give 2.5 px/in at row 786. The tall left lamp gives 1.85 at row 578 only if it is 12 ft, which is MY ASSUMPTION. The lamps shrink with distance much faster than that line (they point to a horizon near row 500); under that reading the lamps would be about 30 ft tall and a person at row 578 would be only about 47 px. The grey figure on the proof shows that alternative next to the proposed one.",
     refs=["park bench 34 in: 2.5 px/in at row 786", "tall left lamp 266 px, assumed 12 ft: 1.85 at row 578", "five lamps in a row shrink to zero height at row ~500", "park benches, both sides, 34 in to the back top: 2.5 at rows 780-793 (re-measured 2026-10-18, left and right agree; bench length 6 ft reads 2.4)"],
     alt=dict(label="lamps as 30 ft", samples=[(578, 0.70), (786, 2.5)], row=595, xs=(1300, 1360), lab_dx=-200)),
}
def ppi(key, y, z=0.0):
    c = CAL[key]
    if c["kind"] == "camera": return (y - c["h"]) / (c["E"] - z)
    sm = c["samples"]
    if len(sm) == 2:
        (y0, p0), (y1, p1) = sm; return p0 + (y - y0) * (p1 - p0) / (y1 - y0)
    n = len(sm); my = sum(a for a, _ in sm) / n; mp = sum(b for _, b in sm) / n      # least-squares line, as fit_scale does
    k = sum((a - my) * (b - mp) for a, b in sm) / sum((a - my) ** 2 for a, _ in sm)
    return mp + (y - my) * k

# where the proof figures stand: (rows for Purfluous, RePete, Pete; x positions). Chosen to stand on open floor.
PROOF_AT = {
 "basement_bar/main": ([735, 850, 975], [600, 790, 900]),
 "studio_overlook/main": ([640, 780, 930], [330, 560, 800]),
 "studio_fixedsets/main": ([700, 770, 930], [380, 560, 470]),
 "studio_director/main": ([470, 560, 680], [150, 700, 880]),
 "parking_lot/main": ([330, 520, 700], [500, 400, 650]),
 "monument/day": ([560, 800, 820], [200, 470, 1250]),
}

# The numbers each camera was fitted from, as (row, px per inch). They must agree with the camera (checked by the
# tests and by placements validation) and must appear in the written "refs" of the same picture.
MEAS = {
 "green_room/main": [(305, 1.9), (370, 2.9), (420, 3.6), (510, 4.2)],
 "dressing_room/wide": [(594, 4.3), (695, 5.5), (582, 3.6)],
 "palace_hallway/main": [(612, 4.2), (495, 2.1)],
 "manager_office/main": [(728, 4.8), (865, 6.1)],
 "lobby_upstairs/main": [(470, 3.1)],
 "control_room/main": [(405, 2.3), (408, 2.4), (490, 3.0), (540, 3.8)],
 "studio_director/main": [(562, 2.9), (670, 4.3), (553, 3.0)],
 "studio_overlook/main": [(515, 0.88), (572, 1.07), (575, 1.15)],
 "studio_fixedsets/main": [(503, 0.81), (548, 1.03), (572, 1.10)],
}
for _k, _c in list(CAL.items()):
    if _c["kind"] == "samples":
        MEAS[_k] = [tuple(p) for p in _c["samples"]]
# cross-check measurements added 2026-10-18 (each is written in that picture's refs)
MEAS["vortex_bar/main"] = [(532, 2.3), (773, 5.6), (868, 6.2)]
MEAS["lobby_upstairs/main"] = MEAS["lobby_upstairs/main"] + [(548, 4.2)]
MEAS["lobby/main"] = MEAS["lobby/main"] + [(430, 1.5), (330, 1.1)]
MEAS["writers_room/main"] = [(620, 3.5), (528, 3.0), (528, 3.8), (598, 3.5), (835, 4.0), (905, 5.1)]
MEAS["parking_lot/main"] = MEAS["parking_lot/main"] + [(279, 0.40), (297, 0.35), (295, 0.35), (775, 1.05)]
MEAS["monument/day"] = MEAS["monument/day"] + [(793, 2.5)]
