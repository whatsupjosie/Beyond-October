use crate::{camera::engine::CameraEngine, voxel::{preset, adapter::{VoxelCameraAdapter,VoxelObject}, renderer_stub::StubRenderer, frustum::Aabb}};
pub fn demo_scene() -> Vec<VoxelObject> {
    vec![VoxelObject{id:"stage".into(),bounds:Aabb{min:[-5.0,-1.0,-5.0],max:[5.0,3.0,5.0]}}]
}
pub fn demo_control_room() -> (CameraEngine, VoxelCameraAdapter<StubRenderer>) {
    let mut e=CameraEngine::default();
    for c in preset::all_cameras(){e.add_camera(c);}
    e.activate("cam_wide");
    (e,VoxelCameraAdapter{renderer:StubRenderer})
}
