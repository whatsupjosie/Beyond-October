# PUBCAST REACH — 2.5D STAGE ENGINE ORIGINAL SPECIFICATION + TECHNICAL REVIEW

This single file preserves the original supplied specification first, followed by the complete troubleshooting and design review.

---

# PART I — ORIGINAL MESSAGE / SPECIFICATION

PUBCAST REACH: 2.5D COMPOSITE STAGE ENGINE, SET BUILDER, AND BROADCAST DIRECTOR SPECIFICATION

SECTION 1: SYSTEM OVERVIEW AND COMPOSITE LAYER STACK

The 2.5D Stage Engine renders hand-illustrated or pre-rendered fixed-perspective background plates composited with real-time 3D geometry, procedural collision surfaces, holdout depth occluders, and interactive video surfaces without the overhead of full 3D environment modeling. The visual presentation consists of four unified layers evaluated from back to front:  
Layer 1: Illustrated Base Canvas. A high-resolution 2D image (PNG or JPG) representing the static background plate. It is rendered as an unlit backdrop fitting the stage aspect ratio.
Layer 2: 3D Stage Environment. The active WebGL coordinate space containing rigged character avatars (Pete, Alex, Manny, Purfluous), real-time 3D props (GLB files), perspective-mapped video screen quads, real-time directional and shadow lights, and invisible procedural ground quads, ramps, and drop ledges.  
Layer 3: Foreground Holdouts. Invisible 3D depth-masking boxes (which write to the depth buffer without drawing color) or transparent 2D cutout sprite planes pinned at specific Z-depths. When an avatar walks behind a counter, pillar, or desk, Layer 3 automatically clips the avatar pixels so they appear behind the foreground set piece.
Layer 4: Broadcast Glass and HUD. A 2D vector overlay containing on-screen chyron graphics, lower-third nameplates, interactive hotspot triggers, and the full-screen 2D focus modal for video playback and live guest feeds.

SECTION 2: SCENE MANIFEST SPECIFICATION

Every stage is completely defined by a single JSON document named scene_manifest.json. Claude should implement this structure using strict Pydantic schemas in modules/pubworld_stage/manifest_store.py.

The manifest contains the following required blocks:
scene_id: Unique string identifying the room (example: vortex_bar_stage).
title: Human-readable display label.
version: Semantic version string.
background_image: Absolute or relative URI to the background plate.

camera_setup block:
default_shot: Identifier of the primary camera preset.
focal_length_mm: Virtual camera lens focal length (default 35.0).
sensor_height_mm: Virtual camera sensor height (default 24.0).
calculated_fov_vertical: Computed vertical field of view in degrees.
horizon_y_ratio: Normalized height of the horizon line from 0.0 at the top to 1.0 at the bottom.
camera_pitch_deg: Downward tilt angle of the camera in degrees.
camera_roll_deg: Rotation of the camera around the optical axis (Dutch angle).
camera_elevation_m: Height of the camera above the zero floor plane in meters.
shots: Dictionary of shot presets. Each shot contains a label, a 3D position array [X, Y, Z], a 3D rotation array in degrees [pitch, yaw, roll], and a field of view value. Standard presets are cam_wide (full room establishing shot), cam_anchor_close (tight anchor desk framing), cam_guest_monitor (over-the-shoulder framing of the television monitor), and cam_weather_wall (flat framing of the presentation area).

ground_surfaces array:
Contains objects defining walkable areas. Each surface has a surface_id, a type (plane, ramp, or drop_ledge), an elevation_y value, a pitch_deg value, and a walkable_polygon array containing normalized [X, Y] screen coordinates that clamp character navigation. Ramps include elevation_start_y, elevation_end_y, and ramp_pitch_deg. Drop ledges include ledge_trigger_line defining the 2D segment where a character hops down.

occluders array:
Contains objects defining foreground holdouts. Type 3d_depth_box includes a transform object with position [X, Y, Z], rotation_deg [pitch, yaw, roll], and scale [width, height, depth]. Type 2d_sprite_plane includes image URI, depth_z position in meters, and screen position [X, Y].

interactive_screens array:
Contains objects defining television and monitor surfaces. Each screen has a screen_id, label, type (local_file, playlist, or webrtc_stream), stream_channel, fallback_video URI, a transform block specifying [X, Y, Z] position, pitch/yaw/roll rotation, and [width, height, depth] scale, an audio block specifying spatialized boolean, ref_distance, and max_distance, and an allow_focus_overlay boolean.

props array:
Contains objects defining placed 3D items. Each prop has a prop_id, model URI (pointing to a GLB file), is_interactive boolean, and default_transform block containing position, rotation_deg, and scale.

ambient_animations array:
Contains objects defining animated background details. Each animation has an id, type (flipbook or rotation), frames array of image paths, fps integer, rect defining normalized screen bounding box [X, Y, width, height], and depth_order integer.

SECTION 3: PERSPECTIVE SOLVER MATHEMATICS

The mathematical engine in modules/pubworld_stage/perspective_solver.py derives camera intrinsics and extrinsics deterministically from converging 2D lines that represent parallel physical lines in the scene.

Let Line Pair A represent two lines parallel to the world Z-axis (floorboard planks or receding walls):
Line A1 passes through points (x1, y1) and (x2, y2).
Line A2 passes through points (x3, y3) and (x4, y4).

Let Line Pair B represent two lines parallel to the world X-axis (rug edges, ceiling beams, or baseboards):
Line B1 passes through points (u1, v1) and (u2, v2).
Line B2 passes through points (u3, v3) and (u4, v4).

Intersection Calculation:
The intersection of Line A1 and Line A2 yields Vanishing Point 1 (VP1_x, VP1_y).
The intersection of Line B1 and Line B2 yields Vanishing Point 2 (VP2_x, VP2_y).
Standard determinant intersection formula:
X = (((x1y2 - y1x2)(x3 - x4)) - ((x1 - x2)(x3y4 - y3x4))) / (((x1 - x2)(y3 - y4)) - ((y1 - y2)(x3 - x4)))
Y = (((x1y2 - y1x2)(y3 - y4)) - ((y1 - y2)(x3y4 - y3x4))) / (((x1 - x2)(y3 - y4)) - ((y1 - y2)(x3 - x4)))

Camera Roll:
The slope of the horizon line connecting VP1 and VP2 determines roll:
roll_rad = arctan2(VP2_y - VP1_y, VP2_x - VP1_x)
camera_roll_deg = roll_rad * (180 / pi)

Focal Length:
Assuming the optical center (cx, cy) is at image center (width / 2, height / 2):
f_squared = -((VP1_x - cx)(VP2_x - cx) + (VP1_y - cy)(VP2_y - cy))
If f_squared is greater than 0, focal_length_px = sqrt(f_squared).
If f_squared is less than or equal to 0 (non-orthogonal lines), clamp focal length to a standard 35mm equivalent:
focal_length_px = (width / 2) / tan(22.5 * pi / 180)

Vertical Field of View:
fov_vertical_rad = 2 * arctan(height / (2 * focal_length_px))
calculated_fov_vertical = fov_vertical_rad * (180 / pi)

Camera Pitch:
Compute the perpendicular distance d from the image center (cx, cy) to the infinite line passing through VP1 and VP2.
pitch_rad = arctan(d / focal_length_px)
camera_pitch_deg = pitch_rad * (180 / pi)
The sign of pitch is negative if the horizon lies above the image center (camera looking downward).

SECTION 4: PROCEDURAL SURFACES, STAIRS, RAMPS, AND OCCLUSION GEOMETRY

Floor surfaces, elevation changes, and foreground occluders are built procedurally at scene launch to avoid custom modeling for each room.

Flat Floor Planes:
Constructed using Three.js PlaneGeometry with dimensions 100m by 100m, positioned at elevation_y and tilted to match camera_pitch_deg.
The material is THREE.ShadowMaterial with opacity set to 0.45. Color writing is enabled, but incoming diffuse color is transparent, capturing only real-time directional drop shadows from avatars and props.
Pathfinding and click-to-walk destination coordinates are strictly clamped within walkable_polygon using a 2D point-in-polygon raycasting algorithm.

Stairs and Ramps:
Stairs are represented physically as continuous inclined plane ramps rather than individual steps.
The geometry is built dynamically from the bounding vertices of the ramp polygon, connecting the lower elevation start to the upper landing elevation.
The ramp surface normal vector N is calculated from the cross product of its spanning vectors.
During avatar navigation, the avatar controller detects floor normal N. When N dot [0, 1, 0] is less than 0.95, the controller shifts locomotion from flat walk to stair climbing animation, adjusting avatar pitch to prevent foot penetration into the incline.

Drop Ledges:
Drop ledges separate two floor surfaces at different heights without an inclined ramp.
A boundary trigger line is established along the edge.
When an avatar reaches this boundary walking toward the lower elevation, player input is temporarily locked, a short hop-down animation plays, the avatar's transform Y snaps to the lower elevation plane, and normal walking controls resume on the lower polygon.

3D Depth Holdout Boxes:
Used for solid, geometric foreground furniture such as anchor desks, bar counters, and square pillars.
The box is instantiated as a standard THREE.BoxGeometry matching the object's physical dimensions.
The material is set to THREE.MeshBasicMaterial with colorWrite set to false and depthWrite set to true.
This renders the box completely invisible on screen, but it populates the GPU depth buffer (Z-buffer). Any 3D avatar or prop moving behind the box is automatically occluded by hardware depth testing without requiring manual artwork masking.

2D Foreground Sprite Cutouts:
Used for complex organic silhouettes such as hanging glassware, ceiling light fixtures, plants, or iron railings.
The cutout is stored as a transparent PNG and mapped onto a flat plane placed in the 3D scene at the exact depth_z distance of the real-world object.
When an avatar's Z-position is greater than depth_z, the cutout renders in front of the avatar. When the avatar walks closer to the camera than depth_z, the avatar renders in front of the cutout.

SECTION 5: IN-ENGINE CALIBRATOR AND SET BUILDER WORKFLOW

The authoring tool runs at /tools/calibrator and provides real-time visual alignment controls.

Setup and Alignment:
The background plate is loaded into Layer 1.
The user activates Guide Tool A (Red) and drags two lines over painted floorboard planks or receding walls.
The user activates Guide Tool B (Blue) and drags two lines over orthogonal features such as rug borders, table edges, or crossbeams.
Clicking Auto-Solve calls the perspective solver, sets camera pitch, roll, and FOV, and projects a bright green wireframe alignment grid over the floor.
Slider controls allow manual fine-tuning: Camera Pitch (+/- 45 deg), Camera Roll (+/- 20 deg), Camera Elevation (0.5m to 5.0m), and Horizon Offset (+/- 200px).

Surface and Boundary Definition:
The user clicks Add Surface, selects Plane, and clicks points on the canvas to outline the walkable floor polygon.
The user clicks Add Ramp, draws the boundary over the painted stairs, and sets the Landing Elevation slider until the ramp matches the painted upper floor height.
The user clicks Add Drop Ledge to draw curbs or stage lips.

Occluder Placement:
The user clicks Add Occluder and chooses 3D Depth Box.
A translucent wireframe box appears on screen. The user presses W to translate, E to rotate, or R to scale the box until it tightly envelopes the desk or bar counter in the painting.
Pressing G snaps the base of the box to the active floor surface.

Prop and Decoration Placement:
The user clicks Import Asset and selects any GLB file, PNG cutout, or JPG frame.
The asset spawns on the stage with an active transform gizmo.
The user positions, scales, and tilts the prop (for example, setting a framed photograph onto Purfluous's desk).
Clicking Commit Transform as Default saves the prop's transform to default_transform in the manifest so it always spawns in that resting position.

Live Avatar Scrubbing:
A test avatar puppet (Pete or Manny) stands on the stage.
The user drags a Depth Scrubber slider from 0% to 100%.
The avatar automatically walks from the foreground to the background wall along the solved floor plane, allowing immediate visual verification that character scaling, foot planting, and occluder clipping look natural across the entire space.

SECTION 6: VIDEO SCREEN PIPELINE AND AUDIO ARCHITECTURE

The video engine supports playing local video files, VTR clips, or live WebRTC incoming video calls on designated monitor surfaces in the scene.

In-World Screen Mapping:
In the calibrator, the user clicks Add Display and selects Video Surface.
A flat 3D plane spawns on the stage.
The user drags the four corners or uses transform gizmos to tilt and scale the quad so it fits inside the painted bezel of a television or monitor on set.
The quad's position, rotation angles, and dimensions are saved to interactive_screens in the manifest.
The video frames are rendered to a THREE.VideoTexture linked to a single HTML5 video element with minFilter and magFilter set to THREE.LinearFilter and generateMipmaps disabled.

Web Audio Routing Graph:
Audio from the video element connects to an AudioContext via createMediaElementSource and splits into two distinct parallel buses:

Path A: In-World Spatial Bus.
The signal flows into a Web Audio PannerNode with panningModel set to HRTF and distanceModel set to inverse.
The panner coordinates are continuously bound to the 3D world position of the screen quad.
The panner connects to an In-World GainNode, which connects to the audio destination.
As the player moves around the room, the video audio pans directionally and drops in volume with distance.

Path B: Focus Master Bus.
The signal flows directly into a Focus GainNode with no spatial panner, connecting to the audio destination.
In normal stage view, Focus Gain is set to 0.0 (muted) and In-World Gain is set to 1.0 (audible).

Click-to-Focus Overlay Modal:
When a user clicks the in-world television quad:
The room backdrop smoothly blurs and dims.
In-World Gain ramps to 0.0 over 120ms using linearRampToValueAtTime.
Focus Gain ramps to 1.0 over 120ms.
A 2D modal expands over Layer 4, displaying the exact same video element centered on screen at 16:9 aspect ratio.
Because the 2D overlay and the 3D texture share the exact same video element in memory, there is zero re-buffering, reloading, or audio stutter during the transition.
A clean transport bar docks at the bottom of the focus modal with controls: Seek Backward 10s, Play/Pause toggle, Stop (resets to 00:00:00), Seek Forward 10s, Skip Track, Volume Slider, and Return to Stage.
Closing the modal ramps Focus Gain back to 0.0 and In-World Gain back to 1.0, returning the camera to the room while the television continues playing in perspective.

SECTION 7: LIVE WEBRTC GUEST FEEDS, PERCEPTION TAP, AND AVATAR GAZE

Live remote guests connect via browser WebRTC and participate as active broadcast participants.

Live Feed Ingest:
The remote guest connects over a standard WebRTC PeerConnection.
The incoming remote MediaStreamTrack for video is assigned directly to the video element's srcObject.
The incoming video renders live onto the in-world monitor quad at 30 or 60 FPS with sub-100ms latency.
The remote audio track feeds both the room spatial audio panner and a silent digital perception tap.

Agent Speech Perception Tap:
The guest's raw audio feed streams over a local WebSocket directly into the speech-to-text service in modules/stt_engine.py.
Transcriptions are delivered into the shared conversational orchestration bus (Jeremy / Cricket) with role labeled as remote_guest.
AI character agents (Pete, Alex, Purfluous) parse the transcript in real time, detect when the guest stops talking, and generate contextual dialogue responses.

Avatar Gaze and Eye-Line Control:
Each character avatar rig contains a Head and Eye Look-At IK constraint managed by modules/avatar_studio_bridge.py.
The screen quad exports its center coordinate [X, Y, Z] to the stage state.
When the remote guest is speaking, character avatars within sightlines calculate direction vector D = P_screen - P_head and smoothly slerp their head and neck bones toward the monitor over 250ms.
An eye-saccade generator adds subtle micro-drift (+/- 3.5 degrees) every 1.5 to 3.0 seconds across the screen area, preventing static gaze fixation and creating the illusion that characters are watching the speaker's face.

Production Mode Split:
Live Guests: Always rendered directly on the television monitor quad using real-time WebRTC video and spatial audio.
Pre-Recorded Interviews: Audio is processed through an offline forced-viseme aligner, and video is processed through pose extraction to generate neck and shoulder Euler rotation tracks. The character spawner can then instantiate a 3D avatar directly into an empty chair on Layer 2, delivering synchronous lip-sync and body posture without webcam jitter.

SECTION 8: MULTI-CAM VISION SWITCHER AND AUTONOMOUS DIRECTOR

The broadcast production suite provides both tactile manual camera switching and automated speaker-tracking direction.

Switcher Bus Architecture:
The switcher maintains two video buses: Preview Bus (the staged camera angle being cued) and Program Bus (the live camera angle being broadcast or recorded).
Camera sources include Cam 1 (Wide Establishing), Cam 2 (Anchor Close), Cam 3 (Guest Monitor OTS), Cam 4 (Weather Wall), and Source 5 (Direct VTR / Screen Feed).

Manual Control Mappings:
Keys 1 through 5: Select corresponding input onto the Preview Bus.
Spacebar: CUT command. Instantly swaps Preview Bus and Program Bus.
Enter: AUTO command. Executes a smooth cross-dissolve or directional wipe over a configured duration (default 30 frames / 1000ms).
Key F: Focus active monitor full-screen.
Key M: Master mute toggle.

Autonomous Director Engine:
Implemented in modules/director_engine.py as an event loop running every 100ms.
Input Signals: Ingests RMS audio energy levels from microphone channels (Anchor A, Anchor B, Guest Stream) and speech-start/speech-stop events from the STT engine.
Hold Timer Rule: Once a camera cut occurs, the director locks the shot for a minimum of 2.5 seconds to eliminate erratic rapid switching.

Switching Rules:
If Guest Speech Energy exceeds -24 dB for more than 400ms: Cue and cut to Cam 3 (Guest Monitor OTS) or trigger full-screen focus.
If Anchor A Speech Energy exceeds -24 dB: Cue and cut to Cam 2 (Anchor Close).
If Multiple Speakers Speak Simultaneously: Cut to Cam 1 (Wide Establishing Two-Shot).
If Silence exceeds 4.0 seconds: Cut to Cam 1 (Wide Establishing).
Reaction Shot Rule: If one speaker talks continuously for more than 6.0 seconds, the director triggers a 1.8-second cutaway reaction shot to an off-axis listening avatar nodding, then returns to the active speaker.

Tally and Broadcast Events:
Every camera transition on the Program Bus broadcasts a tally packet across the WebSocket room stage_control:
Event name: broadcast_tally_change
Payload: active_camera_id, camera_world_position [X, Y, Z], transition_type (cut or dissolve), duration_ms.
On-air avatars receive this packet and orient their primary gaze toward the live camera lens.

SECTION 9: OPERATOR STEP-BY-STEP TUTORIALS

These instructions are served inside the builder UI help drawer at /tools/calibrator/docs.

Tutorial 1: Calibrating Background Camera Perspective
Step 1: Click Import Art and select the background image file (PNG or JPG). The image displays in native resolution on the canvas.
Step 2: Click Vanishing Guide A. Click and drag two red line segments over painted features receding along the floorboards or side walls toward the distance.
Step 3: Click Vanishing Guide B. Click and drag two blue line segments over features that run perpendicular to the first set, such as a rug edge, desk front, or crossbeam.
Step 4: Click Auto-Solve Perspective. The system calculates intersections, sets pitch, roll, and vertical FOV, and projects a green wireframe grid over the floor.
Step 5: Drag the Camera Pitch or Horizon Height sliders until the green grid lines lay flat along the painted floorboards.

Tutorial 2: Adding Walkable Surfaces, Stairs, and Drops
Step 1: Click Add Surface and select Plane. Click four points on the canvas to outline the walkable floor boundary. Avatars cannot step outside this shape.
Step 2: For staircases, click Add Surface and select Ramp. Drag the lower edge to meet the floor polygon and drag the upper edge to the top landing. Adjust the Landing Elevation slider until the ramp matches the height of the painted balcony.
Step 3: For ledges or stages, click Add Surface and select Drop Ledge. Draw the ledge edge line. Avatars stepping over this line play a hop animation down to the lower floor.

Tutorial 3: Placing Occluders for Counters and Furniture
Step 1: For solid objects like desks or bars, click Add Occluder and choose 3D Depth Box. A wireframe box appears.
Step 2: Press W to move, E to rotate, and R to scale the box so it matches the painted furniture. Press G to drop it flush to the floor. The box is invisible in the broadcast, but avatars walking behind it will have their lower bodies occluded naturally.
Step 3: For delicate objects like hanging lamps or iron railings, click Add Occluder and select 2D Cutout. Upload a transparent PNG of the object and adjust its Z-Depth slider to set where it sits relative to walking actors.

Tutorial 4: Placing Interactive Video Screens and Props
Step 1: Click Add Display and select Video Surface. A 3D quad appears.
Step 2: Drag the corners or use transform handles to tilt and position the quad so it sits inside the bezel of the painted television.
Step 3: Select Local File, Playlist, or Live WebRTC Stream. The video immediately plays on the wall in perspective with spatial audio.
Step 4: Click Add Prop and select any GLB file (such as a mug, bottle, or picture frame). Position and rotate the prop on Sir Purfluous's desk. Press G to snap it flush to the desktop.
Step 5: Click Commit Transform as Default. The prop will now persist in that exact spot every time the room loads.

SECTION 10: CLAUDE IMPLEMENTATION ROADMAP AND SOURCE CODE

Claude should build this subsystem into PubCast Reach strictly following the project structure below, with zero regressions against the existing 1,042 test suite.

File Layout:
modules/pubworld_stage/init.py
modules/pubworld_stage/perspective_solver.py
modules/pubworld_stage/manifest_store.py
modules/pubworld_stage/stage_service.py
modules/director_engine.py
static/stage_builder/index.html
static/stage_builder/stage_builder.js
static/stage_builder/video_surface.js
static/stage_builder/switcher_panel.js
tests/test_perspective_solver.py
tests/test_stage_manifest.py
tests/test_director_engine.py

FILE: modules/pubworld_stage/perspective_solver.py
Content:

import math
from typing import Tuple, List, Optional
from pydantic import BaseModel

class Line2D(BaseModel):
    p1: Tuple[float, float]
    p2: Tuple[float, float]

class SolverResult(BaseModel):
    success: bool
    pitch_deg: float
    roll_deg: float
    fov_vertical_deg: float
    focal_length_px: float
    horizon_y_ratio: float
    error_message: Optional[str] = None

class PerspectiveSolver:
    @staticmethod
    def compute_intersection(line1: Line2D, line2: Line2D) -> Optional[Tuple[float, float]]:
        x1, y1 = line1.p1
        x2, y2 = line1.p2
        x3, y3 = line2.p1
        x4, y4 = line2.p2

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6:
            return None

        t1 = x1 * y2 - y1 * x2
        t2 = x3 * y4 - y3 * x4

        px = (t1 * (x3 - x4) - (x1 - x2) * t2) / denom
        py = (t1 * (y3 - y4) - (y1 - y2) * t2) / denom
        return (px, py)

    @classmethod
    def solve(
        cls,
        pair_a_line1: Line2D,
        pair_a_line2: Line2D,
        pair_b_line1: Line2D,
        pair_b_line2: Line2D,
        image_width: float,
        image_height: float
    ) -> SolverResult:
        vp1 = cls.compute_intersection(pair_a_line1, pair_a_line2)
        vp2 = cls.compute_intersection(pair_b_line1, pair_b_line2)

        if not vp1 or not vp2:
            return SolverResult(
                success=False,
                pitch_deg=0.0,
                roll_deg=0.0,
                fov_vertical_deg=45.0,
                focal_length_px=(image_width / 2.0) / math.tan(math.radians(22.5)),
                horizon_y_ratio=0.5,
                error_message="Lines are parallel; vanishing points could not be established."
            )

        cx = image_width / 2.0
        cy = image_height / 2.0

        dx = vp2[0] - vp1[0]
        dy = vp2[1] - vp1[1]
        roll_rad = math.atan2(dy, dx)
        roll_deg = math.degrees(roll_rad)

        f_squared = -((vp1[0] - cx) * (vp2[0] - cx) + (vp1[1] - cy) * (vp2[1] - cy))
        if f_squared > 0:
            focal_length_px = math.sqrt(f_squared)
        else:
            focal_length_px = (image_width / 2.0) / math.tan(math.radians(22.5))

        fov_v_rad = 2.0 * math.atan(image_height / (2.0 * focal_length_px))
        fov_v_deg = math.degrees(fov_v_rad)

        line_mag = math.hypot(dx, dy)
        if line_mag < 1e-6:
            dist_to_horizon = cy - vp1[1]
        else:
            dist_to_horizon = ((vp2[0] - vp1[0]) * (vp1[1] - cy) - (vp1[0] - cx) * (vp2[1] - vp1[1])) / line_mag

        pitch_rad = math.atan(dist_to_horizon / focal_length_px)
        pitch_deg = math.degrees(pitch_rad)

        horizon_y_center = vp1[1] + (cx - vp1[0]) * (dy / dx) if abs(dx) > 1e-6 else vp1[1]
        horizon_y_ratio = max(0.0, min(1.0, horizon_y_center / image_height))

        return SolverResult(
            success=True,
            pitch_deg=round(pitch_deg, 2),
            roll_deg=round(roll_deg, 2),
            fov_vertical_deg=round(fov_v_deg, 2),
            focal_length_px=round(focal_length_px, 2),
            horizon_y_ratio=round(horizon_y_ratio, 4)
        )

FILE: modules/pubworld_stage/manifest_store.py
Content:

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class CameraShot(BaseModel):
    label: str
    position: List[float] = Field(default_factory=lambda: [0.0, 1.65, 4.0])
    rotation_deg: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    fov: float = 45.0

class CameraSetup(BaseModel):
    default_shot: str = "cam_wide"
    focal_length_mm: float = 35.0
    sensor_height_mm: float = 24.0
    calculated_fov_vertical: float = 45.0
    horizon_y_ratio: float = 0.5
    camera_pitch_deg: float = 0.0
    camera_roll_deg: float = 0.0
    camera_elevation_m: float = 1.65
    shots: Dict[str, CameraShot] = Field(default_factory=dict)

class GroundSurface(BaseModel):
    surface_id: str
    type: str  # plane, ramp, drop_ledge
    elevation_y: float = 0.0
    pitch_deg: float = 0.0
    elevation_start_y: Optional[float] = None
    elevation_end_y: Optional[float] = None
    ramp_pitch_deg: Optional[float] = None
    ledge_trigger_line: Optional[List[List[float]]] = None
    walkable_polygon: List[List[float]] = Field(default_factory=list)

class Transform3D(BaseModel):
    position: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation_deg: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: List[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])

class Occluder(BaseModel):
    occluder_id: str
    type: str  # 3d_depth_box, 2d_sprite_plane
    transform: Optional[Transform3D] = None
    image: Optional[str] = None
    depth_z: Optional[float] = None
    position: Optional[List[float]] = None

class ScreenAudio(BaseModel):
    spatialized: bool = True
    ref_distance: float = 1.5
    max_distance: float = 10.0

class InteractiveScreen(BaseModel):
    screen_id: str
    label: str
    type: str  # local_file, playlist, webrtc_stream
    stream_channel: Optional[str] = None
    fallback_video: Optional[str] = None
    transform: Transform3D
    audio: ScreenAudio = Field(default_factory=ScreenAudio)
    allow_focus_overlay: bool = True

class PropItem(BaseModel):
    prop_id: str
    model: str
    is_interactive: bool = True
    default_transform: Transform3D

class AmbientAnimation(BaseModel):
    id: str
    type: str  # flipbook, rotation
    frames: List[str] = Field(default_factory=list)
    fps: int = 8
    rect: List[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    depth_order: int = 0

class SceneManifest(BaseModel):
    schema_version: str = Field(default="1.0.0", alias="$schema")
    scene_id: str
    title: str
    version: str = "1.0.0"
    background_image: str
    camera_setup: CameraSetup
    ground_surfaces: List[GroundSurface] = Field(default_factory=list)
    occluders: List[Occluder] = Field(default_factory=list)
    interactive_screens: List[InteractiveScreen] = Field(default_factory=list)
    props: List[PropItem] = Field(default_factory=list)
    ambient_animations: List[AmbientAnimation] = Field(default_factory=list)

class ManifestStore:
    def init(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def get_manifest_path(self, scene_id: str) -> Path:
        return self.storage_root / scene_id / "scene_manifest.json"

    def load(self, scene_id: str) -> Optional[SceneManifest]:
        target = self.get_manifest_path(scene_id)
        if not target.exists():
            return None
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SceneManifest.model_validate(data)

    def save(self, manifest: SceneManifest) -> Path:
        target = self.get_manifest_path(manifest.scene_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(by_alias=True), f, indent=2)
        return target

    def export_bundle(self, scene_id: str) -> Optional[bytes]:
        scene_dir = self.storage_root / scene_id
        if not scene_dir.exists():
            return None

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for file_path in scene_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(scene_dir)
                    z.write(file_path, arcname)
        buf.seek(0)
        return buf.getvalue()

    def import_bundle(self, scene_id: str, bundle_bytes: bytes) -> bool:
        scene_dir = self.storage_root / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)
        buf = BytesIO(bundle_bytes)
        with zipfile.ZipFile(buf, "r") as z:
            z.extractall(scene_dir)
        return self.get_manifest_path(scene_id).exists()

FILE: modules/director_engine.py
Content:

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel

class SwitcherState(BaseModel):
    program_camera: str = "cam_wide"
    preview_camera: str = "cam_anchor_close"
    in_transition: bool = False
    transition_type: str = "cut"
    transition_progress: float = 0.0
    last_switch_timestamp: float = 0.0
    manual_override: bool = False

class DirectorDecision(BaseModel):
    action: str  # HOLD, CUT, AUTO_TRANSITION, FOCUS_SCREEN
    target_camera: Optional[str] = None
    target_screen: Optional[str] = None
    reason: str

class AutonomousDirector:
    def init(self, min_hold_duration_sec: float = 2.5, silence_threshold_sec: float = 4.0):
        self.min_hold_duration_sec = min_hold_duration_sec
        self.silence_threshold_sec = silence_threshold_sec
        self.state = SwitcherState(last_switch_timestamp=time.time())

    def manual_cut(self, new_camera: str) -> Dict[str, Any]:
        self.state.program_camera = new_camera
        self.state.last_switch_timestamp = time.time()
        self.state.in_transition = False
        return {
            "event": "broadcast_tally_change",
            "active_camera_id": self.state.program_camera,
            "transition_type": "cut",
            "timestamp": self.state.last_switch_timestamp
        }

    def evaluate(
        self,
        anchor_a_energy_db: float,
        anchor_b_energy_db: float,
        guest_energy_db: float,
        current_time: Optional[float] = None
    ) -> DirectorDecision:
        now = current_time or time.time()
        time_since_last_cut = now - self.state.last_switch_timestamp

        if self.state.manual_override:
            return DirectorDecision(action="HOLD", reason="Manual override active")

        if time_since_last_cut < self.min_hold_duration_sec:
            return DirectorDecision(action="HOLD", reason="Minimum hold duration not met")

        threshold_active_db = -24.0
        guest_active = guest_energy_db > threshold_active_db
        anchor_a_active = anchor_a_energy_db > threshold_active_db
        anchor_b_active = anchor_b_energy_db > threshold_active_db

        active_count = sum([guest_active, anchor_a_active, anchor_b_active])

        if active_count > 1:
            if self.state.program_camera != "cam_wide":
                self.manual_cut("cam_wide")
                return DirectorDecision(action="CUT", target_camera="cam_wide", reason="Multiple speakers active; cut to wide")
            return DirectorDecision(action="HOLD", reason="Holding wide on overlapping speech")

        if guest_active:
            if self.state.program_camera != "cam_guest_monitor":
                self.manual_cut("cam_guest_monitor")
                return DirectorDecision(action="CUT", target_camera="cam_guest_monitor", reason="Remote guest dominant speaker")
            return DirectorDecision(action="HOLD", reason="Holding guest monitor")

        if anchor_a_active:
            if self.state.program_camera != "cam_anchor_close":
                self.manual_cut("cam_anchor_close")
                return DirectorDecision(action="CUT", target_camera="cam_anchor_close", reason="Anchor A dominant speaker")
            return DirectorDecision(action="HOLD", reason="Holding Anchor A")

        if anchor_b_active:
            if self.state.program_camera != "cam_weather_wall":
                self.manual_cut("cam_weather_wall")
                return DirectorDecision(action="CUT", target_camera="cam_weather_wall", reason="Anchor B dominant speaker")
            return DirectorDecision(action="HOLD", reason="Holding Anchor B")

        if active_count == 0 and time_since_last_cut > self.silence_threshold_sec:
            if self.state.program_camera != "cam_wide":
                self.manual_cut("cam_wide")
                return DirectorDecision(action="CUT", target_camera="cam_wide", reason="Cadence silence timeout; return to wide")

        return DirectorDecision(action="HOLD", reason="Conversation state stable")

FILE: tests/test_perspective_solver.py
Content:

import pytest
from modules.pubworld_stage.perspective_solver import PerspectiveSolver, Line2D

def test_perspective_solver_orthogonal_box():
    line_a1 = Line2D(p1=(100.0, 800.0), p2=(400.0, 450.0))
    line_a2 = Line2D(p1=(300.0, 900.0), p2=(500.0, 450.0))
    line_b1 = Line2D(p1=(1800.0, 800.0), p2=(1500.0, 450.0))
    line_b2 = Line2D(p1=(1600.0, 900.0), p2=(1400.0, 450.0))

    result = PerspectiveSolver.solve(
        pair_a_line1=line_a1,
        pair_a_line2=line_a2,
        pair_b_line1=line_b1,
        pair_b_line2=line_b2,
        image_width=1920.0,
        image_height=1080.0
    )

    assert result.success is True
    assert 10.0 <= result.fov_vertical_deg <= 90.0
    assert result.horizon_y_ratio < 0.60
    assert result.focal_length_px > 0

def test_perspective_solver_parallel_lines_fallback():
    line_a1 = Line2D(p1=(100.0, 100.0), p2=(100.0, 800.0))
    line_a2 = Line2D(p1=(300.0, 100.0), p2=(300.0, 800.0))
    line_b1 = Line2D(p1=(100.0, 100.0), p2=(800.0, 100.0))
    line_b2 = Line2D(p1=(100.0, 300.0), p2=(800.0, 300.0))

    result = PerspectiveSolver.solve(
        pair_a_line1=line_a1,
        pair_a_line2=line_a2,
        pair_b_line1=line_b1,
        pair_b_line2=line_b2,
        image_width=1920.0,
        image_height=1080.0
    )

    assert result.success is False
    assert result.fov_vertical_deg == 45.0
    assert "parallel" in result.error_message.lower()

FILE: tests/test_stage_manifest.py
Content:

import json
from pathlib import Path
from modules.pubworld_stage.manifest_store import (
    ManifestStore, SceneManifest, CameraSetup, GroundSurface, Transform3D, PropItem
)

def test_manifest_serialization_roundtrip(tmp_path):
    store = ManifestStore(storage_root=tmp_path)

    manifest = SceneManifest(
        scene_id="test_studio_set",
        title="Test Studio",
        background_image="/assets/test.png",
        camera_setup=CameraSetup(camera_pitch_deg=15.0),
        ground_surfaces=[
            GroundSurface(surface_id="main_floor", type="plane", elevation_y=0.0)
        ],
        props=[
            PropItem(
                prop_id="chair_01",
                model="/assets/chair.glb",
                default_transform=Transform3D(position=[1.0, 0.0, 2.0])
            )
        ]
    )

    saved_path = store.save(manifest)
    assert saved_path.exists()

    loaded = store.load("test_studio_set")
    assert loaded is not None
    assert loaded.scene_id == "test_studio_set"
    assert loaded.camera_setup.camera_pitch_deg == 15.0
    assert len(loaded.props) == 1
    assert loaded.props[0].default_transform.position == [1.0, 0.0, 2.0]

def test_manifest_export_import_bundle(tmp_path):
    store_a = ManifestStore(storage_root=tmp_path / "origin")
    store_b = ManifestStore(storage_root=tmp_path / "destination")

    manifest = SceneManifest(
        scene_id="bundle_scene",
        title="Bundle Room",
        background_image="/assets/room.png",
        camera_setup=CameraSetup(camera_pitch_deg=22.0)
    )
    store_a.save(manifest)

    bundle_bytes = store_a.export_bundle("bundle_scene")
    assert bundle_bytes is not None

    success = store_b.import_bundle("bundle_scene", bundle_bytes)
    assert success is True

    imported_manifest = store_b.load("bundle_scene")
    assert imported_manifest is not None
    assert imported_manifest.camera_setup.camera_pitch_deg == 22.0

FILE: tests/test_director_engine.py
Content:

from modules.director_engine import AutonomousDirector

def test_autonomous_director_cuts_to_guest():
    director = AutonomousDirector(min_hold_duration_sec=2.0)
    now = 1000.0

    decision = director.evaluate(
        anchor_a_energy_db=-60.0,
        anchor_b_energy_db=-60.0,
        guest_energy_db=-10.0,
        current_time=now + 2.5
    )

    assert decision.action == "CUT"
    assert decision.target_camera == "cam_guest_monitor"
    assert director.state.program_camera == "cam_guest_monitor"

def test_autonomous_director_respects_min_hold():
    director = AutonomousDirector(min_hold_duration_sec=3.0)
    start_time = 1000.0

    director.evaluate(
        anchor_a_energy_db=-10.0,
        anchor_b_energy_db=-60.0,
        guest_energy_db=-60.0,
        current_time=start_time + 4.0
    )
    assert director.state.program_camera == "cam_anchor_close"

    decision = director.evaluate(
        anchor_a_energy_db=-60.0,
        anchor_b_energy_db=-60.0,
        guest_energy_db=-10.0,
        current_time=start_time + 5.0
    )
    assert decision.action == "HOLD"
    assert "hold duration not met" in decision.reason

def test_autonomous_director_silence_cut_to_wide():
    director = AutonomousDirector(min_hold_duration_sec=2.0, silence_threshold_sec=4.0)
    start_time = 1000.0

    director.evaluate(-10.0, -60.0, -60.0, current_time=start_time + 3.0)
    assert director.state.program_camera == "cam_anchor_close"

    decision = director.evaluate(-60.0, -60.0, -60.0, current_time=start_time + 8.5)
    assert decision.action == "CUT"
    assert decision.target_camera == "cam_wide"
    assert "silence timeout" in decision.reason

EXECUTION VERIFICATION SEQUENCE:

Save the above files into the canonical repository.

Run pytest tests/test_perspective_solver.py tests/test_stage_manifest.py tests/test_director_engine.py to verify mathematical stability, schema validity, and automated switching accuracy.

Run the full canonical regression suite to ensure zero regressions across the existing 1,042 test baseline.


---

# PART II — TECHNICAL CRITIQUE AND RECOMMENDATIONS

# TECHNICAL CRITIQUE, TROUBLESHOOTING, PUBCAST ADJUSTMENTS, PERFORMANCE, GRAPHICS, AND USER EXPERIENCE

Yes. The core idea is strong, and a large part of it will work, but I would not hand this specification to Claude and say “build exactly this” yet. There are several places where it will either fail outright, produce visually wrong results, or quietly lock PubCast into an architecture we’ll regret.

The most important repository issue discovered during review is that the current `whatsupjosie/Pubcast-Reach` GitHub repository appears to be primarily a documentation/artwork shell rather than the complete runnable application source. The visible repository contents include design files, artwork, and Cricket documentation rather than the expected Python/JavaScript runtime, so the statement “save these files into the canonical repository and run the 1,042-test regression suite” should not be acted on until the actual runnable canonical Reach source repository or branch is identified.

## The biggest problem: one painted set cannot support those cameras as written

This is the one thing I would change before writing a line of Stage Engine code.

The specification says:

> one fixed-perspective background plate

and then gives cameras with independent:

- XYZ positions
- pitch/yaw/roll
- FOV

Those two ideas conflict.

If we calibrate a painting for one camera position, then move the Three.js camera three feet to the side for an over-the-shoulder shot, the painting does not acquire new perspective. The 3D avatar does.

So Pete moves correctly.

The desk moves correctly.

The television moves correctly.

But the room painting stays the same.

Everything starts sliding against everything else.

### PubCast needs three types of shots

I would make this explicit in the manifest:

```text
shot_mode:

CROP
    Same calibrated physical camera.
    Pan/crop/zoom the rendered composition.
    Cheap and perfectly aligned.

PLATE
    Alternate painted background plate with its own calibration.
    Used for genuinely different camera angles.

THREE_D
    Actual free-moving camera.
    Allowed only for scenes with sufficient reconstructed 3D geometry.
```

That actually makes the system more useful rather than less.

A normal hand-painted PubCast room could have:

- Wide — calibrated master plate
- Pete close-up — crop of master
- Alex close-up — crop of master
- Weather wall — crop of master
- TV close-up — crop or direct source
- Dramatic side angle — optional alternate plate

And because these are crops rather than additional complete 3D renders, they're extremely cheap.

For a fancier room later, we can provide multiple painted camera plates.

That's very much in keeping with the thing you've been describing for PubWorld: don't model what doesn't need modeling.

## The second major issue: calibration currently solves perspective, but not scale

Two vanishing points can give us:

- horizon
- roll
- focal length/FOV under assumptions
- pitch

They cannot tell us:

> How many pixels equal one meter?

That's critical.

Otherwise Pete may technically stand on the floor but appear 9 feet tall beside a painted chair.

We need one scale reference.

The builder should have:

### Set Scale tool

Click two points corresponding to a known physical distance.

Examples:

> Floor → top of doorway = 2.03 m

or

> floor → top of Manny = 1.75 m

or

> front edge of desk = 1.8 m wide

Then we know actual world scale.

I'd actually make the test puppet part of this:

> “Pete is 1.78 m tall. Drag Pete until his feet and head match the painted reference.”

Boom.

Calibration becomes intuitive rather than mathematical.

## There is another geometry error

This:

> Flat Floor Planes... tilted to match `camera_pitch_deg`

should not happen.

The floor stays horizontal.

The camera pitches.

If we pitch the camera 15° and then tilt the floor 15° to compensate, we've applied the perspective correction twice.

World convention should be:

```text
Y = vertical
XZ = floor

floor normal = [0, 1, 0]

camera = pitched/rolled
```

Ramps are physically tilted.

Floors are not.

That's an important correction.

## The builder needs screen-to-world projection

This is currently missing entirely.

The spec says:

> user draws a polygon on the painting

and then somehow that becomes a 3D walking surface.

We need the actual operation connecting those two things.

For every clicked canvas point:

```text
screen coordinate
      ↓
camera ray
      ↓
intersect ray with chosen floor plane
      ↓
world XYZ
```

So I would store both:

```text
authoring_polygon_uv
world_polygon_xz
```

The screen polygon is useful for editing.

The world polygon is what Pete actually walks on.

Otherwise the navigation controller is being asked to walk around using pixels.

## Also: don't call normalized screen coordinates X/Y

That's going to become confusing almost immediately because Three.js already uses Y as vertical.

Call them:

```text
[u, v]
```

Then:

```text
world = [x, y, z]
screen = [u, v]
```

Tiny change. Huge reduction in future bullshit.

## The ramp behavior needs adjustment

The general ramp idea is excellent.

Using ramps underneath painted stairs is exactly the right cheat.

But this part:

> adjust avatar pitch to prevent foot penetration

would make people lean forward/backward with the staircase.

Humans don't rotate their entire bodies parallel to stairs.

Better:

- root stays upright
- root Y follows ramp
- locomotion blends into stair animation
- foot IK plants feet on incline
- knees compensate

And don't infer stairs solely from:

```text
normal dot up < 0.95
```

We already know the object is a `ramp`.

Use its semantic type.

That gives us much more predictable animation.

## We need a surface connectivity graph

Right now there are surfaces but not a proper relationship between them.

PubWorld really wants:

```text
main_floor
   │
 ramp_01
   │
balcony
   │
drop_ledge
   ↓
lower_stage
```

Each connection knows:

- from surface
- to surface
- traversal type
- direction
- height
- animation
- whether reversible

Then pathfinding can say:

> Pete can walk from bar → staircase → balcony.

Instead of simply:

> Pete is constrained inside this polygon.

That becomes the beginning of real PubWorld navigation without requiring a complicated navmesh package.

## Perspective solver: good idea, needs to become forgiving

The mathematics are fundamentally reasonable under:

- centered principal point
- square pixels
- zero skew
- approximately orthogonal world axes

But we're dealing with art.

People cheat perspective when they draw.

I wouldn't make the user draw exactly four perfect lines.

Let them draw several red and blue guides:

```text
A1
A2
A3
A4

B1
B2
B3
```

Then fit the best vanishing points.

That gives us a confidence value:

> Perspective solve: 94%

or

> Perspective solve: 51% — guides disagree. Fine-tune manually.

Much friendlier.

And add:

- one-point perspective mode
- two-point perspective mode
- manual mode

Some gorgeous PubCast sets are inevitably going to be deliberately geometrically impossible.

The engine should say:

> Cool.

rather than:

> ERROR: ART IS WRONG.

## Do not clamp the horizon to the picture

This code:

```python
max(0.0, min(1.0, horizon_y_ratio))
```

should go.

The horizon can legitimately be above or below the image.

Clamping it destroys useful calibration information.

Allow values like:

```text
-0.18
1.12
```

The builder can still display an offscreen indicator.

## There's a focal-length inconsistency too

The fallback says 45° but calculates the focal length using:

```python
width / 2 / tan(22.5°)
```

which produces 45° horizontal FOV.

The reported value is then:

```text
vertical FOV = 45°
```

Those aren't the same on a 16:9 image.

We need to choose one canonical quantity.

Three.js cameras naturally want vertical FOV, so I would make:

> vertical FOV authoritative everywhere.

Then derive focal length from image height.

## The manifest is a good beginning, not yet a strict schema

It's described as “strict Pydantic,” but most of the fields currently accept almost anything.

For example:

```python
type: str
```

should become something equivalent to:

```python
Literal["plane", "ramp", "drop_ledge"]
```

And:

```text
position → exactly 3 numbers
rotation → exactly 3
screen UV → exactly 2
rect → exactly 4
```

Normalized coordinates need validation.

Scale cannot normally be zero.

FPS should have bounds.

IDs should obey safe naming rules.

Scene IDs especially must not permit:

```text
../../anything
```

because they're currently being used as filesystem paths.

## There is an actual security bug in the proposed importer

This:

```python
z.extractall(scene_dir)
```

cannot ship as-is.

A malicious ZIP can contain:

```text
../../some_file
```

and escape the scene directory.

Bundle import needs safe extraction and path validation.

That's not theoretical cruft; it's an easy fix now and an awful thing to discover after people can share PubCast sets.

## Bundles need to actually be portable

Currently a manifest may say:

```text
/assets/chair.glb
```

but `export_bundle()` only zips files physically inside the scene directory.

So we could export a “scene bundle” missing half the scene.

I want a bundle packer that produces:

```text
scene_manifest.json
assets/
    background.webp
    monitor_fallback.mp4
    desk.glb
    railing.png
    ...
```

and rewrites the manifest to portable relative URIs.

Also:

```text
bundle_version
manifest_version
checksums
```

Then people can email/share/import sets.

That could become a genuinely fun PubCast ecosystem later.

## The proposed code literally won't pass the tests right now

There are two very simple transcription/code mistakes.

Both classes use:

```python
def init(...)
```

instead of:

```python
def __init__(...)
```

So:

```python
ManifestStore(storage_root=tmp_path)
```

fails.

And:

```python
AutonomousDirector(min_hold_duration_sec=2)
```

fails.

Similarly the proposed file:

```text
modules/pubworld_stage/init.py
```

should be:

```text
modules/pubworld_stage/__init__.py
```

Those are easy fixes.

## The Director code doesn't yet implement the Director specification

This is a much larger discrepancy.

The written spec says:

- guest must be active for >400 ms
- speech-start/speech-stop events
- 6-second continuous-speaker detection
- 1.8-second reaction shot
- return to active speaker
- Preview bus
- Program bus
- CUT
- AUTO
- dissolves
- screen focus
- camera coordinates in tally packet

The supplied `director_engine.py` doesn't implement most of that yet.

It currently just asks:

> Which channel is above -24 dB right now?

and chooses a camera.

That's a useful prototype, but not the described director.

## And its timing is currently broken

The constructor starts with real Unix time:

```python
time.time()
```

The tests use:

```python
current_time = 1002.5
```

So:

```text
1002.5 - ~1,800,000,000
```

is a giant negative duration.

The minimum-hold test immediately fails.

We should give the Director an injectable clock.

Then every decision uses the same clock.

That gives us deterministic tests and also makes replaying Blackbox sessions possible.

That last part is particularly interesting for PubCast.

You could replay:

> Why the hell did the director cut to Manny there?

and reconstruct exactly what it saw.

## Raw -24 dB switching will look twitchy

Even with the 2.5-second hold.

Audio levels bounce.

Instead:

```text
audio RMS
   ↓
short moving average
   ↓
voice activity detector
   ↓
speech-start / continuing / stop
   ↓
STT confirmation
   ↓
Director
```

Give every speaker a tiny hysteresis window.

Something like:

> activate after 250–400 ms
> release after 300–500 ms

That will feel dramatically more human.

## PubCast can do something better than an ordinary auto-director

This is where our existing architecture becomes useful.

The Director should not become another Jeremy.

It shouldn't be thinking about everything.

I would keep responsibilities separated:

**Director Engine**
handles camera grammar mechanically.

**Pub Manager**
chooses production mode and has authority over the show.

**E-Pete**
deals with operational/render problems.

**Jeremy**
provides meaningful conversational state where appropriate.

**System Alex**
can provide limited emotional/contextual cues.

**Blackbox**
records what happened and why.

That means the director can occasionally receive structured cues like:

```text
moment_type: emotional
speaker: Alex
interruptibility: low
```

Then instead of doing the dumb:

> six seconds elapsed — REACTION SHOT!

it can know:

> Don't fucking cut away right now.

That's a really PubCast thing.

And it doesn't require an LLM making every camera decision.

Most direction remains a tiny deterministic state machine.

## Give the Director styles

This could be ridiculously fun and almost free computationally.

Not “AI models.” Just rule presets.

For example:

**News**
- steady
- longer holds
- clean closeups
- very few reactions

**Talk Show**
- more listener reactions
- occasional wide
- monitor OTS
- moderate pacing

**Sitcom**
- wider two-shots
- reaction shots
- longer visual jokes

**Documentary**
- slower
- off-axis
- pauses tolerated

**Chaos**
- snap zooms
- aggressive cuts
- deliberately cheesy wipes

The operator could literally tell Pub Manager:

> Run this like a late-night show.

That's delightful.

## The video architecture is mostly excellent

The shared video-element idea is particularly good.

One decoder feeds:

```text
VideoTexture → television
       +
DOM focus view → fullscreen
```

No reload.

No resync.

That's exactly what I would want.

There are a few implementation details we need:

- Only create one `MediaElementSource` per video element.
- Prevent accidental direct audio + WebAudio double playback.
- Unlock `AudioContext` from a user gesture on browsers that require it.
- Use `requestVideoFrameCallback()` where supported rather than blindly uploading textures every render frame.
- For WebRTC, don't promise `<100ms`; design for low latency and report measured latency.

I'd also make the crossfade equal-power rather than linear.

Tiny thing, sounds nicer.

## Local focus and broadcast focus must be separate

This is PubCast-specific and important.

Suppose a guest clicks the television.

Do they:

1. enlarge the screen only on their device, or
2. take the television fullscreen on the broadcast?

Those cannot be the same command.

So:

```text
local_focus_screen
```

can be available to everyone.

But:

```text
program_take_screen
```

requires production authority.

Owner / operator / Pub Manager rules apply.

Otherwise some guest watching PubCast could accidentally hijack Program.

## We also need an authoritative stage state

The specification doesn't currently answer:

> Who owns where Pete actually is?

For a shared PubWorld room, clients shouldn't each independently decide.

We want:

```text
Stage Service
    authoritative actor state
    authoritative scene state
    authoritative interactions
            ↓
       WebSocket events
            ↓
        render clients
```

The manifest defines the set.

Runtime state defines:

```text
Pete position
Alex position
current animation
screen currently playing
current program camera
doors/props state
lighting state
```

Keep those separate.

That also makes Blackbox recording beautifully straightforward.

## The rendering approach can be extremely cheap

This is actually one of the strongest aspects of the entire idea.

The expensive part of a normal 3D world is:

- geometry
- materials
- textures
- lights
- shadows
- draw calls

Here, a gorgeous room may be:

> one image.

That's almost free.

I'd structure quality tiers.

### Low / mobile

- background plate
- 3D avatars
- simple GLBs
- one shadow-catcher
- one directional light
- 1024 shadow map
- no postprocessing
- capped DPR
- 30 FPS

### Standard

- 2048 shadows
- soft contact shadows
- animated set details
- better texture filtering
- basic color grade
- 60 FPS where available

### Broadcast

- higher render resolution
- selective postprocessing
- higher shadow resolution
- better avatar textures
- subtle depth/lighting effects

And dynamically reduce internal resolution when frame time spikes.

PubCast shouldn't care whether the laptop is glorious.

It should degrade gracefully.

## For graphical quality, lighting match matters more than polygons

This is where I would invest.

Each scene should have a tiny lighting profile:

```text
key direction
key intensity
key softness
ambient intensity
color temperature
shadow opacity
exposure
```

The goal isn't physically perfect light.

The goal is:

> Pete looks like he belongs in the painting.

A mediocre avatar with matching light and a good contact shadow looks surprisingly convincing.

A gorgeous avatar under the wrong light looks pasted on.

I'd also establish proper color management:

- sRGB art/textures
- linear lighting
- consistent tone mapping
- optional final scene grade

Then let the builder have something deliciously simple:

> Match Actors to Set

with controls for warmth, brightness, shadow strength and contrast.

## Cheap graphical tricks will buy us a lot

Your earlier instinct about lightly animated drawings is exactly right.

A set can feel alive with almost nothing:

- slow cloud drift
- neon flicker
- smoke curl
- one leaf falling
- ceiling fan rotation
- light shimmer
- tiny curtain movement
- TV glow
- clock hand
- blinking sign
- occasional distant silhouette

Atlas those animations.

Don't load 40 separate PNGs if one sprite sheet will do.

They can run at:

> 4–12 FPS.

The human eye accepts it because it's part of the illustrated style.

## And I'd add subtle 2.5D parallax

Not free-moving camera parallax.

Tiny compositional parallax.

Split a painting into:

```text
far background
midground
foreground
```

During a closeup/crop, offset them by maybe:

```text
0 px
3 px
8 px
```

Very small.

It gives the set just a whisper of dimensionality without revealing the trick.

It would look fantastic with hand-drawn/cartoon environments.

## Occlusion is good, but needs one refinement

The invisible depth boxes are smart.

Keep them.

For PNG foreground elements, I would prefer they participate in actual depth rendering rather than manually ask:

> Is avatar Z > sprite Z?

That condition only works with a very specific camera orientation.

Let the GPU do the depth comparison.

And for hard-edge PNGs such as railings/plants:

```text
alphaTest
```

will often produce more reliable depth behavior than fully blended transparent materials.

## The calibrator needs more “Photoshop” and less “engineering console”

This is probably where the user experience either becomes magical or miserable.

I would add:

- undo/redo
- autosave
- object list/outliner
- lock/unlock objects
- hide/show
- duplicate
- numeric transform inspector
- snapping
- grid
- scene versions
- named checkpoints
- multi-select eventually
- missing-asset warnings
- scene validation

Most importantly:

### Test Actor

Not just the depth scrubber.

Give us Pete.

Drag Pete around with the mouse.

Click:

> Walk there.

Make him walk.

Walk him behind the bar.

Up the stairs.

Onto the balcony.

Past the television.

If anything looks stupid, fix it immediately.

That is worth more than twelve mathematical diagnostic panels.

## I love the depth scrubber idea

Keep that one.

I would make it even better:

As Pete moves from 0% → 100%, leave faint ghost silhouettes behind him.

Then you can instantly see:

- scale progression
- foot placement
- clipping
- apparent perspective

Maybe five ghosts.

That's an incredibly good calibration visualization.

## Give props attachment points

This is missing and will unlock a ton of fun.

A desk shouldn't only exist.

It should expose:

```text
sit_anchor
lean_anchor
mug_anchor
paper_anchor
hand_rest_anchor
```

A chair:

```text
seat_anchor
```

A television:

```text
gaze_anchor
```

A door:

```text
approach_anchor
exit_anchor
```

Then Pete doesn't have to understand furniture geometry.

He understands:

> Sit here.

That makes interactive sets dramatically easier.

## Give the stage blocking marks

This feels extremely PubCast.

Operator drops little invisible marks:

```text
A
B
C
HOST
GUEST
ENTRANCE
WEATHER
BAR
```

Then production instructions become:

> Pete, go to A.

> Alex, take Weather.

> Manny, enter from stage left and stand on C.

This bridges theater/blocking language and the navigation system beautifully.

## The broadcast engine also needs to define how Program is rendered

The specification defines Program and Preview logically but not physically.

We need one actual production canvas.

Something like:

```text
Program RenderTarget
Preview RenderTarget
       ↓
Switcher compositor
       ↓
Program canvas
       ↓
captureStream / recorder / broadcast output
```

Performance trick:

Don't render five complete cameras constantly.

Render:

- Program at full rate
- Preview at lower resolution/rate
- other camera thumbnails as occasional snapshots

During a dissolve, temporarily render both at full speed.

On weak hardware, transitions can dissolve from a frozen last frame instead.

That saves an enormous amount of GPU.

## The proposed implementation roadmap is missing most of the engine

This is important.

The file list sounds complete, but the supplied source only actually implements:

- perspective math
- manifest persistence
- a rudimentary Director

There is no implementation yet for:

- `stage_service.py`
- actual Three.js scene renderer
- screen-to-world projection
- surfaces
- actor navigation
- ramp traversal
- ledges
- occluders
- asset loading
- screen/video runtime
- WebRTC
- WebAudio routing
- focus modal
- gaze controller
- calibrator UI
- transforms
- scene API
- WebSocket state
- Program/Preview compositor
- recording/broadcast output
- permission handling
- Blackbox events

So this should be called what it currently is:

> excellent Stage Engine architecture draft plus three starter modules

rather than “implementation specification ready to execute.”

That's not a criticism of the concept. It tells us exactly what work remains.

## What I'd add to the manifest

Not hundreds of things. Just the missing fundamentals:

```text
canvas
    source_width
    source_height
    target_aspect_ratio

scale_calibration
    meters_per_world_unit
    reference_points

lighting
    key_direction
    key_intensity
    ambient_intensity
    temperature
    shadow_strength

shots
    mode: crop | plate | 3d
    background_override
    calibration_override

surface_connections

interaction_anchors

blocking_marks

performance_profile

asset_manifest
```

And keep live runtime state out of it.

## Things I'd specifically leave for later

I would resist stuffing these into V1:

- full physics
- freeform object manipulation during shows
- SSAO
- volumetric lighting
- dynamic global illumination
- arbitrary free-moving cameras on painted stages
- sophisticated procedural navmesh generation
- facial vision analysis of remote guests
- fully LLM-directed camera switching

None of those are necessary to make this magical.

## What I think V1 should actually prove

A single illustrated PubCast room.

Pete and Alex.

One floor.

One ramp/staircase.

One counter.

One foreground PNG.

One TV.

One chair.

Five production shots, mostly crop shots.

And demonstrate this sequence:

1. Load painted room.
2. Calibrate perspective.
3. Calibrate scale with Pete.
4. Draw walkable region.
5. Draw staircase ramp.
6. Box the counter.
7. Put television video into painted screen.
8. Pete walks from foreground to background and scales correctly.
9. Pete walks behind counter and disappears correctly.
10. Pete climbs stairs.
11. Pete sits in chair.
12. Guest appears on TV.
13. Pete looks at guest.
14. User clicks TV and gets seamless full-screen focus.
15. Director cuts between Wide, Pete, Alex and Guest.
16. Blackbox records the production decisions.
17. Everything still runs acceptably on modest hardware.

If that works, PubWorld suddenly stops being theoretical.

It's a studio.

And from there, adding a new room becomes mostly drawing and calibrating, not programming. That is the real payoff of this architecture.

## Overall assessment

Keep the architecture. Do not implement the pasted version verbatim.

The 2.5D concept itself is extremely well matched to PubCast: it gives us vastly more visual freedom than conventional 3D while respecting real hardware constraints. The biggest architectural correction is to make the painted background's calibrated camera immutable and treat most “cameras” as broadcast crops unless a shot has its own plate. The biggest missing technical piece is screen-to-world plus physical scale calibration. The biggest missing PubCast piece is authoritative shared stage state and proper integration with Pub Manager, E-Pete, Jeremy, System Alex, and Blackbox instead of creating an isolated director subsystem. And the biggest user-experience opportunity is making the builder feel like drawing a stage and teaching Pete where everything is, rather than doing CAD.

With those changes, this isn't just viable. It becomes a very clever way to get a visually rich PubWorld without paying the normal full-3D cost.

