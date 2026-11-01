use crate::camera::packet::CameraPacket;
pub trait VoxelRenderer { fn render(&mut self, packet: &CameraPacket) -> RenderStats; }
#[derive(Debug, Clone, Default)]
pub struct RenderStats { pub submitted_objects: usize, pub rendered: bool }
pub struct StubRenderer;
impl VoxelRenderer for StubRenderer {
    fn render(&mut self, packet: &CameraPacket) -> RenderStats {
        RenderStats { submitted_objects: packet.visible_object_ids.len(), rendered: true }
    }
}
