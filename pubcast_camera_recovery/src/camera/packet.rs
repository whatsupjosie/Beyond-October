use crate::time::TimestampMs;

/// Structured per-frame camera packet emitted toward the switcher and renderer.
/// Designed to grow: add fields freely; downstream consumers skip what they don't know.
#[derive(Debug, Clone)]
pub struct CameraPacket {
    pub camera_id:         String,
    pub scene_id:          Option<String>,
    pub shot_id:           Option<String>,
    pub timestamp_ms:      TimestampMs,

    // --- Voxel world context (populated by VoxelCameraAdapter) ---
    /// IDs of world objects currently inside the camera frustum.
    pub visible_object_ids:    Vec<String>,
    /// Human-readable summary of what each target is doing.
    pub target_summary:        Vec<String>,
    /// Named screen-space regions that are priority render areas (e.g. "face_region").
    pub priority_regions:      Vec<String>,
    /// Named screen-space regions to mask/blur (e.g. "screen_glare").
    pub mask_regions:          Vec<String>,
    /// Active script cue flags visible to the switcher.
    pub cue_flags:             Vec<String>,
    /// Free-text notes for editor / post pipeline.
    pub downstream_notes:      Vec<String>,

    // --- Lens / transform snapshot (populated by VoxelCameraAdapter) ---
    pub world_position:    [f32; 3],
    pub world_rotation:    [f32; 3],
    pub fov_h_deg:         f32,
    pub fov_v_deg:         f32,
    pub focal_length_mm:   f32,
}
