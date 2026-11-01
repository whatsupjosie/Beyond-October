/**
 * Complete Animation Presets for Pubcast Avatars (JavaScript/React)
 * Mirrors animation_presets_complete.py
 * 
 * 35 naturalistic, performative animations:
 *   - 9 listening & presence animations (nods, leans, weight shifts)
 *   - 8 hand gestures & expressions (pointing, presenting, thinking)
 *   - 7 micro-interactions & fidgets (collar adjustments, taps, grooming)
 *   - 6 seated interactions (pivots, leans, leg crosses—podcast context)
 *   - 5 emotional/attitudinal overlays (confident, thoughtful, relaxed, etc.)
 * 
 * All animations are designed to be:
 *   - Naturalistic (no slapstick, believable movement)
 *   - Performative (convey intent and body language)
 *   - Blendable (can layer without visual conflict)
 *   - Context-aware (different needs for seated vs standing)
 * 
 * Usage:
 *   const anim = getAnimation("nod_slow");
 *   const seated = getAnimationsForContext("seated");
 *   const byTag = getAnimationsByTag("thinking");
 */

// ============================================================================
// CORE CONSTANTS & TYPES
// ============================================================================

const AnimationCategory = {
  LOCOMOTION: "locomotion",
  IDLE: "idle",
  GESTURE: "gesture",
  TRANSITION: "transition",
  LISTENING: "listening",
  SEATED: "seated",
  FIDGET: "fidget",
  EMOTIONAL: "emotional",
  SCRIPTED: "scripted",
  INTERACTION: "interaction",
};

/**
 * @typedef {Object} BoneKeyframe
 * @property {string} boneId
 * @property {number} frameNumber
 * @property {number} durationMs
 * @property {[number, number, number]} [position] - [x, y, z]
 * @property {[number, number, number]} [rotation] - [yaw, pitch, roll]
 * @property {[number, number, number]} [scale] - [x, y, z]
 */

/**
 * @typedef {Object} AnimationPreset
 * @property {string} animationId
 * @property {string} category - AnimationCategory
 * @property {string} displayName
 * @property {number} durationMs
 * @property {boolean} isLoopable
 * @property {boolean} isBlocking
 * @property {BoneKeyframe[]} frames
 * @property {boolean} [rootMotion]
 * @property {Set<string>} [blendableWith]
 * @property {Set<string>} [tags]
 * @property {string} [description]
 * @property {Object} [characterSpecific] - {avatarModelId: animationId}
 */

// ============================================================================
// LISTENING & PRESENCE ANIMATIONS
// ============================================================================

const NOD_SLOW = {
  animationId: "nod_slow",
  category: AnimationCategory.LISTENING,
  displayName: "Slow Nod",
  durationMs: 1500,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 15, durationMs: 500, rotation: [0, 2, 0] },
    { boneId: "head", frameNumber: 30, durationMs: 500, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 45, durationMs: 500, rotation: [0, -1, 0] },
  ],
  blendableWith: ["idle_stand", "idle_sit"],
  tags: ["agreement", "listening", "natural", "presence"],
  description: "Thoughtful agreement nod (~1.5s cycle). Use during active listening.",
};

const NOD_EMPHATIC = {
  animationId: "nod_emphatic",
  category: AnimationCategory.LISTENING,
  displayName: "Emphatic Nod",
  durationMs: 800,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 10, durationMs: 300, rotation: [0, 3, 0] },
    { boneId: "head", frameNumber: 20, durationMs: 300, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 30, durationMs: 200, rotation: [0, -2, 0] },
  ],
  blendableWith: ["idle_stand", "idle_sit"],
  tags: ["strong_agreement", "listening"],
  description: "Quick emphatic nod (strong agreement/emphasis). Stresses a point.",
};

const HEAD_SHAKE = {
  animationId: "head_shake",
  category: AnimationCategory.LISTENING,
  displayName: "Head Shake",
  durationMs: 1200,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 10, durationMs: 300, rotation: [0, 0, -8] },
    { boneId: "head", frameNumber: 20, durationMs: 300, rotation: [0, 0, 8] },
    { boneId: "head", frameNumber: 30, durationMs: 300, rotation: [0, 0, -5] },
    { boneId: "head", frameNumber: 40, durationMs: 300, rotation: [0, 0, 0] },
  ],
  tags: ["disagreement", "skepticism", "listening"],
  description: "Natural head shake (disagreement/skepticism).",
};

const HEAD_TILT_LEFT = {
  animationId: "head_tilt_left",
  category: AnimationCategory.LISTENING,
  displayName: "Tilt Head Left",
  durationMs: 400,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 20, durationMs: 400, rotation: [-2, 0, -5] },
  ],
  blendableWith: ["idle_stand", "idle_sit"],
  tags: ["curiosity", "listening", "engagement"],
  description: "Curious head tilt (shows interest/engagement).",
};

const HEAD_TILT_RIGHT = {
  animationId: "head_tilt_right",
  category: AnimationCategory.LISTENING,
  displayName: "Tilt Head Right",
  durationMs: 400,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 20, durationMs: 400, rotation: [2, 0, 5] },
  ],
  blendableWith: ["idle_stand", "idle_sit"],
  tags: ["curiosity", "listening"],
  description: "Curious head tilt right (shows interest/engagement).",
};

const LEAN_FORWARD = {
  animationId: "lean_forward",
  category: AnimationCategory.LISTENING,
  displayName: "Lean Forward",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 800, position: [2, 0, 0], rotation: [0, 0, 5] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 800, position: [1, 0, 0], rotation: [0, 0, 0] },
  ],
  tags: ["engagement", "interest", "forward", "listening"],
  description: "Slight lean forward (shows engagement/interest).",
};

const LEAN_BACK = {
  animationId: "lean_back",
  category: AnimationCategory.LISTENING,
  displayName: "Lean Back",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 800, position: [-2, 0, 0], rotation: [0, 0, -3] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 800, position: [-1, 0, 0], rotation: [0, 0, 0] },
  ],
  tags: ["skepticism", "relaxation", "listening"],
  description: "Lean back (shows skepticism or relaxed confidence).",
};

const WEIGHT_SHIFT_LEFT = {
  animationId: "weight_shift_left",
  category: AnimationCategory.LISTENING,
  displayName: "Shift Weight Left",
  durationMs: 600,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "leg_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "leg_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 15, durationMs: 600, position: [-1, 0, 0] },
    { boneId: "leg_left", frameNumber: 15, durationMs: 600, rotation: [0.5, 0, 0] },
    { boneId: "leg_right", frameNumber: 15, durationMs: 600, rotation: [-0.5, 0, 0] },
  ],
  tags: ["stance", "rebalance", "natural"],
  description: "Weight shift to left leg (natural postural adjustment).",
};

const WEIGHT_SHIFT_RIGHT = {
  animationId: "weight_shift_right",
  category: AnimationCategory.LISTENING,
  displayName: "Shift Weight Right",
  durationMs: 600,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "leg_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "leg_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 15, durationMs: 600, position: [1, 0, 0] },
    { boneId: "leg_left", frameNumber: 15, durationMs: 600, rotation: [-0.5, 0, 0] },
    { boneId: "leg_right", frameNumber: 15, durationMs: 600, rotation: [0.5, 0, 0] },
  ],
  tags: ["stance", "rebalance"],
  description: "Weight shift to right leg (natural postural adjustment).",
};

// ============================================================================
// HAND GESTURES & EXPRESSION
// ============================================================================

const SHOULDER_SHRUG = {
  animationId: "shoulder_shrug",
  category: AnimationCategory.GESTURE,
  displayName: "Shoulder Shrug",
  durationMs: 900,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "shoulder_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "shoulder_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "shoulder_left", frameNumber: 15, durationMs: 400, position: [0, 2, 0] },
    { boneId: "shoulder_right", frameNumber: 15, durationMs: 400, position: [0, 2, 0] },
    { boneId: "shoulder_left", frameNumber: 30, durationMs: 500, rotation: [0, 0, 0] },
    { boneId: "shoulder_right", frameNumber: 30, durationMs: 500, rotation: [0, 0, 0] },
  ],
  tags: ["uncertainty", "doubt", "gesture", "natural"],
  description: "Shoulder shrug (expresses uncertainty/doubt).",
};

const HANDS_TOGETHER_CHEST = {
  animationId: "hands_together_chest",
  category: AnimationCategory.GESTURE,
  displayName: "Hands Together at Chest",
  durationMs: 600,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 15, durationMs: 600, position: [1, 0, 0] },
    { boneId: "hand_right", frameNumber: 15, durationMs: 600, position: [-1, 0, 0] },
  ],
  tags: ["thoughtful", "composed", "engaged", "gesture"],
  description: "Hands clasped at chest (thoughtful/composed pose).",
};

const OPEN_PALM_PRESENTATION = {
  animationId: "open_palm_presentation",
  category: AnimationCategory.GESTURE,
  displayName: "Open Palm Presentation",
  durationMs: 1000,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 20, durationMs: 500, position: [2, 1, 0], rotation: [0, 0, 45] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 500, position: [-2, 1, 0], rotation: [0, 0, -45] },
    { boneId: "arm_left", frameNumber: 20, durationMs: 500, rotation: [0, 0, 30] },
    { boneId: "arm_right", frameNumber: 20, durationMs: 500, rotation: [0, 0, -30] },
  ],
  tags: ["presentation", "offering", "idea", "gesture"],
  description: "Palms-up presenting gesture (offering/presenting idea).",
};

const HAND_TO_CHIN = {
  animationId: "hand_to_chin",
  category: AnimationCategory.GESTURE,
  displayName: "Hand to Chin",
  durationMs: 700,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 20, durationMs: 700, position: [2, 3, 0] },
    { boneId: "arm_left", frameNumber: 20, durationMs: 700, rotation: [0, 0, 45] },
  ],
  tags: ["thinking", "considering", "pondering", "gesture"],
  description: "Thinking pose (hand to chin—contemplative).",
};

const HANDS_ON_HIPS = {
  animationId: "hands_on_hips",
  category: AnimationCategory.GESTURE,
  displayName: "Hands on Hips",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 20, durationMs: 800, position: [-1, 0, 0] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 800, position: [1, 0, 0] },
    { boneId: "arm_left", frameNumber: 20, durationMs: 800, rotation: [0, 0, -30] },
    { boneId: "arm_right", frameNumber: 20, durationMs: 800, rotation: [0, 0, 30] },
  ],
  tags: ["confident", "assertive", "ready", "gesture"],
  description: "Hands on hips (confident/assertive stance).",
};

const HANDS_CROSS_CHEST = {
  animationId: "hands_cross_chest",
  category: AnimationCategory.GESTURE,
  displayName: "Arms Crossed",
  durationMs: 600,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 15, durationMs: 600, position: [1, 0.5, 0] },
    { boneId: "hand_right", frameNumber: 15, durationMs: 600, position: [-1, 0.5, 0] },
    { boneId: "arm_left", frameNumber: 15, durationMs: 600, rotation: [0, 0, 45] },
    { boneId: "arm_right", frameNumber: 15, durationMs: 600, rotation: [0, 0, -45] },
  ],
  tags: ["defensive", "protective", "guarded", "gesture"],
  description: "Arms crossed (defensive/protective stance).",
};

const POINTING_GESTURE = {
  animationId: "pointing_gesture",
  category: AnimationCategory.GESTURE,
  displayName: "Pointing",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 15, durationMs: 400, position: [3, 0, 0] },
    { boneId: "arm_right", frameNumber: 15, durationMs: 400, rotation: [0, 0, -45] },
    { boneId: "hand_right", frameNumber: 30, durationMs: 400, position: [3, 0, 0] },
    { boneId: "arm_right", frameNumber: 30, durationMs: 400, rotation: [0, 0, -45] },
  ],
  tags: ["direction", "emphasis", "reference", "gesture"],
  description: "Pointing gesture (directs attention).",
};

const HAND_WAVE = {
  animationId: "hand_wave",
  category: AnimationCategory.GESTURE,
  displayName: "Hand Wave",
  durationMs: 1200,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 10, durationMs: 300, position: [1, 1, 0], rotation: [0, 0, 30] },
    { boneId: "arm_right", frameNumber: 10, durationMs: 300, rotation: [0, 0, -45] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 300, position: [1, 0.5, 0], rotation: [0, 0, -30] },
    { boneId: "hand_right", frameNumber: 30, durationMs: 300, position: [1, 1, 0], rotation: [0, 0, 30] },
    { boneId: "arm_right", frameNumber: 30, durationMs: 300, rotation: [0, 0, -45] },
    { boneId: "hand_right", frameNumber: 40, durationMs: 300, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 40, durationMs: 300, rotation: [0, 0, 0] },
  ],
  tags: ["greeting", "friendly", "gesture"],
  description: "Friendly hand wave (greeting/acknowledgment).",
};

// ============================================================================
// MICRO-INTERACTIONS & FIDGETS
// ============================================================================

const ADJUST_COLLAR = {
  animationId: "adjust_collar",
  category: AnimationCategory.FIDGET,
  displayName: "Adjust Collar",
  durationMs: 1200,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "shoulder_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 10, durationMs: 400, position: [2, 2, 0] },
    { boneId: "arm_right", frameNumber: 10, durationMs: 400, rotation: [0, 0, 30] },
    { boneId: "shoulder_right", frameNumber: 10, durationMs: 400, position: [0, 0.5, 0] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 400, position: [2, 2, 0] },
    { boneId: "arm_right", frameNumber: 20, durationMs: 400, rotation: [0, 0, 30] },
    { boneId: "shoulder_right", frameNumber: 20, durationMs: 400, position: [0, 0.5, 0] },
    { boneId: "hand_right", frameNumber: 30, durationMs: 400, position: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 30, durationMs: 400, rotation: [0, 0, 0] },
    { boneId: "shoulder_right", frameNumber: 30, durationMs: 400, position: [0, 0, 0] },
  ],
  tags: ["fidget", "natural", "subtle", "grooming"],
  description: "Quick collar adjustment (natural grooming fidget).",
};

const SMOOTH_HAIR = {
  animationId: "smooth_hair",
  category: AnimationCategory.FIDGET,
  displayName: "Smooth Hair",
  durationMs: 1000,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 10, durationMs: 500, position: [0, 3, 0] },
    { boneId: "arm_left", frameNumber: 10, durationMs: 500, rotation: [0, 0, 60] },
    { boneId: "hand_left", frameNumber: 25, durationMs: 500, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 25, durationMs: 500, rotation: [0, 0, 0] },
  ],
  tags: ["fidget", "grooming", "natural"],
  description: "Brief hair smooth gesture (natural grooming).",
};

const CLASP_HANDS_RELAX = {
  animationId: "clasp_hands_relax",
  category: AnimationCategory.FIDGET,
  displayName: "Clasp Hands Relaxed",
  durationMs: 800,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 15, durationMs: 800, position: [0, -1, 0] },
    { boneId: "hand_right", frameNumber: 15, durationMs: 800, position: [0, -1, 0] },
  ],
  tags: ["relaxed", "calm", "seated", "fidget"],
  description: "Hands clasped in lap (calm resting state—seated).",
};

const FINGER_TAP = {
  animationId: "finger_tap",
  category: AnimationCategory.FIDGET,
  displayName: "Finger Tap",
  durationMs: 500,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 5, durationMs: 100, position: [0, -0.2, 0] },
    { boneId: "hand_right", frameNumber: 10, durationMs: 100, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 15, durationMs: 100, position: [0, -0.2, 0] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 100, position: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 25, durationMs: 100, position: [0, -0.2, 0] },
  ],
  tags: ["fidget", "rhythm", "impatient", "thinking"],
  description: "Finger tapping rhythm (impatience or thinking rhythm).",
};

const GLANCE_DOWN = {
  animationId: "glance_down",
  category: AnimationCategory.FIDGET,
  displayName: "Glance Down",
  durationMs: 600,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 15, durationMs: 300, rotation: [5, 0, 0] },
    { boneId: "head", frameNumber: 30, durationMs: 300, rotation: [0, 0, 0] },
  ],
  tags: ["fidget", "natural", "brief", "thinking"],
  description: "Brief glance downward (momentary gaze break—natural).",
};

const TOUCH_FACE = {
  animationId: "touch_face",
  category: AnimationCategory.FIDGET,
  displayName: "Touch Face",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 15, durationMs: 400, position: [1, 2, 0] },
    { boneId: "arm_left", frameNumber: 15, durationMs: 400, rotation: [0, 0, 45] },
    { boneId: "hand_left", frameNumber: 30, durationMs: 400, position: [0, 0, 0] },
    { boneId: "arm_left", frameNumber: 30, durationMs: 400, rotation: [0, 0, 0] },
  ],
  tags: ["fidget", "natural", "thinking"],
  description: "Quick touch to face (thinking/composure fidget).",
};

// ============================================================================
// SEATED INTERACTIONS
// ============================================================================

const LEAN_LEFT_SEATED = {
  animationId: "lean_left_seated",
  category: AnimationCategory.SEATED,
  displayName: "Lean Left (Seated)",
  durationMs: 700,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 700, position: [-2, 0, 0], rotation: [0, 0, -8] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 700, position: [-1, 0, 0], rotation: [0, 0, 0] },
  ],
  tags: ["seated", "interaction", "direction", "body"],
  description: "Lean torso left while seated (address someone beside).",
};

const LEAN_RIGHT_SEATED = {
  animationId: "lean_right_seated",
  category: AnimationCategory.SEATED,
  displayName: "Lean Right (Seated)",
  durationMs: 700,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 700, position: [2, 0, 0], rotation: [0, 0, 8] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 700, position: [1, 0, 0], rotation: [0, 0, 0] },
  ],
  tags: ["seated", "interaction", "direction", "body"],
  description: "Lean torso right while seated (address someone beside).",
};

const PIVOT_TORSO_LEFT = {
  animationId: "pivot_torso_left",
  category: AnimationCategory.SEATED,
  displayName: "Pivot Torso Left",
  durationMs: 900,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 900, position: [0, 0, 0], rotation: [0, 0, -15] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 900, position: [0, 0, 0], rotation: [0, 0, -10] },
  ],
  tags: ["seated", "rotation", "look", "body"],
  description: "Rotate upper body left while seated (look/address).",
};

const PIVOT_TORSO_RIGHT = {
  animationId: "pivot_torso_right",
  category: AnimationCategory.SEATED,
  displayName: "Pivot Torso Right",
  durationMs: 900,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 20, durationMs: 900, position: [0, 0, 0], rotation: [0, 0, 15] },
    { boneId: "pelvis", frameNumber: 20, durationMs: 900, position: [0, 0, 0], rotation: [0, 0, 10] },
  ],
  tags: ["seated", "rotation", "look", "body"],
  description: "Rotate upper body right while seated (look/address).",
};

const SIT_CROSS_LEGS = {
  animationId: "sit_cross_legs",
  category: AnimationCategory.SEATED,
  displayName: "Cross Legs (Seated)",
  durationMs: 1200,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "leg_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "leg_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "leg_left", frameNumber: 20, durationMs: 1200, rotation: [0, 0, 45] },
    { boneId: "leg_right", frameNumber: 20, durationMs: 1200, rotation: [0, 0, -30] },
  ],
  tags: ["seated", "posture", "comfort", "body"],
  description: "Cross legs while seated (alternative posture).",
};

const ADJUST_SEAT = {
  animationId: "adjust_seat",
  category: AnimationCategory.FIDGET,
  displayName: "Adjust Seat",
  durationMs: 800,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 15, durationMs: 400, position: [0, -0.5, 0] },
    { boneId: "spine", frameNumber: 15, durationMs: 400, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 30, durationMs: 400, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 30, durationMs: 400, rotation: [0, 0, 0] },
  ],
  tags: ["seated", "fidget", "comfort", "body"],
  description: "Reposition in seat (natural shift—comfort).",
};

const REACH_FORWARD_SEATED = {
  animationId: "reach_forward_seated",
  category: AnimationCategory.SEATED,
  displayName: "Reach Forward (Seated)",
  durationMs: 900,
  isLoopable: false,
  isBlocking: false,
  frames: [
    { boneId: "arm_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_right", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 20, durationMs: 450, rotation: [0, 0, -30] },
    { boneId: "hand_right", frameNumber: 20, durationMs: 450, position: [2, 0, -0.5] },
    { boneId: "spine", frameNumber: 20, durationMs: 450, rotation: [0, 0, 0] },
    { boneId: "arm_right", frameNumber: 40, durationMs: 450, rotation: [0, 0, -30] },
    { boneId: "hand_right", frameNumber: 40, durationMs: 450, position: [2, 0, -0.5] },
  ],
  tags: ["seated", "interaction", "reach", "body"],
  description: "Reach forward while seated (grab/gesture toward table).",
};

// ============================================================================
// EMOTIONAL/ATTITUDINAL STATES
// ============================================================================

const CONFIDENT_STANCE = {
  animationId: "confident_stance",
  category: AnimationCategory.EMOTIONAL,
  displayName: "Confident Stance",
  durationMs: 2000,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0.5, 0, 0], rotation: [0, 0, 0] },
    { boneId: "shoulder_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 5] },
    { boneId: "shoulder_right", frameNumber: 0, durationMs: 0, rotation: [0, 0, -5] },
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 2] },
    { boneId: "spine", frameNumber: 30, durationMs: 2000, position: [0.5, 0, 0], rotation: [0, 0, 0] },
    { boneId: "shoulder_left", frameNumber: 30, durationMs: 2000, rotation: [0, 0, 5] },
    { boneId: "shoulder_right", frameNumber: 30, durationMs: 2000, rotation: [0, 0, -5] },
    { boneId: "head", frameNumber: 30, durationMs: 2000, rotation: [0, 0, 2] },
  ],
  blendableWith: ["idle_stand"],
  tags: ["emotional", "attitude", "confident", "overlay"],
  description: "Confident upright posture overlay (assured, authoritative).",
};

const THOUGHTFUL_IDLE = {
  animationId: "thoughtful_idle",
  category: AnimationCategory.EMOTIONAL,
  displayName: "Thoughtful Idle",
  durationMs: 1500,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 0, durationMs: 0, position: [1, 0, 0] },
    { boneId: "arm_left", frameNumber: 0, durationMs: 0, rotation: [0, 0, 10] },
    { boneId: "spine", frameNumber: 20, durationMs: 750, position: [-0.5, 0, 0], rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 20, durationMs: 750, rotation: [-1, 0, -3] },
    { boneId: "hand_left", frameNumber: 20, durationMs: 750, position: [1.5, 0.5, 0] },
    { boneId: "arm_left", frameNumber: 20, durationMs: 750, rotation: [0, 0, 20] },
    { boneId: "spine", frameNumber: 40, durationMs: 750, position: [0, 0, 0], rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 40, durationMs: 750, rotation: [0, 0, 0] },
    { boneId: "hand_left", frameNumber: 40, durationMs: 750, position: [1, 0, 0] },
    { boneId: "arm_left", frameNumber: 40, durationMs: 750, rotation: [0, 0, 10] },
  ],
  tags: ["emotional", "thinking", "engaged", "overlay"],
  description: "Thoughtful, slightly introspective idle (contemplative).",
};

const SKEPTICAL_EXPRESSION = {
  animationId: "skeptical_expression",
  category: AnimationCategory.EMOTIONAL,
  displayName: "Skeptical Expression",
  durationMs: 1000,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "head", frameNumber: 20, durationMs: 1000, rotation: [0.5, 0, -5] },
  ],
  tags: ["emotional", "expression", "skeptical", "overlay"],
  description: "Skeptical expression with raised brow (doubtful).",
};

const ENTHUSIASM_BOUNCE = {
  animationId: "enthusiasm_bounce",
  category: AnimationCategory.EMOTIONAL,
  displayName: "Enthusiastic Bounce",
  durationMs: 1200,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "pelvis", frameNumber: 0, durationMs: 0, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 15, durationMs: 300, position: [0, 0.3, 0] },
    { boneId: "spine", frameNumber: 15, durationMs: 300, rotation: [0, 0, 0] },
    { boneId: "pelvis", frameNumber: 30, durationMs: 300, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 30, durationMs: 300, rotation: [0.5, 0, 0] },
    { boneId: "pelvis", frameNumber: 45, durationMs: 600, position: [0, 0, 0] },
    { boneId: "spine", frameNumber: 45, durationMs: 600, rotation: [0, 0, 0] },
  ],
  tags: ["emotional", "energy", "positive", "overlay"],
  description: "Subtle upward energy bounce (positive/enthusiastic).",
};

const RELAXED_IDLE = {
  animationId: "relaxed_idle",
  category: AnimationCategory.EMOTIONAL,
  displayName: "Relaxed Idle",
  durationMs: 2000,
  isLoopable: true,
  isBlocking: false,
  frames: [
    { boneId: "spine", frameNumber: 0, durationMs: 0, position: [-0.5, 0, 0], rotation: [0, 0, 0] },
    { boneId: "shoulder_left", frameNumber: 0, durationMs: 0, position: [0, -0.5, 0] },
    { boneId: "shoulder_right", frameNumber: 0, durationMs: 0, position: [0, -0.5, 0] },
    { boneId: "head", frameNumber: 0, durationMs: 0, rotation: [0, 0, 0] },
    { boneId: "spine", frameNumber: 30, durationMs: 2000, position: [-0.5, 0, 0], rotation: [0, 0, 0] },
    { boneId: "shoulder_left", frameNumber: 30, durationMs: 2000, position: [0, -0.5, 0] },
    { boneId: "shoulder_right", frameNumber: 30, durationMs: 2000, position: [0, -0.5, 0] },
    { boneId: "head", frameNumber: 30, durationMs: 2000, rotation: [0, 0, 0] },
  ],
  tags: ["emotional", "relaxed", "casual", "overlay"],
  description: "Relaxed, casual posture overlay (comfortable, at-ease).",
};

// ============================================================================
// ANIMATION LIBRARY & UTILITY FUNCTIONS
// ============================================================================

const ANIMATION_LIBRARY = {
  // Listening & Presence
  nod_slow: NOD_SLOW,
  nod_emphatic: NOD_EMPHATIC,
  head_shake: HEAD_SHAKE,
  head_tilt_left: HEAD_TILT_LEFT,
  head_tilt_right: HEAD_TILT_RIGHT,
  lean_forward: LEAN_FORWARD,
  lean_back: LEAN_BACK,
  weight_shift_left: WEIGHT_SHIFT_LEFT,
  weight_shift_right: WEIGHT_SHIFT_RIGHT,

  // Hand Gestures & Expression
  shoulder_shrug: SHOULDER_SHRUG,
  hands_together_chest: HANDS_TOGETHER_CHEST,
  open_palm_presentation: OPEN_PALM_PRESENTATION,
  hand_to_chin: HAND_TO_CHIN,
  hands_on_hips: HANDS_ON_HIPS,
  hands_cross_chest: HANDS_CROSS_CHEST,
  pointing_gesture: POINTING_GESTURE,
  hand_wave: HAND_WAVE,

  // Micro-Interactions & Fidgets
  adjust_collar: ADJUST_COLLAR,
  smooth_hair: SMOOTH_HAIR,
  clasp_hands_relax: CLASP_HANDS_RELAX,
  finger_tap: FINGER_TAP,
  glance_down: GLANCE_DOWN,
  touch_face: TOUCH_FACE,

  // Seated Interactions
  lean_left_seated: LEAN_LEFT_SEATED,
  lean_right_seated: LEAN_RIGHT_SEATED,
  pivot_torso_left: PIVOT_TORSO_LEFT,
  pivot_torso_right: PIVOT_TORSO_RIGHT,
  sit_cross_legs: SIT_CROSS_LEGS,
  adjust_seat: ADJUST_SEAT,
  reach_forward_seated: REACH_FORWARD_SEATED,

  // Emotional/Attitudinal States
  confident_stance: CONFIDENT_STANCE,
  thoughtful_idle: THOUGHTFUL_IDLE,
  skeptical_expression: SKEPTICAL_EXPRESSION,
  enthusiasm_bounce: ENTHUSIASM_BOUNCE,
  relaxed_idle: RELAXED_IDLE,
};

/**
 * Retrieve an animation preset by ID
 * @param {string} animationId
 * @returns {AnimationPreset|undefined}
 */
function getAnimation(animationId) {
  return ANIMATION_LIBRARY[animationId];
}

/**
 * Get all animations in a category
 * @param {string} category
 * @returns {Object<string, AnimationPreset>}
 */
function getAnimationsByCategory(category) {
  return Object.fromEntries(
    Object.entries(ANIMATION_LIBRARY).filter(([_, preset]) => preset.category === category)
  );
}

/**
 * Get all animations with a specific tag
 * @param {string} tag
 * @returns {Object<string, AnimationPreset>}
 */
function getAnimationsByTag(tag) {
  return Object.fromEntries(
    Object.entries(ANIMATION_LIBRARY).filter(([_, preset]) =>
      preset.tags && Array.isArray(preset.tags) ? preset.tags.includes(tag) : false
    )
  );
}

/**
 * Get all loopable animations (safe for continuous playback)
 * @returns {Object<string, AnimationPreset>}
 */
function getLoopableAnimations() {
  return Object.fromEntries(
    Object.entries(ANIMATION_LIBRARY).filter(([_, preset]) => preset.isLoopable)
  );
}

/**
 * Get animations suitable for a specific context
 * @param {string} context - "seated", "standing", "listening", "speaking", "thinking"
 * @returns {Object<string, AnimationPreset>}
 */
function getAnimationsForContext(context) {
  const contextTags = {
    seated: ["seated", "fidget", "body"],
    standing: ["gesture", "listening", "presence"],
    listening: ["listening", "nod", "agreement", "engagement"],
    speaking: ["gesture", "presentation", "emphasis", "direction"],
    thinking: ["thinking", "contemplative", "pondering", "fidget"],
  };

  const tags = contextTags[context] || [];
  if (tags.length === 0) return {};

  return Object.fromEntries(
    Object.entries(ANIMATION_LIBRARY).filter(([_, preset]) =>
      tags.some((tag) => preset.tags && preset.tags.includes(tag))
    )
  );
}

/**
 * List all animations with metadata (for UI/debugging)
 * @returns {Object<string, Object>}
 */
function listAllAnimations() {
  const result = {};
  for (const [id, preset] of Object.entries(ANIMATION_LIBRARY)) {
    result[id] = {
      animationId: preset.animationId,
      category: preset.category,
      displayName: preset.displayName,
      durationMs: preset.durationMs,
      isLoopable: preset.isLoopable,
      isBlocking: preset.isBlocking,
      frames: preset.frames.length,
      tags: preset.tags || [],
      description: preset.description || "",
    };
  }
  return result;
}

// ============================================================================
// VALIDATION & STATS (run in Node/test context)
// ============================================================================

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    AnimationCategory,
    ANIMATION_LIBRARY,
    getAnimation,
    getAnimationsByCategory,
    getAnimationsByTag,
    getLoopableAnimations,
    getAnimationsForContext,
    listAllAnimations,
  };
}

// For browser/module context, make available globally
if (typeof window !== "undefined") {
  window.PubcastAnimations = {
    AnimationCategory,
    ANIMATION_LIBRARY,
    getAnimation,
    getAnimationsByCategory,
    getAnimationsByTag,
    getLoopableAnimations,
    getAnimationsForContext,
    listAllAnimations,
  };
}
