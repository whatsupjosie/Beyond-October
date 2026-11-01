
use std::sync::{Arc};
use std::time::{Instant, Duration};
use crossbeam::queue::ArrayQueue;

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum EngineMode {
    Program,
    Preview,
    Donor,
    Transition,
}

pub struct FrameBuffer {
    queue: Arc<ArrayQueue<Vec<u8>>>,
}

impl FrameBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            queue: Arc::new(ArrayQueue::new(capacity)),
        }
    }

    pub fn push(&self, frame: Vec<u8>) {
        if self.queue.is_full() {
            self.queue.pop();
        }
        let _ = self.queue.push(frame);
    }

    pub fn latest(&self) -> Option<Vec<u8>> {
        self.queue.pop()
    }
}

pub struct PreheatState {
    start_time: Instant,
    min_duration: Duration,
    ready: bool,
}

impl PreheatState {
    pub fn new(ms: u64) -> Self {
        Self {
            start_time: Instant::now(),
            min_duration: Duration::from_millis(ms),
            ready: false,
        }
    }

    pub fn reset(&mut self) {
        self.start_time = Instant::now();
        self.ready = false;
    }

    pub fn update(&mut self, fps: f32) {
        if self.start_time.elapsed() >= self.min_duration && fps > 55.0 {
            self.ready = true;
        }
    }

    pub fn is_ready(&self) -> bool {
        self.ready
    }
}

pub struct DonationState {
    active: bool,
    last_change: Instant,
    min_hold: Duration,
}

impl DonationState {
    pub fn new(ms: u64) -> Self {
        Self {
            active: false,
            last_change: Instant::now(),
            min_hold: Duration::from_millis(ms),
        }
    }

    pub fn can_switch(&self) -> bool {
        self.last_change.elapsed() >= self.min_hold
    }

    pub fn set(&mut self, state: bool) {
        if self.can_switch() {
            self.active = state;
            self.last_change = Instant::now();
        }
    }
}

#[derive(Clone, Copy)]
pub struct ComputeBudget {
    pub cpu_share: f32,
    pub gpu_priority: u8,
}

pub struct CameraEngine {
    pub id: String,
    pub mode: EngineMode,
    pub buffer: FrameBuffer,
    pub preheat: PreheatState,
    pub donation: DonationState,
    pub budget: ComputeBudget,
    pub reserve: f32,
}

impl CameraEngine {
    pub fn new(id: &str) -> Self {
        Self {
            id: id.to_string(),
            mode: EngineMode::Donor,
            buffer: FrameBuffer::new(5),
            preheat: PreheatState::new(2000),
            donation: DonationState::new(500),
            budget: ComputeBudget {
                cpu_share: 1.0,
                gpu_priority: 5,
            },
            reserve: 0.15,
        }
    }

    pub fn update_mode(&mut self, new_mode: EngineMode) {
        if self.mode != new_mode {
            if new_mode == EngineMode::Preview {
                self.preheat.reset();
                self.mode = EngineMode::Transition;
            } else {
                self.mode = new_mode;
            }
        }
    }

    pub fn tick(&mut self, fps: f32) {
        match self.mode {
            EngineMode::Program => {
                self.budget.cpu_share = 1.0;
                self.budget.gpu_priority = 10;
                self.donation.set(false);
            }

            EngineMode::Preview => {
                self.budget.cpu_share = 1.0;
                self.budget.gpu_priority = 8;
                self.donation.set(false);
            }

            EngineMode::Transition => {
                self.preheat.update(fps);

                if self.preheat.is_ready() {
                    self.mode = EngineMode::Preview;
                }

                self.budget.cpu_share = 0.8;
                self.budget.gpu_priority = 7;
            }

            EngineMode::Donor => {
                if self.donation.can_switch() {
                    self.donation.set(true);
                }

                self.budget.cpu_share = self.reserve;
                self.budget.gpu_priority = 2;
            }
        }
    }

    pub fn donate_amount(&self) -> f32 {
        if self.mode == EngineMode::Donor {
            1.0 - self.reserve
        } else {
            0.0
        }
    }
}
