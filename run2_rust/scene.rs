/*!
Scene Management System for PubCast AI Renderer

Manages 3D scenes, avatars, objects, and their relationships in the virtual world.
Handles scene updates, culling, and coordination with the rendering pipeline.
*/

use nalgebra::{Point3, Vector3, Matrix4};
use std::collections::HashMap;
use std::time::Instant;

use crate::skeleton::{SkeletonState, SkeletalAnimator, SkeletonHierarchy};

/// Unique identifier for scene objects
pub type ObjectId = String;
pub type AvatarId = String;

/// 3D transformation data
#[derive(Debug, Clone, Copy)]
pub struct Transform {
    pub position: Point3<f32>,
    pub rotation: Vector3<f32>, // Euler angles in radians
    pub scale: Vector3<f32>,
}

impl Default for Transform {
    fn default() -> Self {
        Self {
            position: Point3::origin(),
            rotation: Vector3::zeros(),
            scale: Vector3::new(1.0, 1.0, 1.0),
        }
    }
}

impl Transform {
    pub fn new(position: Point3<f32>, rotation: Vector3<f32>, scale: Vector3<f32>) -> Self {
        Self { position, rotation, scale }
    }
    
    /// Convert to 4x4 transformation matrix
    pub fn to_matrix(&self) -> Matrix4<f32> {
        let translation = Matrix4::new_translation(&self.position.coords);
        
        // Create rotation matrix from Euler angles (ZYX order)
        let rotation_x = Matrix4::from_euler_angles(self.rotation.x, 0.0, 0.0);
        let rotation_y = Matrix4::from_euler_angles(0.0, self.rotation.y, 0.0);
        let rotation_z = Matrix4::from_euler_angles(0.0, 0.0, self.rotation.z);
        let rotation = rotation_z * rotation_y * rotation_x;
        
        let scale = Matrix4::new_nonuniform_scaling(&self.scale);
        
        translation * rotation * scale
    }
    
    /// Interpolate between two transforms
    pub fn interpolate(&self, other: &Transform, t: f32) -> Transform {
        let t = t.clamp(0.0, 1.0);
        
        Transform {
            position: Point3::from(self.position.coords.lerp(&other.position.coords, t)),
            rotation: self.rotation.lerp(&other.rotation, t),
            scale: self.scale.lerp(&other.scale, t),
        }
    }
}

/// Different types of scene objects
#[derive(Debug, Clone)]
pub enum ObjectType {
    StaticMesh { mesh_id: String, material_id: String },
    VoxelChunk { chunk_data: Vec<u8> },
    Light { light_type: LightType },
    ParticleSystem { effect_id: String },
    Audio { source_id: String },
}

/// Types of lights in the scene
#[derive(Debug, Clone)]
pub enum LightType {
    Directional { direction: Vector3<f32>, intensity: f32, color: Vector3<f32> },
    Point { intensity: f32, color: Vector3<f32>, radius: f32 },
    Spot { direction: Vector3<f32>, intensity: f32, color: Vector3<f32>, cone_angle: f32 },
}

/// A generic scene object
#[derive(Debug, Clone)]
pub struct SceneObject {
    pub id: ObjectId,
    pub name: String,
    pub transform: Transform,
    pub object_type: ObjectType,
    pub visible: bool,
    pub static_object: bool, // Objects that don't move often
    pub last_updated: Instant,
}

impl SceneObject {
    pub fn new(id: ObjectId, name: String, object_type: ObjectType) -> Self {
        Self {
            id,
            name,
            transform: Transform::default(),
            object_type,
            visible: true,
            static_object: false,
            last_updated: Instant::now(),
        }
    }
    
    /// Update object transform
    pub fn set_transform(&mut self, transform: Transform) {
        self.transform = transform;
        self.last_updated = Instant::now();
    }
    
    /// Move object by delta
    pub fn translate(&mut self, delta: Vector3<f32>) {
        self.transform.position += delta;
        self.last_updated = Instant::now();
    }
    
    /// Rotate object by delta (in radians)
    pub fn rotate(&mut self, delta: Vector3<f32>) {
        self.transform.rotation += delta;
        self.last_updated = Instant::now();
    }
    
    /// Get world transformation matrix
    pub fn world_matrix(&self) -> Matrix4<f32> {
        self.transform.to_matrix()
    }
}

/// Avatar in the scene with skeletal animation
#[derive(Debug)]
pub struct Avatar {
    pub id: AvatarId,
    pub name: String,
    pub transform: Transform,
    pub animator: SkeletalAnimator,
    pub visible: bool,
    pub animation_state: String, // Current animation: "idle", "walk", "dance", etc.
    
    // Avatar-specific properties
    pub facial_blendshapes: HashMap<String, f32>,
    pub outfit_id: Option<String>,
    pub user_controlled: bool,
    pub ai_controlled: bool,
    pub last_updated: Instant,
}

impl Avatar {
    pub fn new(id: AvatarId, name: String, skeleton: SkeletonHierarchy) -> Self {
        Self {
            id,
            name,
            transform: Transform::default(),
            animator: SkeletalAnimator::new(skeleton),
            visible: true,
            animation_state: "idle".to_string(),
            facial_blendshapes: HashMap::new(),
            outfit_id: None,
            user_controlled: false,
            ai_controlled: false,
            last_updated: Instant::now(),
        }
    }
    
    /// Update avatar animation
    pub fn update(&mut self, delta_time: f32) {
        self.animator.update(delta_time);
        self.last_updated = Instant::now();
    }
    
    /// Set animation target
    pub fn set_animation_target(&mut self, skeleton_state: SkeletonState) {
        self.animator.set_target_pose(skeleton_state);
        self.last_updated = Instant::now();
    }
    
    /// Apply motion capture data
    pub fn apply_motion_capture(&mut self, joint_data: &HashMap<String, Vec<f32>>) {
        self.animator.apply_motion_capture_frame(joint_data);
        self.last_updated = Instant::now();
    }
    
    /// Update facial blendshapes (for facial animation)
    pub fn update_facial_blendshapes(&mut self, blendshapes: HashMap<String, f32>) {
        self.facial_blendshapes = blendshapes;
        self.last_updated = Instant::now();
    }
    
    /// Get world position
    pub fn world_position(&self) -> Point3<f32> {
        self.transform.position
    }
    
    /// Get joint world position
    pub fn get_joint_world_position(&mut self, joint_name: &str) -> Option<Point3<f32>> {
        if let Some(local_pos) = self.animator.get_joint_world_position(joint_name) {
            // Transform to world space
            let world_matrix = self.transform.to_matrix();
            let world_point = world_matrix.transform_point(&local_pos);
            Some(world_point)
        } else {
            None
        }
    }
}

/// Environment settings for the scene
#[derive(Debug, Clone)]
pub struct Environment {
    pub ambient_light: Vector3<f32>,
    pub sky_color: Vector3<f32>,
    pub fog_density: f32,
    pub fog_color: Vector3<f32>,
    pub time_of_day: f32, // 0.0 = midnight, 0.5 = noon, 1.0 = midnight
}

impl Default for Environment {
    fn default() -> Self {
        Self {
            ambient_light: Vector3::new(0.3, 0.3, 0.3),
            sky_color: Vector3::new(0.5, 0.7, 1.0),
            fog_density: 0.01,
            fog_color: Vector3::new(0.7, 0.8, 0.9),
            time_of_day: 0.5, // Default to noon
        }
    }
}

/// Complete 3D scene containing all objects, avatars, and environment
pub struct Scene {
    pub name: String,
    pub objects: HashMap<ObjectId, SceneObject>,
    pub avatars: HashMap<AvatarId, Avatar>,
    pub environment: Environment,
    
    // Scene hierarchy and spatial organization
    object_update_queue: Vec<ObjectId>,
    avatar_update_queue: Vec<AvatarId>,
    
    // Performance tracking
    pub last_full_update: Instant,
    pub update_count: u64,
}

impl Scene {
    pub fn new(name: String) -> Self {
        Self {
            name,
            objects: HashMap::new(),
            avatars: HashMap::new(),
            environment: Environment::default(),
            object_update_queue: Vec::new(),
            avatar_update_queue: Vec::new(),
            last_full_update: Instant::now(),
            update_count: 0,
        }
    }
    
    /// Add object to scene
    pub fn add_object(&mut self, object: SceneObject) {
        let id = object.id.clone();
        self.objects.insert(id.clone(), object);
        self.object_update_queue.push(id);
    }
    
    /// Remove object from scene
    pub fn remove_object(&mut self, object_id: &str) -> bool {
        let removed = self.objects.remove(object_id).is_some();
        if removed {
            self.object_update_queue.retain(|id| id != object_id);
        }
        removed
    }
    
    /// Add avatar to scene
    pub fn add_avatar(&mut self, avatar: Avatar) {
        let id = avatar.id.clone();
        self.avatars.insert(id.clone(), avatar);
        self.avatar_update_queue.push(id);
    }
    
    /// Remove avatar from scene
    pub fn remove_avatar(&mut self, avatar_id: &str) -> bool {
        let removed = self.avatars.remove(avatar_id).is_some();
        if removed {
            self.avatar_update_queue.retain(|id| id != avatar_id);
        }
        removed
    }
    
    /// Get mutable reference to avatar
    pub fn get_avatar_mut(&mut self, avatar_id: &str) -> Option<&mut Avatar> {
        self.avatars.get_mut(avatar_id)
    }
    
    /// Get reference to avatar
    pub fn get_avatar(&self, avatar_id: &str) -> Option<&Avatar> {
        self.avatars.get(avatar_id)
    }
    
    /// Update entire scene
    pub fn update(&mut self, delta_time: f32) {
        self.update_count += 1;
        
        // Update all avatars
        for avatar in self.avatars.values_mut() {
            avatar.update(delta_time);
        }
        
        // Update objects that need updates (typically non-static ones)
        for object_id in &self.object_update_queue {
            if let Some(object) = self.objects.get_mut(object_id) {
                if !object.static_object {
                    // Update dynamic objects here if needed
                    object.last_updated = Instant::now();
                }
            }
        }
        
        // Update environment (time of day, lighting changes, etc.)
        self.update_environment(delta_time);
        
        self.last_full_update = Instant::now();
    }
    
    /// Update environmental effects
    fn update_environment(&mut self, delta_time: f32) {
        // Simple time of day progression (very slow)
        self.environment.time_of_day += delta_time * 0.001; // 1000 seconds = full day
        if self.environment.time_of_day > 1.0 {
            self.environment.time_of_day -= 1.0;
        }
        
        // Update ambient light based on time of day
        let daylight_strength = (self.environment.time_of_day * std::f32::consts::TAU).sin().max(0.1);
        self.environment.ambient_light = Vector3::new(
            0.2 + 0.3 * daylight_strength,
            0.2 + 0.3 * daylight_strength,
            0.2 + 0.2 * daylight_strength,
        );
    }
    
    /// Create default test scene
    pub fn create_test_scene() -> Self {
        let mut scene = Self::new("Test Scene".to_string());
        
        // Add ground plane
        let ground = SceneObject::new(
            "ground".to_string(),
            "Ground Plane".to_string(),
            ObjectType::StaticMesh {
                mesh_id: "plane".to_string(),
                material_id: "ground_material".to_string(),
            }
        );
        scene.add_object(ground);
        
        // Add directional light (sun)
        let mut sun = SceneObject::new(
            "sun".to_string(),
            "Sun Light".to_string(),
            ObjectType::Light {
                light_type: LightType::Directional {
                    direction: Vector3::new(-0.3, -1.0, -0.5).normalize(),
                    intensity: 3.0,
                    color: Vector3::new(1.0, 0.95, 0.8),
                }
            }
        );
        sun.static_object = true;
        scene.add_object(sun);
        
        // Add point light
        let mut point_light = SceneObject::new(
            "lamp".to_string(),
            "Room Lamp".to_string(),
            ObjectType::Light {
                light_type: LightType::Point {
                    intensity: 2.0,
                    color: Vector3::new(1.0, 0.9, 0.7),
                    radius: 10.0,
                }
            }
        );
        point_light.transform = Transform::new(
            Point3::new(0.0, 3.0, 0.0),
            Vector3::zeros(),
            Vector3::new(1.0, 1.0, 1.0)
        );
        scene.add_object(point_light);
        
        scene
    }
    
    /// Get visible objects (for rendering)
    pub fn get_visible_objects(&self) -> Vec<&SceneObject> {
        self.objects.values().filter(|obj| obj.visible).collect()
    }
    
    /// Get visible avatars (for rendering)
    pub fn get_visible_avatars(&self) -> Vec<&Avatar> {
        self.avatars.values().filter(|avatar| avatar.visible).collect()
    }
    
    /// Get all avatar positions (for camera following, etc.)
    pub fn get_avatar_positions(&self) -> HashMap<String, Point3<f32>> {
        self.avatars.iter()
            .map(|(id, avatar)| (id.clone(), avatar.world_position()))
            .collect()
    }
}

/// Manages multiple scenes and handles scene switching
pub struct SceneManager {
    scenes: HashMap<String, Scene>,
    active_scene_id: Option<String>,
    
    // Scene loading and unloading
    loading_queue: Vec<String>,
    
    // Performance metrics
    total_updates: u64,
    last_performance_check: Instant,
}

impl SceneManager {
    pub fn new() -> Self {
        Self {
            scenes: HashMap::new(),
            active_scene_id: None,
            loading_queue: Vec::new(),
            total_updates: 0,
            last_performance_check: Instant::now(),
        }
    }
    
    /// Add scene to manager
    pub fn add_scene(&mut self, scene: Scene) {
        let id = scene.name.clone();
        self.scenes.insert(id.clone(), scene);
        
        // Set as active if no active scene
        if self.active_scene_id.is_none() {
            self.active_scene_id = Some(id);
        }
    }
    
    /// Switch to different scene
    pub fn switch_to_scene(&mut self, scene_name: &str) -> bool {
        if self.scenes.contains_key(scene_name) {
            self.active_scene_id = Some(scene_name.to_string());
            true
        } else {
            false
        }
    }
    
    /// Get active scene
    pub fn get_active_scene(&self) -> Option<&Scene> {
        if let Some(ref id) = self.active_scene_id {
            self.scenes.get(id)
        } else {
            None
        }
    }
    
    /// Get mutable active scene
    pub fn get_active_scene_mut(&mut self) -> Option<&mut Scene> {
        if let Some(ref id) = self.active_scene_id {
            self.scenes.get_mut(id)
        } else {
            None
        }
    }
    
    /// Update active scene
    pub fn update(&mut self, delta_time: f32) {
        self.total_updates += 1;
        
        if let Some(scene) = self.get_active_scene_mut() {
            scene.update(delta_time);
        }
    }
    
    /// Update avatar skeleton in active scene
    pub fn update_avatar_skeleton(&mut self, avatar_id: &str, skeleton_state: SkeletonState) {
        if let Some(scene) = self.get_active_scene_mut() {
            if let Some(avatar) = scene.get_avatar_mut(avatar_id) {
                avatar.set_animation_target(skeleton_state);
            }
        }
    }
    
    /// Apply motion capture to avatar in active scene
    pub fn apply_motion_capture_to_avatar(&mut self, avatar_id: &str, 
                                         joint_data: &HashMap<String, Vec<f32>>) {
        if let Some(scene) = self.get_active_scene_mut() {
            if let Some(avatar) = scene.get_avatar_mut(avatar_id) {
                avatar.apply_motion_capture(joint_data);
            }
        }
    }
    
    /// Get avatar positions from active scene
    pub fn get_avatar_positions(&self) -> HashMap<String, Point3<f32>> {
        if let Some(scene) = self.get_active_scene() {
            scene.get_avatar_positions()
        } else {
            HashMap::new()
        }
    }
    
    /// Create default scene setup
    pub fn setup_default_scenes(&mut self) {
        // Create test scene
        let test_scene = Scene::create_test_scene();
        self.add_scene(test_scene);
        
        // Create studio scene
        let mut studio_scene = Scene::new("Studio".to_string());
        
        // Add default avatar with standard skeleton
        let skeleton = SkeletonHierarchy::create_standard_humanoid();
        let mut default_avatar = Avatar::new(
            "default_avatar".to_string(),
            "Default Avatar".to_string(),
            skeleton
        );
        default_avatar.transform = Transform::new(
            Point3::new(0.0, 0.0, 0.0),
            Vector3::zeros(),
            Vector3::new(1.0, 1.0, 1.0)
        );
        studio_scene.add_avatar(default_avatar);
        
        self.add_scene(studio_scene);
        self.switch_to_scene("Studio");
    }
    
    /// Get performance metrics
    pub fn get_performance_metrics(&self) -> HashMap<String, f64> {
        let mut metrics = HashMap::new();
        
        metrics.insert("total_scenes".to_string(), self.scenes.len() as f64);
        metrics.insert("total_updates".to_string(), self.total_updates as f64);
        
        if let Some(scene) = self.get_active_scene() {
            metrics.insert("objects_in_scene".to_string(), scene.objects.len() as f64);
            metrics.insert("avatars_in_scene".to_string(), scene.avatars.len() as f64);
            metrics.insert("scene_update_count".to_string(), scene.update_count as f64);
        }
        
        metrics
    }
    
    /// List all scenes
    pub fn list_scenes(&self) -> Vec<String> {
        self.scenes.keys().cloned().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transform_creation() {
        let transform = Transform::new(
            Point3::new(1.0, 2.0, 3.0),
            Vector3::new(0.0, 1.0, 0.0),
            Vector3::new(1.0, 1.0, 1.0)
        );
        
        assert_eq!(transform.position, Point3::new(1.0, 2.0, 3.0));
        assert_eq!(transform.rotation, Vector3::new(0.0, 1.0, 0.0));
    }
    
    #[test]
    fn test_scene_object_creation() {
        let object = SceneObject::new(
            "test_obj".to_string(),
            "Test Object".to_string(),
            ObjectType::StaticMesh {
                mesh_id: "cube".to_string(),
                material_id: "default".to_string(),
            }
        );
        
        assert_eq!(object.id, "test_obj");
        assert!(object.visible);
    }
    
    #[test]
    fn test_scene_management() {
        let mut scene = Scene::new("Test".to_string());
        
        let object = SceneObject::new(
            "obj1".to_string(),
            "Object 1".to_string(),
            ObjectType::StaticMesh {
                mesh_id: "cube".to_string(),
                material_id: "default".to_string(),
            }
        );
        
        scene.add_object(object);
        assert_eq!(scene.objects.len(), 1);
        
        assert!(scene.remove_object("obj1"));
        assert_eq!(scene.objects.len(), 0);
    }
    
    #[test]
    fn test_scene_manager() {
        let mut manager = SceneManager::new();
        let scene = Scene::new("Test Scene".to_string());
        
        manager.add_scene(scene);
        assert_eq!(manager.list_scenes().len(), 1);
        
        assert!(manager.switch_to_scene("Test Scene"));
        assert!(manager.get_active_scene().is_some());
    }
}
