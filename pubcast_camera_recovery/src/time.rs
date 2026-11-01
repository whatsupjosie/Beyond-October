pub type TimestampMs = u64;
pub fn now_ms() -> TimestampMs {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default().as_millis() as u64
}
