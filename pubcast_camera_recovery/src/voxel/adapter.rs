use crate::camera::{engine::CameraEngine, packet::CameraPacket};
use crate::time::now_ms;
use super::frustum::{Frustum, Aabb};
use super::renderer_stub::{VoxelRenderer, RenderStats};

#[derive(Debug, Clone)]
pub struct VoxelObject { pub id: String, pub bounds: Aabb }

pub struct VoxelCameraAdapter<R: VoxelRenderer> { pub renderer: R }
impl<R: VoxelRenderer> VoxelCameraAdapter<R> {
    pub fn frame(&mut self, engine: &CameraEngine, scene_id: Option<String>, objects: &[VoxelObject]) -> Option<(CameraPacket, RenderStats)> {
        let camera=engine.get_active_camera()?;
        let frustum=Frustum { position: camera.position, forward: camera.forward(), fov_h_deg: camera.lens.fov_h_deg, far: 500.0 };
        let visible_object_ids=objects.iter().filter(|o| frustum.contains_aabb(&o.bounds)).map(|o| o.id.clone()).collect();
        let packet=CameraPacket {
            camera_id: camera.id.clone(), scene_id, shot_id: None, timestamp_ms: now_ms(),
            visible_object_ids, target_summary: vec![], priority_regions: vec![], mask_regions: vec![],
            cue_flags: vec![], downstream_notes: vec![],
            world_position: camera.position, world_rotation: camera.rotation,
            fov_h_deg: camera.lens.fov_h_deg, fov_v_deg: camera.lens.fov_v_deg,
            focal_length_mm: camera.lens.focal_length_mm,
        };
        let stats=self.renderer.render(&packet);
        Some((packet, stats))
    }
}
