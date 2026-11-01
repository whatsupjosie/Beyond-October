use std::collections::HashMap;
use super::state::CameraState;
use super::targeting::CameraTarget;
use super::fallback::FallbackLevel;

#[derive(Default)]
pub struct CameraEngine {
    cameras: HashMap<String, CameraState>,
    pub active_camera: Option<String>,
}
impl CameraEngine {
    pub fn add_camera(&mut self, camera: CameraState) { self.cameras.insert(camera.id.clone(), camera); }
    pub fn get_active_camera(&self) -> Option<&CameraState> {
        self.active_camera.as_ref().and_then(|id| self.cameras.get(id))
    }
    pub fn get_camera(&self, id: &str) -> Option<&CameraState> { self.cameras.get(id) }
    pub fn activate(&mut self, id: &str) -> bool {
        if self.cameras.contains_key(id) {
            for c in self.cameras.values_mut() { c.active=false; }
            if let Some(c)=self.cameras.get_mut(id) { c.active=true; }
            self.active_camera=Some(id.to_string()); true
        } else { false }
    }
    pub fn target(&mut self, id: &str, target: &CameraTarget, alpha: f32) -> bool {
        let Some(c)=self.cameras.get_mut(id) else { return false; };
        let a=alpha.clamp(0.0,1.0);
        for i in 0..3 { c.position[i] += (target.position[i]-c.position[i])*a; }
        true
    }
    pub fn fallback(&self) -> FallbackLevel {
        if self.active_camera.is_some() { FallbackLevel::None } else { FallbackLevel::WideShot }
    }
}
