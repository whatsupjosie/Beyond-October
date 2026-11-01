"""Floor footprints of solid things, traced by eye against each picture (source pixels), tight to what the
picture shows. Nothing here is approved until Josie has seen it on the sheets.

FOOTPRINTS[view][occluder id] = the floor contact area of an object that already has an outline (occluder):
    it blocks walking AND its lower edge is the object's real front line, so the avatar is in front of or
    behind it along that line instead of one flat row.
BLOCKERS[view] = [{"id", "label", "footprint", "note"}]: solid things with no outline yet; they only block.
Reasoning notes sit next to each entry.
"""
import math as _m


def ell(cx, cy, rx, ry, n=32):
    """Points of an ellipse (round tables, pedestals): centre, radii in source pixels."""
    return [[round(cx + rx * _m.cos(2 * _m.pi * i / n)), round(cy + ry * _m.sin(2 * _m.pi * i / n))] for i in range(n)]


def zoomed(ox, oy, k, pts):
    """Points read off a close-up (crop starting at source pixel (ox, oy), enlarged k times) -> source pixels."""
    return [[round(ox + x / k), round(oy + y / k)] for x, y in pts]


def hull(*shapes):
    """Convex hull (monotone chain) of one or more point lists: the silhouette of a drum, a bucket, a stool."""
    pts = sorted({(round(x), round(y)) for s in shapes for x, y in s})
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return [list(p) for p in lo[:-1] + up[:-1]]


def band(contour, depth, toward, ysq=0.7):
    """The floor footprint of a CURVED piece (an arc-shaped desk or sofa) from its visible floor-contact contour: a band of
    ``depth`` pixels towards the point ``toward`` (the inside of the curve), measured along the contour's normal, with the
    vertical part squeezed by ``ysq`` because a floor depth looks shorter than a width in these high camera pictures."""
    n = len(contour)
    back = []
    for i, (x, y) in enumerate(contour):
        (x0, y0), (x1, y1) = contour[max(i - 1, 0)], contour[min(i + 1, n - 1)]
        tx, ty = x1 - x0, y1 - y0
        ln = _m.hypot(tx, ty) or 1
        nx, ny = -ty / ln, tx / ln
        if (toward[0] - x) * nx + (toward[1] - y) * ny < 0:
            nx, ny = -nx, -ny
        back.append([x + nx * depth, y + ny * depth * ysq])
    return [list(map(round, p)) for p in contour] + [list(map(round, p)) for p in reversed(back)]


def slab(front, depth, lean=0):
    """The floor footprint of a box-like thing from its FRONT contact line (the visible bottom edge, left to right) and
    its depth in picture rows: the back edge is the front line moved up by ``depth`` (and ``lean`` sideways), because the
    floor under and behind it is hidden by the thing itself. The depth is worked out per picture from the round table's
    ellipse ratio and the camera's px/in, and is my estimate."""
    back = [[x + lean, y - depth] for x, y in reversed(front)]
    return [list(map(round, p)) for p in front] + [list(map(round, p)) for p in back]


FOOTPRINTS = {}
BLOCKERS = {}
# OUTLINE_FIXES[view][occluder id] = (points, why): the automatic cut-out reached over something else; these points replace it.
OUTLINE_FIXES = {}
# OUTLINES[view][occluder id] = {"points", "base_y", "note"}: hand-traced silhouettes for solids the automatic cut-out
# (GrabCut) could not separate from the background. Same meaning as any occluder outline.
OUTLINES = {}
# FROM_OUTLINE_MINUS_FLOOR[view] = occluder ids whose footprint is the outline minus the walkable zones: low solids (a couch)
# whose whole visible body is what blocks the floor, but whose automatic outline also reaches over some carpet.
FROM_OUTLINE_MINUS_FLOOR = {"green_room/main": ["sofa-front"]}

# ── green room: the sunken living room ──────────────────────────────────────
FOOTPRINTS["green_room/main"] = {
    # Corners are the four leg bases of the table, each pushed out by half a leg: left (772,523), front (862,563),
    # right (978,537), and the hidden back leg completed as left + right - front = (888,497).
    "coffee-table": [[763, 524], [862, 570], [992, 538], [897, 493]],
    # The TV is a flat panel on two foot plates (left about 970-1005 x 440-459, right about 1075-1122 x 482-497).
    # The footprint is a band joining them; the floor behind the TV is hidden and is not walkable.
    "tv": [[966, 454], [1004, 438], [1112, 472], [1126, 488], [1092, 500], [1070, 493], [978, 462]],
    # The back section of the sunken couch: its front edge is the skirt line, slanting up to the right.
    "sofa-back": [[697, 503], [780, 481], [850, 456], [866, 438], [866, 380], [780, 400], [697, 430]],
}

OUTLINES["green_room/main"] = {
    # The lamp (shade 1247-1317 x 358-407, shaft 1267-1292) standing on the side table. The table top runs 1180-1340,
    # its right block to x=1351, its base meets the pit at y about 511. The lower left of the table is behind the couch's
    # right arm, so the outline follows the line where the two meet (the couch is a separate, nearer outline).
    "lamp-table": {
        "points": [[1250, 368], [1258, 360], [1305, 359], [1314, 366], [1317, 380], [1316, 396], [1308, 404], [1292, 407],
                   [1292, 450], [1337, 459], [1340, 467], [1351, 471], [1351, 489], [1313, 511], [1312, 502], [1290, 489],
                   [1268, 484], [1215, 477], [1181, 466], [1180, 459], [1191, 452], [1240, 435], [1267, 442], [1267, 407],
                   [1250, 404], [1247, 392]],
        "base_y": 511,
        "note": "Hand-traced 2026-10-18 (the automatic cut-out could not separate it). The table sits in the pit at the right end of the couch.",
    },
}

BLOCKERS["green_room/main"] = [
    {"id": "sofa-left-curve", "label": "Sunken sofa, left curve",
     "footprint": [[504, 435], [511, 419], [525, 405], [567, 385], [631, 371], [669, 365], [697, 364], [697, 430], [697, 503],
                   [696, 508], [689, 507], [683, 497], [563, 472], [507, 441]],
     "note": "The curved left end of the couch (seat, back and pillows). It joins the back section at x=697 and the near seat below it; "
             "the floor under it is hidden, so it is simply solid. Traced from the couch's own outline, 2026-10-18."},
]

# ── upstairs lobby (1536x1024; horizon row 278, eye 62 in, LOW confidence) ────────────────────────────────
# Sizes: at the sofa's right end (row 475) the camera gives 3.2 px/in; the round table's top is an ellipse 0.31 as tall as
# it is wide, so one inch of floor depth is about 1.1-1.3 px of height. A 36 in deep sofa is then about 44 px deep.
FOOTPRINTS["lobby_upstairs/main"] = {
    # Bottom edge of the sofa where it meets the floor (left chaise block, then the seat skirt sloping up to the right).
    "sofa": slab([[312, 533], [351, 545], [411, 548], [418, 539], [490, 524], [556, 503], [609, 478], [631, 471]], 44),
    # Bottom edge of the armchair (left arm, seat skirt, right arm).
    "armchair": slab([[656, 512], [678, 521], [730, 537], [737, 544], [804, 541], [823, 531]], 40),
}
OUTLINES["lobby_upstairs/main"] = {
    # The round table: its top is an ellipse centred (575, 505), 84 x 27; the pedestal is 531-621 wide, rows 523-565.
    "round-table": {
        "union": [ell(575, 505, 84, 27, 36), [[532, 515], [620, 515], [621, 560], [610, 565], [542, 565], [531, 560]]],
        "base_y": 578,
        "note": "Hand-traced 2026-10-18 (the automatic cut-out could not separate it).",
    },
}
# The foreground handrail (the curved band across the lower left to right) and its four posts, 2026-10-18. The band was measured
# column by column against 7x close-ups (top face + dark front face, about 25-45 px thick); only the TOP rail is cut out. The second
# and third rails and the see-through panels below are not: nothing walkable reaches them (the floor stops at the handrail's top edge).
_RAIL_BAND = [[0, 918], [50, 895], [100, 872], [150, 850], [200, 830], [250, 806], [300, 785], [350, 760], [400, 738], [450, 722], [500, 700], [550, 677], [600, 655], [650, 633], [700, 605], [750, 580], [800, 552], [850, 516], [880, 490], [900, 458], [907, 472], [880, 515], [850, 540], [800, 578], [750, 605], [700, 631], [650, 656], [600, 681], [550, 704], [500, 728], [450, 750], [400, 774], [350, 798], [300, 822], [250, 846], [200, 873], [150, 893], [100, 914], [50, 938], [0, 962]]
_RAIL_POSTS = [[[485, 733], [497, 730], [499, 764], [487, 767]], [[710, 622], [720, 620], [722, 648], [712, 650]], [[797, 570], [807, 568], [809, 598], [799, 600]], [[860, 527], [868, 525], [870, 542], [862, 544]]]
OUTLINES["lobby_upstairs/main"].update({
    "railing": {
        "union": [_RAIL_BAND] + _RAIL_POSTS,
        "always": True, "base_y": None,
        "note": "Hand-measured 2026-10-18: the top handrail only (about +-5 px), with its four posts. A foreground piece: always drawn over the avatar. "
                "The second and third rails and the glass-like panels under them are NOT cut out.",
    },
})
BLOCKERS["lobby_upstairs/main"] = [
    {"id": "round-table-drip-line", "label": "Round table (the floor under its top)",
     "footprint": ell(575, 552, 84, 26, 28),
     "note": "The table top is about 15 in off the floor and 84 px (about 25 in) from the centre to the edge, so the floor under it is solid "
             "for an avatar. Centre is the top's centre moved down by the table's height."},
]


# ── manager's office (1536x1024; horizon row 313, eye 87 in, fair) ──────────────────────────────────────────
FOOTPRINTS["manager_office/main"] = {
    # Four leg bases of the coffee table (left (176,895), front (360,975), right (548,840) read off the picture; the back
    # leg is hidden behind the table and completed as left + right - front = (364,760)), each pushed out by half a leg.
    "coffee-table": [[160, 897], [360, 984], [560, 842], [366, 755]],
    # The four leg bottoms of the chair in front of the desk (front legs rows 866-868, back legs rows 818-820), pushed out 5 px.
    "visitor-chair": [[748, 868], [904, 871], [913, 816], [736, 818]],
    # The desk's floor contact: its base line along the bottom of the left pedestal, the kneehole panel and the right pedestal
    # (read off a 1.9x close-up), pushed back 55 rows for the depth of the desk (my estimate; the floor under it is hidden).
    "desk": slab([[556, 729], [700, 744], [840, 752], [969, 754], [1140, 792], [1152, 788]], 55),
    "wastebasket": ell(1192, 756, 36, 11, 24),
    "bucket-planter": ell(1448, 752, 30, 10, 24),
}
OUTLINES["manager_office/main"] = {
    "visitor-chair": {
        "union": [[[735, 656], [752, 651], [905, 652], [922, 658], [925, 672], [928, 690], [922, 715], [917, 760], [912, 790], [740, 790],
                   [738, 760], [730, 712], [722, 690], [724, 672], [732, 668]],
                  [[748, 780], [758, 780], [758, 868], [748, 868]], [[892, 780], [905, 780], [905, 870], [893, 870]],
                  [[737, 780], [745, 780], [745, 820], [737, 820]], [[905, 770], [913, 770], [913, 818], [905, 818]]],
        "base_y": 871,
        "note": "Hand-traced 2026-10-18 from a 3x close-up: back and seat, armrests, four legs (the back legs end about 50 rows higher).",
    },
    "wastebasket": {
        "label": "Wastebasket, right of the desk",
        "points": hull(ell(1192, 673, 40, 12, 24), ell(1192, 757, 36, 11, 24)),
        "base_y": 768,
        "note": "Hand-traced 2026-10-18: rim ellipse centred (1192, 673), base ellipse centred (1192, 757).",
    },
    "bucket-planter": {
        "label": "Wooden bucket planter, right",
        "points": hull(ell(1448, 684, 32, 9, 24), ell(1448, 752, 30, 9, 24)),
        "base_y": 762,
        "note": "Hand-traced 2026-10-18: the bucket only (the plant's leaves are not part of the outline).",
    },
}
# The leather sofa (left) and the table at the bottom left, traced 2026-10-18 from 2.2x and 2.7x close-ups.
FOOTPRINTS["manager_office/main"]["sofa"] = [[0, 742], [396, 744], [396, 826], [0, 828]]   # front line row 826-828 (the skirt meets the dark floor); the back edge is NOT measured
OUTLINES["manager_office/main"].update({
    "sofa": {
        "points": [[0, 537], [14, 534], [30, 531], [59, 528], [105, 521], [136, 515], [182, 512], [218, 508], [240, 514], [256, 531],
                   [266, 552], [290, 556], [318, 558], [345, 559], [364, 561], [380, 565], [391, 575], [394, 596], [392, 640],
                   [394, 665], [392, 688], [388, 706], [392, 740], [388, 790], [360, 822], [330, 826], [145, 826], [0, 828]],
        "base_y": 828,
        "note": "Hand-traced 2026-10-18 from a 2.2x close-up: back, right arm, front skirt. The lower right is behind the coffee table, so that part "
                "follows the table's back edge; the front line (row ~826) is my reading of where the skirt meets the dark floor (about +-10 rows).",
    },
    "table-foreground": {
        "union": [[[0, 888], [60, 886], [122, 883], [134, 886], [148, 896], [175, 905], [210, 915], [255, 927], [290, 932], [303, 938],
                   [306, 950], [298, 960], [297, 1000], [296, 1024], [0, 1024]],
                  [[30, 766], [50, 765], [50, 790], [52, 815], [60, 838], [68, 855], [67, 962], [63, 977], [41, 983], [20, 981], [11, 970],
                   [9, 947], [9, 881], [13, 858], [23, 836], [28, 814], [30, 784]],
                  [[86, 776], [102, 775], [104, 790], [103, 805], [110, 830], [120, 855], [124, 880], [124, 955], [119, 968], [98, 974],
                   [80, 971], [70, 955], [70, 900], [70, 860], [78, 830], [85, 800], [85, 785]]],
        "always": True, "base_y": None,
        "note": "Hand-traced 2026-10-18 from a 2.7x close-up: the table top and front (it runs off the left and bottom of the picture), "
                "and the two tall bottles standing on it. A foreground piece: always drawn over the avatar.",
    },
})
BLOCKERS["manager_office/main"] = [
    {"id": "film-camera-tripod", "label": "Film camera tripod",
     "footprint": [[1214, 660], [1283, 724], [1392, 718], [1387, 708], [1300, 700], [1228, 655]],
     "note": "The three feet are at about (1218, 665) (behind the wastebasket), (1282, 716) and (1387, 713); the camera sits above their middle, "
             "so the triangle between them is solid. Not outlined as something to walk behind yet."},
    {"id": "floor-tray", "label": "Large framed tray on the floor, bottom right",
     "footprint": [[1318, 884], [1474, 911], [1478, 1024], [1243, 1024], [1243, 1002]],
     "note": "Runs off the bottom of the picture."},
    {"id": "floor-books", "label": "Book stacks on the floor, bottom right",
     "footprint": [[1174, 935], [1272, 930], [1283, 1000], [1236, 1024], [1116, 1024], [1118, 978], [1150, 962]],
     "note": "Two stacks of books and a second frame leaning on the tray."},
]


# ── dressing room (1536x1024; horizon row 346, eye 60 in, fair) ──────────────────────────────────────────────
FOOTPRINTS["dressing_room/wide"] = {
    # Leg bases of the coffee table: left (654,884), front (1181,952), right (1270,870) read off a 1.7x close-up; the back-left leg
    # is hidden and is completed as left + right - front = (743,802); each corner pushed out about 12 px.
    "coffee-table": [[642, 887], [1181, 957], [1285, 870], [740, 796]],
}

# ── writers' room (1024x1024, scale from two samples, LOW confidence) ───────────────────────────────────────
# A stylised drawing: the egg chairs have no legs, so each footprint is the patch of floor under the lower part of the shell.
FOOTPRINTS["writers_room/main"] = {
    # The table top is an ellipse 538 x 116 centred (535, 680); its pedestal base is centred near row 814, so the table stands
    # about 134 rows above the floor patch under it. The floor under the top is solid for an avatar (the top is waist high).
    "table": ell(520, 814, 269, 58, 40),
    "chair-front-left": ell(282, 880, 106, 42, 28),
    "chair-front-right": ell(631, 878, 106, 44, 28),
}
BLOCKERS["writers_room/main"] = [
    {"id": "chair-left-back", "label": "Green chair, left side", "footprint": ell(138, 826, 38, 14, 20),
     "note": "Shell bottom read off a 2.4x close-up. No outline yet."},
    {"id": "chair-back-left", "label": "Green chair, back left (behind the table)", "footprint": ell(318, 757, 62, 22, 20),
     "note": "Mostly hidden by the table; shell bottom edge (256,761) to (381,748)."},
    {"id": "chair-back-1", "label": "Green chair, back row, first", "footprint": ell(404, 748, 36, 12, 16),
     "note": "Only its top shows above the table; base row estimated from the chair's height (about 160 rows at this distance)."},
    {"id": "chair-back-2", "label": "Green chair, back row, second", "footprint": ell(541, 748, 36, 12, 16), "note": "As above."},
    {"id": "chair-back-3", "label": "Green chair, back row, third", "footprint": ell(762, 750, 36, 12, 16), "note": "As above."},
    {"id": "chair-right-middle", "label": "Green chair, right middle", "footprint": ell(796, 848, 60, 22, 20),
     "note": "Shell bottom read off a 2.4x close-up: left (737,847), right (855,845), bottom (820,864)."},
    {"id": "chair-right-back", "label": "Green chair, right back", "footprint": ell(892, 796, 36, 12, 16),
     "note": "Shell bottom (874-916, 799-805)."},
]

OUTLINE_FIXES["dressing_room/wide"] = {
    "sofa-foreground": ([[152, 1023], [152, 949], [151, 891], [160, 870], [187, 850], [212, 842], [258, 841], [321, 850], [392, 867],
                         [440, 893], [470, 891], [500, 889], [560, 892], [622, 895], [680, 908], [711, 922], [756, 945], [778, 941],
                         [889, 939], [1000, 950], [1078, 980], [1111, 962], [1178, 953], [1211, 960], [1228, 985], [1228, 1023]],
                        "The automatic cut-out had also taken in the coffee table's front and legs (a spill along rows 804-869), "
                        "which would have been painted over an avatar standing in front of the table. Re-traced along the sofa's own top edge."),
}


# ── studio, fixed sets (1024x1024, camera high above the floor, LOW confidence) ───────────────────────────────
# All read off a 2.8x close-up whose top-left is source pixel (300, 500).
_SF = lambda pts: zoomed(300, 500, 2.8, pts)
_hex_top = [(445, 230), (465, 190), (520, 165), (610, 165), (665, 190), (690, 235), (665, 265), (610, 285), (520, 285), (465, 265)]
_hex_floor = [(445, 295), (465, 255), (520, 230), (610, 230), (665, 255), (690, 300), (665, 330), (610, 350), (520, 350), (465, 330)]
FOOTPRINTS["studio_fixedsets/main"] = {
    # The curved news desk: its floor contact runs along the bottom of the wooden front; about 2 ft deep, which at this distance is
    # about 85 close-up px sideways (the glass table's top and floor patch are 65 close-up px apart for a 30 in high table).
    "round-desk": _SF([(95, 150), (72, 230), (68, 300), (95, 420), (140, 500), (200, 560), (300, 600), (450, 610), (560, 605),
                       (585, 580), (595, 540),
                       (540, 480), (540, 520), (520, 540), (450, 545), (340, 535), (270, 510), (215, 470), (180, 410), (160, 310),
                       (165, 235), (185, 150)]),
}
OUTLINES["studio_fixedsets/main"] = {
    "round-desk": {
        "points": _SF([(95, 140), (130, 110), (210, 60), (330, 45), (440, 38), (475, 65), (440, 110), (400, 150), (330, 185), (250, 235),
                       (215, 255), (300, 265), (435, 300), (436, 395), (595, 395), (598, 470), (590, 590), (550, 610), (450, 615),
                       (300, 605), (190, 565), (120, 500), (92, 420), (70, 320), (72, 250), (90, 180)]),
        "base_y": 718,
        "note": "Hand-traced 2026-10-18 on a 2.8x close-up: the desk, its three monitors and the figurines on it.",
    },
    "glass-table": {
        "label": "Glass hexagonal table",
        "points": _SF(hull(_hex_top, _hex_floor)),
        "base_y": 625,
        "note": "Hand-traced 2026-10-18: the glowing top (an octagon) and the same octagon 65 close-up px lower where the table meets the floor.",
    },
    "teal-sofa-back": {
        "label": "Teal sofa, back of the set",
        "points": _SF([(610, 90), (650, 60), (700, 55), (790, 70), (850, 100), (855, 150), (830, 190), (780, 205), (720, 195), (660, 175), (620, 150)]),
        "base_y": 568,
        "note": "Hand-traced 2026-10-18: the whole visible body; the floor behind it is hidden, so it is solid.",
    },
}
BLOCKERS["studio_fixedsets/main"] = [
    {"id": "red-chair-1", "label": "Red chair, left", "footprint": ell(418, 586, 20, 8, 16), "note": "Legs end about row 586."},
    {"id": "red-chair-2", "label": "Red chair, right", "footprint": ell(455, 566, 20, 8, 16), "note": "Legs end about row 566."},
    {"id": "camera-tripod-left", "label": "Camera on a tripod, left patch",
     "footprint": [[84, 658], [100, 650], [150, 665], [158, 678], [120, 686], [96, 676]],
     "note": "Three feet at about (87,660), (118,681) and (154,677) read off a 2.8x close-up; the camera sits above the middle. The left patch is dark and cluttered, so this is rough."},
    {"id": "brass-light-left", "label": "Brass studio light on a stand, left patch", "footprint": ell(214, 682, 20, 8, 16),
     "note": "Base plate of the stand under the big brass light. The oval dish to its right I could not identify, so it is not cut out."},
    {"id": "brass-light-right", "label": "Brass studio light, right", "footprint": ell(655, 725, 26, 10, 16),
     "note": "The big drum light at the right edge of the platform; base read off a 2.8x close-up."},
    {"id": "corridor-lamp-post", "label": "Lamp post in the corridor", "footprint": ell(508, 968, 14, 6, 16),
     "note": "Standing in the middle of the corridor at the bottom; its base plate is about 28 px wide."},
]
FOOTPRINT_FROM_OUTLINE = {"studio_fixedsets/main": ["teal-sofa", "teal-sofa-back"]}

FOOTPRINTS["studio_fixedsets/main"]["glass-table"] = _SF(_hex_floor)

OUTLINE_FIXES["studio_fixedsets/main"] = {
    "teal-sofa": (_SF([(680, 335), (695, 322), (745, 318), (780, 335), (830, 330), (845, 310), (850, 270), (840, 240), (870, 215), (890, 185),
                       (930, 170), (970, 185), (990, 215), (1005, 300), (990, 360), (950, 415), (895, 455), (830, 482), (770, 480),
                       (712, 465), (682, 430)]),
                  "The automatic cut-out had also taken in part of the other teal sofa behind it. Re-traced on a 2.8x close-up: the curved sofa only."),
}


# ── studio, director's chair view (1024x768, horizon row 380, eye 62 in, fair) ────────────────────────────────
# The chair and cart: read off a 4x close-up whose top-left is source pixel (270, 480).
_chair_q = [[427, 595], [466, 619], [531, 596], [492, 572]]     # the four feet of the director's chair, pushed out 4 px
_cart_q = [[390, 556], [413, 582], [463, 570], [452, 548]]      # the cart's casters (front-left wheel, rear-left wheel read; right side estimated)
_TD = lambda pts: zoomed(0, 420, 3.4, pts)                       # 3.4x close-up of the left equipment table, top-left (0, 420)
FOOTPRINTS["studio_director/main"] = {
    "chair-and-cart": hull(_chair_q, _cart_q),
    "stool": ell(335, 538, 25, 13, 18),
}
OUTLINES["studio_director/main"] = {
    "table-left": {
        "union": [_TD([(0, 150), (235, 112), (430, 90), (560, 100), (622, 120), (600, 190), (420, 262), (330, 350), (250, 405), (120, 420), (0, 425)]),
                  _TD([(100, 425), (150, 425), (150, 860), (130, 866), (100, 430)]), _TD([(30, 862), (245, 850), (248, 872), (30, 880)]),
                  _TD([(270, 420), (305, 420), (305, 560), (270, 560)]), _TD([(230, 570), (470, 545), (480, 585), (235, 595)]),
                  _TD([(405, 260), (440, 260), (440, 545), (405, 545)]), _TD([(545, 200), (580, 200), (580, 385), (545, 385)]),
                  _TD([(470, 380), (600, 380), (605, 410), (470, 410)])],
        "base_y": 680,
        "note": "Hand-traced 2026-10-18 on a 3.4x close-up: the table top with what stands on it, and its four legs with their foot bars.",
    },
}
BLOCKERS["studio_director/main"] = [
    {"id": "equipment-table-floor", "label": "Equipment table at the left (the floor under it)",
     "footprint": [[0, 676], [75, 676], [138, 594], [178, 542], [178, 520], [120, 545], [60, 575], [0, 600]],
     "note": "Foot bars at rows 673, 590 and 536 read off a 3.4x close-up; the table runs off the left edge."},
    {"id": "equipment-case", "label": "Equipment case on the floor", "footprint": _TD([(612, 558), (810, 548), (858, 520), (700, 520)]),
     "note": "A flat case about 8 in deep; front edge read off the close-up, back edge is the top's far edge lowered by the case's height."},
    {"id": "light-stand-left", "label": "Light stand with a monitor, left", "footprint": ell(295, 515, 26, 9, 16), "note": "Base ring of the stand, rough."},
    {"id": "camera-tripod-back", "label": "Camera tripod at the back", "footprint": ell(488, 432, 14, 5, 12), "note": "Its feet, rough: it sits right at the back edge of the floor."},
    {"id": "light-stand-right", "label": "Light stand with the sign, right", "footprint": ell(858, 456, 18, 6, 12), "note": "Base of the stand under the HOLLYLAND sign, rough."},
]


# ── vortex bar (1024x1024, low confidence: the whirlpool is paint on a normal floor, Josie) ───────────────────
def _clip(pts, w=1023, h=1023):
    return [[min(max(x, 0), w), min(max(y, 0), h)] for x, y in pts]


# The three bar stools: each is seat and back, a pole, a foot ring (about 8 in up, drawn here as a filled oval) and a brass base disc.
# Read off 2.2x and 2.6x close-ups. The stool behind the left one shows only its backrest (x 704-756, rows 512-571), well off the green, so it is not cut out.
_stool1 = [
    [[668, 537], [684, 532], [700, 548], [727, 598], [756, 616], [770, 639], [768, 662], [738, 675], [706, 662], [693, 639], [679, 598], [670, 562]],
    [[729, 668], [742, 668], [742, 758], [729, 758]], ell(737, 725, 33, 15, 20), ell(732, 768, 40, 15, 20)]
_stool2 = [
    [[740, 612], [756, 603], [772, 616], [779, 653], [802, 660], [834, 655], [861, 660], [865, 680], [863, 703], [852, 716], [811, 728],
     [770, 721], [752, 707], [743, 671]],
    [[798, 722], [816, 722], [816, 845], [798, 845]], ell(804, 800, 43, 19, 20), ell(797, 860, 46, 19, 20)]
_stool3 = [
    [[883, 676], [900, 664], [935, 664], [960, 676], [985, 712], [1002, 770], [1023, 805], [1023, 845], [985, 850], [940, 842], [905, 822],
     [895, 790], [888, 730]],
    [[972, 840], [1006, 840], [1006, 990], [972, 990]], _clip(ell(977, 958, 52, 28, 24)), _clip(ell(985, 1008, 50, 18, 20))]
# The counter: its lower edge is the brass foot rail (lower edge read at (840,824), (880,858), (920,894), (960,922)). The floor contact is taken
# 12 px below the rail: the picture draws floor tiles right under the rail, so the true line could be 15 px higher or lower. My reading.
_rail_low = [[790, 790], [840, 824], [880, 858], [920, 894], [960, 922], [1023, 952]]
_counter_front = [[790, 802], [840, 836], [880, 870], [920, 906], [960, 934], [1023, 964]]
FOOTPRINTS["vortex_bar/main"] = {
    "bar-counter": [[777, 745]] + _counter_front + [[1023, 924], [960, 894], [920, 866], [880, 830], [840, 796], [790, 762]],
    "stool-1": ell(732, 768, 40, 15, 20),
    "stool-2": ell(797, 860, 46, 19, 20),
    "stool-3": _clip(ell(985, 1008, 50, 18, 20)),
}
OUTLINE_FIXES["vortex_bar/main"] = {
    "bar-counter": ([[743, 503], [765, 496], [804, 496], [809, 509], [847, 525], [902, 544], [1023, 578], [1023, 952], [960, 922], [920, 894],
                     [880, 858], [840, 824], [790, 790], [775, 745], [772, 700], [768, 640], [764, 580], [757, 530]],
                    "Hand-traced 2026-10-18 on 2.2x close-ups: the brass top, the panelled front and the foot rail. The first automatic cut-out ran over floor tiles and the stools."),
}
OUTLINES["vortex_bar/main"] = {
    "stool-1": {"label": "Bar stool, left (farthest)", "union": _stool1, "base_y": 783,
                "note": "Hand-traced 2026-10-18 on a 2.2x close-up: seat and back, pole, foot ring (filled in) and brass base."},
    "stool-2": {"label": "Bar stool, middle", "union": _stool2, "base_y": 879,
                "note": "Hand-traced 2026-10-18 on a 2.2x close-up: seat and back, pole, foot ring (filled in) and brass base."},
    "stool-3": {"label": "Bar stool, right (nearest the camera)", "union": _stool3, "base_y": 1022,
                "note": "Hand-traced 2026-10-18 on a 2.6x close-up; its brass base runs off the bottom of the picture."},
    # The striped booths at the left: backrests, seats, the tables between them and their dark bases, as one cluster. The picture's
    # lower edge of the cluster is where it meets the floor tiles (read off 3x and 3.8x close-ups).
    "booths": {
        "points": [[0, 546], [20, 540], [60, 535], [85, 528], [95, 513], [130, 508], [300, 503], [320, 490], [345, 486], [416, 486], [421, 500],
                   [420, 555], [426, 585], [432, 600], [400, 625], [372, 645], [345, 655], [300, 668], [250, 670], [232, 675], [225, 700],
                   [215, 722], [180, 748], [140, 772], [100, 792], [50, 800], [0, 806]],
        "base_y": 806,
        "note": "Hand-traced 2026-10-18: all three booths with their tables as one piece. The floor behind them is hidden, so it is solid.",
    },
}
FOOTPRINTS["vortex_bar/main"]["booths"] = [[0, 776], [50, 770], [100, 762], [140, 742], [180, 718], [215, 693], [225, 670], [232, 645], [250, 641],
                                           [300, 639], [345, 626], [372, 616], [400, 595], [432, 570], [432, 600], [400, 625], [372, 645],
                                           [345, 655], [300, 668], [250, 670], [232, 675], [225, 700], [215, 722], [180, 748], [140, 772],
                                           [100, 792], [50, 800], [0, 806]]


# ── basement bar (1024x1536, low confidence) ────────────────────────────────────────────────────────────────
# Folding chairs. Each outline is the back and seat (read off 3x to 4.4x close-ups) plus the legs I could see. A chair's feet are mostly hidden
# in the dark, so each footprint is four feet: the lowest leg tips where I could read them, otherwise the seat's front corners dropped by the
# leg length seen on the clear chairs (about 34 px at row 775, 62 px at row 880) with the back feet one chair-depth (about 0.55 x the width)
# further up. Rough: the true feet could be 10-15 px off.
def _leg(x0, y0, x1, y1, w=6):
    return [[x0 - w // 2, y0], [x0 + w // 2, y0], [x1 + w // 2, y1], [x1 - w // 2, y1]]


_chairs = {
    "chair-back-1": ("Folding chair, back row, 1 (left)", 773,
        [[[533, 676], [545, 669], [570, 674], [582, 688], [592, 716], [600, 744], [560, 746], [540, 744], [535, 712]]],
        [[544, 771], [609, 773], [616, 742], [551, 740]]),
    "chair-back-2": ("Folding chair, back row, 2", 808,
        [[[608, 696], [620, 690], [655, 692], [672, 700], [680, 725], [686, 750], [684, 770], [680, 778], [618, 774], [612, 740], [608, 712]],
         _leg(684, 776, 686, 809)],
        [[614, 802], [686, 809], [694, 775], [622, 768]]),
    "chair-back-3": ("Folding chair, back row, 3", 814,
        [[[691, 709], [705, 705], [740, 707], [758, 714], [764, 730], [766, 760], [766, 780], [692, 776], [688, 745], [689, 718]]],
        [[687, 807], [767, 814], [775, 774], [695, 767]]),
    "chair-back-4": ("Folding chair, back row, 4", 829,
        [[[814, 723], [830, 720], [870, 721], [890, 730], [892, 745], [886, 765], [884, 780], [881, 792], [850, 795], [815, 792], [808, 786],
          [803, 768], [808, 740]]],
        [[803, 825], [885, 829], [893, 789], [811, 785]]),
    "chair-back-5": ("Folding chair, back row, 5 (right, by the wall)", 834,
        [[[912, 726], [930, 721], [965, 720], [979, 725], [979, 755], [975, 775], [965, 790], [962, 796], [920, 796], [893, 792], [890, 780],
          [897, 760], [905, 735]]],
        [[888, 829], [966, 834], [974, 796], [896, 791]]),
    "chair-mid-1": ("Folding chair, second row, left", 870,
        [[[478, 719], [497, 721], [523, 726], [540, 733], [555, 747], [568, 772], [573, 787], [571, 802], [555, 807], [523, 803], [503, 801],
          [490, 790], [485, 757]],
         _leg(484, 790, 485, 845), _leg(559, 803, 565, 869)],
        [[486, 846], [566, 870], [576, 830], [496, 806]]),
    "chair-mid-2": ("Folding chair, second row, right", 872,
        [[[567, 745], [580, 741], [615, 741], [636, 749], [647, 775], [660, 800], [666, 815], [662, 820], [620, 826], [578, 829], [572, 805],
          [571, 775]],
         _leg(571, 828, 568, 872), _leg(658, 815, 665, 858)],
        [[565, 872], [667, 858], [678, 806], [576, 820]]),
    "chair-front-1": ("Folding chair, front row, left", 942,
        [[[729, 783], [745, 778], [790, 779], [822, 790], [830, 810], [830, 840], [822, 865], [820, 882], [790, 882], [750, 875], [725, 868],
          [723, 830], [725, 800]],
         _leg(725, 866, 709, 922), _leg(812, 880, 799, 941)],
        [[708, 923], [799, 942], [807, 894], [716, 875]]),
    "chair-left-1": ("Folding chair at the head of the stairs, left", 1028,
        [[[426, 884], [445, 880], [500, 880], [525, 886], [532, 905], [540, 938], [545, 966], [500, 972], [440, 968], [426, 962], [428, 930],
          [426, 900]],
         _leg(540, 966, 535, 1026), _leg(430, 966, 428, 1010)],
        [[428, 1012], [536, 1028], [546, 985], [438, 968]]),
    "chair-front-2": ("Folding chair, front row, right", 946,
        [[[858, 799], [880, 797], [930, 800], [958, 806], [966, 822], [966, 845], [950, 872], [946, 884], [900, 888], [850, 880], [844, 872],
          [850, 840], [854, 810]],
         _leg(843, 878, 833, 944), _leg(947, 876, 931, 944)],
        [[832, 946], [930, 946], [938, 896], [840, 896]]),
}
OUTLINES["basement_bar/main"] = {cid: {"label": lab, "union": parts, "base_y": by,
                                       "note": "Hand-traced 2026-10-18 on 3-4.4x close-ups: back, seat and the legs I could see. The floor under a chair is mostly hidden, so the chair is solid."}
                                 for cid, (lab, by, parts, fp) in _chairs.items()}
FOOTPRINTS["basement_bar/main"] = {cid: fp for cid, (lab, by, parts, fp) in _chairs.items()}
# The candlelit table: tabletop (ellipse about 186 x 104 px, centre (378,853)) and its fold-up base, read off a 2.8x close-up. The automatic cut-out only
# found the candle's glow. The foot ring is a guess from the table's height (about 30 in = 90 px below the top at this distance).
_tbl_top = ell(378, 853, 93, 52, 40)
_tbl_feet = ell(385, 945, 58, 20, 24)
OUTLINE_FIXES["basement_bar/main"] = {
    "round-table": (hull(_tbl_top, _tbl_feet),
                    "Hand-traced 2026-10-18: the whole tabletop and its legs down to a foot ring I estimated; the first automatic cut-out only found the candle's glow."),
}
FOOTPRINTS["basement_bar/main"]["round-table"] = _tbl_feet


# ── lobby (1024x565, low confidence) ─────────────────────────────────────────────────────────────────────────
# The round fountain bar: a drum whose top rim is an ellipse about 276 x 31 px (x 555-832, rows 357-388). The foot is the same ellipse
# lower down, ending at the front at about row 450 (read off a 2.8x close-up where the base meets the floor). The floor behind the far side
# (rows 372-417) is hidden by the bar, so it stays walkable and is shown striped, like any walk-behind.
_bar_foot = ell(693, 433, 138, 17, 48)
FOOTPRINTS["lobby/main"] = {"fountain-bar": _bar_foot}
OUTLINES["lobby/main"] = {
    "fountain-bar": {
        "points": [[556, 372], [558, 400], [562, 425], [580, 438], [620, 446], [670, 451], [720, 452], [770, 449], [810, 440], [828, 424],
                   [832, 395], [832, 372], [820, 362], [780, 355], [700, 350], [620, 352], [575, 360]],
        "base_y": 450,
        "note": "Hand-traced 2026-10-18 on a 2.8x close-up: the drum with its top rim; the fountain's glow above it is background.",
    },
}
# The stools round the bar: each pole ends in a small base disc; the discs are tiny at this size (about 26 px wide), and I could read the
# pole bottoms only roughly in this low-resolution picture, so these are rough.
BLOCKERS["lobby/main"] = [
    {"id": f"stool-{i}", "label": "Bar stool", "footprint": ell(x, y, 13, 5, 12),
     "note": "Base of the stool; position read from where the pole ends, within about 8 px."}
    for i, (x, y) in enumerate([(552, 430), (567, 446), (627, 457), (710, 448), (802, 441), (836, 428)], 1)
]


# ── palace hallway (1408x768, camera horizon row 350, eye 62 in, fair) ────────────────────────────────────────
# Concession counter at the left: its long glass front recedes to the right, so its floor line runs from about (272,601) up to (540,491); the end
# panel at the left runs back from (272,601) to about (190,592). Read off 1.5x close-ups; the back right corner is the front right corner moved
# back by the end panel's direction.
_hall_counter_fp = [[190, 592], [272, 601], [330, 577], [400, 548], [470, 519], [540, 491], [458, 482], [380, 485], [300, 490], [215, 498]]
_pedestal = ell(811, 492, 40, 15, 28)
FOOTPRINTS["palace_hallway/main"] = {
    "concession-counter": _hall_counter_fp,
    "statue": _pedestal,
    "ticket-booth": [[1085, 470], [1090, 560], [1096, 598], [1185, 634], [1260, 628], [1307, 617], [1307, 540], [1190, 500]],
    "small-booth": [[979, 440], [1069, 466], [1070, 450], [985, 426]],
}
OUTLINE_FIXES["palace_hallway/main"] = {
    "concession-counter": ([[190, 442], [300, 437], [320, 436], [324, 408], [338, 394], [352, 400], [354, 418], [433, 411], [450, 414], [527, 421],
                            [545, 425], [548, 470], [545, 492], [470, 521], [400, 550], [330, 580], [272, 604], [190, 596], [175, 560],
                            [180, 500], [188, 460]],
                           "Re-traced 2026-10-18 on a 1.5x close-up: the first automatic cut-out cut across the front and left the base out. Includes the till and goods on top."),
}
OUTLINES["palace_hallway/main"] = {
    "statue": {
        "union": [[[788, 258], [795, 246], [808, 245], [816, 258], [816, 282], [832, 292], [838, 320], [836, 345], [830, 380], [825, 420], [824, 448],
                   [842, 462], [775, 462], [775, 448], [769, 420], [768, 385], [775, 350], [772, 335], [773, 308], [776, 292], [786, 282]],
                  [[771, 470], [775, 462], [810, 455], [846, 463], [850, 478], [848, 497], [830, 505], [810, 508], [790, 505], [772, 497]]],
        "base_y": 507,
        "note": "Hand-traced 2026-10-18 on a 3x close-up: the statue with the film reel and her round plinth. The floor behind the plinth is hidden by it.",
    },
    "ticket-booth": {
        "points": [[1087, 262], [1100, 255], [1120, 222], [1145, 218], [1165, 250], [1195, 238], [1310, 236], [1318, 250], [1316, 540], [1308, 617],
                   [1260, 628], [1185, 634], [1096, 600], [1088, 520], [1084, 455]],
        "base_y": 634,
        "note": "Hand-traced 2026-10-18 on 1.9x close-ups: the big octagonal booth from its roof finial down to its plinth.",
    },
    "small-booth": {
        "points": [[972, 300], [985, 285], [1000, 278], [1072, 288], [1074, 330], [1072, 460], [1069, 468], [979, 442], [974, 400]],
        "base_y": 468,
        "note": "Hand-traced 2026-10-18 on a 1.9x close-up.",
    },
}
BLOCKERS["palace_hallway/main"] = [
    {"id": "bin-right", "label": "Dark bin at the right edge", "footprint": [[1306, 568], [1408, 568], [1408, 768], [1306, 768]],
     "note": "A tall dark bin that runs off the bottom and right edge of the picture; I read it as a solid in the foreground."},
    {"id": "dust-pan", "label": "Dust pan on the floor", "footprint": [[1229, 744], [1274, 708], [1316, 727], [1300, 762], [1260, 764]],
     "note": "A tilted tray lying on the floor, read off a 3.5x close-up."},
]


# ── control room (1024x687, horizon row 242, eye 75 in, fair) ───────────────────────────────────────────────
# Read off 2x to 2.6x close-ups. The dais is a three-step round platform with a curved console wall and the director's chair on it; its lowest
# step's front edge is the floor line, the back half of its footprint is hidden behind it. The two back-wall console groups stand against the wall,
# so only their base strips are cut out. The right desk's left front leg ends at (795,481); its right legs are behind the door frame.
_dais_front = [[366, 405], [372, 432], [385, 452], [410, 464], [450, 468], [520, 469], [590, 466], [640, 455], [690, 441], [698, 420]]
FOOTPRINTS["control_room/main"] = {
    "dais": _dais_front + [[700, 380], [695, 345], [450, 335], [380, 345], [366, 370]],
    "console-left": [[238, 376], [300, 380], [372, 374], [376, 335], [300, 332], [240, 338]],
    "console-right": [[758, 368], [884, 386], [946, 389], [950, 345], [884, 340], [760, 335]],
    "desk-right": [[792, 481], [978, 505], [982, 430], [800, 405]],
    "desk-chair": [[858, 528], [928, 534], [932, 495], [862, 490]],
    "desk-left": [[62, 395], [198, 398], [200, 350], [64, 348]],
    "desk-left-chair": [[138, 404], [196, 408], [200, 375], [142, 370]],
}
OUTLINES["control_room/main"] = {
    "dais": {
        "points": _dais_front + [[700, 380], [692, 330], [668, 300], [640, 285], [600, 280], [560, 272], [525, 262], [500, 258], [470, 262], [440, 268],
                                 [430, 285], [395, 292], [372, 320], [364, 370]],
        "base_y": 469,
        "note": "Hand-traced 2026-10-18 on a 2.1x close-up: the three steps, the curved console wall and the director's chair on top.",
    },
    "console-left": {
        "points": [[238, 300], [250, 285], [262, 276], [300, 275], [340, 282], [380, 282], [430, 285], [448, 300], [440, 330], [380, 345], [376, 374],
                   [300, 380], [238, 376]],
        "base_y": 380,
        "note": "Hand-traced 2026-10-18 on a 2x close-up: the console group at the back left; its middle is open under the desk top but it stands against the wall.",
    },
    "console-right": {
        "union": [[[747, 310], [775, 296], [780, 272], [930, 272], [945, 300], [946, 389], [884, 386], [760, 368], [748, 330]],
                  [[776, 314], [800, 310], [836, 316], [842, 350], [838, 385], [812, 392], [790, 385], [780, 350]]],
        "base_y": 392,
        "note": "Hand-traced 2026-10-18 on a 2.6x close-up: the console group at the back right with the operator's chair beside it.",
    },
    "desk-right": {
        "union": [[[790, 383], [985, 385], [985, 447], [792, 430]], [[789, 428], [800, 428], [799, 481], [790, 481]], [[940, 338], [985, 338], [985, 405], [940, 405]]],
        "base_y": 505, "label": "Writing desk, right, with its lamp",
        "note": "Hand-traced 2026-10-18 on a 2.6x close-up: the top, its left front leg and the lamp; the rest of the legs are in shadow or behind the door frame.",
    },
    "desk-chair": {
        "points": [[853, 402], [870, 398], [910, 400], [915, 455], [932, 462], [935, 482], [928, 490], [925, 525], [915, 533], [870, 525], [862, 490], [858, 455]],
        "base_y": 534, "label": "Chair at the right desk",
        "note": "Hand-traced 2026-10-18 on a 2.6x close-up.",
    },
    "desk-left": {
        "union": [[[62, 327], [200, 326], [202, 345], [62, 346]], [[62, 345], [76, 345], [70, 398], [62, 398]], [[190, 345], [204, 345], [198, 398], [190, 398]],
                  [[100, 280], [135, 280], [135, 326], [100, 326]]],
        "base_y": 398, "label": "Small desk, left, with its lamp",
        "note": "Hand-traced 2026-10-18 on a 2x close-up: the top, its two front legs and the lamp.",
    },
    "desk-left-chair": {
        "points": [[138, 322], [190, 320], [195, 372], [196, 396], [190, 402], [145, 400], [138, 372]],
        "base_y": 408, "label": "Chair at the small desk",
        "note": "Hand-traced 2026-10-18 on a 2x close-up.",
    },
}


# ── studio, far shot (1024x1024, horizon row 315, eye 232 in, fair) ────────────────────────────────────────
# The floor is very dark; this was traced on a brightened copy of the picture (gamma 0.45) at 2x to 2.8x. Positions are within about 10 px.
# The control desk at the back left has two seated operators in red chairs; desk, chairs and people are one solid. The green's top edge runs along
# their bases (the strip below is the red band).
_so_desk_fp = [[338, 598], [338, 640], [375, 650], [425, 655], [455, 640], [470, 625], [500, 625], [510, 600], [500, 590], [340, 590]]
FOOTPRINTS["studio_overlook/main"] = {"control-desk": _so_desk_fp, "lamp-post": ell(307, 857, 25, 10, 20), "palm": ell(535, 583, 16, 7, 14)}
OUTLINES["studio_overlook/main"] = {
    "control-desk": {
        "label": "Control desk at the back left, with its operators",
        "points": [[335, 522], [360, 508], [400, 502], [450, 500], [500, 506], [512, 540], [510, 585], [510, 612], [500, 626], [470, 628], [455, 642],
                   [425, 656], [375, 652], [338, 642], [336, 600], [335, 560]],
        "base_y": 656,
        "note": "Hand-traced 2026-10-18 on a 2.8x close-up of a brightened copy: the desk with its monitors, the cabinet, two chairs and the two seated people.",
    },
    "lamp-post": {
        "label": "Tall lamp post",
        "union": [[[296, 592], [305, 592], [311, 850], [301, 850]], [[283, 562], [313, 562], [313, 600], [283, 600]], [[282, 846], [332, 846], [332, 870], [282, 870]]],
        "base_y": 867,
        "note": "Hand-traced 2026-10-18: a very tall thin lamp post from its base at the bottom to the lamp head at the top; the picture is a steep high view.",
    },
    "palm": {
        "label": "Palm in a pot",
        "points": [[505, 520], [540, 505], [575, 515], [590, 545], [575, 575], [548, 590], [525, 592], [510, 575]],
        "base_y": 590,
        "note": "Hand-traced 2026-10-18: the whole palm and its pot, against the glass wall.",
    },
}
BLOCKERS["studio_overlook/main"] = [
    {"id": "small-pot", "label": "Small pot", "footprint": ell(330, 880, 15, 9, 12), "note": "Brightened copy, 2x close-up."},
    {"id": "ornament", "label": "Ornament on the floor", "footprint": ell(407, 922, 26, 10, 14), "note": "A tall decorative piece with flowers; base read off a 2x close-up."},
    {"id": "floor-lamp", "label": "Glowing lamp on the floor", "footprint": ell(456, 903, 14, 5, 12), "note": "Brightened copy, 2x close-up."},
    {"id": "small-urn", "label": "Small urn", "footprint": ell(490, 904, 13, 6, 12), "note": "Brightened copy, 2x close-up."},
    {"id": "barrel-table", "label": "Round pedestal table", "footprint": ell(481, 983, 30, 11, 16), "note": "Round table with a bowl; bottom read off a 2x close-up."},
    {"id": "crates", "label": "Stack of crates, bottom left",
     "footprint": [[250, 985], [280, 945], [300, 918], [335, 912], [345, 925], [350, 950], [360, 975], [340, 1000], [300, 1020], [255, 1020]],
     "note": "Brightened copy, 2x close-up; the stack runs off the left of the green."},
    {"id": "glass-urn", "label": "Glass urn on a stand", "footprint": ell(906, 968, 22, 8, 14), "note": "Brightened copy, 2.4x close-up."},
    {"id": "coil-basket", "label": "Coiled basket", "footprint": _clip(ell(846, 995, 28, 14, 16)), "note": "Runs off the bottom of the green."},
    {"id": "boxes-right", "label": "Boxes at the right edge", "footprint": [[948, 926], [1015, 926], [1015, 1005], [950, 1005]],
     "note": "Dark stack of boxes beside the glass wall; the green ran 15-30 px over them."},
]


# ── studio set (foreground consoles): both stand along the bottom edges of the picture and are always in front of the avatar ──────────
OUTLINES["studio_fixedsets/main"].update({
    "console-left": {
        "points": [[136, 689], [240, 690], [350, 712], [356, 760], [378, 810], [376, 880], [372, 945], [325, 955], [285, 925], [262, 880], [200, 862],
                   [165, 900], [125, 900], [85, 880], [72, 830], [78, 790], [100, 765], [78, 755], [100, 745], [136, 745]],
        "always": True, "base_y": None,
        "note": "Hand-traced 2026-10-18 on a 2.4x close-up: the foreground control console with its operator, bottom left. It is in front of everything, so it is not cut out of the floor (the floor never reaches it).",
    },
    "console-right": {
        "points": [[592, 812], [603, 758], [640, 744], [682, 722], [740, 705], [807, 682], [873, 680], [878, 722], [905, 752], [940, 778], [946, 830],
                   [930, 870], [880, 885], [850, 850], [800, 830], [740, 860], [690, 900], [660, 950], [622, 955], [604, 893]],
        "always": True, "base_y": None,
        "note": "Hand-traced 2026-10-18 on 2.4x close-ups: the foreground control console with its operator, bottom right. The green's right edge now follows its left edge.",
    },
})


# ── monument entrance, day (1536x1024, low confidence): the four park benches, two on each plaza ─────────────────────────────────
# Read off 3x close-ups. Each bench's visible feet are read; the hidden feet are the missing corners of the same parallelogram.
_mon_fp = {
    "bench-left-1": [[160, 758], [238, 771], [288, 757], [210, 741]],
    "bench-left-2": [[274, 780], [369, 798], [430, 785], [432, 748], [380, 752], [288, 757]],
    "bench-right-1": [[1108, 785], [1164, 802], [1260, 782], [1262, 748], [1207, 757], [1128, 752]],
    "bench-right-2": [[1292, 773], [1373, 758], [1376, 730], [1325, 741], [1258, 742]],
}
_mon_out = {
    "bench-left-1": ("Park bench, left plaza, 1",
                     [[155, 677], [238, 687], [241, 730], [278, 727], [285, 740], [240, 772], [236, 772], [212, 745], [165, 758], [160, 757], [170, 722], [158, 700]]),
    "bench-left-2": ("Park bench, left plaza, 2",
                     [[268, 695], [371, 722], [375, 738], [425, 730], [432, 740], [430, 785], [424, 783], [372, 762], [370, 797], [364, 797], [350, 765],
                      [290, 758], [278, 780], [272, 780], [280, 740], [270, 712]]),
    "bench-right-1": ("Park bench, right plaza, 1",
                      [[1108, 730], [1118, 725], [1167, 708], [1263, 693], [1265, 740], [1262, 782], [1256, 782], [1245, 752], [1210, 760], [1207, 762],
                       [1170, 800], [1160, 802], [1157, 765], [1115, 785], [1108, 784], [1108, 745]]),
    "bench-right-2": ("Park bench, right plaza, 2",
                      [[1258, 712], [1297, 682], [1377, 677], [1378, 725], [1373, 758], [1366, 758], [1330, 742], [1325, 745], [1300, 773], [1293, 773],
                       [1292, 745], [1262, 740]]),
}
OUTLINES["monument/day"] = {bid: {"label": lab, "points": pts, "base_y": max(y for _, y in _mon_fp[bid]),
                                  "note": "Hand-traced 2026-10-18 on a 3x close-up: the back, seat, arm and legs."}
                            for bid, (lab, pts) in _mon_out.items()}
FOOTPRINTS["monument/day"] = _mon_fp
