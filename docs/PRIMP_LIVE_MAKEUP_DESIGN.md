# Primp: live makeup on a real face, applied by hand

Status: **design proposal for Josie's review**. Nothing here is built. The design decisions are hers; open questions are at the end.

## What it does

The user sits in front of a camera. Primp tracks their face and their hand. They hold an imaginary brush, a pen, or a real brush, and make the same motions they would make applying real makeup. Primp applies the makeup on screen as they go. It works as a simulation for practice and as a teacher for technique.

## Josie's rules (2026-11-07)

1. **Pencil grip means tip down.** When the hand is in the position you'd hold a pencil in, the brush is touching and paints. When the hand leaves that position, the tip lifts.
2. **The tip extends from the index fingertip,** in a straight line along the index finger, the way a pencil would rest on that finger.
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
The grip is recognised from the hand's own shape: thumb tip pressed toward the index finger near its last joint, index and middle fingers partly curled, ring and little fingers tucked. A short hold (a few frames) before switching on or off stops flicker.

**The brush tip** (rule 2)
Tip position = index fingertip + (direction of the index finger's last segment × brush length). Brush length has a default for the invisible brush. When holding a real pen or brush, a one-time calibration (touch the tip to your nose) measures its true length. An optional coloured dot on a held tip lets the camera lock onto the real tip instead of estimating it.

**Painting**
- While the grip is held, every frame where the tip is over the face paints at that spot.
- Paint goes onto a **face map** (the face unwrapped into a flat sheet: lips, lids, brows, cheeks, forehead, jaw), not onto the video. So blush stays on the cheek when the head turns, and makeup survives the hand passing in front of the face.
- The face map is held steady while the hand blocks part of the face.
- **Mirror view** by default: moving the hand left moves it left on screen.

**Brush kit** (same idea as the Dremel bit kit)
Foundation brush, blending sponge, powder puff, blush brush, eyeshadow brush (flat and crease), lip brush, eyeliner, brow pencil, fan brush, mascara wand. Each has its own size, softness (hard edge vs. feathered), how much colour it lays per pass, and whether it blends what's already there.

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
2. **Pressure:** should anything control how much colour goes on (how tight the grip is, how long it dwells), or is that set by the brush and product?
3. **Which hand:** either hand, or a chosen dominant hand?
4. **Teaching guides:** who writes the technique guides, and what's in the first set (for example a basic everyday look, a stage look)?
