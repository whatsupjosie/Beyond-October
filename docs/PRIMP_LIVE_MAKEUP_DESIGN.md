# Primp: live makeup on a real face, applied by hand

Status: **design proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are at the end.

## What it does

The user sits in front of a camera. Primp tracks their face and their hand. They hold an imaginary brush, a pen, or a real brush, and make the same motions they would make applying real makeup. Primp applies the makeup on screen as they go. It works as a simulation for practice and as a teacher for technique.

## Josie's rules (2026-11-07)

1. **Pencil grip means tip down.** When the hand is in the position you'd hold a pencil in, the brush is touching and paints. When the hand leaves that position, the tip lifts.
2. **The brush rests along the top of the index finger, pinned by the thumb,** lying along the finger's length the way a bird perches on a finger. It is not aimed out from the fingertip. **Its tip is 1 inch (25.4 mm) past the end of the finger.**
3. **Invisible brush or held object.** The user can hold nothing (the imaginary brush), or hold a pen or a brush to mimic the motion.

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

**Painting**
- While the grip is held, every frame where the tip is over the face paints at that spot.
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

## Build order

1. Hand tracking and pencil-grip detection on a laptop camera, with the tip drawn as a dot. Prove the grip switch and the tip position feel right.
2. Face map, with one product (lipstick) painted by the tip and staying put as the head moves.
3. The brush kit and finishes; blush and eyeshadow.
4. Hand-in-front-of-face stability and calibration for held objects.
5. Stroke recording, replay and technique feedback.

## Decisions for Josie

1. **Closeness check:** under rule 1, the tip paints wherever it is over the face on screen, even with the hand held well in front of the face. Add an optional check that the tip is also roughly at the face's depth (from the trackers' depth estimates, or a depth camera on phones that have one)? Your rule stays the default; the check would be a setting.
2. **Pressure:** answered by "Reading the stroke": push depth first, then grip squeeze and speed toward the face. Open: should the user be able to turn pressure off (constant colour) for simpler use?
3. **Which hand:** either hand, or a chosen dominant hand?
4. **Teaching guides:** who writes the technique guides, and what's in the first set (for example a basic everyday look, a stage look)?
