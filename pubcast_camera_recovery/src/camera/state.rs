use super::types::{CameraRole, FollowBehavior, LensProfile};

#[derive(Debug, Clone)]
pub struct CameraState {
    pub id: String,
    pub role: CameraRole,
    pub position: [f32; 3],
    pub rotation: [f32; 3],
    pub lens: LensProfile,
    pub follow_behavior: FollowBehavior,
    pub active: bool,
}
impl CameraState {
    pub fn forward(&self) -> [f32;3] {
        let pitch=self.rotation[0].to_radians(); let yaw=self.rotation[1].to_radians();
        [yaw.sin()*pitch.cos(), -pitch.sin(), -yaw.cos()*pitch.cos()]
    }
}
