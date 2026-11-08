# Primp: live makeup on a real face, applied by hand

Status: **design proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are at the end.

## What it does

The user sits in front of a camera. Primp tracks their face and their hand. They hold an imaginary brush, a pen, or a real brush, and make the same motions they would make applying real makeup. Primp applies the makeup on screen as they go. It works as a simulation for practice and as a teacher for technique.

## Josie's rules (2026-11-07)

1. **Pencil grip means tip down.** When the hand is in the position you'd hold a pencil in, the brush is touching and paints. When the hand leaves that position, the tip lifts.
2. **The brush rests along the top of the index finger, pinned by the thumb,** lying along the finger's length the way a bird perches on a finger. It is not aimed out from the fingertip. **Its tip is 1 inch (25.4 mm) past the end of the finger.**
3. **Voice engages the stroke** (2026-11-07). The user takes the grip, leans closer and says **"engage"** (or "apply"). From then on the tool is applying through each forward stroke. It ends when the hand retreats without re-engaging a forward stroking motion within a couple of seconds, or immediately when the user says **"disengage"**.
4. **Undo** (2026-11-07). Undo the last 10 moves, in case you streaked everything because you forgot to disengage.
5. **Invisible brush or held object.** The user can hold nothing (the imaginary brush), or hold a pen or a brush to mimic the motion.

## What already exists in PubCast (checked 2026-11-07)

- Face tracking from a live camera: `modules/evo/facial_performance.py` uses MediaPipe's face mesh (optional dependency).
- Face points and ARKit-style face shapes driving avatars: `modules/avatar_performer.py`.
- **Not built:** hand tracking, the brush, the face paint map, and makeup rendering on video.

## How it works

**Tracking**
- Face: MediaPipe face landmarks, as PubCast already uses.
- Hand: MediaPipe's hand tracker (21 points per hand, ordinary camera). It's the same family of tools, offline and free.

**Pencil grip detection** (rule 1)
The grip is recognised from the hand's own shape: the thumb tip pressed onto the top of the index finger (pinning the brush there), the index finger extended or gently curved, and the other fingers relaxed or tucked. A short hold (a few frames) before switching on or off stops flicker.

**The brush tip** (rule 2)
The brush line lies along the top of the index finger: parallel to the whole finger (base knuckle to fingertip, not just the last joint), raised by about half the finger's thickness so it sits on top rather than through it, and anchored where the thumb pins it. Tip position = the point on that line level with the fingertip + 1 inch (25.4 mm) further along it (Josie, 2026-11-07). The inch is converted to screen distance using the hand's and face's own size on camera, so it stays a real inch at any distance from the camera. When holding a real pen or brush, a one-time calibration (touch the tip to your nose) measures its true length. An optional coloured dot on a held tip lets the camera lock onto the real tip instead of estimating it.

**Showing the tool in the hand** (Josie, 2026-11-07)
While the hand is in the correct grip, Primp draws the chosen tool (brush, pencil, sponge, lip brush) in the user's hand on screen, lying along the top of the index finger where the thumb pins it, so they can see exactly what they're working with.
- It appears only while the grip is correct and fades out when the grip is released. Its presence is the user's confirmation that Primp sees the grip.
- It shows the tool picked from the brush kit, at its real size.
- The tip glows, or shows its colour, while it's painting, so the user can see the moment of contact.
- It doubles as calibration: the user sees where Primp thinks the tip is and can adjust the length with a slider if it doesn't match their real pen or brush.

**Voice control** (rule 3)
- A small offline word spotter (wake-word style) listens only for "engage", "apply" and "disengage". It reacts in a fraction of a second, with no internet and no full speech-to-text.
- **"Disengage" contains "engage".** The spotter is trained on both words and waits about 0.3 s before acting on "engage", so "disengage" always wins and the brush never switches on mid-word.
- It only listens while the grip is held and a face is in view, so a TV or another person can't trigger it.
- **Retreat** means the tip moves away from the face by a set distance (confirmed by the hand shrinking on screen), with no new forward stroke within about 1.5 seconds. Both values are adjustable.
- Audio is processed on the device: keyword only, nothing recorded.
- A non-voice way to engage and disengage (a key, a tap, or a gesture with the other hand) gives the same mode for quiet rooms, shared spaces and users who can't or won't speak.
- Caution: saying a word moves the lips. For lipstick, engage before the brush reaches the mouth.

**Undo** (rule 4)
- Every stroke is already recorded (for teaching), so undo simply rebuilds the face map from the remaining strokes: clean, with no leftover smear. Redo puts strokes back.
- **Undo the last stroke** steps back one stroke at a time, through the last 10 (Josie's number).
- **Undo the whole engage**: one command removes everything since the last "engage". That's the direct fix for forgetting to disengage, since a forgotten disengage makes one long accidental stroke run.
- By voice ("undo", "redo", "undo all"; listened for only while a face is in view), by key or by button.

**Painting**
- While engaged (rule 3), every frame where the tip is over the face paints at that spot.
- Paint goes onto a **face map** (the face unwrapped into a flat sheet: lips, lids, brows, cheeks, forehead, jaw), not onto the video. So blush stays on the cheek when the head turns, and makeup survives the hand passing in front of the face.
- The face map is held steady while the hand blocks part of the face.
- **Mirror view** by default: moving the hand left moves it left on screen.

**Brush kit** (same idea as the Dremel bit kit)
Foundation brush, blending sponge, powder puff, blush brush, eyeshadow brush (flat and crease), lip brush, eyeliner, brow pencil, fan brush, mascara wand. Each has its own size, softness (hard edge vs. feathered), how much colour it lays per pass, and whether it blends what's already there.

**Reading the stroke** (pressure and stroke type, from the trackers alone)

Everything is measured relative to the face (head motion doesn't count as a stroke) and in millimetres, using the face as the ruler.

Signals:
1. **Push depth:** how far the tip goes past the face surface, from the hand's depth compared with the face's depth at that spot. This is the main pressure signal. Deeper means the brush spreads: a wider mark and more colour, like real bristles.
2. **Hand size on screen:** a hand moving toward the camera looks bigger. It's a steady second depth signal that confirms push depth.
3. **Speed toward the face:** a quick push in is a firm dab; a slow approach is a soft press.
4. **Speed across the face:** governs how much colour goes down, not pressure. Fast is lighter, thinner and feathered; slow lays more colour in one place.
5. **Path shape:** distance travelled compared with how far the tip ends up from where it started. Long and straight is a swipe; lots of travel ending near the start is rubbing.
6. **Direction changes per second:** a rhythmic back-and-forth is rubbing or buffing.
7. **Circling:** steady curving in a small area is buffing (foundation, blush).
8. **Time in one spot:** holding still in the grip is pressing or stippling.
9. **Grip squeeze:** the thumb pressed tighter to the index finger is pressing harder.
10. **Brush angle:** finger direction compared with the face surface. Side-of-brush sweeps are wide; tip-on work is narrow and precise.
11. **Stroke ending:** speeding up and lifting at the end is a flick, so colour tapers off.

Stroke types:
- **Dab:** almost no sideways movement, a quick in-and-out toward the face, short contact, often repeated in place.
- **Rub / buff:** repeated back-and-forth or circles in a small area, medium speed, steady contact.
- **Swipe:** one long, straight, fast stroke in one direction, brief.
- **Brush / blend:** long and curving, lighter push, medium speed, tapering out at the end.

Jitter is mostly tracking noise, not hand movement. It is smoothed with a filter made for live tracking, and what remains lowers Primp's confidence in its pressure reading; it is never read as pressure.

Calibration: at the start, the user does "press lightly" and "press hard" a few times so Primp learns their range. Classification starts as clear rule thresholds; recorded strokes later train a small model to sort strokes better.

**Products and finishes**
Colour, opacity and finish (matte, satin, gloss, shimmer, metallic), with blending that follows the person's skin tone and the room's lighting.

**Teaching** (Primp's real-person purpose)
Every stroke is recorded: path, direction, speed, how long the grip was held, and which brush. Technique guides compare strokes against the intended motion ("blend upward toward the temple", "short strokes along the lash line", "too much product on the lid") and give feedback. Strokes can be replayed and saved as looks.

## Resolution (Josie, 2026-11-08)

- **1/128 block (about 2 mm) is for Primp and close-ups only:** avatar faces shaped in Primp, makeup-related detail, and specific camera close-ups. Everything else stays at 1/64 or coarser. (1/128 is the next halving after 1/64, so every existing size still lines up on it.)
- **Avatars:** the fine features (lip edges, eyelids, nostril rims, eye corners, nail edges) get 1/128 blocks, and the rest of the face stays 1/64. Filler Cream picks its working grid per selection, so the cost stays with those features. Keep fine features in their own selections, since one 1/128 piece inside a big selection makes the whole selection fine.
- **Close-ups:** bake two versions of the face, standard (1/64) and close-up (1/128), and let camera distance pick which one is shown (the same idea as VoxelStudio's LOD tiers).
- **Live makeup on a real person** uses no voxels. Sharpness there comes from the resolution of the face paint map, which should be high enough for sub-millimetre eyeliner.
- **Needed to support it:** the voxel contract only knows full, half and quarter, so 1/64 and 1/128 need adding (Josie's call). Filler Cream's internal unit then moves from 1/64 to 1/128, with existing 1/64 work unchanged at double the numbers.

## Hurdles and recommendations (Claude's review, 2026-11-07; each is Josie's call)

1. **One grip doesn't fit every tool.** Real artists hold a liner near the tip, a blending brush loosely at the end, a sponge in the fingertips. Recommendation: the perched-pencil grip as the default, with a grip profile per tool in the kit, so teaching doesn't train the wrong hold.
2. **The hand blocks the camera.** Near the eyes, the hand covers part of the face, and the thumb on top of the index finger can be hidden from a front camera. Tracking is weakest exactly where precision matters most; the face map must hold through it.
3. **Fine lines.** Webcam tracking wobbles by a few millimetres, while eyeliner and lip lines need about one. Recommendation: **Practice mode** shows true accuracy; **Beauty mode** gently snaps strokes to the lash line or lip edge.
4. **No touch feedback.** The tip glow helps; a soft sound on contact helps more.
5. **Lighting and skin tone.** Test in dim rooms, on cheap webcams and across many skin tones, so it works for everyone.
6. **Laptop load.** Face tracking, hand tracking, the voice spotter and live painting at once need frame-rate testing on modest laptops.
7. **Left-handed users and a second hand** (holding a palette): choose a dominant hand, or allow either.
8. **Calibration fatigue.** Defaults must be good enough to skip calibration.
9. **Privacy (recommended as a rule):** live video and audio stay on the device, never uploaded, not recorded by default. Strokes are recorded, not faces.
10. **Eye safety (recommended as a rule):** warn anyone holding a real pen or brush near the eyes, and suggest the invisible brush for eye work.

## Build order

1. Hand tracking and pencil-grip detection on a laptop camera, with the tip drawn as a dot. Prove the grip switch and the tip position feel right.
2. Face map, with one product (lipstick) painted by the tip and staying put as the head moves.
3. The brush kit and finishes; blush and eyeshadow.
4. Hand-in-front-of-face stability and calibration for held objects.
5. Stroke recording, replay and technique feedback.

## Decisions for Josie

1. **Closeness check:** largely answered by voice engage/disengage (rule 3). Still open: also require the tip to be near the face's depth while engaged, as an optional setting?
2. **Pressure:** answered by "Reading the stroke": push depth first, then grip squeeze and speed toward the face. Open: should the user be able to turn pressure off (constant colour) for simpler use?
3. **Which hand:** either hand, or a chosen dominant hand?
4. **Tip length:** 1 inch past the fingertip (as written), or 1 inch from where the thumb pins the tool? The on-screen tool lets users fine-tune it either way.
5. **Undo depth:** 10 as you said, or unlimited? Strokes are recorded anyway, so a longer history costs almost nothing.
6. **Teaching guides:** who writes the technique guides, and what's in the first set (for example a basic everyday look, a stage look)?
