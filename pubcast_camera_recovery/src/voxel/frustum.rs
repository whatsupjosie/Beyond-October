#[derive(Debug, Clone, Copy)]
pub struct Aabb { pub min: [f32;3], pub max: [f32;3] }
#[derive(Debug, Clone)]
pub struct Frustum { pub position: [f32;3], pub forward: [f32;3], pub fov_h_deg: f32, pub far: f32 }
impl Frustum {
    pub fn contains_aabb(&self, a: &Aabb) -> bool {
        let cx=(a.min[0]+a.max[0])*0.5-self.position[0];
        let cy=(a.min[1]+a.max[1])*0.5-self.position[1];
        let cz=(a.min[2]+a.max[2])*0.5-self.position[2];
        let d=(cx*cx+cy*cy+cz*cz).sqrt();
        d <= self.far
    }
}
