
pub enum RenderQuality {
    Full,
    Reduced,
    Minimal,
}

pub trait RenderBackend {
    fn render_frame(&mut self, quality: RenderQuality) -> Vec<u8>;
    fn set_priority(&mut self, priority: u8);
}
