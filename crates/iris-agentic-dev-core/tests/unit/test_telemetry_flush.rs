//! 130 round 4 (FR-014): a durable telemetry write has to finish before the process exits.
//!
//! `record_call` spawned `write_durable` and nothing waited for it. Every IRIS write runs a scratch
//! class through put, compile, query and delete, and a CLI process (`iad exec`, `iad tool`, every
//! ladder check) exits right after its one call. The runtime dropped the task between compile and
//! delete, and 78,183 `IrisDevTmp.IrisDevRun*` classes piled up in USER on iris-dev-iris, each one
//! a single `set ^IRISDEV("telemetry",...)`.
//!
//! No IRIS here: the tracker counts futures, and these futures sleep.

use iris_agentic_dev_core::telemetry::{PendingWrites, TELEMETRY_SCRATCH_PREFIX};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

#[tokio::test]
async fn flush_waits_for_a_pending_write() {
    static WRITES: PendingWrites = PendingWrites::new();
    static DONE: AtomicBool = AtomicBool::new(false);

    WRITES.spawn(async {
        tokio::time::sleep(Duration::from_millis(50)).await;
        DONE.store(true, Ordering::SeqCst);
    });
    assert_eq!(WRITES.pending(), 1);

    assert!(WRITES.flush(Duration::from_secs(5)).await);
    assert!(
        DONE.load(Ordering::SeqCst),
        "flush returned before the write ran"
    );
    assert_eq!(WRITES.pending(), 0);
}

#[tokio::test]
async fn flush_gives_up_at_its_timeout() {
    static WRITES: PendingWrites = PendingWrites::new();

    WRITES.spawn(async {
        tokio::time::sleep(Duration::from_secs(60)).await;
    });
    let started = Instant::now();
    assert!(!WRITES.flush(Duration::from_millis(100)).await);
    assert!(
        started.elapsed() < Duration::from_secs(2),
        "a hung write must not hold the process past the timeout"
    );
}

#[tokio::test]
async fn flush_with_nothing_pending_returns_at_once() {
    static WRITES: PendingWrites = PendingWrites::new();
    let started = Instant::now();
    assert!(WRITES.flush(Duration::from_secs(5)).await);
    assert!(started.elapsed() < Duration::from_millis(500));
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn flush_blocking_runs_a_write_spawned_on_the_same_worker() {
    // The exit path is sync code on the thread that just recorded the call. A task spawned from a
    // worker goes to that worker's LIFO slot, which no other worker steals, so a plain sleep loop
    // there would wait out the whole timeout while the write never started.
    static WRITES: PendingWrites = PendingWrites::new();
    static DONE: AtomicBool = AtomicBool::new(false);

    let flushed = tokio::spawn(async {
        WRITES.spawn(async {
            tokio::time::sleep(Duration::from_millis(20)).await;
            DONE.store(true, Ordering::SeqCst);
        });
        WRITES.flush_blocking(Duration::from_secs(5))
    })
    .await
    .unwrap();

    assert!(flushed);
    assert!(DONE.load(Ordering::SeqCst));
}

#[test]
fn flush_blocking_outside_a_runtime_does_not_panic() {
    static WRITES: PendingWrites = PendingWrites::new();
    assert!(WRITES.flush_blocking(Duration::from_millis(10)));
}

#[test]
fn telemetry_scratch_classes_have_their_own_prefix() {
    // A leak has to be attributable. User code keeps `IrisDevRun`; telemetry gets its own name, so
    // a count of `IrisDevTmp.IrisDevTel*` measures this fix alone.
    assert_eq!(TELEMETRY_SCRATCH_PREFIX, "IrisDevTel");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn flush_blocking_works_from_the_block_on_thread() {
    // `main`'s own exits run here, on the thread `#[tokio::main]` blocks, not on a worker.
    static WRITES: PendingWrites = PendingWrites::new();
    static DONE: AtomicBool = AtomicBool::new(false);

    WRITES.spawn(async {
        tokio::time::sleep(Duration::from_millis(20)).await;
        DONE.store(true, Ordering::SeqCst);
    });
    assert!(WRITES.flush_blocking(Duration::from_secs(5)));
    assert!(DONE.load(Ordering::SeqCst));
}
