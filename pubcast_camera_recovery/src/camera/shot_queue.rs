use std::collections::VecDeque;
#[derive(Debug, Clone)]
pub struct ShotRequest { pub shot_id: String, pub camera_id: String, pub target_id: Option<String> }
#[derive(Debug, Default)]
pub struct ShotQueue { queue: VecDeque<ShotRequest> }
impl ShotQueue {
    pub fn push(&mut self, shot: ShotRequest) { self.queue.push_back(shot); }
    pub fn pop(&mut self) -> Option<ShotRequest> { self.queue.pop_front() }
    pub fn len(&self) -> usize { self.queue.len() }
}
