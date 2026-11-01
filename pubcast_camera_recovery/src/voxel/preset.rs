use crate::camera::{state::CameraState, types::{CameraRole, FollowBehavior, LensProfile}};

fn camera(id:&str, role:CameraRole, pos:[f32;3], rot:[f32;3], focal:f32, behavior:FollowBehavior)->CameraState {
    CameraState { id:id.into(), role, position:pos, rotation:rot,
        lens:LensProfile::from_focal_length(focal,36.0,20.25), follow_behavior:behavior, active:false }
}
pub fn cam_wide()->CameraState { camera("cam_wide",CameraRole::Preview,[0.0,4.5,10.0],[0.0,180.0,0.0],24.0,FollowBehavior::SoftFollow) }
pub fn cam_host()->CameraState { camera("cam_host",CameraRole::Program,[0.5,1.65,3.0],[0.0,180.0,0.0],85.0,FollowBehavior::SoftFollow) }
pub fn cam_reaction()->CameraState { camera("cam_reaction",CameraRole::Standby,[-1.8,1.8,4.5],[0.0,180.0,0.0],135.0,FollowBehavior::HardLock) }
pub fn cam_orbital()->CameraState { camera("cam_orbital",CameraRole::Analysis,[0.0,20.0,0.0],[90.0,0.0,0.0],35.0,FollowBehavior::OrbitSlow) }
pub fn all_cameras()->Vec<CameraState>{ vec![cam_wide(),cam_host(),cam_reaction(),cam_orbital()] }
