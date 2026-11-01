//! Reconstructed PubCast Stage-1 camera control plane (2026-09-13 contract).
//! This module proves authenticated/ordered control state only. It does NOT
//! claim the GPU consumed the state or that a rendered frame exists.
use std::collections::HashMap;
use std::sync::Arc;
use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

pub const PROTOCOL: &str = "pubcast.camera.control.v1";

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Pose { pub position: Option<[f64;3]>, pub rotation: Option<[f64;3]>, pub fov: Option<f64> }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CameraControlEnvelope {
    pub protocol: String,
    #[serde(default)] pub token: String,
    pub request_id: String,
    pub action: String,
    #[serde(default)] pub timestamp: f64,
    #[serde(default)] pub camera_id: Option<String>,
    #[serde(default)] pub revision: Option<u64>,
    #[serde(default)] pub name: Option<String>,
    #[serde(default)] pub mode: Option<String>,
    #[serde(default)] pub position: Option<[f64;3]>,
    #[serde(default)] pub rotation: Option<[f64;3]>,
    #[serde(default)] pub fov: Option<f64>,
}
impl CameraControlEnvelope {
    pub fn looks_like(text:&str)->bool { text.contains("\"protocol\"") && text.contains(PROTOCOL) }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CameraControlAck {
    pub protocol: String, pub request_id: String, pub ok: bool,
    pub stage: u8, pub frame_path_proven: bool,
    #[serde(skip_serializing_if="Option::is_none")] pub camera_id: Option<String>,
    #[serde(skip_serializing_if="Option::is_none")] pub revision: Option<u64>,
    #[serde(skip_serializing_if="Option::is_none")] pub error: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct CameraControlState {
    pub name: String, pub mode: String, pub pose: Pose, pub revision: u64,
}

#[derive(Clone)]
pub struct CameraFleet { inner: Arc<RwLock<HashMap<String,CameraControlState>>>, token: Option<String> }
impl CameraFleet {
    pub fn from_env()->Self {
        let token=std::env::var("PUBCAST_CAMERA_CONTROL_TOKEN").ok().filter(|v|!v.is_empty());
        Self{inner:Arc::new(RwLock::new(HashMap::new())),token}
    }
    fn ack(req:&CameraControlEnvelope, ok:bool, err:Option<String>)->CameraControlAck {
        CameraControlAck{protocol:PROTOCOL.into(),request_id:req.request_id.clone(),ok,stage:1,frame_path_proven:false,
            camera_id:req.camera_id.clone(),revision:req.revision,error:err}
    }
    pub async fn handle(&self, req:CameraControlEnvelope)->CameraControlAck {
        if req.protocol != PROTOCOL { return Self::ack(&req,false,Some("unsupported protocol".into())); }
        let Some(expected)=&self.token else { return Self::ack(&req,false,Some("camera control disabled: token not configured".into())); };
        if &req.token != expected { return Self::ack(&req,false,Some("unauthorized".into())); }
        if req.action=="hello" || req.action=="status" { return Self::ack(&req,true,None); }
        let Some(id)=req.camera_id.clone() else { return Self::ack(&req,false,Some("camera_id required".into())); };
        let Some(rev)=req.revision else { return Self::ack(&req,false,Some("revision required".into())); };
        let mut fleet=self.inner.write().await;
        if let Some(old)=fleet.get(&id) { if rev<=old.revision { return Self::ack(&req,false,Some("stale/non-increasing revision".into())); } }
        match req.action.as_str() {
            "register" => {
                fleet.insert(id,CameraControlState{name:req.name.clone().unwrap_or_else(||"camera".into()),mode:"Donor".into(),pose:Pose{position:req.position,rotation:req.rotation,fov:req.fov},revision:rev});
            }
            "set_mode" => {
                let Some(state)=fleet.get_mut(&id) else { return Self::ack(&req,false,Some("camera not registered".into())); };
                let mode=req.mode.as_deref().unwrap_or("");
                if !matches!(mode,"Program"|"Preview"|"Donor") { return Self::ack(&req,false,Some("invalid mode".into())); }
                state.mode=mode.into(); state.pose=Pose{position:req.position.or(state.pose.position),rotation:req.rotation.or(state.pose.rotation),fov:req.fov.or(state.pose.fov)}; state.revision=rev;
            }
            "update_pose" => {
                let Some(state)=fleet.get_mut(&id) else { return Self::ack(&req,false,Some("camera not registered".into())); };
                if let Some(f)=req.fov { if !(1.0..=179.0).contains(&f) { return Self::ack(&req,false,Some("fov out of range".into())); } }
                state.pose=Pose{position:req.position.or(state.pose.position),rotation:req.rotation.or(state.pose.rotation),fov:req.fov.or(state.pose.fov)}; state.revision=rev;
            }
            _ => return Self::ack(&req,false,Some("unsupported action".into())),
        }
        Self::ack(&req,true,None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn rejects_stale_revision_and_never_claims_frame_proof(){
        std::env::set_var("PUBCAST_CAMERA_CONTROL_TOKEN","t");
        let f=CameraFleet::from_env();
        let base=CameraControlEnvelope{protocol:PROTOCOL.into(),token:"t".into(),request_id:"a".into(),action:"register".into(),timestamp:0.0,camera_id:Some("c".into()),revision:Some(10),name:None,mode:None,position:None,rotation:None,fov:None};
        let a=f.handle(base.clone()).await; assert!(a.ok); assert!(!a.frame_path_proven);
        let mut stale=base; stale.request_id="b".into(); stale.revision=Some(9);
        assert!(!f.handle(stale).await.ok);
    }
}
