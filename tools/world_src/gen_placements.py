"""One-off generator for data/world/placements.json (first-pass proposals).
Positions are source-picture pixels. 'proposed' = placed by Claude by eye, needs Josie's approval.
Door/hotspot positions taken from Josie's Level Annotator exports are marked 'confirmed'."""
import json, math, sys
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))           # tools/world_src
_os.chdir(_os.path.dirname(_os.path.dirname(_HERE)))           # run from the repo root whatever the cwd
sys.path.insert(0, '.')
from modules import pubcast_world as W

K = 0.846354  # display->source for the 1536x1024 sheets read at display scale

def d2s(poly):
    return [[round(x / K), round(y / K)] for x, y in poly]

def ellipse(cx, cy, rx, ry, n=16):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]

def mirror(poly, w=1300):
    return [(w - x, y) for x, y in reversed(poly)]

def zone(zid, pts, kind="floor", level="main", z_in=0, rise_in=None, axis=None, note="", estimated=False):
    """estimated=True: the height numbers on this zone are MY estimate, not Josie's; they are listed as open questions."""
    z = {"id": zid, "kind": kind, "level": level, "z_in": z_in, "points": pts}
    if estimated: z["estimated"] = True
    if kind != "floor":
        z["axis"] = axis; z["rise_in"] = rise_in
    if note: z["note"] = note
    return z

def flat(polys):
    """Plain flat floor polygons -> zones at the picture's base level."""
    return [zone("floor" if i == 0 else f"floor-{i+1}", p) for i, p in enumerate(polys)]

def view(status="proposed", scale=None, floor=None, zones=None, doors=None, hotspots=None, notes="", pad_status="proposed"):
    """status = the whole picture (pads, size, doors); pad_status = only the walkable outlines, which Josie
    approves on their own after seeing them filled in on the picture."""
    zs = zones if zones is not None else flat(floor or [])
    return {"status": status, "pad_status": pad_status, "scale": scale or [], "zones": zs, "occluders": [], "blockers": [], "doors": doors or [], "hotspots": hotspots or [], "notes": notes}

def door(to, at, st="proposed", r=40, group=None, note="", label=None):
    d = {"to": to, "at": list(at), "r": r, "status": st}
    if label: d["label"] = label
    if group: d["group"] = group
    if note: d["note"] = note
    return d

V = {}

# ── monument ────────────────────────────────────────────────────────────────
road_l = [(0,545),(150,495),(300,458),(440,436),(450,452),(330,490),(260,525),(250,625),(120,625),(0,640)]
plaza_l = ellipse(245, 670, 205, 62)
V["monument/day"] = view(
    floor=[d2s(road_l), d2s(plaza_l), d2s(mirror(road_l)), d2s(mirror(plaza_l))],
    doors=[door("parking_lot", (526, 523), note="Far end of the left road, where it runs off behind the monument. Josie (2026-10-18): once you are off back there somewhere, the hotspot triggers and you go back."),
           door("parking_lot", (1010, 523), note="Far end of the right road, the mirror of the left one. My placement: the mirrored spot, not yet seen by Josie.")],
    notes="Floor is the two curving roads and the two bench plazas; the reflecting pool is not walkable. Scale from the lamp posts and benches. "
          "Josie (2026-10-18): the camera looks as if our backs were to the rest of the city and we were driving in, like into Universal Studios; "
          "the roads at the sides go off in the distance behind the monument. This is the end of the world for now: no way out to the rest of Hollywood, only back to the parking lot.")
# Josie (2026-10-27): the monument is daytime only; the three night views were dropped.

# ── parking lot ─────────────────────────────────────────────────────────────
V["parking_lot/main"] = view(
    zones=[zone("lot-slope", [[105,262],[350,292],[360,285],[700,285],[720,300],[1000,320],[1000,350],[940,430],[850,490],[790,560],[700,640],[900,700],[1335,708],[1345,738],[1000,745],[700,740],[640,720],[700,800],[1150,890],[1200,1000],[300,1000],[310,880],[265,700],[250,560],[200,440],[110,330]], kind="ramp", level="lot", z_in=0, rise_in=None, axis=[[300,300],[950,640]], note="The lot slopes: the studio is built into a hill, so the Palace Theater end is higher and the Vortex Bar end is lower. Axis runs from the Palace end to the Vortex end; rise_in is negative (down) and not known yet. The strip along the right (x 900-1345, y 700-745) is the sidewalk in front of the Vortex Bar, added so the bar's door can be reached.")],
    doors=[door("lobby", (265, 252), "confirmed", note="Under the PALACE marquee. Josie (2026-10-18): the Palace Theater is right."),
           door("monument", (300, 1005), note="Bottom of the curving road."),
           door("vortex_bar", (1278, 668), note="Josie (2026-10-18): the Vortex Bar entrance, right in front of the car in the middle of the three parked there. I read it as the glass door with the doorstep, which sits above the middle and right-hand cars; the position is mine.")],
    pad_status="confirmed",
    notes="Aerial view, so avatars are tiny. Tree islands and parked cars are not cut out of the floor yet. "
          "The picture also shows a STAGE I door (about 770,215); no exit goes there yet. "
          "WALKING PATH APPROVED by Josie 2026-10-18 16:37, on the sheet that showed the green outline: \"that's the area that you can walk in\", "
          "\"everything inside that green line\", \"a little bit outside\" is fine too. She also said you can walk behind some of the trees "
          "and, close to the cars, they may cover you up a little. The trees and cars are not cut out as occluders yet.")

# ── Palace ground floor ─────────────────────────────────────────────────────
V["lobby/main"] = view(
    floor=[[[310,430],[330,395],[520,372],[555,370],[835,372],[1024,360],[1024,440],[700,450],[620,500],[600,565],[430,565],[380,500],[330,470]]],
    doors=[door("parking_lot", (375, 350), "confirmed", note="The round vault door in the back: the Palace front door. Josie (2026-10-18): right."),
           door("palace_hallway", (510, 562), "confirmed", note="Very bottom of the picture. Josie (2026-10-18): right, the entrance to the Palace Hall."),
           door("lobby_upstairs", (1018, 400), note="Josie (2026-10-18): off to the right, you go over there and it leads upstairs to the second floor. The right edge of the floor; the exact height on the edge is my choice.")],
    notes="Low-resolution picture (1024 px wide). The central fountain bar is not cut out of the floor.")
V["palace_hallway/main"] = view(
    zones=[zone("floor", [[140,598],[190,594],[272,603],[330,579],[400,550],[470,521],[540,492],[548,414],[720,410],[772,412],[772,442],[925,442],[979,440],[1069,466],[1085,470],[1088,520],[1090,560],[1096,598],[1185,634],[1260,628],[1306,617],[1306,768],[140,768]]),
           zone("stairs-up", [[772,442],[925,442],[915,358],[838,358]], kind="stairs", level="main", z_in=0, rise_in=None, axis=[[850,442],[876,358]], note="The first flight of the stairs on the back wall, behind the statue, straight back from the camera. Josie (2026-10-18): at the very back of the room a stairway leads straight back and up to a little flat plateau, then you turn left and go up more stairs, walking in profile. Only this first flight is outlined: the plateau and the left-turning flight are hidden behind the statue or not drawn, so they are not guessed. Climb height not known yet. Moved 2026-10-18: my first outline sat on the statue, not on the stairs.")],
    doors=[door("lobby", (700, 758), note="Josie (2026-10-18): the bottom of the screen leads back to the lobby. My earlier mark was the open door in the left foreground; I moved it to the bottom."),
           door("palace_theater", (520, 405), note="PARKED. Brown door at the back left; my guess for the auditorium entrance. Josie (2026-10-18): there is no Palace Theater image yet and she does not know if or when it will be used, so this hotspot is not to be worried about now."),
           door("green_room", (876, 366), group="stairs_choice", label="Green Room", note="Josie (2026-10-18): at the very back the character walks up the stairs and, if they go left off screen, gets two options; Green Room first, because almost everybody picks it almost every time. The spot is the top of the first flight, on the back wall: my reading of where they turn left and go off screen; the picture does not show the turn."),
           door("writers_room", (876, 366), group="stairs_choice", label="Writers' Room")],
    notes="Floor edge re-traced 2026-10-18 along the concession counter base, the two ticket booths and the dark bin at the right edge; the statue pedestal and the little dust pan on the floor are cut out of it.")
V["lobby_upstairs/main"] = view(
    floor=[[[0,520],[106,498],[300,478],[520,455],[768,402],[800,411],[830,427],[852,446],[870,474],[882,492],[850,516],[800,552],[750,580],[700,605],[650,633],[600,655],[550,677],[500,700],[450,722],[400,738],[350,760],[300,785],[250,806],[200,830],[150,850],[100,872],[50,895],[0,918]]],
    doors=[door("manager_office", (266, 470), "confirmed", note="Door marked MANAGER. Josie (2026-10-18): right, it is Sir Purfluous's office."),
           door("projection_booth", (712, 400), "confirmed", note="Smaller door beside it. Josie (2026-10-18): right, it is the projection booth."),
           door("lobby", (10, 640), note="Josie (2026-10-18): walking left out of frame takes you back downstairs to the main lobby. The left edge of the floor; the exact height on the edge is my choice.")],
    notes="Walkable part is the upper balcony only (inside the railing); the lobby floor below with the fountain bar is not. Re-traced 2026-10-18: the floor's near edge now follows the TOP EDGE of the curved handrail (before, its right half ran 35-65 px down into the railing). Sofa, armchair and round table are cut out; the handrail is cut out as a foreground piece. OPEN QUESTION for Josie: the floor behind the railing (between the handrail and the rail's base) is not included, so an avatar cannot walk right up to the rail; I do not know whether you want that.")
V["manager_office/main"] = view(
    floor=[[[410,610],[545,600],[552,731],[700,746],[840,754],[969,756],[1140,794],[1160,792],[1195,640],[1300,620],[1500,720],[1420,960],[1000,1020],[600,1020],[580,980],[410,980]]],
    hotspots=[{"id": "sofa-sit", "label": "Sit (leather sofa)", "at": [385, 700], "r": 40, "status": "proposed",
               "note": "MY PROPOSAL, not yours: the sofa is just LEFT of the walkable floor (the floor starts at x=410, the sofa's right arm ends at x=395), "
                       "so the spot is on the end of the right arm where the avatar can stand next to it. The generic sit animation; I have not made a sofa-specific one.",
               "action": {"type": "animation", "animation": "sit down on the leather sofa"}}],
    doors=[door("lobby_upstairs", (800, 1014), note="Josie (2026-10-18): the entrance and exit to the office is a hotspot at the bottom of the screen. My earlier mark was the PRIVATE door at the back; I moved it to the bottom.")],
    notes="Floor wraps the desk on the right and front; its front edge now follows the desk's own base line (2026-10-18) instead of a straight row 810. The sofa and coffee table (left) are partly inside it and are cut out with footprints. "
          "Josie (2026-10-18): the back door (the brown one with the small sign, about 570,350) leads into the back of the theater's mezzanine, up on the second floor. "
          "The theater is not built, so there is no exit through it yet.")
V["projection_booth/main"] = view(
    notes="This picture shows no walkable floor and no door, only the projector, platters and the window onto the auditorium. "
          "Needs a decision: a floor strip drawn at the bottom, or a different picture.")

# ── green room hub (positions from Josie's annotator export) ────────────────
V["green_room/main"] = view(
    zones=[
        zone("main", [[120,650],[180,540],[235,402],[470,395],[520,470],[590,550],[700,610],[860,625],[1007,614],[1071,611],[1132,586],[1286,526],[1306,520],[1399,482],[1351,470],[1342,458],[1258,435],[1357,397],[1480,395],[1560,430],[1586,650]], note="Main floor level, around the sunken living room. Re-traced 2026-10-18 so the edge follows the near side of the couch and the pit rim (the rim runs to about 1399,482), then the back edge of the side table and the edge of the rug; before, it cut across the couch's right arm and the side table."),
        zone("back-floor", [[470,395],[500,352],[700,342],[862,338],[965,330],[972,352],[868,360],[700,372],[540,378],[480,408]], note="Narrow strip behind the sofa; the little podium with the dress form is at its right end."),
        zone("sunken-living-room-steps", [[835,352],[930,350],[960,428],[867,432],[867,383],[852,373]], kind="stairs", level="main", z_in=0, rise_in=-20, estimated=True, axis=[[882,351],[913,430]], note="The three steps down into the sunken living room, between the couch's back section and the TV. Outline traced on the picture 2026-10-18; its left edge steps in to x=867 below y=383 so it stops at the couch's right arm. Axis runs from the top step (back platform) to the bottom step (carpet). rise_in -20 is MY ESTIMATE (not Josie's number): see the note on the sunken living room floor."),
        zone("sunken-living-room", [[697,503],[740,491],[780,481],[850,456],[864,437],[960,430],[966,452],[978,463],[1070,494],[1094,501],[1080,510],[1035,527],[1015,531],[960,548],[890,563],[850,566],[800,568],[766,563],[748,555],[726,541],[709,520],[700,507]], level="sunken-living-room", z_in=-20, estimated=True, note="The carpet and wood floor INSIDE the sunken living room, traced tight to the couch, the stairs and the TV (2026-10-18). Josie (2026-10-18): the sunken living room is walkable, you walk down the stairs, around the coffee table and sit on the couch, and to get out you walk all the way back round to the stairs. z_in -20 is MY ESTIMATE, not her number: the couch (about 33 in tall) and the coffee table (about 15-18 in tall) both fit the camera if the floor is about 20 in below the main floor, and the three steps agree; the sizes are only as good as that estimate."),
    ],
    doors=[door("palace_hallway", (343, 252), "confirmed", group="hall_or_writers", label="Palace Hall (theater lobby hallway)",
                note="Josie (2026-10-18): one bubble with two choices, the Writers' Room or the Palace Hall. The theater itself is not built yet."),
           door("writers_room", (343, 252), "confirmed", group="hall_or_writers", label="Writers' Room"),
           door("control_room", (1477, 297), "confirmed"),
           door("studio_overlook", (954, 220), "confirmed"),
           door("dressing_room", (5, 583), "confirmed"),
           door("vortex_bar", (1072, 672), "confirmed", note="Annotator put it at y=686, below the picture's bottom edge (672); clamped.")],
    hotspots=[{"id": "tv", "label": "TV", "at": [1012, 375], "r": 40, "status": "confirmed",
               "action": {"type": "animation", "animation": "tv turns on character bends over turns it on flips a channel or two between prerecorded and when availible live chatter and studio happenings"}},
              {"id": "couch-sit", "label": "Sit", "at": [780, 429], "r": 40, "status": "confirmed",
               "action": {"type": "animation", "animation": "sit down and watch tv on couch"}},
              {"id": "couch", "label": "Couch", "at": [684, 513], "r": 40, "status": "confirmed",
               "action": {"type": "animation", "animation": "sit down and watch tv on couch"}},
              {"id": "couch-sit-left", "label": "Sit (left curve)", "at": [550, 490], "r": 40, "status": "proposed",
               "note": "MY PROPOSAL, not yours: another place to sit on the curve of the couch, on the left. Same animation as your two couch spots.",
               "action": {"type": "animation", "animation": "sit down and watch tv on couch"}},
              {"id": "couch-sit-right", "label": "Sit (right end)", "at": [1105, 525], "r": 40, "status": "proposed",
               "note": "MY PROPOSAL, not yours: a place to sit on the couch's right end, by the side table. Same animation as your two couch spots.",
               "action": {"type": "animation", "animation": "sit down and watch tv on couch"}}],
    notes="Doors and hotspots are Josie's own (Level Annotator, 2026-04-11). Floor and scale are first-pass. "
          "The sunken sofa pit is the floor's edge; the platform behind it is a second polygon so the studio door is reachable. "
          "Scale from the stool, chair and dress form at the back (about 1.7 px/in) and the sofa front (about 2.8 px/in); the side doors are nearer the camera, so they read bigger.")

# ── dressing room ───────────────────────────────────────────────────────────
V["dressing_room/wide"] = view(
    zones=[zone("floor", [[10,740],[360,708],[410,662],[690,658],[735,602],[1050,592],[1110,640],[1480,652],[1500,1020],[1240,1020],[1228,983],[1211,958],[1178,951],[1111,960],[1078,978],[1000,948],[889,937],[778,939],[756,943],[711,920],[680,906],[622,893],[560,890],[500,887],[470,889],[440,891],[392,865],[321,848],[258,839],[212,840],[187,848],[160,868],[150,889],[150,1020],[10,1020]], note="Extended 2026-10-18 from the old straight line at row 830 down to the top edge of the sofa and the bottom of the picture: the rug in front of the coffee table is visible floor."),
           zone("foundry-stage", [[372,664],[420,592],[640,586],[690,640],[640,668],[420,668]], level="foundry-stage", z_in=None, note="The low round wood stage in front of the full-length mirror (the Avatar Foundry). How high is not known yet.")],
    doors=[door("green_room", (951, 435), "confirmed"),
           door("avatar_foundry", (486, 425), "confirmed", note="The wood stage in front of the full-length mirror.")],
    hotspots=[
        {"id": "message-board", "label": "Message board", "at": [686, 297], "r": 40, "status": "confirmed", "action": {"type": "view", "view": "corkboard", "event": "Check message board"}},
        {"id": "makeup-station", "label": "Hair and makeup", "at": [167, 425], "r": 40, "status": "confirmed", "action": {"type": "view", "view": "makeup_mirror", "event": "hair and makeup"}},
        {"id": "typewriter", "label": "Typewriter", "at": [979, 767], "r": 40, "status": "confirmed", "action": {"type": "view", "view": "typewriter_standing_above", "event": "Sitting at your type writer in the first person view typing messages sending them working on scripts of whatever documents you would liek"}},
        {"id": "phone", "label": "Phone", "at": [1180, 791], "r": 40, "status": "confirmed", "action": {"type": "custom", "event": "accesses zoom or the internal audio and video meeting software for a quick chat or full meeting from your dressingroom"}},
        {"id": "wardrobe", "label": "Wardrobe", "at": [1229, 373], "r": 40, "status": "confirmed", "action": {"type": "program", "program": "wardrobe", "event": "Clothes maker and clothing closet menue are entered and you can dress your avtar and even create new clothing"}},
        {"id": "scripts", "label": "Scripts", "at": [783, 729], "r": 40, "status": "confirmed", "action": {"type": "custom", "event": "you can see the list of scripts you have at hand that you compelteedd were provided or sent to you by the game or other users and you can read them and offer conversation comment and advice on them"}}],
    notes="Hotspot positions are Josie's (Level Annotator, 2026-04-11); on 2026-10-18 she said I had pretty much everything. Which close-up view each one opens is my guess from the names. Furniture (coffee table, vanity, mirror platform) not cut out of the floor. "
          "Typewriter, as she described it on 2026-10-18 (not built): it starts 2i; typing on the typewriter alone might go straight into manuscript writing mode, "
          "but instead of the notebook coming up she wants to see the typewriter and the words appearing on the paper. There is an area to type freely, then you hit enter, "
          "with a couple of sound effects, the paper rolls up a bit, and after it rolls up several times you hear the ding (she is unsure whether the ding belongs at the end of a line). "
          "The typewriter sounds can be muted, because not everybody will like them. Other views she mentioned: the corkboard close-up, the makeup boudoir (a little high-tech, a place to start), "
          "and the Foundry (Avatar Foundry), which she has not sent yet.")
V["dressing_room/typewriter_standing_above"] = view(
    hotspots=[{"id": "sit-down", "label": "Sit down", "at": [370, 560], "r": 60, "status": "proposed", "action": {"type": "view", "view": "typewriter_sitting"}}],
    notes="Close-up looking down at the typewriter; no avatar walking here.")
for k in ("typewriter_sitting", "makeup_mirror", "corkboard"):
    V[f"dressing_room/{k}"] = view(notes="Close-up view; no avatar walking here.")

# ── writers, studio, control, vortex, basement ──────────────────────────────
V["writers_room/main"] = view(
    floor=[[[40,700],[300,640],[650,620],[900,650],[970,760],[900,880],[600,960],[300,950],[60,880]]],
    doors=[door("green_room", (560, 610), "confirmed", group="writers_out", label="Green Room", note="The open arched door at the back. Josie (2026-10-18): right, just the one door in and out."),
           door("palace_hallway", (560, 610), group="writers_out", label="Palace Hall", note="My inference, not hers: the same door also offers the way back to the Palace Hall, because the Writers' Room can be entered from the hallway stairs as well.")],
    notes="Floor is the oval rug platform; the table and chairs are not cut out. Per Josie the writers' room door itself is not installed yet.")
V["studio_overlook/main"] = view(
    floor=[[[300,600],[338,600],[338,640],[375,650],[425,655],[455,640],[470,625],[500,625],[510,600],[520,590],[548,595],[560,610],[760,760],[960,930],[980,1000],[330,1000],[300,860],[280,760],[215,690]]],
    doors=[door("green_room", (480, 1015), "confirmed", note="Bottom edge, where you came in. Josie (2026-10-18): right, back to the green room at the bottom."),
           door("studio_fixedsets", (330, 590), "confirmed", note="Trigger spot: walking up the lit path toward the set. Josie (2026-10-18): right, up at the top, deeper into the studio.")],
    notes="Tiny avatars on purpose: the point is how big the hangar is. The glass wall on the right hides a second stage that is not walkable. Floor edge re-traced 2026-10-18 under the operators' desk and the palm; the dark floor was traced on a brightened copy of the picture. The consoles on the left stand outside the floor.")
V["studio_fixedsets/main"] = view(
    floor=[[[300,650],[330,580],[470,540],[540,560],[650,570],[720,660],[700,712],[682,720],[610,752],[592,805],[600,880],[615,945],[620,1000],[420,1000],[440,800],[380,760],[320,720]],
           [[20,600],[150,590],[310,600],[320,700],[180,700],[20,690]]],
    doors=[door("studio_director", (15, 650), "confirmed", note="All the way to the left edge. Josie (2026-10-18): right, to the left you get the director's chair."),
           door("studio_overlook", (500, 1010), "confirmed", note="Bottom edge: step back. Josie (2026-10-18): right, back is the far shot of the studio.")],
    notes="Round set floor plus a left strip leading to the left edge. The round desk on the set is not cut out. "
          "Josie (2026-10-18): several more hotspots are coming here for the news sets; she will work those out later, so none are placed now.")
V["studio_director/main"] = view(
    floor=[[[0,470],[160,440],[450,420],[900,445],[1024,470],[1024,720],[0,720]]],
    doors=[door("pubworld", (560, 420), "confirmed", note="Toward the back of the picture; the portal is not drawn yet. Josie (2026-10-18): walking back toward the screen eventually triggers you to enter PubWorld."),
           door("studio_fixedsets", (1010, 600), "confirmed", note="Josie (2026-10-18): walking back toward the bottom of the screen, the bottom right especially, a hotspot triggers and takes you back to the main studio.")],
    notes="Chair, stool and equipment not cut out of the floor.")
V["control_room/main"] = view(
    floor=[[[46,345],[236,345],[238,372],[300,378],[364,372],[366,405],[372,432],[385,452],[410,464],[450,468],[520,469],[590,466],[640,455],[690,441],[698,420],[700,380],[702,345],[758,350],[760,368],[790,395],[792,481],[978,505],[985,505],[985,687],[50,687]]],
    doors=[door("green_room", (25, 520), "confirmed", note="Open door in the left foreground. Josie (2026-10-18): right, the bottom left of the screen takes you back to the green room.")],
    hotspots=[{"id": "director-console", "label": "Director's console", "at": [540, 330], "r": 50, "status": "proposed",
               "action": {"type": "custom", "event": "Josie (2026-10-18): right at the center, that is going to be the director's console. What it does is not decided yet."}},
              {"id": "audio-console", "label": "Audio console", "at": [330, 315], "r": 50, "status": "proposed",
               "action": {"type": "custom", "event": "Josie (2026-10-18): the console near the window is going to be the audio console. What it does is not decided yet."}},
              {"id": "right-console", "label": "Console, to be decided", "at": [805, 325], "r": 50, "status": "proposed",
               "action": {"type": "custom", "event": "Josie (2026-10-18): the console towards the right near the screen is going to be either VTR, Chyron or computer effects; she does not know yet."}}],
    notes="Floor edge re-traced 2026-10-18 along the dais steps, the console bases and the right desk; the dais, consoles, desks and chairs are cut out as solids. The three console hotspots are my placement from her description of which console is which; the spots are mine.")
V["vortex_bar/main"] = view(
    floor=[[[430,600],[540,540],[690,545],[720,640],[758,770],[790,802],[840,836],[880,870],[920,906],[960,934],[990,950],[0,950],[0,806],[100,794],[140,773],[180,749],[215,723],[226,700],[232,676],[250,671],[300,669],[345,656],[372,646],[400,624]]],
    doors=[door("green_room", (610, 520), "confirmed", note="Door at the back of the room. Josie (2026-10-18): right, coming from the green room you enter through the very back door, the back wall at the top middle of the picture."),
           door("parking_lot", (435, 480), note="Josie (2026-10-18): the front door into the parking lot is the door on the left, behind the three booths. I read it as the tall blue glass door beside the wall lamp (about 415-455 wide, 305-470 tall); the exact door is my guess, tell me if she meant another.")],
    hotspots=[{"id": "booth-sit", "label": "Sit (booth)", "at": [95, 725], "r": 40, "status": "proposed",
               "note": "MY PROPOSAL, not yours: a place to sit in the nearest striped booth. What happens when you click is not decided.",
               "action": {"type": "animation", "animation": "sit down in the booth"}},
              {"id": "stool-sit-middle", "label": "Sit (bar stool)", "at": [836, 680], "r": 35, "status": "proposed",
               "note": "MY PROPOSAL, not yours: sit on the middle bar stool. What happens when you click is not decided.",
               "action": {"type": "animation", "animation": "sit down on the bar stool"}},
              {"id": "stool-sit-right", "label": "Sit (bar stool)", "at": [950, 790], "r": 35, "status": "proposed",
               "note": "MY PROPOSAL, not yours: sit on the right-hand bar stool, the one nearest the camera. What happens when you click is not decided.",
               "action": {"type": "animation", "animation": "sit down on the bar stool"}}],
    notes="Josie (2026-10-18): \"Oh no, that whirlpool, that's just paint on the floor. That's a normal floor.\" "
          "So the whole floor, whirlpool included, is walkable. "
          "She says there should be a spiral staircase leading down and the picture may be tweaked to show it; the pit below is not to be worried about now, "
          "so the way down to the Basement Bar has no click spot until then.")
V["basement_bar/main"] = view(
    zones=[zone("floor", [[540,686],[955,686],[975,735],[968,790],[955,850],[942,900],[933,935],[880,925],[830,930],[790,935],[745,915],[700,917],[650,945],[590,985],[520,992],[440,1000],[420,960],[440,905],[470,853],[457,767],[530,731]], level="basement"),
           zone("spiral-stairs", [[520,992],[590,985],[650,945],[700,917],[745,915],[790,935],[830,930],[880,925],[933,935],[960,990],[1020,1160],[1010,1536],[720,1536],[500,1100]], kind="stairs", level="basement", z_in=0, rise_in=None, axis=[[740,1010],[880,1520]], note="The spiral stair up to the Vortex Bar. Axis runs from the bottom step (basement floor) toward the camera and up; climb height not known yet.")],
    doors=[door("vortex_bar", (880, 1520), note="Bottom of the spiral stairs.")],
    notes="Second polygon is the spiral stair coming toward the camera.")

# every picture needs an entry
for r in W.WORLD.values():
    for v in r.views:
        V.setdefault(f"{r.room_id}/{v.view_id}", view(notes="Not placed yet."))

# avatar size: one calibration per picture (calib_data.py is the single source of the numbers)
sys.path.insert(0, _HERE)
from calib_data import CAL, MEAS
for _key, _c in CAL.items():
    _v = V[_key]
    if _c["kind"] == "camera":
        _v["camera"] = {"horizon_y": _c["h"], "eye_in": _c["E"]}
        _v["scale"] = []
    else:
        _v["scale"] = [{"y": y, "ppi": p} for y, p in _c["samples"]]
    _info = {"confidence": _c["conf"], "basis": _c["why"], "refs": list(_c["refs"]),
             "measured": [{"row": r, "ppi": p} for r, p in MEAS[_key]]}
    if _c.get("alt"):
        _info["alt"] = {"label": _c["alt"]["label"], "samples": [{"y": y, "ppi": p} for y, p in _c["alt"]["samples"]]}
    _v["scale_info"] = _info
_stray = [k for k, v in V.items() if v["scale"] and k not in CAL]
assert not _stray, f"scale without a calibration entry: {_stray}"

# occluders from the GrabCut cache (only outlines that refined well)
import json as _j
_cache = _j.load(open(_os.path.join(_HERE, 'cutout_cache.json')))
sys.path.insert(0, _HERE)
from occluders_src import R as _R
_missing = []
for _view, _objs in _R.items():
    for _ob in _objs:
        _c = _cache.get(_view + '|' + _ob['id'])
        if not _c or not _c['poly'] or _c['ratio'] < 0.45:
            _missing.append(f"{_view}: {_ob['label']}")
            continue
        _entry = {"id": _ob['id'], "label": _ob['label'], "points": _c['poly']}
        if _ob['always']: _entry["always"] = True
        else: _entry["base_y"] = _ob['base_y']
        V[_view]["occluders"].append(_entry)
from furniture_src import OUTLINE_FIXES as _OF
for _view, _fixes in _OF.items():
    for _oid, (_pts, _why) in _fixes.items():
        _o = next(e for e in V[_view]["occluders"] if e["id"] == _oid)
        _o["points"] = _pts
        _o["note"] = _why
for _view in V:
    V[_view]["occluders"].sort(key=lambda e: e["id"])
# floor footprints of solid things, traced by eye (furniture_src.py): blocks walking and gives the real front line
from furniture_src import FOOTPRINTS as _FP, BLOCKERS as _BL, OUTLINES as _OL
for _view, _outs in _OL.items():
    for _oid, _o in _outs.items():
        assert not any(e["id"] == _oid for e in V[_view]["occluders"]), f"{_view} '{_oid}' already has a GrabCut outline"
        _label = _o.get("label") or next(ob["label"] for ob in _R[_view] if ob["id"] == _oid)
        if "union" in _o:                      # an outline made of several simple shapes (a tabletop and its pedestal, or a table and its legs)
            from shapely.geometry import Polygon as _P2
            from shapely.ops import unary_union as _U2
            _u = _U2([_P2(p).buffer(0) for p in _o["union"]]).buffer(0.6).simplify(0.7)
            _parts = sorted(_u.geoms, key=lambda p: -p.area) if hasattr(_u, "geoms") else [_u]
            _polys = [[[max(0, round(x)), max(0, round(y))] for x, y in list(p.exterior.coords)[:-1]] for p in _parts if p.area > 20]
        else:
            _polys = [_o["points"]]
        for _i, _pts in enumerate(_polys):    # parts that do not touch become separate outlines with the same base row
            _e = {"id": _oid if _i == 0 else f"{_oid}-part{_i + 1}", "label": _label if _i == 0 else f"{_label} (part {_i + 1})",
                  "points": _pts, "note": _o["note"]}
            if _o.get("always"):               # a foreground thing: always drawn over the avatar, no base row
                _e["always"] = True
            else:
                _e["base_y"] = _o["base_y"]
            V[_view]["occluders"].append(_e)
        _missing = [m for m in _missing if m != f"{_view}: {_label}"]
for _view in V:
    V[_view]["occluders"].sort(key=lambda e: e["id"])
for _view, _fps in _FP.items():
    for _oid, _fp in _fps.items():
        _o = next((e for e in V[_view]["occluders"] if e["id"] == _oid), None)
        assert _o is not None, f"footprint for {_view} '{_oid}' but no outline of that id"
        _o["footprint"] = _fp
        _o["base_y"] = max(y for _, y in _fp)
from furniture_src import FROM_OUTLINE_MINUS_FLOOR as _FOM, FOOTPRINT_FROM_OUTLINE as _FFO
from shapely.geometry import Polygon as _Poly
from shapely.ops import unary_union as _union
for _view, _ids in _FFO.items():                 # low solids whose whole outline is the footprint
    for _oid in _ids:
        _o = next(e for e in V[_view]["occluders"] if e["id"] == _oid)
        _o["footprint"] = [list(p) for p in _o["points"]]
        _o["base_y"] = max(y for _, y in _o["footprint"])
for _view, _ids in _FOM.items():
    _floor = _union([_Poly(z["points"]).buffer(0) for z in V[_view]["zones"]])
    for _oid in _ids:
        _o = next(e for e in V[_view]["occluders"] if e["id"] == _oid)
        _rest = _Poly(_o["points"]).buffer(0).difference(_floor)
        _parts = list(_rest.geoms) if hasattr(_rest, "geoms") else [_rest]
        _big = max(_parts, key=lambda p: p.area).simplify(0.6)
        _o["footprint"] = [[round(x), round(y)] for x, y in list(_big.exterior.coords)[:-1]]
        _o["base_y"] = max(y for _, y in _o["footprint"])
for _view in V:
    V[_view]["blockers"] = list(_BL.get(_view, []))
# nothing stands ON a staircase: trim any solid's floor footprint that reaches into a stairs/ramp zone (the feet were read off by eye,
# +-10-15 px, and the stairs edge is shared with the floor edge)
_trimmed = []
for _view, _vv in V.items():
    _st = [_Poly(z["points"]).buffer(0) for z in _vv["zones"] if z.get("kind", "floor") != "floor"]
    if not _st:
        continue
    _stairs = _union(_st).buffer(2.5)
    for _item in [o for o in _vv["occluders"] if o.get("footprint")] + _vv["blockers"]:
        _shape = _Poly(_item["footprint"]).buffer(0)
        if _shape.intersection(_stairs).area <= 0:
            continue
        _rest = _shape.difference(_stairs)
        _parts = list(_rest.geoms) if hasattr(_rest, "geoms") else [_rest]
        _parts = [q for q in _parts if q.area > 20]
        if not _parts:
            continue
        _big = max(_parts, key=lambda q: q.area).simplify(0.6)
        _item["footprint"] = [[round(x), round(y)] for x, y in list(_big.exterior.coords)[:-1]]
        if "base_y" in _item:
            _item["base_y"] = max(y for _, y in _item["footprint"])
        _trimmed.append(f"{_view}:{_item['id']}")
print("footprints trimmed out of stairs:", _trimmed)
print("occluders:", sum(len(v["occluders"]) for v in V.values()), "kept;", len(_missing), "need outlining")
open(_os.path.join(_HERE, 'occluders_missing.txt'), 'w').write("\n".join(_missing))

ELEV = {"lobby": 0, "palace_hallway": 0, "lobby_upstairs": None, "green_room": None, "vortex_bar": None, "basement_bar": None,
        "manager_office": None, "projection_booth": None}

out = {"version": 1, "elevations": ELEV,
       "note": "First-pass placements. status 'proposed' means Claude placed it by eye and Josie has not approved it yet. Positions are source-picture pixels.",
       "views": dict(sorted(V.items()))}
json.dump(out, open('data/world/placements.json', 'w'), indent=1)
print(len(V), "views")
