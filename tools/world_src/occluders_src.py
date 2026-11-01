# Rough outlines (source-picture px) of objects the avatar walks in front of / behind.
# base_y = row where the object meets the floor; always=True = foreground, always in front.
# GrabCut (cutout.py) tightens each rough outline to the object's real edge.
R = {}
def o(view, oid, label, rough, base_y=None, always=False, note=""):
    R.setdefault(view, []).append(dict(id=oid, label=label, rough=rough, base_y=base_y, always=always, note=note))

# green room 1586x672
o("green_room/main", "sofa-back", "Sunken sofa, back section", [[500,420],[525,385],[600,360],[740,360],[865,385],[865,440],[760,470],[690,490],[600,450],[530,455]], 480)
o("green_room/main", "sofa-front", "Sunken sofa, front curve and right arm", [[490,440],[560,480],[640,555],[780,600],[900,625],[1040,620],[1150,585],[1240,530],[1300,505],[1295,545],[1160,625],[900,640],[700,620],[560,560],[490,500]], 622)
o("green_room/main", "coffee-table", "Coffee table in the pit", [[770,445],[890,445],[975,478],[975,560],[790,565],[770,520]], 565)
o("green_room/main", "tv", "TV on its stand", [[960,318],[1100,318],[1145,420],[1100,500],[990,500],[962,420]], 500)
o("green_room/main", "lamp-table", "Side table and lamp", [[1190,470],[1180,420],[1245,355],[1320,355],[1335,430],[1345,470]], 470)
o("green_room/main", "foreground-bust", "Bust on the shelf, bottom right", [[1440,520],[1480,420],[1560,400],[1586,430],[1586,672],[1440,672]], always=True)

# dressing room wide 1536x1024
o("dressing_room/wide", "sofa-foreground", "Sofa in the foreground", [[150,880],[200,830],[350,800],[520,790],[700,810],[850,800],[1050,830],[1200,860],[1240,950],[1215,1024],[120,1024]], always=True)
o("dressing_room/wide", "coffee-table", "Coffee table with typewriter", [[630,720],[760,700],[1280,720],[1295,780],[1230,950],[1180,950],[1170,880],[760,860],[750,950],[700,950],[640,800]], 945)
o("dressing_room/wide", "vanity", "Vanity desk and chair", [[24,490],[366,490],[366,700],[290,700],[270,690],[100,700],[24,700]], 700)

# palace hallway 1408x768
o("palace_hallway/main", "door-frame-left", "Open door in the left foreground", [[0,0],[180,0],[185,700],[140,768],[0,768]], always=True)
o("palace_hallway/main", "concession-counter", "Concession counter", [[185,375],[525,375],[530,560],[250,572],[185,548]], 565)
o("palace_hallway/main", "statue", "Gold statue and pedestal", [[700,230],[830,230],[850,400],[880,440],[870,472],[710,472],[700,440],[730,380]], 470)
o("palace_hallway/main", "ticket-booth", "Ticket booth, right", [[1000,215],[1230,215],[1235,592],[1000,592]], 595)
o("palace_hallway/main", "small-booth", "Small booth", [[895,255],[995,255],[990,430],[900,430]], 430)

# lobby 1024x565
o("lobby/main", "fountain-bar", "Central fountain bar", [[555,350],[835,350],[835,440],[700,452],[555,422]], 445)
o("lobby/main", "counter-foreground", "Curved counter, bottom right", [[610,445],[1024,430],[1024,565],[595,565]], always=True)

# upstairs lobby 1536x1024
o("lobby_upstairs/main", "railing", "Curved railing, foreground", [[0,880],[600,640],[870,520],[900,380],[935,380],[915,545],[640,705],[300,865],[0,1010]], always=True)
o("lobby_upstairs/main", "sofa", "Sofa", [[307,396],[632,396],[632,550],[307,550]], 550)
o("lobby_upstairs/main", "armchair", "Armchair", [[656,423],[824,423],[824,543],[656,543]], 543)
o("lobby_upstairs/main", "round-table", "Round table", [[490,478],[660,478],[660,565],[490,565]], 565)

# manager's office 1536x1024
o("manager_office/main", "desk", "Theater manager's desk", [[546,532],[1176,532],[1176,792],[546,792]], 792)
o("manager_office/main", "visitor-chair", "Chair in front of the desk", [[727,656],[922,656],[922,868],[727,868]], 868)
o("manager_office/main", "sofa", "Leather sofa", [[0,508],[396,508],[396,827],[0,827]], 827)
o("manager_office/main", "coffee-table", "Coffee table", [[148,709],[567,709],[567,969],[148,969]], 969)
o("manager_office/main", "table-foreground", "Table, bottom left", [[0,900],[250,900],[250,1024],[0,1024]], always=True)

# writers room 1024x1024
o("writers_room/main", "table", "Oval table", [[270,620],[800,620],[800,830],[270,830]], 830)
o("writers_room/main", "chair-front-left", "Green chair, front left", [[100,650],[390,650],[390,930],[100,930]], 925)
o("writers_room/main", "chair-front-right", "Green chair, front right", [[525,690],[880,690],[880,920],[525,920]], 915)

# control room 1024x687
o("control_room/main", "dais", "Center console on its dais", [[365,255],[695,255],[695,470],[365,470]], 470)
o("control_room/main", "console-left", "Console, left", [[240,265],[440,265],[440,385],[240,385]], 385)
o("control_room/main", "console-right", "Console, right", [[750,275],[945,275],[945,390],[750,390]], 390)
o("control_room/main", "door-left", "Door frame, left foreground", [[0,0],[45,0],[45,687],[0,687]], always=True)
o("control_room/main", "door-right", "Door frame, right foreground", [[985,0],[1024,0],[1024,687],[985,687]], always=True)

# vortex bar 1024x1024
o("vortex_bar/main", "bar-counter", "Bar counter", [[740,495],[1024,500],[1024,1024],[880,1024],[800,880],[740,700]], 960)
o("vortex_bar/main", "booths", "Striped booths, left", [[0,500],[420,490],[420,650],[230,700],[0,790]], 760)

# basement bar 1024x1536
o("basement_bar/main", "round-table", "Candlelit table", [[292,799],[468,799],[468,899],[292,899]], 899)

# studio far shot 1024x1024

# studio closer 1024x1024
o("studio_fixedsets/main", "console-left", "Foreground consoles, left", [[70,690],[340,700],[360,860],[140,900],[60,820]], always=True)
o("studio_fixedsets/main", "console-right", "Foreground consoles, right", [[600,720],[900,690],[910,850],[780,900],[620,860]], always=True)
o("studio_fixedsets/main", "round-desk", "Round desk on the set", [[330,490],[510,490],[510,700],[330,700]], 700)
o("studio_fixedsets/main", "teal-sofa", "Teal sofa", [[540,540],[660,540],[660,670],[540,670]], 670)

# studio director 1024x768
o("studio_director/main", "chair-and-cart", "Director's chair and laptop cart", [[380,420],[530,420],[530,620],[380,620]], 620)
o("studio_director/main", "stool", "Stool", [[310,470],[360,470],[360,555],[310,555]], 555)
o("studio_director/main", "table-left", "Equipment table, left", [[0,455],[185,455],[185,690],[0,690]], 690)

# monument day 1536x1024
