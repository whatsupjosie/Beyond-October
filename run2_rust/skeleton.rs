/*!
Skeletal Animation System for PubCast AI Renderer

High-performance skeletal animation and deformation system with support for:
- Real-time bone transformations
- Multiple skeleton rigs
- Motion capture data integration
- SIMD-optimized matrix operations
*/

use nalgebra::{Matrix4, Point3, Quaternion, UnitQuaternion, Vector3};
use std::collections::HashMap;
use std::time::Instant;

/// Transform data for a single joint
#[derive(Debug, Clone, Copy)]
pub struct JointTransform {
    pub position: Point3<f32>,
    pub rotation: UnitQuaternion<f32>,
    pub scale: Vector3<f32>,
}

impl Default for JointTransform {
    fn default() -> Self {
        Self {
            position: Point3::origin(),
            rotation: UnitQuaternion::identity(),
            scale: Vector3::new(1.0, 1.0, 1.0),
        }
    }
}

impl JointTransform {
    /// Create a new joint transform
    pub fn new(position: Point3<f32>, rotation: UnitQuaternion<f32>, scale: Vector3<f32>) -> Self {
        Self {
            position,
            rotation,
            scale,
        }
    }
    
    /// Convert to 4x4 transformation matrix
    pub fn to_matrix(&self) -> Matrix4<f32> {
        let translation = Matrix4::new_translation(&self.position.coords);
        let rotation_matrix = self.rotation.to_homogeneous();
        let scale_matrix = Matrix4::new_nonuniform_scaling(&self.scale);
        
        translation * rotation_matrix * scale_matrix
    }
    
    /// Interpolate between two transforms (SLERP for rotation, linear for position/scale)
    pub fn interpolate(&self, other: &JointTransform, t: f32) -> JointTransform {
        let t = t.clamp(0.0, 1.0);
        
        JointTransform {
            position: self.position.coords.lerp(&other.position.coords, t).into(),
            rotation: self.rotation.slerp(&other.rotation, t),
            scale: self.scale.lerp(&other.scale, t),
        }
    }
}

/// Represents the hierarchical structure of bones in a skeleton
#[derive(Debug, Clone)]
pub struct SkeletonHierarchy {
    pub joint_names: Vec<String>,
    pub parent_indices: Vec<Option<usize>>,
    pub rest_pose: Vec<JointTransform>,
}

impl SkeletonHierarchy {
    pub fn new() -> Self {
        Self {
            joint_names: Vec::new(),
            parent_indices: Vec::new(),
            rest_pose: Vec::new(),
        }
    }
    
    pub fn add_joint(&mut self, name: String, parent_index: Option<usize>, rest_transform: JointTransform) -> usize {
        let index = self.joint_names.len();
        self.joint_names.push(name);
        self.parent_indices.push(parent_index);
        self.rest_pose.push(rest_transform);
        index
    }
    
    pub fn find_joint(&self, name: &str) -> Option<usize> {
        self.joint_names.iter().position(|n| n == name)
    }
    
    /// Create standard humanoid skeleton hierarchy
    pub fn create_standard_humanoid() -> Self {
        let mut skeleton = Self::new();
        
        // Root joint (hips)
        let hips_idx = skeleton.add_joint("hips".to_string(), None, JointTransform::default());
        
        // Spine chain
        let spine_idx = skeleton.add_joint("spine".to_string(), Some(hips_idx), 
            JointTransform::new(Point3::new(0.0, 0.1, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let spine1_idx = skeleton.add_joint("spine1".to_string(), Some(spine_idx),
            JointTransform::new(Point3::new(0.0, 0.1, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let spine2_idx = skeleton.add_joint("spine2".to_string(), Some(spine1_idx),
            JointTransform::new(Point3::new(0.0, 0.1, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let neck_idx = skeleton.add_joint("neck".to_string(), Some(spine2_idx),
            JointTransform::new(Point3::new(0.0, 0.08, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let _head_idx = skeleton.add_joint("head".to_string(), Some(neck_idx),
            JointTransform::new(Point3::new(0.0, 0.08, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        
        // Left arm
        let left_shoulder_idx = skeleton.add_joint("left_shoulder".to_string(), Some(spine2_idx),
            JointTransform::new(Point3::new(0.05, 0.05, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let left_upper_arm_idx = skeleton.add_joint("left_upper_arm".to_string(), Some(left_shoulder_idx),
            JointTransform::new(Point3::new(0.15, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let left_forearm_idx = skeleton.add_joint("left_forearm".to_string(), Some(left_upper_arm_idx),
            JointTransform::new(Point3::new(0.12, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let _left_hand_idx = skeleton.add_joint("left_hand".to_string(), Some(left_forearm_idx),
            JointTransform::new(Point3::new(0.08, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        
        // Right arm
        let right_shoulder_idx = skeleton.add_joint("right_shoulder".to_string(), Some(spine2_idx),
            JointTransform::new(Point3::new(-0.05, 0.05, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let right_upper_arm_idx = skeleton.add_joint("right_upper_arm".to_string(), Some(right_shoulder_idx),
            JointTransform::new(Point3::new(-0.15, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let right_forearm_idx = skeleton.add_joint("right_forearm".to_string(), Some(right_upper_arm_idx),
            JointTransform::new(Point3::new(-0.12, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let _right_hand_idx = skeleton.add_joint("right_hand".to_string(), Some(right_forearm_idx),
            JointTransform::new(Point3::new(-0.08, 0.0, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        
        // Left leg
        let left_upper_leg_idx = skeleton.add_joint("left_upper_leg".to_string(), Some(hips_idx),
            JointTransform::new(Point3::new(0.05, -0.05, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let left_lower_leg_idx = skeleton.add_joint("left_lower_leg".to_string(), Some(left_upper_leg_idx),
            JointTransform::new(Point3::new(0.0, -0.2, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let left_foot_idx = skeleton.add_joint("left_foot".to_string(), Some(left_lower_leg_idx),
            JointTransform::new(Point3::new(0.0, -0.18, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let _left_toe_idx = skeleton.add_joint("left_toe".to_string(), Some(left_foot_idx),
            JointTransform::new(Point3::new(0.0, 0.0, 0.06), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        
        // Right leg
        let right_upper_leg_idx = skeleton.add_joint("right_upper_leg".to_string(), Some(hips_idx),
            JointTransform::new(Point3::new(-0.05, -0.05, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let right_lower_leg_idx = skeleton.add_joint("right_lower_leg".to_string(), Some(right_upper_leg_idx),
            JointTransform::new(Point3::new(0.0, -0.2, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let right_foot_idx = skeleton.add_joint("right_foot".to_string(), Some(right_lower_leg_idx),
            JointTransform::new(Point3::new(0.0, -0.18, 0.0), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        let _right_toe_idx = skeleton.add_joint("right_toe".to_string(), Some(right_foot_idx),
            JointTransform::new(Point3::new(0.0, 0.0, 0.06), UnitQuaternion::identity(), Vector3::new(1.0, 1.0, 1.0)));
        
        skeleton
    }
}

/// Current pose/state of a skeleton
#[derive(Debug, Clone)]
pub struct SkeletonState {
    pub joint_transforms: HashMap<String, JointTransform>,
    pub last_updated: Instant,
}

impl SkeletonState {
    pub fn new(joint_transforms: HashMap<String, JointTransform>) -> Self {
        Self {
            joint_transforms,
            last_updated: Instant::now(),
        }
    }
    
    pub fn from_rest_pose(hierarchy: &SkeletonHierarchy) -> Self {
        let mut joint_transforms = HashMap::new();
        
        for (i, transform) in hierarchy.rest_pose.iter().enumerate() {
            if let Some(name) = hierarchy.joint_names.get(i) {
                joint_transforms.insert(name.clone(), *transform);
            }
        }
        
        Self::new(joint_transforms)
    }
    
    pub fn update_joint(&mut self, joint_name: &str, transform: JointTransform) {
        self.joint_transforms.insert(joint_name.to_string(), transform);
        self.last_updated = Instant::now();
    }
    
    pub fn get_joint(&self, joint_name: &str) -> Option<&JointTransform> {
        self.joint_transforms.get(joint_name)
    }
    
    /// Interpolate towards target pose
    pub fn blend_towards(&mut self, target: &SkeletonState, blend_factor: f32) {
        let blend_factor = blend_factor.clamp(0.0, 1.0);
        
        for (joint_name, current_transform) in &mut self.joint_transforms {
            if let Some(target_transform) = target.joint_transforms.get(joint_name) {
                *current_transform = current_transform.interpolate(target_transform, blend_factor);
            }
        }
        
        self.last_updated = Instant::now();
    }
}

/// Skeletal animation system
pub struct SkeletalAnimator {
    pub hierarchy: SkeletonHierarchy,
    pub current_pose: SkeletonState,
    pub target_pose: Option<SkeletonState>,
    pub blend_speed: f32, // Blending speed for pose transitions
    
    // Performance optimization
    cached_matrices: Vec<Matrix4<f32>>,
    matrices_dirty: bool,
}

impl SkeletalAnimator {
    pub fn new(hierarchy: SkeletonHierarchy) -> Self {
        let current_pose = SkeletonState::from_rest_pose(&hierarchy);
        let cached_matrices = vec![Matrix4::identity(); hierarchy.joint_names.len()];
        
        Self {
            hierarchy,
            current_pose,
            target_pose: None,
            blend_speed: 5.0, // 5 units per second
            cached_matrices,
            matrices_dirty: true,
        }
    }
    
    /// Update animation state
    pub fn update(&mut self, delta_time: f32) {
        if let Some(ref target_pose) = self.target_pose {
            let blend_amount = (self.blend_speed * delta_time).min(1.0);
            self.current_pose.blend_towards(target_pose, blend_amount);
            self.matrices_dirty = true;
            
            // Remove target pose when blend is complete
            if blend_amount >= 1.0 {
                self.target_pose = None;
            }
        }
    }
    
    /// Set new target pose for blending
    pub fn set_target_pose(&mut self, pose: SkeletonState) {
        self.target_pose = Some(pose);
        self.matrices_dirty = true;
    }
    
    /// Immediately set current pose (no blending)
    pub fn set_pose_immediate(&mut self, pose: SkeletonState) {
        self.current_pose = pose;
        self.target_pose = None;
        self.matrices_dirty = true;
    }
    
    /// Get world-space transformation matrices for all joints
    pub fn get_world_matrices(&mut self) -> &[Matrix4<f32>] {
        if self.matrices_dirty {
            self.update_world_matrices();
            self.matrices_dirty = false;
        }
        &self.cached_matrices
    }
    
    /// Update world-space matrices from current pose
    fn update_world_matrices(&mut self) {
        // Clear matrices
        for matrix in &mut self.cached_matrices {
            *matrix = Matrix4::identity();
        }
        
        // Compute world matrices in hierarchical order
        for (joint_index, joint_name) in self.hierarchy.joint_names.iter().enumerate() {
            let local_transform = self.current_pose.joint_transforms
                .get(joint_name)
                .unwrap_or(&self.hierarchy.rest_pose[joint_index]);
            
            let local_matrix = local_transform.to_matrix();
            
            // Apply parent transformation if exists
            if let Some(parent_index) = self.hierarchy.parent_indices[joint_index] {
                self.cached_matrices[joint_index] = self.cached_matrices[parent_index] * local_matrix;
            } else {
                self.cached_matrices[joint_index] = local_matrix;
            }
        }
    }
    
    /// Apply motion capture data
    pub fn apply_motion_capture_frame(&mut self, joint_data: &HashMap<String, Vec<f32>>) {
        let mut new_transforms = HashMap::new();
        
        for (joint_name, data) in joint_data {
            if data.len() >= 7 { // position (3) + quaternion (4)
                let position = Point3::new(data[0], data[1], data[2]);
                let rotation = UnitQuaternion::from_quaternion(Quaternion::new(
                    data[6], // w
                    data[3], // x
                    data[4], // y
                    data[5], // z
                ));
                
                let scale = if data.len() >= 10 {
                    Vector3::new(data[7], data[8], data[9])
                } else {
                    Vector3::new(1.0, 1.0, 1.0)
                };
                
                new_transforms.insert(joint_name.clone(), JointTransform::new(position, rotation, scale));
            }
        }
        
        if !new_transforms.is_empty() {
            let new_pose = SkeletonState::new(new_transforms);
            self.set_target_pose(new_pose);
        }
    }
    
    /// Get joint world position
    pub fn get_joint_world_position(&mut self, joint_name: &str) -> Option<Point3<f32>> {
        let joint_index = self.hierarchy.find_joint(joint_name)?;
        let matrices = self.get_world_matrices();
        
        if joint_index < matrices.len() {
            let matrix = &matrices[joint_index];
            Some(Point3::new(matrix.m14, matrix.m24, matrix.m34))
        } else {
            None
        }
    }
}

/// Motion capture data processor for real-time skeletal animation
pub struct MotionCaptureProcessor {
    smoothing_factor: f32,
    previous_frame: Option<HashMap<String, JointTransform>>,
    velocity_buffer: HashMap<String, Vector3<f32>>,
}

impl MotionCaptureProcessor {
    pub fn new(smoothing_factor: f32) -> Self {
        Self {
            smoothing_factor: smoothing_factor.clamp(0.0, 1.0),
            previous_frame: None,
            velocity_buffer: HashMap::new(),
        }
    }
    
    /// Process raw motion capture data with smoothing and filtering
    pub fn process_frame(&mut self, raw_data: &HashMap<String, Vec<f32>>) -> HashMap<String, JointTransform> {
        let mut processed_transforms = HashMap::new();
        
        for (joint_name, data) in raw_data {
            if data.len() >= 7 {
                let mut position = Point3::new(data[0], data[1], data[2]);
                let rotation = UnitQuaternion::from_quaternion(Quaternion::new(
                    data[6], data[3], data[4], data[5]
                ));
                
                // Apply smoothing if we have previous data
                if let Some(ref prev_frame) = self.previous_frame {
                    if let Some(prev_transform) = prev_frame.get(joint_name) {
                        // Smooth position using exponential moving average
                        let prev_pos = prev_transform.position;
                        position = Point3::new(
                            prev_pos.x + self.smoothing_factor * (position.x - prev_pos.x),
                            prev_pos.y + self.smoothing_factor * (position.y - prev_pos.y),
                            prev_pos.z + self.smoothing_factor * (position.z - prev_pos.z),
                        );
                    }
                }
                
                let transform = JointTransform::new(position, rotation, Vector3::new(1.0, 1.0, 1.0));
                processed_transforms.insert(joint_name.clone(), transform);
            }
        }
        
        // Store for next frame
        self.previous_frame = Some(processed_transforms.clone());
        
        processed_transforms
    }
    
    /// Detect and filter out obvious tracking errors
    pub fn filter_tracking_errors(&mut self, transforms: &mut HashMap<String, JointTransform>) {
        // Remove transforms with extremely high velocities (likely tracking errors)
        let max_velocity = 10.0; // meters per frame (very high)
        
        let mut to_remove = Vec::new();
        
        for (joint_name, transform) in transforms.iter() {
            if let Some(velocity) = self.velocity_buffer.get(joint_name) {
                if velocity.magnitude() > max_velocity {
                    tracing::warn!("Filtering tracking error for joint {}: velocity {}", 
                                 joint_name, velocity.magnitude());
                    to_remove.push(joint_name.clone());
                }
            }
            
            // Update velocity for next frame
            if let Some(ref prev_frame) = self.previous_frame {
                if let Some(prev_transform) = prev_frame.get(joint_name) {
                    let velocity = transform.position - prev_transform.position;
                    self.velocity_buffer.insert(joint_name.clone(), velocity.coords);
                }
            }
        }
        
        // Remove problematic transforms
        for joint_name in to_remove {
            transforms.remove(&joint_name);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_joint_transform_interpolation() {
        let transform1 = JointTransform::new(
            Point3::new(0.0, 0.0, 0.0),
            UnitQuaternion::identity(),
            Vector3::new(1.0, 1.0, 1.0)
        );
        
        let transform2 = JointTransform::new(
            Point3::new(1.0, 1.0, 1.0),
            UnitQuaternion::from_euler_angles(0.0, std::f32::consts::PI / 2.0, 0.0),
            Vector3::new(2.0, 2.0, 2.0)
        );
        
        let interpolated = transform1.interpolate(&transform2, 0.5);
        
        assert_eq!(interpolated.position, Point3::new(0.5, 0.5, 0.5));
        assert_eq!(interpolated.scale, Vector3::new(1.5, 1.5, 1.5));
    }
    
    #[test]
    fn test_skeleton_hierarchy_creation() {
        let skeleton = SkeletonHierarchy::create_standard_humanoid();
        
        assert!(skeleton.find_joint("hips").is_some());
        assert!(skeleton.find_joint("left_upper_arm").is_some());
        assert!(skeleton.find_joint("right_foot").is_some());
        
        // Test hierarchy relationships
        let spine_idx = skeleton.find_joint("spine").unwrap();
        let hips_idx = skeleton.find_joint("hips").unwrap();
        assert_eq!(skeleton.parent_indices[spine_idx], Some(hips_idx));
    }
    
    #[test]
    fn test_skeletal_animator() {
        let hierarchy = SkeletonHierarchy::create_standard_humanoid();
        let mut animator = SkeletalAnimator::new(hierarchy);
        
        // Test setting a new pose
        let mut new_pose = SkeletonState::new(HashMap::new());
        new_pose.update_joint("hips", JointTransform::new(
            Point3::new(0.0, 1.0, 0.0),
            UnitQuaternion::identity(),
            Vector3::new(1.0, 1.0, 1.0)
        ));
        
        animator.set_target_pose(new_pose);
        
        // Simulate animation update
        animator.update(1.0); // 1 second
        
        let world_matrices = animator.get_world_matrices();
        assert!(!world_matrices.is_empty());
    }
}
