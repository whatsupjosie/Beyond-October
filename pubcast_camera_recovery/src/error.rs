#[derive(Debug, Clone)]
pub enum CameraError { CameraNotFound(String), Invalid(String) }
pub type Result<T> = std::result::Result<T, CameraError>;
