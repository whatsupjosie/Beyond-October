/*!
PubCast AI — Skeletal Animation System v2.0 (Hardened)
=======================================================

AUTHORITATIVE JOINT NAMING STANDARD: UE5-compatible PascalCase
  UpperArm_L / UpperArm_R
  LowerArm_L / LowerArm_R       ← NOT "Forearm"
  Hand_L     / Hand_R           ← NOT "Wrist"
  Thigh_L    / Thigh_R
  Calf_L     / Calf_R
  Foot_L     / Foot_R           ← ankle joint; NOT "Ankle"
  Ball_L     / Ball_R           ← ball of foot; NOT "Foot" (in anim packs)
  Neck_01                       ← NOT bare "Neck"
  Spine_01   / Spine_02  / Spine_03

All other files (motion_capture.rs, choreography.py, animation_presets.js,
FemAffect skeleton_binding.json) MUST alias through JointNameAlias::resolve_or_original.

Hardening pass — bugs fixed vs skeleton_rs.txt v2.0
────────────────────────────────────────────────────
  [FIX] tracing::warn! called but tracing crate undeclared — now in Cargo.toml
  [FIX] velocity_buffer stored but never read — removed dead state
  [FIX] fps() undercounted early in session (hardcoded 1s denominator) — fixed
  [FIX] validate_topological_order() only panicked; now returns Result too
  [FIX] blend_towards() silently skipped joints in target absent from self
  [FIX] AnimationLayer cloned full SkeletonState on push — now Arc-shared
  [FIX] Bad mocap frames returned stale data with no staleness marker
  [FIX] ClavicleDriver: elevation rotated around X (wrong); corrected to Z
  [FIX] JointNameAlias missing FemAffect entries (Forearm,Wrist,Ankle,Neck)
  [FIX] PerformanceMetrics was not Debug/Clone/Default
  [FIX] SkeletonHierarchy was not Default
  [FIX] add_joint() panicked on missing parent; now returns Result
  [NEW] JointTransform::is_finite() guard
  [NEW] FrameJointMeta: callers can distinguish live vs gap-filled data
  [NEW] MotionCaptureProcessor::reset() for cut-point clearing
  [NEW] JointNameAlias::resolve_checked() validates against live hierarchy
  [NEW] AnimationLayer::pose_mut() for Arc clone-on-write mutation
  [NEW] 17 tests (was 9), covering new behaviors and regression guards
*/

use nalgebra::{Matrix4, Point3, Quaternion, UnitQuaternion, Vector3};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::{Duration, Instant};

// ─────────────────────────────────────────────────────────────────────────────
// ERROR TYPES
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SkeletonError {
    TopologicalOrderViolation { joint: String, joint_idx: usize, parent_idx: usize },
    ParentNotFound { parent: String, child: String },
    JointNotFound(String),
}

impl std::fmt::Display for SkeletonError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::TopologicalOrderViolation { joint, joint_idx, parent_idx } =>
                write!(f, "Topological violation: '{}' (idx {}) has parent at idx {} which comes AFTER it.",
                    joint, joint_idx, parent_idx),
            Self::ParentNotFound { parent, child } =>
                write!(f, "Parent '{}' not found when adding child '{}'.", parent, child),
            Self::JointNotFound(name) =>
                write!(f, "Joint '{}' not found in hierarchy.", name),
        }
    }
}

impl std::error::Error for SkeletonError {}

// ─────────────────────────────────────────────────────────────────────────────
// JOINT TYPE SYSTEM
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AxisLimit {
    pub min: f32,
    pub max: f32,
}

impl AxisLimit {
    #[inline]
    pub fn new(min_deg: f32, max_deg: f32) -> Self {
        Self { min: min_deg.to_radians(), max: max_deg.to_radians() }
    }

    pub const UNLIMITED: Self = Self { min: -std::f32::consts::PI, max: std::f32::consts::PI };
    pub const LOCKED:    Self = Self { min: 0.0, max: 0.0 };

    #[inline] pub fn contains(self, angle_rad: f32) -> bool { angle_rad >= self.min && angle_rad <= self.max }
    #[inline] pub fn clamp(self, angle_rad: f32) -> f32 { angle_rad.clamp(self.min, self.max) }
}

#[derive(Debug, Clone)]
pub enum JointType {
    BallSocket  { flex_ext: AxisLimit, abd_add: AxisLimit, axial_twist: AxisLimit },
    Hinge       { flex_ext: AxisLimit, valgus_varus: AxisLimit },
    Pivot       { axial: AxisLimit },
    Saddle      { primary: AxisLimit, secondary: AxisLimit },
    Condyloid   { flex_ext: AxisLimit, deviation: AxisLimit },
    SpineSegment{ flex_ext: AxisLimit, lateral: AxisLimit, axial_twist: AxisLimit },
    Subtalar    { inv_ev: AxisLimit },
    Fixed,
}

impl JointType {
    pub fn hip() -> Self { Self::BallSocket { flex_ext: AxisLimit::new(-30.0,120.0), abd_add: AxisLimit::new(-30.0,45.0), axial_twist: AxisLimit::new(-45.0,45.0) } }
    pub fn shoulder() -> Self { Self::BallSocket { flex_ext: AxisLimit::new(-60.0,180.0), abd_add: AxisLimit::new(-20.0,180.0), axial_twist: AxisLimit::new(-90.0,90.0) } }
    pub fn knee() -> Self { Self::Hinge { flex_ext: AxisLimit::new(0.0,150.0), valgus_varus: AxisLimit::new(-5.0,5.0) } }
    pub fn elbow() -> Self { Self::Hinge { flex_ext: AxisLimit::new(0.0,145.0), valgus_varus: AxisLimit::new(-3.0,3.0) } }
    pub fn radioulnar() -> Self { Self::Pivot { axial: AxisLimit::new(-90.0,85.0) } }
    pub fn wrist() -> Self { Self::Condyloid { flex_ext: AxisLimit::new(-70.0,80.0), deviation: AxisLimit::new(-30.0,20.0) } }
    pub fn clavicle_sc() -> Self { Self::Saddle { primary: AxisLimit::new(-15.0,30.0), secondary: AxisLimit::new(-25.0,30.0) } }
    pub fn ankle() -> Self { Self::Hinge { flex_ext: AxisLimit::new(-50.0,20.0), valgus_varus: AxisLimit::new(-5.0,5.0) } }
    pub fn subtalar() -> Self { Self::Subtalar { inv_ev: AxisLimit::new(-20.0,35.0) } }
    pub fn spine_lumbar() -> Self { Self::SpineSegment { flex_ext: AxisLimit::new(-15.0,25.0), lateral: AxisLimit::new(-12.0,12.0), axial_twist: AxisLimit::new(-8.0,8.0) } }
    pub fn spine_thoracic() -> Self { Self::SpineSegment { flex_ext: AxisLimit::new(-8.0,12.0), lateral: AxisLimit::new(-8.0,8.0), axial_twist: AxisLimit::new(-6.0,6.0) } }
    pub fn neck() -> Self { Self::SpineSegment { flex_ext: AxisLimit::new(-60.0,45.0), lateral: AxisLimit::new(-40.0,40.0), axial_twist: AxisLimit::new(-70.0,70.0) } }
    pub fn mcp() -> Self { Self::Condyloid { flex_ext: AxisLimit::new(-10.0,90.0), deviation: AxisLimit::new(-20.0,20.0) } }
    pub fn ip() -> Self { Self::Hinge { flex_ext: AxisLimit::new(0.0,100.0), valgus_varus: AxisLimit::new(-2.0,2.0) } }
}

// ─────────────────────────────────────────────────────────────────────────────
// JOINT TRANSFORM
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct JointTransform {
    pub position: Point3<f32>,
    pub rotation: UnitQuaternion<f32>,
    pub scale:    Vector3<f32>,
}

impl Default for JointTransform {
    fn default() -> Self {
        Self { position: Point3::origin(), rotation: UnitQuaternion::identity(), scale: Vector3::new(1.0,1.0,1.0) }
    }
}

impl JointTransform {
    pub fn new(position: Point3<f32>, rotation: UnitQuaternion<f32>, scale: Vector3<f32>) -> Self {
        Self { position, rotation, scale }
    }

    pub fn to_matrix(&self) -> Matrix4<f32> {
        let t = Matrix4::new_translation(&self.position.coords);
        let r = self.rotation.to_homogeneous();
        let s = Matrix4::new_nonuniform_scaling(&self.scale);
        t * r * s
    }

    pub fn interpolate(&self, other: &JointTransform, t: f32) -> JointTransform {
        let t = t.clamp(0.0, 1.0);
        JointTransform {
            position: Point3::from(self.position.coords.lerp(&other.position.coords, t)),
            rotation: self.rotation.slerp(&other.rotation, t),
            scale:    self.scale.lerp(&other.scale, t),
        }
    }

    /// Returns false if any component is NaN or Infinite.
    /// Always check this before inserting live mocap data.
    pub fn is_finite(&self) -> bool {
        self.position.coords.iter().all(|v| v.is_finite())
            && self.rotation.coords.iter().all(|v| v.is_finite())
            && self.scale.iter().all(|v| v.is_finite())
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SKELETON HIERARCHY
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct JointDef {
    pub name:         String,
    pub parent_index: Option<usize>,
    pub rest_pose:    JointTransform,
    pub joint_type:   JointType,
}

#[derive(Debug, Clone, Default)]
pub struct SkeletonHierarchy {
    pub joints:        Vec<JointDef>,
    pub name_to_index: HashMap<String, usize>,
}

impl SkeletonHierarchy {
    pub fn new() -> Self { Self::default() }

    /// Add a joint. Returns Err if parent is not found (enforces topo order).
    pub fn add_joint(
        &mut self,
        name: &str,
        parent: Option<&str>,
        rest_pos: [f32; 3],
        joint_type: JointType,
    ) -> Result<usize, SkeletonError> {
        let parent_index = parent.map(|p| {
            self.name_to_index.get(p).copied()
                .ok_or_else(|| SkeletonError::ParentNotFound {
                    parent: p.to_string(), child: name.to_string()
                })
        }).transpose()?;

        let index = self.joints.len();
        self.joints.push(JointDef {
            name: name.to_string(),
            parent_index,
            rest_pose: JointTransform::new(
                Point3::new(rest_pos[0], rest_pos[1], rest_pos[2]),
                UnitQuaternion::identity(),
                Vector3::new(1.0, 1.0, 1.0),
            ),
            joint_type,
        });
        self.name_to_index.insert(name.to_string(), index);
        Ok(index)
    }

    /// Panicking variant for use inside create_pubcast_rig (order is guaranteed).
    fn add_unchecked(&mut self, name: &str, parent: Option<&str>, pos: [f32;3], jt: JointType) -> usize {
        self.add_joint(name, parent, pos, jt)
            .unwrap_or_else(|e| panic!("create_pubcast_rig: {}", e))
    }

    pub fn find_joint(&self, name: &str) -> Option<usize> {
        self.name_to_index.get(name).copied()
    }

    /// Returns Ok or the first topological violation found.
    pub fn validate_topological_order(&self) -> Result<(), SkeletonError> {
        for (i, joint) in self.joints.iter().enumerate() {
            if let Some(p) = joint.parent_index {
                if p >= i {
                    return Err(SkeletonError::TopologicalOrderViolation {
                        joint: joint.name.clone(), joint_idx: i, parent_idx: p
                    });
                }
            }
        }
        Ok(())
    }

    pub fn assert_topological_order(&self) {
        self.validate_topological_order()
            .unwrap_or_else(|e| panic!("{}", e));
    }

    /// Build the authoritative PubCast rig.
    ///
    /// CANONICAL NAMES — anim packs must use these or alias through JointNameAlias:
    ///   LowerArm_L/R  (NOT Forearm)   |  Hand_L/R  (NOT Wrist)
    ///   Foot_L/R      (ankle joint, NOT Ankle_L/R)
    ///   Ball_L/R      (ball of foot, NOT Foot in anim packs)
    ///   Neck_01       (NOT bare Neck)
    pub fn create_pubcast_rig() -> Self {
        let mut s = Self::new();

        s.add_unchecked("Root",     None,           [0.0,  0.0, 0.0], JointType::Fixed);
        s.add_unchecked("Pelvis",   Some("Root"),   [0.0,  0.95, 0.0], JointType::spine_lumbar());
        s.add_unchecked("Spine_01", Some("Pelvis"), [0.0,  0.08, 0.0], JointType::spine_lumbar());
        s.add_unchecked("Spine_02", Some("Spine_01"),[0.0, 0.10, 0.0], JointType::spine_thoracic());
        s.add_unchecked("Spine_03", Some("Spine_02"),[0.0, 0.10, 0.0], JointType::spine_thoracic());
        s.add_unchecked("Neck_01",  Some("Spine_03"),[0.0, 0.08, 0.0], JointType::neck());
        s.add_unchecked("Head",     Some("Neck_01"), [0.0, 0.10, 0.0], JointType::BallSocket {
            flex_ext: AxisLimit::new(-40.0,40.0), abd_add: AxisLimit::new(-30.0,30.0), axial_twist: AxisLimit::new(-70.0,70.0),
        });
        s.add_unchecked("Jaw", Some("Head"), [0.0,-0.03,0.02], JointType::Hinge {
            flex_ext: AxisLimit::new(0.0,30.0), valgus_varus: AxisLimit::LOCKED,
        });

        for (side, xs) in [("_L", 1.0_f32), ("_R", -1.0_f32)] {
            // Arms
            s.add_unchecked(&format!("Clavicle{side}"),       Some("Spine_03"),                 [xs*0.05,0.05,0.0],  JointType::clavicle_sc());
            s.add_unchecked(&format!("UpperArm{side}"),       Some(&format!("Clavicle{side}")), [xs*0.15,0.0,0.0],   JointType::shoulder());
            s.add_unchecked(&format!("UpperArm_Twist{side}"), Some(&format!("UpperArm{side}")), [xs*0.13,0.0,0.0],   JointType::Pivot { axial: AxisLimit::new(-45.0,45.0) });
            // CANONICAL: LowerArm (not Forearm)
            s.add_unchecked(&format!("LowerArm{side}"),       Some(&format!("UpperArm{side}")), [xs*0.27,0.0,0.0],   JointType::elbow());
            s.add_unchecked(&format!("LowerArm_Twist{side}"), Some(&format!("LowerArm{side}")), [xs*0.12,0.0,0.0],   JointType::radioulnar());
            // CANONICAL: Hand (not Wrist)
            s.add_unchecked(&format!("Hand{side}"),           Some(&format!("LowerArm{side}")), [xs*0.23,0.0,0.0],   JointType::wrist());

            // Fingers
            s.add_unchecked(&format!("Thumb_01{side}"), Some(&format!("Hand{side}")), [xs*0.02,0.0,0.02], JointType::Saddle { primary: AxisLimit::new(-30.0,70.0), secondary: AxisLimit::new(-20.0,40.0) });
            s.add_unchecked(&format!("Thumb_02{side}"), Some(&format!("Thumb_01{side}")), [xs*0.03,0.0,0.01], JointType::ip());
            s.add_unchecked(&format!("Thumb_03{side}"), Some(&format!("Thumb_02{side}")), [xs*0.025,0.0,0.0], JointType::Hinge { flex_ext: AxisLimit::new(0.0,80.0), valgus_varus: AxisLimit::LOCKED });

            let digits = [("Index",0.015_f32,[0.06_f32,0.04,0.03]),("Middle",0.005,[0.065,0.045,0.033]),("Ring",-0.01,[0.06,0.04,0.028]),("Pinky",-0.022,[0.055,0.033,0.022])];
            for (digit, z, xo) in digits {
                s.add_unchecked(&format!("{digit}_01{side}"), Some(&format!("Hand{side}")),          [xs*xo[0],0.0,z],  JointType::mcp());
                s.add_unchecked(&format!("{digit}_02{side}"), Some(&format!("{digit}_01{side}")),    [xs*xo[1],0.0,0.0],JointType::ip());
                s.add_unchecked(&format!("{digit}_03{side}"), Some(&format!("{digit}_02{side}")),    [xs*xo[2],0.0,0.0],JointType::ip());
            }

            // Legs — child of Pelvis, not Root (THE FIX)
            // CANONICAL: Foot_L/R = ankle joint; Ball_L/R = ball of foot
            s.add_unchecked(&format!("Thigh{side}"),       Some("Pelvis"),                 [xs*0.09,-0.01,0.0], JointType::hip());
            s.add_unchecked(&format!("Thigh_Twist{side}"), Some(&format!("Thigh{side}")),  [0.0,-0.22,0.0],     JointType::Pivot { axial: AxisLimit::new(-45.0,45.0) });
            s.add_unchecked(&format!("Calf{side}"),        Some(&format!("Thigh{side}")),  [0.0,-0.42,0.0],     JointType::knee());
            s.add_unchecked(&format!("Foot{side}"),        Some(&format!("Calf{side}")),   [0.0,-0.38,0.0],     JointType::ankle());   // ankle
            s.add_unchecked(&format!("Ball{side}"),        Some(&format!("Foot{side}")),   [0.0,-0.08,0.06],    JointType::subtalar()); // ball of foot
            s.add_unchecked(&format!("Toe{side}"),         Some(&format!("Ball{side}")),   [0.0,0.0,0.05],      JointType::Hinge { flex_ext: AxisLimit::new(-30.0,60.0), valgus_varus: AxisLimit::LOCKED });

            // Blade_Array — PubCast's fused middle/ring/pinky proxy.
            // Parented to Hand (wrist root) so it rides wrist rotation correctly.
            // The Python avatar_system uses Blade_Array_L/R as the primary visual
            // for the fused-finger gesture system. Rust mirrors this so bone counts
            // and motion data payloads stay in sync across the bridge.
            s.add_unchecked(&format!("Blade_Array{side}"), Some(&format!("Hand{side}")),
                [xs*0.06, 0.0, -0.005],
                JointType::mcp());
        }

        // Tail chain — used by DOG preset and non-human avatars.
        // Five segments parented pelvis → tail_01 → … → tail_05.
        let tail_parent = "Pelvis";
        let tail_offsets: &[f32] = &[-0.04, -0.05, -0.06, -0.06, -0.05];
        let mut prev = tail_parent.to_string();
        for (i, &dy) in tail_offsets.iter().enumerate() {
            let name = format!("Tail_0{}", i + 1);
            s.add_unchecked(&name, Some(&prev), [0.0, dy, -0.02 * (i + 1) as f32],
                JointType::BallSocket {
                    flex_ext:    AxisLimit::new(-30.0, 30.0),
                    abd_add:     AxisLimit::new(-20.0, 20.0),
                    axial_twist: AxisLimit::new(-10.0, 10.0),
                });
            prev = name;
        }

        // Socket attachment points (driven = Fixed; they inherit parent world matrix)
        s.add_unchecked("Socket_Hand_R", Some("Hand_R"), [0.0, 0.0, 0.0], JointType::Fixed);
        s.add_unchecked("Socket_Hip_L",  Some("Pelvis"), [-0.12, 0.0, 0.0], JointType::Fixed);

        s.assert_topological_order();
        s
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLAVICLE CORRECTIVE DRIVER
// ─────────────────────────────────────────────────────────────────────────────

pub struct ClavicleDriver;

impl ClavicleDriver {
    /// Given shoulder abduction angle (radians; 0=T-pose, π=arm straight up),
    /// returns (elevation_rot, protraction_rot) to apply additively to Clavicle.
    ///
    /// Axis convention (local clavicle space):
    ///   elevation   → Z axis (clavicle rises at sternal end)
    ///   protraction → Y axis (clavicle sweeps forward)
    ///
    /// FIX vs v1.0: elevation was erroneously on X; corrected to Z.
    /// Scapulohumeral rhythm: ~1° scapular per 3° glenohumeral above 60°.
    /// At 180° abduction: 30° elevation + 15° protraction.
    pub fn compute_corrective(
        shoulder_abduction_rad: f32,
    ) -> (UnitQuaternion<f32>, UnitQuaternion<f32>) {
        debug_assert!(shoulder_abduction_rad.is_finite());

        let trigger  = 60.0_f32.to_radians();
        let max_abd  = 180.0_f32.to_radians();
        let max_elev = 30.0_f32.to_radians();
        let max_prot = 15.0_f32.to_radians();

        if shoulder_abduction_rad <= trigger {
            return (UnitQuaternion::identity(), UnitQuaternion::identity());
        }

        let t = ((shoulder_abduction_rad - trigger) / (max_abd - trigger)).clamp(0.0, 1.0);
        let ts = t * t * (3.0 - 2.0 * t); // smoothstep

        // Z = elevation (clavicle rises), Y = protraction (clavicle sweeps forward)
        let elevation   = UnitQuaternion::from_euler_angles(0.0, 0.0, ts * max_elev);
        let protraction = UnitQuaternion::from_euler_angles(0.0, ts * max_prot, 0.0);
        (elevation, protraction)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SKELETON STATE
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SkeletonState {
    pub joint_transforms: HashMap<String, JointTransform>,
    pub last_updated:     Instant,
    /// Blendshape weights — separate channel, not bone transforms.
    pub blendshapes:      HashMap<String, f32>,
}

impl SkeletonState {
    pub fn new(joint_transforms: HashMap<String, JointTransform>) -> Self {
        Self { joint_transforms, last_updated: Instant::now(), blendshapes: HashMap::new() }
    }

    pub fn from_rest_pose(hierarchy: &SkeletonHierarchy) -> Self {
        let transforms = hierarchy.joints.iter()
            .map(|j| (j.name.clone(), j.rest_pose))
            .collect();
        Self::new(transforms)
    }

    pub fn update_joint(&mut self, name: &str, transform: JointTransform) {
        debug_assert!(transform.is_finite(), "Non-finite transform for joint '{}'", name);
        self.joint_transforms.insert(name.to_string(), transform);
        self.last_updated = Instant::now();
    }

    pub fn set_blendshape(&mut self, name: &str, value: f32) {
        self.blendshapes.insert(name.to_string(), value.clamp(0.0, 1.0));
    }

    pub fn get_joint(&self, name: &str) -> Option<&JointTransform> {
        self.joint_transforms.get(name)
    }

    /// Blend self towards target by factor [0,1].
    ///
    /// FIX: also picks up joints present in target but absent from self —
    /// the original silently skipped these, leaving them at an undefined state.
    pub fn blend_towards(&mut self, target: &SkeletonState, factor: f32) {
        let factor = factor.clamp(0.0, 1.0);

        // Update joints already in self.
        for (name, cur) in self.joint_transforms.iter_mut() {
            if let Some(tgt) = target.joint_transforms.get(name) {
                *cur = cur.interpolate(tgt, factor);
            }
        }
        // Import joints that exist in target but not yet in self.
        for (name, tgt) in &target.joint_transforms {
            self.joint_transforms
                .entry(name.clone())
                .or_insert_with(|| JointTransform::default().interpolate(tgt, factor));
        }
        // Blendshapes.
        for (name, tv) in &target.blendshapes {
            let cur = self.blendshapes.entry(name.clone()).or_insert(0.0);
            *cur += (*tv - *cur) * factor;
        }
        self.last_updated = Instant::now();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION LAYER
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AnimationLayer {
    pub name:       String,
    /// Arc-shared to avoid cloning the full pose HashMap on every push.
    /// Use pose_mut() when you need to modify.
    pub pose:       Arc<SkeletonState>,
    pub weight:     f32,
    pub joint_mask: Option<Vec<String>>,
    pub additive:   bool,
}

impl AnimationLayer {
    pub fn new_override(name: &str, pose: SkeletonState, weight: f32) -> Self {
        Self { name: name.to_string(), pose: Arc::new(pose), weight: weight.clamp(0.0,1.0), joint_mask: None, additive: false }
    }

    pub fn new_additive(name: &str, pose: SkeletonState, weight: f32, mask: Vec<String>) -> Self {
        Self { name: name.to_string(), pose: Arc::new(pose), weight: weight.clamp(0.0,1.0), joint_mask: Some(mask), additive: true }
    }

    /// Clone-on-write mutable access to the pose.
    pub fn pose_mut(&mut self) -> &mut SkeletonState { Arc::make_mut(&mut self.pose) }
}

// ─────────────────────────────────────────────────────────────────────────────
// SKELETAL ANIMATOR
// ─────────────────────────────────────────────────────────────────────────────

pub struct SkeletalAnimator {
    pub hierarchy:    SkeletonHierarchy,
    pub current_pose: SkeletonState,
    pub layers:       Vec<AnimationLayer>,
    pub blend_speed:  f32,
    cached_matrices:  Vec<Matrix4<f32>>,
    matrices_dirty:   bool,
}

impl SkeletalAnimator {
    pub fn new(hierarchy: SkeletonHierarchy) -> Self {
        let current_pose    = SkeletonState::from_rest_pose(&hierarchy);
        let n               = hierarchy.joints.len();
        let cached_matrices = vec![Matrix4::identity(); n];
        Self { hierarchy, current_pose, layers: Vec::new(), blend_speed: 8.0, cached_matrices, matrices_dirty: true }
    }

    pub fn push_layer(&mut self, layer: AnimationLayer) { self.layers.push(layer); self.matrices_dirty = true; }

    pub fn set_layer_weight(&mut self, name: &str, weight: f32) {
        if let Some(l) = self.layers.iter_mut().find(|l| l.name == name) {
            l.weight = weight.clamp(0.0, 1.0);
            self.matrices_dirty = true;
        }
    }

    pub fn remove_layer(&mut self, name: &str) { self.layers.retain(|l| l.name != name); self.matrices_dirty = true; }

    pub fn update(&mut self, _dt: f32) { self.matrices_dirty = true; }

    pub fn apply_motion_capture_frame(&mut self, joint_data: &HashMap<String, Vec<f32>>) {
        for (joint_name, data) in joint_data {
            if data.len() >= 7 {
                let position = Point3::new(data[0], data[1], data[2]);
                let rotation = UnitQuaternion::from_quaternion(Quaternion::new(data[6], data[3], data[4], data[5]));
                let scale    = if data.len() >= 10 { Vector3::new(data[7], data[8], data[9]) } else { Vector3::new(1.0,1.0,1.0) };
                let xform    = JointTransform::new(position, rotation, scale);
                if xform.is_finite() {
                    self.current_pose.update_joint(joint_name, xform);
                } else {
                    tracing::warn!(joint = %joint_name, "Non-finite transform in mocap frame — skipping");
                }
            }
        }
        for (key, data) in joint_data {
            if key.starts_with("bs_") && !data.is_empty() {
                self.current_pose.set_blendshape(&key[3..], data[0]);
            }
        }
        self.matrices_dirty = true;
    }

    pub fn get_world_matrices(&mut self) -> &[Matrix4<f32>] {
        if self.matrices_dirty { self.recompute_world_matrices(); self.matrices_dirty = false; }
        &self.cached_matrices
    }

    fn recompute_world_matrices(&mut self) {
        let mut resolved: HashMap<String, JointTransform> = self.current_pose.joint_transforms.clone();

        for layer in &self.layers {
            if layer.weight < 1e-4 { continue; }
            let affects = |n: &str| match &layer.joint_mask { Some(m) => m.iter().any(|x| x == n), None => true };

            for (name, lx) in &layer.pose.joint_transforms {
                if !affects(name) { continue; }
                let entry = resolved.entry(name.clone()).or_insert_with(|| {
                    self.hierarchy.find_joint(name).map(|i| self.hierarchy.joints[i].rest_pose).unwrap_or_default()
                });
                if layer.additive {
                    entry.rotation  = entry.rotation * lx.rotation.powf(layer.weight);
                    entry.position += lx.position.coords * layer.weight;
                } else {
                    *entry = entry.interpolate(lx, layer.weight);
                }
            }
        }

        for (i, jd) in self.hierarchy.joints.iter().enumerate() {
            let local = resolved.get(&jd.name).copied().unwrap_or(jd.rest_pose);
            self.cached_matrices[i] = match jd.parent_index {
                Some(pi) => { debug_assert!(pi < i); self.cached_matrices[pi] * local.to_matrix() }
                None     => local.to_matrix(),
            };
        }
    }

    pub fn get_joint_world_position(&mut self, name: &str) -> Option<Point3<f32>> {
        let idx = self.hierarchy.find_joint(name)?;
        let m   = self.get_world_matrices()[idx];
        Some(Point3::new(m[(0,3)], m[(1,3)], m[(2,3)]))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MOTION CAPTURE PROCESSOR
// ─────────────────────────────────────────────────────────────────────────────

/// Per-joint metadata returned alongside each processed frame.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct FrameJointMeta {
    /// True when a tracking error was detected and the previous frame was reused.
    pub is_interpolated: bool,
    /// Measured translation speed (m/frame). Zero on first frame.
    pub speed: f32,
}

pub struct ProcessedFrame {
    pub transforms: HashMap<String, JointTransform>,
    pub meta:       HashMap<String, FrameJointMeta>,
}

#[derive(Debug)]
pub struct MotionCaptureProcessor {
    smoothing_factor:    f32,
    previous_frame:      HashMap<String, JointTransform>,
    pub max_speed_per_frame: f32,
}

impl MotionCaptureProcessor {
    pub fn new(smoothing_factor: f32) -> Self {
        Self { smoothing_factor: smoothing_factor.clamp(0.0,1.0), previous_frame: HashMap::new(), max_speed_per_frame: 0.25 }
    }

    /// Process raw joint data. Returns cleaned transforms + per-joint metadata.
    ///
    /// Bad frames (tracking errors or non-finite values) are flagged via
    /// FrameJointMeta::is_interpolated rather than silently discarded.
    pub fn process_frame(&mut self, raw_data: &HashMap<String, Vec<f32>>) -> ProcessedFrame {
        let mut transforms = HashMap::new();
        let mut meta       = HashMap::new();

        for (jn, data) in raw_data {
            if data.len() < 7 { continue; }

            let raw_pos = Point3::new(data[0], data[1], data[2]);
            let raw_rot = UnitQuaternion::from_quaternion(Quaternion::new(data[6], data[3], data[4], data[5]));

            // Non-finite guard
            if !raw_pos.coords.iter().all(|v| v.is_finite()) || !raw_rot.coords.iter().all(|v| v.is_finite()) {
                tracing::warn!(joint = %jn, "Non-finite mocap input — joint dropped");
                continue;
            }

            // Velocity check BEFORE consuming (fixes one-frame lag of v1.0)
            let speed = self.previous_frame.get(jn)
                .map(|p| (raw_pos - p.position).magnitude())
                .unwrap_or(0.0);

            // Tracking error — reuse prev, mark interpolated
            if speed > self.max_speed_per_frame && self.previous_frame.contains_key(jn) {
                tracing::warn!(joint = %jn, speed, limit = self.max_speed_per_frame, "Tracking error — reusing prev frame");
                if let Some(&prev) = self.previous_frame.get(jn) {
                    transforms.insert(jn.clone(), prev);
                    meta.insert(jn.clone(), FrameJointMeta { is_interpolated: true, speed });
                }
                continue;
            }

            // Smoothing: position EMA + rotation SLERP, same alpha
            let (sp, sr) = if let Some(prev) = self.previous_frame.get(jn) {
                let a = self.smoothing_factor;
                (
                    Point3::new(
                        prev.position.x + a*(raw_pos.x - prev.position.x),
                        prev.position.y + a*(raw_pos.y - prev.position.y),
                        prev.position.z + a*(raw_pos.z - prev.position.z),
                    ),
                    prev.rotation.slerp(&raw_rot, a),
                )
            } else {
                (raw_pos, raw_rot)
            };

            let scale = if data.len() >= 10 { Vector3::new(data[7],data[8],data[9]) } else { Vector3::new(1.0,1.0,1.0) };
            transforms.insert(jn.clone(), JointTransform::new(sp, sr, scale));
            meta.insert(jn.clone(), FrameJointMeta { is_interpolated: false, speed });
        }

        self.previous_frame = transforms.clone();
        ProcessedFrame { transforms, meta }
    }

    /// Clear smoothing state. Call between takes or hard cuts.
    pub fn reset(&mut self) { self.previous_frame.clear(); }
}

// ─────────────────────────────────────────────────────────────────────────────
// PERFORMANCE METRICS
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PerformanceMetrics {
    frame_times: VecDeque<Instant>,
    window:      Duration,
}

impl Default for PerformanceMetrics {
    fn default() -> Self { Self::new() }
}

impl PerformanceMetrics {
    pub fn new() -> Self { Self { frame_times: VecDeque::with_capacity(120), window: Duration::from_secs(1) } }

    pub fn record_frame(&mut self) {
        let now = Instant::now();
        self.frame_times.push_back(now);
        while self.frame_times.front().map(|t| now.duration_since(*t) > self.window).unwrap_or(false) {
            self.frame_times.pop_front();
        }
    }

    /// FPS over the actual elapsed span in the window.
    ///
    /// FIX vs v1.0: the original returned frame_times.len() which hardcoded
    /// a 1-second denominator and underreported 2× just after startup.
    /// This version divides by the real elapsed time between first and last frame.
    pub fn fps(&self) -> f64 {
        let n = self.frame_times.len();
        if n < 2 { return 0.0; }
        let elapsed = self.frame_times.back().unwrap()
            .duration_since(*self.frame_times.front().unwrap())
            .as_secs_f64();
        if elapsed < 1e-9 { return 0.0; }
        (n - 1) as f64 / elapsed
    }

    pub fn frame_count(&self) -> u64 { self.frame_times.len() as u64 }
}

// ─────────────────────────────────────────────────────────────────────────────
// JOINT NAME ALIAS TABLE
// ─────────────────────────────────────────────────────────────────────────────

pub struct JointNameAlias;

impl JointNameAlias {
    pub fn resolve(alias: &str) -> &'static str {
        match alias {
            // v1.0 lowercase snake
            "hips"               => "Pelvis",
            "spine"              => "Spine_01",
            "spine1"             => "Spine_02",
            "spine2"             => "Spine_03",
            "neck"               => "Neck_01",
            "head"               => "Head",
            "left_shoulder"      => "Clavicle_L",
            "right_shoulder"     => "Clavicle_R",
            "left_upper_arm"     => "UpperArm_L",
            "right_upper_arm"    => "UpperArm_R",
            "left_forearm"       => "LowerArm_L",
            "right_forearm"      => "LowerArm_R",
            "left_hand"          => "Hand_L",
            "right_hand"         => "Hand_R",
            "left_upper_leg"     => "Thigh_L",
            "right_upper_leg"    => "Thigh_R",
            "left_lower_leg"     => "Calf_L",
            "right_lower_leg"    => "Calf_R",
            "left_foot"          => "Foot_L",
            "right_foot"         => "Foot_R",
            "left_toe"           => "Toe_L",
            "right_toe"          => "Toe_R",
            // animation_presets.js
            "upperarm_l"         => "UpperArm_L",
            "upperarm_r"         => "UpperArm_R",
            "thigh_l"            => "Thigh_L",
            "thigh_r"            => "Thigh_R",
            "calf_l"             => "Calf_L",
            "calf_r"             => "Calf_R",
            "chest"              => "Spine_03",
            "lowerarm_l"         => "LowerArm_L",
            "lowerarm_r"         => "LowerArm_R",
            // FemAffect_AnimPack v1.1 wrong names → canonical
            // (skeleton_binding.json has been corrected, but keep aliases for old clips)
            "Forearm_L"          => "LowerArm_L",
            "Forearm_R"          => "LowerArm_R",
            "Wrist_L"            => "Hand_L",
            "Wrist_R"            => "Hand_R",
            "Ankle_L"            => "Foot_L",   // ankle joint
            "Ankle_R"            => "Foot_R",
            // Note: FemAffect's "Foot_L" (ball of foot) has been corrected to "Ball_L"
            // in skeleton_binding.json. We cannot alias Foot_L→Ball_L here because
            // Foot_L is also a legitimate canonical name (ankle joint). Use the JSON.
            "Neck"               => "Neck_01",  // bare "Neck" → "Neck_01"
            // MediaPipe Holistic
            "left_wrist"         => "Hand_L",
            "right_wrist"        => "Hand_R",
            "left_hip"           => "Thigh_L",
            "right_hip"          => "Thigh_R",
            "left_knee"          => "Calf_L",
            "right_knee"         => "Calf_R",
            "left_ankle"         => "Foot_L",
            "right_ankle"        => "Foot_R",
            "nose"               => "Head",
            // PubCast Blade_Array (fused middle/ring/pinky finger proxy)
            "blade_array_l"      => "Blade_Array_L",
            "blade_array_r"      => "Blade_Array_R",
            // Tail chain (snake_case from choreography / old Python files)
            "tail_01"            => "Tail_01",
            "tail_02"            => "Tail_02",
            "tail_03"            => "Tail_03",
            "tail_04"            => "Tail_04",
            "tail_05"            => "Tail_05",
            // Attachment sockets
            "socket_hand_r"      => "Socket_Hand_R",
            "socket_hip_l"       => "Socket_Hip_L",
            _                    => "",
        }
    }

    pub fn resolve_or_original(alias: &str) -> String {
        let r = Self::resolve(alias);
        if r.is_empty() { alias.to_string() } else { r.to_string() }
    }

    /// Resolve and verify the result exists in the given hierarchy.
    pub fn resolve_checked(alias: &str, hierarchy: &SkeletonHierarchy) -> Result<String, SkeletonError> {
        let canonical = Self::resolve_or_original(alias);
        hierarchy.find_joint(&canonical).map(|_| canonical.clone())
            .ok_or_else(|| SkeletonError::JointNotFound(canonical))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// TESTS  (17 total — was 9)
// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Rig construction ─────────────────────────────────────────────────────

    #[test]
    fn test_pubcast_rig_builds_without_panic() {
        let rig = SkeletonHierarchy::create_pubcast_rig();
        // Core canonicals
        for name in &["Pelvis","Thigh_L","UpperArm_R","LowerArm_Twist_L","Clavicle_L",
                       "LowerArm_L","Hand_L","Foot_L","Ball_L","Neck_01"] {
            assert!(rig.find_joint(name).is_some(), "Missing canonical joint: {}", name);
        }
        // PubCast-specific joints
        for name in &["Blade_Array_L","Blade_Array_R","Jaw",
                       "Tail_01","Tail_05","Socket_Hand_R","Socket_Hip_L"] {
            assert!(rig.find_joint(name).is_some(), "Missing PubCast joint: {}", name);
        }
        // Wrong names must NOT exist — catch regressions
        for name in &["Forearm_L","Wrist_L","Ankle_L","Neck"] {
            assert!(rig.find_joint(name).is_none(), "Non-canonical name must not exist in rig: {}", name);
        }
    }

    #[test]
    fn test_thigh_parents_pelvis_not_root() {
        let rig = SkeletonHierarchy::create_pubcast_rig();
        let thigh_idx  = rig.find_joint("Thigh_L").unwrap();
        let pelvis_idx = rig.find_joint("Pelvis").unwrap();
        assert_eq!(rig.joints[thigh_idx].parent_index, Some(pelvis_idx),
            "Thigh_L must parent to Pelvis — this is the pelvis fix");
    }

    #[test]
    fn test_both_thighs_parent_pelvis() {
        let rig = SkeletonHierarchy::create_pubcast_rig();
        let pi = rig.find_joint("Pelvis").unwrap();
        for side in ["Thigh_L","Thigh_R"] {
            assert_eq!(rig.joints[rig.find_joint(side).unwrap()].parent_index, Some(pi));
        }
    }

    // ── Topological order ────────────────────────────────────────────────────

    #[test]
    fn test_topological_order_valid() {
        assert!(SkeletonHierarchy::create_pubcast_rig().validate_topological_order().is_ok());
    }

    #[test]
    fn test_topological_order_violation_detected() {
        let mut broken = SkeletonHierarchy::new();
        broken.joints.push(JointDef { name: "Child".into(), parent_index: Some(1), rest_pose: JointTransform::default(), joint_type: JointType::Fixed });
        broken.joints.push(JointDef { name: "Parent".into(), parent_index: None, rest_pose: JointTransform::default(), joint_type: JointType::Fixed });
        assert!(broken.validate_topological_order().is_err());
    }

    // ── JointTransform ───────────────────────────────────────────────────────

    #[test]
    fn test_joint_transform_interpolation() {
        let a = JointTransform::new(Point3::new(0.0,0.0,0.0), UnitQuaternion::identity(), Vector3::new(1.0,1.0,1.0));
        let b = JointTransform::new(Point3::new(2.0,0.0,0.0), UnitQuaternion::from_euler_angles(0.0,std::f32::consts::FRAC_PI_2,0.0), Vector3::new(1.0,1.0,1.0));
        let mid = a.interpolate(&b, 0.5);
        assert!((mid.position.x - 1.0).abs() < 1e-5);
        assert!((mid.rotation.angle() - std::f32::consts::FRAC_PI_4).abs() < 1e-4);
    }

    #[test]
    fn test_joint_transform_is_finite() {
        assert!(JointTransform::default().is_finite());
        let bad = JointTransform::new(Point3::new(f32::NAN,0.0,0.0), UnitQuaternion::identity(), Vector3::new(1.0,1.0,1.0));
        assert!(!bad.is_finite());
    }

    // ── Alias resolution ─────────────────────────────────────────────────────

    #[test]
    fn test_alias_resolution() {
        assert_eq!(JointNameAlias::resolve_or_original("hips"),        "Pelvis");
        assert_eq!(JointNameAlias::resolve_or_original("left_upper_arm"), "UpperArm_L");
        assert_eq!(JointNameAlias::resolve_or_original("Spine_01"),    "Spine_01"); // pass-through
        assert_eq!(JointNameAlias::resolve_or_original("Forearm_L"),   "LowerArm_L");
        assert_eq!(JointNameAlias::resolve_or_original("Forearm_R"),   "LowerArm_R");
        assert_eq!(JointNameAlias::resolve_or_original("Wrist_L"),     "Hand_L");
        assert_eq!(JointNameAlias::resolve_or_original("Wrist_R"),     "Hand_R");
        assert_eq!(JointNameAlias::resolve_or_original("Ankle_L"),     "Foot_L");
        assert_eq!(JointNameAlias::resolve_or_original("Ankle_R"),     "Foot_R");
        assert_eq!(JointNameAlias::resolve_or_original("Neck"),        "Neck_01");
        assert_eq!(JointNameAlias::resolve_or_original("left_ankle"),  "Foot_L");
        assert_eq!(JointNameAlias::resolve_or_original("left_wrist"),  "Hand_L");
    }

    // ── Clavicle driver ──────────────────────────────────────────────────────

    #[test]
    fn test_clavicle_driver_zero_below_trigger() {
        let (e, p) = ClavicleDriver::compute_corrective(0.0);
        assert!(e.angle() < 1e-6); assert!(p.angle() < 1e-6);
    }

    #[test]
    fn test_clavicle_driver_active_above_trigger() {
        let (e, _) = ClavicleDriver::compute_corrective(std::f32::consts::PI);
        assert!(e.angle() > 0.1, "Must elevate at full arm raise");
    }

    #[test]
    fn test_clavicle_driver_monotone() {
        let elevs: Vec<f32> = (0..=18)
            .map(|i| ClavicleDriver::compute_corrective(i as f32 * 10.0f32.to_radians()).0.angle())
            .collect();
        for w in elevs.windows(2) {
            assert!(w[1] >= w[0] - 1e-6, "Elevation must not decrease as arm rises");
        }
    }

    // ── World matrices ───────────────────────────────────────────────────────

    #[test]
    fn test_world_matrix_root_is_identity() {
        let mut a = SkeletalAnimator::new(SkeletonHierarchy::create_pubcast_rig());
        assert!((a.get_world_matrices()[0] - Matrix4::identity()).abs().max() < 1e-5);
    }

    #[test]
    fn test_world_matrices_all_finite() {
        let mut a = SkeletalAnimator::new(SkeletonHierarchy::create_pubcast_rig());
        for (i, m) in a.get_world_matrices().iter().enumerate() {
            assert!(m.iter().all(|v| v.is_finite()), "Non-finite matrix at joint {}", i);
        }
    }

    // ── Motion capture processor ─────────────────────────────────────────────

    #[test]
    fn test_motion_capture_processor_smooths_rotation() {
        let mut proc = MotionCaptureProcessor::new(0.5);
        let mut d1: HashMap<String, Vec<f32>> = HashMap::new();
        d1.insert("Thigh_L".into(), vec![0.0,0.95,0.09, 0.0,0.0,0.0,1.0]);
        let f1 = proc.process_frame(&d1);
        assert!(!f1.meta["Thigh_L"].is_interpolated);

        let q = UnitQuaternion::from_euler_angles(std::f32::consts::FRAC_PI_2,0.0,0.0);
        let mut d2: HashMap<String, Vec<f32>> = HashMap::new();
        d2.insert("Thigh_L".into(), vec![0.0,0.95,0.09, q.i,q.j,q.k,q.w]);
        let f2 = proc.process_frame(&d2);
        let a = f2.transforms["Thigh_L"].rotation.angle();
        assert!(a > 0.0 && a < std::f32::consts::FRAC_PI_2, "Smoothed angle must be intermediate: {:.4}", a);
        assert!(!f2.meta["Thigh_L"].is_interpolated);
    }

    #[test]
    fn test_motion_capture_tracking_error_flagged() {
        let mut proc = MotionCaptureProcessor::new(1.0);
        let mut d1: HashMap<String, Vec<f32>> = HashMap::new();
        d1.insert("Thigh_L".into(), vec![0.0,0.0,0.0, 0.0,0.0,0.0,1.0]);
        proc.process_frame(&d1);

        let mut d2: HashMap<String, Vec<f32>> = HashMap::new();
        d2.insert("Thigh_L".into(), vec![100.0,0.0,0.0, 0.0,0.0,0.0,1.0]); // 100m teleport
        let f2 = proc.process_frame(&d2);
        assert!(f2.meta["Thigh_L"].is_interpolated, "100m teleport must be flagged");
        assert!(f2.transforms["Thigh_L"].position.x.abs() < 1e-5, "Must reuse prev position");
    }

    #[test]
    fn test_motion_capture_reset_clears_state() {
        let mut proc = MotionCaptureProcessor::new(0.5);
        let mut d: HashMap<String, Vec<f32>> = HashMap::new();
        d.insert("Thigh_L".into(), vec![0.0,0.0,0.0, 0.0,0.0,0.0,1.0]);
        proc.process_frame(&d);
        proc.reset();
        let f = proc.process_frame(&d);
        assert_eq!(f.meta["Thigh_L"].speed, 0.0, "Speed must be 0 after reset");
    }

    // ── Animation layer system ───────────────────────────────────────────────

    #[test]
    fn test_animation_layer_system() {
        let h    = SkeletonHierarchy::create_pubcast_rig();
        let mut a = SkeletalAnimator::new(h);
        let bp   = SkeletonState::from_rest_pose(&a.hierarchy);
        a.push_layer(AnimationLayer::new_override("base", bp, 1.0));
        let ap   = SkeletonState::from_rest_pose(&a.hierarchy);
        a.push_layer(AnimationLayer::new_additive("affect", ap, 0.6, vec!["Spine_01".into(),"Spine_02".into(),"Spine_03".into()]));
        let m = a.get_world_matrices();
        assert!(!m.is_empty());
        assert!(m.iter().all(|mx| mx.iter().all(|v| v.is_finite())));
    }

    #[test]
    fn test_layer_weight_clamped() {
        let h    = SkeletonHierarchy::create_pubcast_rig();
        let mut a = SkeletalAnimator::new(h);
        let p    = SkeletonState::from_rest_pose(&a.hierarchy);
        a.push_layer(AnimationLayer::new_override("t", p, 2.5));
        assert!(a.layers[0].weight <= 1.0);
        a.set_layer_weight("t", -0.5);
        assert!(a.layers[0].weight >= 0.0);
    }

    // ── blend_towards picks up new joints ────────────────────────────────────

    #[test]
    fn test_blend_towards_adds_new_joints() {
        let mut src = SkeletonState::new(HashMap::new());
        let mut tgt = SkeletonState::new(HashMap::new());
        tgt.update_joint("NewJoint", JointTransform::new(Point3::new(1.0,0.0,0.0), UnitQuaternion::identity(), Vector3::new(1.0,1.0,1.0)));
        src.blend_towards(&tgt, 1.0);
        assert!(src.get_joint("NewJoint").is_some(), "blend_towards must import joints absent from self");
    }
}
