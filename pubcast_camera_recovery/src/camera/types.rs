#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CameraRole { Preview, Program, Standby, Analysis }

#[derive(Debug, Clone, Copy)]
pub enum FollowBehavior { HardLock, SoftFollow, LazyPan, OrbitSlow }

#[derive(Debug, Clone)]
pub struct LensProfile {
    pub focal_length_mm: f32,
    pub sensor_width_mm: f32,
    pub fov_h_deg: f32,
    pub fov_v_deg: f32,
}
impl LensProfile {
    pub fn from_focal_length(focal_length_mm: f32, sensor_width_mm: f32, sensor_height_mm: f32) -> Self {
        let fov_h_deg = 2.0 * (sensor_width_mm / (2.0*focal_length_mm)).atan().to_degrees();
        let fov_v_deg = 2.0 * (sensor_height_mm / (2.0*focal_length_mm)).atan().to_degrees();
        Self { focal_length_mm, sensor_width_mm, fov_h_deg, fov_v_deg }
    }
}
