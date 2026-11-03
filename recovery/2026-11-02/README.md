# Preserved before editing — November 2, 2026

`world/manager_office.png` is Sir Purfluous's office clean plate exactly as it was before Josie's painting was set into the framed tray on the floor (bottom right). The live copy is `static/world/rooms/manager_office.png`; the painting itself, unchanged, is `static/world/rooms/manager_office_painting.png`. To undo, copy this file back over the live one and remove the `painting` view and the `floor-painting` hotspot, then run `python tools/build_world_json.py`.
