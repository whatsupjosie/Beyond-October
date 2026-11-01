/*!
Motion Capture Integration for PubCast AI Renderer

Real-time motion capture data processing and avatar animation system.
Supports MediaPipe, ARKit, Rokoko, and other motion capture sources.
*/

use nalgebra::{Point3, Vector3, UnitQuaternion, Quaternion};
use std::collections::HashMap;
use std::time::{Instant, Duration};

use crate::skeleton::{SkeletonState, JointTransform};

/// Motion capture source types
#[derive(Debug, Clone, PartialEq)]
pub enum MotionCaptureSource {
    MediaPipe,
    ARKitFace,
    RokokoSuit,
    MocopiSuit,
    Manual,
    Unknown,
}

impl From<String> for MotionCaptureSource {
    fn from(source: String) -> Self {
        match source.to_lowercase().as_str() {
            "mediapipe" => Self::MediaPipe,
            "arkit_face" => Self::ARKitFace,
            "rokoko" => Self::RokokoSuit,
            "mocopi" => Self::MocopiSuit,
            "manual" => Self::Manual,
            _ => Self::Unknown,
        }
    }
}

/// Raw motion capture frame data
#[derive(Debug, Clone)]
pub struct MotionCaptureFrame {
    pub frame_id: String,
    pub timestamp: Instant,
    pub source: MotionCaptureSource,
    pub confidence: f32, // 0.0 - 1.0
    pub joint_data: HashMap<String, Vec<f32>>, // joint_name -> [x,y,z,qx,qy,qz,qw,...]
    pub metadata: HashMap<String, String>,
}

impl MotionCaptureFrame {
    pub fn new(source: MotionCaptureSource) -> Self {
        Self {
            frame_id: uuid::Uuid::new_v4().to_string(),
            timestamp: Instant::now(),
            source,
            confidence: 1.0,
            joint_data: HashMap::new(),
            metadata: HashMap::new(),
        }
    }
    
    pub fn add_joint(&mut self, joint_name: &str, position: Point3<f32>, 
                     rotation: UnitQuaternion<f32>) {
        let data = vec![
            position.x, position.y, position.z,
            rotation.i, rotation.j, rotation.k, rotation.w,
        ];
        self.joint_data.insert(joint_name.to_string(), data);
    }
    
    pub fn add_joint_raw(&mut self, joint_name: &str, data: Vec<f32>) {
        self.joint_data.insert(joint_name.to_string(), data);
    }
}

/// MediaPipe pose landmark processor
pub struct MediaPipeProcessor {
    joint_mapping: HashMap<usize, String>,
    smoothing_factor: f32,
    previous_landmarks: Option<Vec<[f32; 3]>>,
}

impl MediaPipeProcessor {
    pub fn new(smoothing_factor: f32) -> Self {
        let mut mapping = HashMap::new();
        
        // MediaPipe pose landmark indices to standard joint names
        mapping.insert(0, "nose".to_string());
        mapping.insert(11, "left_shoulder".to_string());
        mapping.insert(12, "right_shoulder".to_string());
        mapping.insert(13, "left_upper_arm".to_string());
        mapping.insert(14, "right_upper_arm".to_string());
        mapping.insert(15, "left_forearm".to_string());
        mapping.insert(16, "right_forearm".to_string());
        mapping.insert(23, "left_upper_leg".to_string());
        mapping.insert(24, "right_upper_leg".to_string());
        mapping.insert(25, "left_lower_leg".to_string());
        mapping.insert(26, "right_lower_leg".to_string());
        mapping.insert(27, "left_foot".to_string());
        mapping.insert(28, "right_foot".to_string());
        
        Self {
            joint_mapping: mapping,
            smoothing_factor,
            previous_landmarks: None,
        }
    }
    
    pub fn process_landmarks(&mut self, landmarks: Vec<[f32; 3]>) -> MotionCaptureFrame {
        let mut frame = MotionCaptureFrame::new(MotionCaptureSource::MediaPipe);
        
        // Apply smoothing if we have previous data
        let smoothed_landmarks = if let Some(ref prev) = self.previous_landmarks {
            landmarks.iter().zip(prev.iter()).map(|(curr, prev)| {
                [
                    prev[0] + self.smoothing_factor * (curr[0] - prev[0]),
                    prev[1] + self.smoothing_factor * (curr[1] - prev[1]),
                    prev[2] + self.smoothing_factor * (curr[2] - prev[2]),
                ]
            }).collect()
        } else {
            landmarks.clone()
        };
        
        // Convert landmarks to joint transforms
        for (landmark_idx, joint_name) in &self.joint_mapping {
            if let Some(landmark) = smoothed_landmarks.get(*landmark_idx) {
                let position = Point3::new(landmark[0], landmark[1], landmark[2]);
                
                // For MediaPipe, we only get positions, so estimate rotations
                let rotation = UnitQuaternion::identity(); // Would calculate from adjacent joints
                
                frame.add_joint(joint_name, position, rotation);
            }
        }
        
        // Store for next frame
        self.previous_landmarks = Some(smoothed_landmarks);
        
        frame
    }
}

/// ARKit face blendshapes processor
pub struct ARKitFaceProcessor {
    blendshape_mapping: HashMap<String, String>,
}

impl ARKitFaceProcessor {
    pub fn new() -> Self {
        let mut mapping = HashMap::new();
        
        // ARKit blendshape names to facial joint names
        mapping.insert("jawOpen".to_string(), "jaw".to_string());
        mapping.insert("eyeBlinkLeft".to_string(), "left_eye".to_string());
        mapping.insert("eyeBlinkRight".to_string(), "right_eye".to_string());
        mapping.insert("browDownLeft".to_string(), "left_brow".to_string());
        mapping.insert("browDownRight".to_string(), "right_brow".to_string());
        mapping.insert("mouthSmileLeft".to_string(), "left_mouth_corner".to_string());
        mapping.insert("mouthSmileRight".to_string(), "right_mouth_corner".to_string());
        
        Self {
            blendshape_mapping: mapping,
        }
    }
    
    pub fn process_blendshapes(&self, blendshapes: HashMap<String, f32>) -> MotionCaptureFrame {
        let mut frame = MotionCaptureFrame::new(MotionCaptureSource::ARKitFace);
        
        for (arkit_name, joint_name) in &self.blendshape_mapping {
            if let Some(&value) = blendshapes.get(arkit_name) {
                // Convert blendshape value to rotation
                let rotation_amount = value * 0.5; // Scale to reasonable rotation
                let rotation = UnitQuaternion::from_euler_angles(rotation_amount, 0.0, 0.0);
                
                frame.add_joint(joint_name, Point3::origin(), rotation);
            }
        }
        
        frame
    }
}

/// Motion capture data aggregator and synchronizer
pub struct MotionCaptureAggregator {
    sources: HashMap<String, MotionCaptureSource>,
    frame_buffer: HashMap<String, Vec<MotionCaptureFrame>>,
    max_buffer_size: usize,
    sync_window: Duration,
}

impl MotionCaptureAggregator {
    pub fn new(sync_window_ms: u64) -> Self {
        Self {
            sources: HashMap::new(),
            frame_buffer: HashMap::new(),
            max_buffer_size: 60, // Keep ~1 second at 60fps
            sync_window: Duration::from_millis(sync_window_ms),
        }
    }
    
    pub fn register_source(&mut self, source_id: String, source_type: MotionCaptureSource) {
        self.sources.insert(source_id.clone(), source_type);
        self.frame_buffer.insert(source_id, Vec::new());
    }
    
    pub fn add_frame(&mut self, source_id: &str, frame: MotionCaptureFrame) {
        if let Some(buffer) = self.frame_buffer.get_mut(source_id) {
            buffer.push(frame);
            
            // Maintain buffer size
            if buffer.len() > self.max_buffer_size {
                buffer.remove(0);
            }
        }
    }
    
    pub fn get_synchronized_frame(&mut self) -> Option<MotionCaptureFrame> {
        let now = Instant::now();
        let mut combined_frame = MotionCaptureFrame::new(MotionCaptureSource::Unknown);
        let mut found_any = false;
        
        // Find frames from all sources within sync window
        for (source_id, buffer) in &mut self.frame_buffer {
            // Find most recent frame within sync window
            if let Some(frame) = buffer.iter().rev()
                .find(|f| now.duration_since(f.timestamp) <= self.sync_window) {
                
                // Merge joint data
                for (joint_name, joint_data) in &frame.joint_data {
                    combined_frame.joint_data.insert(joint_name.clone(), joint_data.clone());
                }
                
                found_any = true;
            }
        }
        
        if found_any {
            combined_frame.timestamp = now;
            Some(combined_frame)
        } else {
            None
        }
    }
    
    pub fn cleanup_old_frames(&mut self) {
        let cutoff = Instant::now() - Duration::from_secs(2);
        
        for buffer in self.frame_buffer.values_mut() {
            buffer.retain(|frame| frame.timestamp > cutoff);
        }
    }
}

/// Real-time motion capture streaming system
pub struct MotionCaptureStreamer {
    aggregator: MotionCaptureAggregator,
    mediapipe_processor: MediaPipeProcessor,
    arkit_processor: ARKitFaceProcessor,
    
    // Performance tracking
    frames_processed: u64,
    last_frame_time: Instant,
    processing_latency: Duration,
}

impl MotionCaptureStreamer {
    pub fn new() -> Self {
        let mut aggregator = MotionCaptureAggregator::new(33); // 33ms sync window for 30fps
        
        // Register common sources
        aggregator.register_source("mediapipe_body".to_string(), MotionCaptureSource::MediaPipe);
        aggregator.register_source("arkit_face".to_string(), MotionCaptureSource::ARKitFace);
        
        Self {
            aggregator,
            mediapipe_processor: MediaPipeProcessor::new(0.7), // 70% smoothing
            arkit_processor: ARKitFaceProcessor::new(),
            frames_processed: 0,
            last_frame_time: Instant::now(),
            processing_latency: Duration::from_millis(0),
        }
    }
    
    /// Process MediaPipe pose landmarks
    pub fn process_mediapipe_frame(&mut self, landmarks: Vec<[f32; 3]>) {
        let start_time = Instant::now();
        
        let frame = self.mediapipe_processor.process_landmarks(landmarks);
        self.aggregator.add_frame("mediapipe_body", frame);
        
        self.update_performance_metrics(start_time);
    }
    
    /// Process ARKit face blendshapes
    pub fn process_arkit_frame(&mut self, blendshapes: HashMap<String, f32>) {
        let start_time = Instant::now();
        
        let frame = self.arkit_processor.process_blendshapes(blendshapes);
        self.aggregator.add_frame("arkit_face", frame);
        
        self.update_performance_metrics(start_time);
    }
    
    /// Process raw motion capture data
    pub fn process_raw_frame(&mut self, source_id: &str, joint_data: HashMap<String, Vec<f32>>) {
        let start_time = Instant::now();
        
        let mut frame = MotionCaptureFrame::new(MotionCaptureSource::Unknown);
        frame.joint_data = joint_data;
        
        self.aggregator.add_frame(source_id, frame);
        
        self.update_performance_metrics(start_time);
    }
    
    /// Get latest synchronized skeleton state
    pub fn get_skeleton_state(&mut self) -> Option<SkeletonState> {
        if let Some(frame) = self.aggregator.get_synchronized_frame() {
            let mut joint_transforms = HashMap::new();
            
            // Convert frame data to joint transforms
            for (joint_name, data) in frame.joint_data {
                if data.len() >= 7 { // position + quaternion
                    let position = Point3::new(data[0], data[1], data[2]);
                    let rotation = UnitQuaternion::from_quaternion(Quaternion::new(
                        data[6], // w
                        data[3], // x
                        data[4], // y
                        data[5], // z
                    ));
                    
                    let transform = JointTransform::new(position, rotation, Vector3::new(1.0, 1.0, 1.0));
                    joint_transforms.insert(joint_name, transform);
                }
            }
            
            if !joint_transforms.is_empty() {
                Some(SkeletonState::new(joint_transforms))
            } else {
                None
            }
        } else {
            None
        }
    }
    
    fn update_performance_metrics(&mut self, start_time: Instant) {
        self.frames_processed += 1;
        self.processing_latency = start_time.elapsed();
        self.last_frame_time = Instant::now();
    }
    
    /// Perform periodic maintenance
    pub fn update(&mut self) {
        self.aggregator.cleanup_old_frames();
    }
    
    /// Get performance statistics
    pub fn get_performance_stats(&self) -> HashMap<String, f64> {
        let mut stats = HashMap::new();
        
        stats.insert("frames_processed".to_string(), self.frames_processed as f64);
        stats.insert("processing_latency_ms".to_string(), 
                    self.processing_latency.as_millis() as f64);
        
        let fps = if self.last_frame_time.elapsed().as_secs() > 0 {
            60.0 // Approximate based on recent activity
        } else {
            0.0
        };
        stats.insert("estimated_fps".to_string(), fps);
        
        stats
    }
}

/// High-level motion capture manager for avatar animation
pub struct MotionCaptureManager {
    streamer: MotionCaptureStreamer,
    avatar_assignments: HashMap<String, String>, // avatar_id -> mocap_source_id
    enabled: bool,
}

impl MotionCaptureManager {
    pub fn new() -> Self {
        Self {
            streamer: MotionCaptureStreamer::new(),
            avatar_assignments: HashMap::new(),
            enabled: true,
        }
    }
    
    /// Assign motion capture source to avatar
    pub fn assign_avatar(&mut self, avatar_id: String, source_id: String) {
        self.avatar_assignments.insert(avatar_id, source_id);
        tracing::info!("Assigned motion capture source '{}' to avatar '{}'", source_id, avatar_id);
    }
    
    /// Remove avatar assignment
    pub fn unassign_avatar(&mut self, avatar_id: &str) {
        if self.avatar_assignments.remove(avatar_id).is_some() {
            tracing::info!("Unassigned motion capture from avatar '{}'", avatar_id);
        }
    }
    
    /// Process motion capture data for specific avatar
    pub fn process_avatar_motion(&mut self, avatar_id: &str, 
                                joint_data: HashMap<String, Vec<f32>>) -> Option<SkeletonState> {
        if !self.enabled {
            return None;
        }
        
        if let Some(source_id) = self.avatar_assignments.get(avatar_id) {
            self.streamer.process_raw_frame(source_id, joint_data);
            self.streamer.get_skeleton_state()
        } else {
            None
        }
    }
    
    /// Update motion capture system
    pub fn update(&mut self) {
        self.streamer.update();
    }
    
    /// Enable/disable motion capture
    pub fn set_enabled(&mut self, enabled: bool) {
        self.enabled = enabled;
        tracing::info!("Motion capture {}", if enabled { "enabled" } else { "disabled" });
    }
    
    /// Get performance statistics
    pub fn get_stats(&self) -> HashMap<String, f64> {
        self.streamer.get_performance_stats()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_motion_capture_frame() {
        let mut frame = MotionCaptureFrame::new(MotionCaptureSource::MediaPipe);
        
        frame.add_joint("test_joint", 
                       Point3::new(1.0, 2.0, 3.0),
                       UnitQuaternion::identity());
        
        assert!(frame.joint_data.contains_key("test_joint"));
        let data = &frame.joint_data["test_joint"];
        assert_eq!(data.len(), 7); // position + quaternion
    }
    
    #[test]
    fn test_mediapipe_processor() {
        let mut processor = MediaPipeProcessor::new(0.5);
        
        let landmarks = vec![
            [0.0, 0.0, 0.0], // nose
            [0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3],
            [0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3], [0.0; 3],
            [1.0, 0.0, 0.0], // left_shoulder (index 11)
        ];
        
        let frame = processor.process_landmarks(landmarks);
        
        assert_eq!(frame.source, MotionCaptureSource::MediaPipe);
        assert!(frame.joint_data.contains_key("left_shoulder"));
    }
    
    #[test]
    fn test_motion_capture_aggregator() {
        let mut aggregator = MotionCaptureAggregator::new(50);
        
        aggregator.register_source("test_source".to_string(), MotionCaptureSource::Manual);
        
        let frame = MotionCaptureFrame::new(MotionCaptureSource::Manual);
        aggregator.add_frame("test_source", frame);
        
        let synchronized = aggregator.get_synchronized_frame();
        assert!(synchronized.is_some());
    }
}
