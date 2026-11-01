/*!
pubcast_animation — Rust crate root
=====================================

Module hierarchy:
  crate
  ├── skeleton                — JointTransform, SkeletonHierarchy, SkeletalAnimator,
  │                             MotionCaptureProcessor, ClavicleDriver, AnimationLayer,
  │                             JointNameAlias  (authoritative — see skeleton.rs)
  ├── avatar_animation_system — [feature = "full-animation"] blend trees, state machine
  ├── animation_data_library  — [feature = "full-animation"] keyframe clips
  ├── avatar_fitting_system   — [feature = "full-animation"] body proportions, DNA presets
  └── complete_animation_controller — [feature = "full-animation"] top-level orchestrator

The `full-animation` feature gates the higher-level animation subsystems which are
still in active development. The core skeleton, bridge protocol, and ws_renderer
binary compile and run without it.

Public re-exports give callers a flat import surface:
  use pubcast_animation::{JointTransform, SkeletalAnimator, BridgeMotionPayload, ...};
*/

pub mod skeleton;

// Higher-level animation subsystems — gated to avoid compilation of incomplete stubs.
// Enable with: cargo build --features full-animation
#[cfg(feature = "full-animation")]
pub mod avatar_animation_system;
#[cfg(feature = "full-animation")]
pub mod animation_data_library;
#[cfg(feature = "full-animation")]
pub mod avatar_fitting_system;
#[cfg(feature = "full-animation")]
pub mod complete_animation_controller;

// ── Flat re-exports ───────────────────────────────────────────────────────────

pub use skeleton::{
    // Core types
    JointTransform,
    JointDef,
    JointType,
    AxisLimit,
    SkeletonError,
    // Hierarchy
    SkeletonHierarchy,
    // Runtime
    SkeletonState,
    SkeletalAnimator,
    AnimationLayer,
    // Motion capture
    MotionCaptureProcessor,
    ProcessedFrame,
    FrameJointMeta,
    // Corrective drivers
    ClavicleDriver,
    // Naming
    JointNameAlias,
    // Metrics
    PerformanceMetrics,
};

// ── Bridge protocol types ─────────────────────────────────────────────────────
// These types mirror the Python bridge.py payload format exactly.
// Python sends: {"avatar_id": str, "motion_data": {bone: {position, rotation}}, "timestamp": f64}

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A single bone's data as received from the Python VoxelBridge MOTION_UPDATE command.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeBoneData {
    pub position:   [f32; 3],
    pub rotation:   [f32; 4],   // [qx, qy, qz, qw]
    pub mesh:       Option<String>,
    pub shape_type: Option<String>,
    pub confidence: Option<f32>,
}

/// Top-level payload of a MOTION_UPDATE bridge command.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeMotionPayload {
    pub avatar_id:   String,
    pub motion_data: HashMap<String, BridgeBoneData>,
    pub timestamp:   f64,
}

impl BridgeMotionPayload {
    /// Convert bridge payload to the flat HashMap<String, Vec<f32>> format
    /// that SkeletalAnimator::apply_motion_capture_frame expects.
    /// Output format per joint: [px, py, pz, qx, qy, qz, qw]
    /// Joint names are passed through JointNameAlias::resolve_or_original so
    /// data arriving with old Python names is silently remapped to canonical.
    pub fn to_mocap_frame(&self) -> HashMap<String, Vec<f32>> {
        self.motion_data
            .iter()
            .map(|(raw_name, bd)| {
                let canonical = JointNameAlias::resolve_or_original(raw_name);
                let data = vec![
                    bd.position[0], bd.position[1], bd.position[2],
                    bd.rotation[0], bd.rotation[1], bd.rotation[2], bd.rotation[3],
                ];
                (canonical, data)
            })
            .collect()
    }
}

// ── Procedural idle system ────────────────────────────────────────────────────

/// Generates a minimal idle-breathing pose when no live mocap data is present.
/// `t` — elapsed seconds. `phase_offset` — per-avatar desync offset (radians).
/// Returns a sparse pose map suitable for SkeletonState::blend_towards.
pub fn procedural_idle_pose(
    t: f32,
    phase_offset: f32,
) -> HashMap<String, JointTransform> {
    use nalgebra::{Point3, UnitQuaternion, Vector3};

    let mut pose = HashMap::new();

    // Breathing rate: ~12 breaths/min = 0.2 Hz = 1.257 rad/s
    let breath_freq = 1.257_f32;
    let breath      = (t * breath_freq + phase_offset).sin();

    // Spine_01: subtle forward/backward sway (±2° = 0.035 rad)
    let spine_pitch = breath * 0.035_f32;
    pose.insert(
        "Spine_01".to_string(),
        JointTransform::new(
            Point3::origin(),
            UnitQuaternion::from_euler_angles(spine_pitch, 0.0, 0.0),
            Vector3::new(1.0, 1.0, 1.0),
        ),
    );

    // Head: opposite phase (head rises as chest expands, ±1.5°)
    let head_pitch = -breath * 0.026_f32;
    pose.insert(
        "Head".to_string(),
        JointTransform::new(
            Point3::origin(),
            UnitQuaternion::from_euler_angles(head_pitch, 0.0, 0.0),
            Vector3::new(1.0, 1.0, 1.0),
        ),
    );

    // Slow weight-shift side sway on Pelvis (period ~7s, ±1°)
    let sway_freq  = 0.9_f32;
    let sway_angle = (t * sway_freq + phase_offset * 1.7).sin() * 0.017_f32;
    pose.insert(
        "Pelvis".to_string(),
        JointTransform::new(
            Point3::origin(),
            UnitQuaternion::from_euler_angles(0.0, 0.0, sway_angle),
            Vector3::new(1.0, 1.0, 1.0),
        ),
    );

    pose
}

// ── Backward-compat shim ──────────────────────────────────────────────────────

impl SkeletonHierarchy {
    /// Alias for create_pubcast_rig() — keeps any code referencing the old
    /// function name working without changes.
    pub fn create_standard_humanoid() -> Self {
        Self::create_pubcast_rig()
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;

    #[test]
    fn test_bridge_payload_round_trip() {
        let mut motion = HashMap::new();
        motion.insert("Thigh_L".to_string(), BridgeBoneData {
            position:   [0.0, 0.5, 0.0],
            rotation:   [0.0, 0.0, 0.0, 1.0],
            mesh:       None,
            shape_type: None,
            confidence: Some(0.95),
        });
        let payload = BridgeMotionPayload {
            avatar_id:   "blockhead_01".to_string(),
            motion_data: motion,
            timestamp:   1234567890.0,
        };

        let frame = payload.to_mocap_frame();
        assert!(frame.contains_key("Thigh_L"));
        let data = &frame["Thigh_L"];
        assert_eq!(data.len(), 7);
        assert!((data[1] - 0.5).abs() < 1e-5);
    }

    #[test]
    fn test_bridge_payload_aliases_old_names() {
        let mut motion = HashMap::new();
        motion.insert("left_forearm".to_string(), BridgeBoneData {
            position:   [1.0, 0.0, 0.0],
            rotation:   [0.0, 0.0, 0.0, 1.0],
            mesh:       None,
            shape_type: None,
            confidence: None,
        });
        let payload = BridgeMotionPayload {
            avatar_id:   "test".to_string(),
            motion_data: motion,
            timestamp:   0.0,
        };

        let frame = payload.to_mocap_frame();
        assert!(frame.contains_key("LowerArm_L"),
            "Old name 'left_forearm' must alias to 'LowerArm_L'");
        assert!(!frame.contains_key("left_forearm"));
    }

    #[test]
    fn test_procedural_idle_is_finite() {
        let pose = procedural_idle_pose(1.5, 0.3);
        for (name, xf) in &pose {
            assert!(xf.is_finite(), "Idle pose joint '{}' has non-finite transform", name);
        }
        assert!(pose.contains_key("Spine_01"));
        assert!(pose.contains_key("Head"));
        assert!(pose.contains_key("Pelvis"));
    }

    #[test]
    fn test_create_standard_humanoid_alias() {
        let a = SkeletonHierarchy::create_standard_humanoid();
        let b = SkeletonHierarchy::create_pubcast_rig();
        assert_eq!(a.joints.len(), b.joints.len());
    }
}
