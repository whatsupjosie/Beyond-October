# Pete 2.5D sprite formula

Directions: 8 screen directions from 5 drawn sets. Mirror gives the other 3.
S front | SE and SW q_front (SW mirrored) | E and W side (W mirrored) | NE and NW q_back (NW mirrored) | N back.

Walk cycle: 8 frames per set (contact, down, passing, up, then the same on the other leg). Frame = floor((distance / stridePx mod 1) * 8). Distance-driven, so speed and animation never drift apart.

Frames needed for walking: 5 sets x 8 = 40 drawings.
Have now: side 8/8, q_front 5/8, front 0/8, q_back 0/8, back 0/8 (still pose used as fallback).
Still to draw: front 8, q_back 8, back 8, q_front 3 = 27.

Portraits (the drawing that pops up when talking): 8 emotions x 8 variants = 64 drawings.
Emotions: neutral, happy, sad, angry, surprised, skeptical, playful, determined.
Have now: 6 drawings, 1 per emotion for 6 emotions. Need 58 more.
Picker: emotion tag from the script picks a random variant, never the same twice in a row.

Other actions (jump, crawl, climb...): add a "walk"-style entry in manifest.json per action, same 8-direction rule only where the action needs it.

Style lock for new drawings: same character sheet, same lighting, transparent background, feet on one baseline, 1448-sheet scale.
