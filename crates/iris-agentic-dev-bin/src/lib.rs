// Re-export cmd modules for integration/unit test access.
pub mod cmd;

/// Exit the process once pending telemetry writes finish (at most
/// `telemetry::EXIT_FLUSH_TIMEOUT`). Use this instead of `std::process::exit`, which drops a write
/// mid-cycle and leaves its `IrisDevTmp` scratch class in USER (130 round 4).
pub fn exit(code: i32) -> ! {
    iris_agentic_dev_core::telemetry::flush_before_exit();
    std::process::exit(code)
}
