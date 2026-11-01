#[derive(Debug, Clone)]
pub enum StudioEvent {
    CameraActivated(String), CameraFallback(String), SceneSynced(String),
}
