// Re-export cmd modules for integration/unit test access.
pub mod cmd;

/// Exit the process once pending telemetry writes finish (at most
/// `telemetry::EXIT_FLUSH_TIMEOUT`). Use this instead of `std::process::exit`, which drops a write
/// mid-cycle and leaves its `IrisDevTmp` scratch class in USER (130 round 4). It also ends the
/// process's CSP sessions, as `main` does (132 B1).
pub fn exit(code: i32) -> ! {
    iris_agentic_dev_core::telemetry::flush_before_exit();
    iris_agentic_dev_core::iris::csp_session::logout_blocking(std::time::Duration::from_secs(3));
    std::process::exit(code)
}
