
pub struct IRMController {
    pub health: f32,
}

impl IRMController {
    pub fn new() -> Self {
        Self {
            health: 100.0,
        }
    }

    pub fn update_health(&mut self, new_health: f32) {
        self.health = new_health;
    }
}
