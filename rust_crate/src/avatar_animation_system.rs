/*!
PubCast Animation System - Comprehensive Avatar Animation Package

Advanced skeletal animation system with:
- State machine-based animation control
- Gender-specific animations and body morphing
- Procedural hair animation
- Avatar-to-skeleton fitting system
- Performance-optimized blending and transitions
*/

use nalgebra::{Matrix4, Point3, Quaternion, UnitQuaternion, Vector3};
use std::collections::{HashMap, VecDeque};
use std::time::{Duration, Instant};
use serde::{Deserialize, Serialize};

/// Animation state machine controller
#[derive(Debug, Clone)]
pub struct AnimationController {
    pub current_state: AnimationState,
    pub target_state: AnimationState,
    pub transition_progress: f32,
    pub transition_speed: f32,
    pub state_machine: AnimationStateMachine,
    pub animation_data: AnimationLibrary,
    pub blend_tree: AnimationBlendTree,
    pub avatar_config: AvatarConfiguration,
}

/// Core animation states with substates
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AnimationState {
    // Locomotion
    Idle { variant: IdleVariant },
    Walking { direction: WalkDirection, gender_variant: GenderVariant },
    Running { direction: RunDirection },
    Stopping,
    Turning { direction: TurnDirection, angle: i32 },
    
    // Vertical Movement
    Jumping { phase: JumpPhase },
    Ducking { depth: DuckDepth },
    Climbing { type_: ClimbType, progress: f32 },
    
    // Positional
    Sitting { furniture_type: SittingType },
    Standing { from_position: StandingFrom },
    Lying { sleep_state: SleepState },
    
    // Interactions
    Handshaking { hand: HandType, progress: f32 },
    Typing { surface_type: TypingType, intensity: TypingIntensity },
    Reading { object_type: ReadingType, posture: ReadingPosture },
    Pushing { direction: PushDirection, intensity: f32 },
    Pulling { direction: PullDirection, intensity: f32 },
    
    // Falls and Recovery
    Tripping { cause: TripCause, phase: TripPhase },
    Falling { fall_type: FallType, direction: FallDirection },
    GettingUp { from_position: GetUpFrom, difficulty: GetUpDifficulty },
    
    // Gestures and Actions
    Bowing { depth: BowDepth, formality: FormalityLevel },
    Curtseying { depth: CurtsyDepth, elegance: EleganceLevel },
    
    // Female-Specific Actions
    PurseAction { action: PurseActionType, progress: f32 },
    MakeupAction { action: MakeupActionType, progress: f32 },
    HighHeelWalk { speed: WalkSpeed, hip_emphasis: f32 },
}

/// Animation substates and variants
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum IdleVariant {
    Basic,
    ArmsFolded,
    HandsInPockets,
    HandsOnHips,
    LookingAround,
    ShiftWeight,
    CheckTime,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum WalkDirection { Forward, Backward, StrafeLeft, StrafeRight }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum GenderVariant { Neutral, Masculine, Feminine }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RunDirection { Forward, Backward }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TurnDirection { Left, Right }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum JumpPhase { Crouch, Launch, Airborne, Landing }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DuckDepth { Slight, Medium, Full }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ClimbType { Ladder, Wall, Obstacle }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SittingType { Chair, Floor, Bed, Bench }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum StandingFrom { Floor, Chair, Bed }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SleepState { FallingAsleep, Sleeping, WakingUp, GettingOutOfBed }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum HandType { Left, Right, Both }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TypingType { Computer, Console, Tablet }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TypingIntensity { Casual, Normal, Intense }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ReadingType { Book, Tablet, Paper, Sign }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ReadingPosture { Standing, Sitting, Lying }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PushDirection { Forward, Up, Down, Left, Right }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PullDirection { Toward, Down, Up, Left, Right }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TripCause { Obstacle, Stumble, Slip }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum TripPhase { Initial, Stumbling, Falling, Impact }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum FallType { Forward, Backward, Side }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum FallDirection { Front, Back, Left, Right }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum GetUpFrom { Ground, Chair, Bed }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum GetUpDifficulty { Easy, Normal, Difficult }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BowDepth { Slight, Formal, Deep }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum FormalityLevel { Casual, Formal, Ceremonial }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CurtsyDepth { Slight, Graceful, Full }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EleganceLevel { Simple, Graceful, Elaborate }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PurseActionType { Opening, Searching, Closing, PullingOut }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MakeupActionType { Lipstick, Mascara, Powder, Mirror }

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum WalkSpeed { Slow, Normal, Fast }

/// Animation keyframe data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimationFrame {
    pub joint_transforms: HashMap<String, JointTransform>,
    pub timestamp: f32,
    pub root_motion: Vector3<f32>,
    pub metadata: AnimationMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimationMetadata {
    pub contact_points: Vec<String>, // Joints touching ground/objects
    pub balance_point: Point3<f32>,
    pub energy_level: f32, // For procedural effects
    pub emotion_state: EmotionState,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EmotionState {
    Neutral, Happy, Sad, Confident, Tired, Alert, Relaxed
}

/// Complete animation sequence
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimationSequence {
    pub name: String,
    pub frames: Vec<AnimationFrame>,
    pub duration: f32,
    pub loop_type: LoopType,
    pub blend_weights: BlendWeights,
    pub root_motion_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LoopType {
    None,
    Loop,
    PingPong,
    LoopWithBlend { blend_duration: f32 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlendWeights {
    pub upper_body: f32,
    pub lower_body: f32,
    pub left_arm: f32,
    pub right_arm: f32,
    pub spine: f32,
}

/// Avatar configuration for body morphing and fitting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AvatarConfiguration {
    pub gender: Gender,
    pub body_proportions: BodyProportions,
    pub clothing_fit: ClothingFit,
    pub hair_config: HairConfiguration,
    pub skeleton_mapping: SkeletonMapping,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Gender {
    Male,
    Female,
    Neutral,
    Custom { masculinity: f32, femininity: f32 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BodyProportions {
    pub height: f32,
    pub shoulder_width: f32,
    pub hip_width: f32,
    pub waist_ratio: f32,
    pub leg_length_ratio: f32,
    pub torso_length_ratio: f32,
    
    // Female-specific
    pub breast_size: f32,
    pub hip_curve: f32,
    pub waist_curve: f32,
    
    // Male-specific  
    pub shoulder_bulk: f32,
    pub chest_depth: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClothingFit {
    pub tightness: f32,
    pub length_adjustments: HashMap<String, f32>, // bone name -> length multiplier
    pub bulk_adjustments: HashMap<String, f32>,   // bone name -> thickness multiplier
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HairConfiguration {
    pub hair_type: HairType,
    pub length: f32,
    pub volume: f32,
    pub simulation_enabled: bool,
    pub physics_settings: HairPhysics,
    pub style_modifiers: Vec<HairStyleModifier>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HairType {
    None,
    Short,
    Medium,
    Long,
    Ponytail,
    Braided,
    Custom { segments: usize, control_points: Vec<Point3<f32>> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HairPhysics {
    pub stiffness: f32,
    pub damping: f32,
    pub gravity_strength: f32,
    pub wind_response: f32,
    pub collision_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HairStyleModifier {
    Wave { frequency: f32, amplitude: f32 },
    Curl { tightness: f32 },
    Part { side: HairPartSide, depth: f32 },
    Layers { count: usize, variation: f32 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HairPartSide { Left, Right, Center, None }

/// Skeleton mapping for avatar attachment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkeletonMapping {
    pub bone_mappings: HashMap<String, String>, // avatar bone -> skeleton bone
    pub scale_adjustments: HashMap<String, f32>,
    pub rotation_offsets: HashMap<String, UnitQuaternion<f32>>,
    pub position_offsets: HashMap<String, Vector3<f32>>,
    pub constraint_overrides: Vec<ConstraintOverride>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConstraintOverride {
    pub bone_name: String,
    pub constraint_type: ConstraintType,
    pub parameters: HashMap<String, f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConstraintType {
    IKChain { target: String, pole_vector: Option<String> },
    LookAt { target: String, up_vector: Vector3<f32> },
    Parent { target: String, maintain_offset: bool },
    Custom(String),
}

// Re-export from skeleton module
use super::{JointTransform, SkeletalAnimator};

impl Default for AvatarConfiguration {
    fn default() -> Self {
        Self {
            gender: Gender::Neutral,
            body_proportions: BodyProportions::default(),
            clothing_fit: ClothingFit::default(),
            hair_config: HairConfiguration::default(),
            skeleton_mapping: SkeletonMapping::default(),
        }
    }
}

impl Default for BodyProportions {
    fn default() -> Self {
        Self {
            height: 1.0,
            shoulder_width: 1.0,
            hip_width: 1.0,
            waist_ratio: 0.8,
            leg_length_ratio: 0.5,
            torso_length_ratio: 0.5,
            breast_size: 0.5,
            hip_curve: 0.5,
            waist_curve: 0.5,
            shoulder_bulk: 0.5,
            chest_depth: 0.5,
        }
    }
}

impl Default for ClothingFit {
    fn default() -> Self {
        Self {
            tightness: 0.5,
            length_adjustments: HashMap::new(),
            bulk_adjustments: HashMap::new(),
        }
    }
}

impl Default for HairConfiguration {
    fn default() -> Self {
        Self {
            hair_type: HairType::Short,
            length: 0.1,
            volume: 0.5,
            simulation_enabled: false,
            physics_settings: HairPhysics::default(),
            style_modifiers: Vec::new(),
        }
    }
}

impl Default for HairPhysics {
    fn default() -> Self {
        Self {
            stiffness: 0.8,
            damping: 0.9,
            gravity_strength: 1.0,
            wind_response: 0.3,
            collision_enabled: false,
        }
    }
}

impl Default for SkeletonMapping {
    fn default() -> Self {
        Self {
            bone_mappings: HashMap::new(),
            scale_adjustments: HashMap::new(),
            rotation_offsets: HashMap::new(),
            position_offsets: HashMap::new(),
            constraint_overrides: Vec::new(),
        }
    }
}
