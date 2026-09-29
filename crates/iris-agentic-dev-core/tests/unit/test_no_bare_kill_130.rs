//! 130 round 4 (FR-014): test harnesses stop a spawned server with `testing::stop_server`.
//!
//! `Child::kill` is SIGKILL, which no process can catch, so the server's telemetry write and any
//! execute still in flight never delete their `IrisDevTmp` scratch class. A per-module bisect of one
//! credentialed run found every leaking module doing this, 39 classes from the gate suite alone.
//! `stop_server` sends SIGTERM, waits, and kills only a server that hangs. A line that has to kill
//! directly says why with an `allow-kill:` comment.

use std::path::{Path, PathBuf};

fn rust_files(dir: &Path, out: &mut Vec<PathBuf>) {
    for entry in std::fs::read_dir(dir).unwrap().flatten() {
        let p = entry.path();
        if p.is_dir() {
            rust_files(&p, out);
        } else if p.extension().is_some_and(|e| e == "rs") {
            out.push(p);
        }
    }
}

#[test]
fn no_test_harness_sigkills_a_spawned_server() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap();
    let mut files = Vec::new();
    for krate in ["iris-agentic-dev-core", "iris-agentic-dev-bin"] {
        rust_files(&root.join("crates").join(krate).join("tests"), &mut files);
    }
    assert!(files.len() > 100, "found only {} test files", files.len());

    let mut offenders = Vec::new();
    for f in &files {
        let text = std::fs::read_to_string(f).unwrap();
        for (i, line) in text.lines().enumerate() {
            let code = line.split("//").next().unwrap_or("");
            if code.contains(concat!(".ki", "ll()")) && !line.contains("allow-kill:") {
                offenders.push(format!(
                    "{}:{}",
                    f.strip_prefix(&root).unwrap().display(),
                    i + 1
                ));
            }
        }
    }
    assert!(
        offenders.is_empty(),
        "use iris_agentic_dev_core::testing::stop_server instead of Child::kill:\n{}",
        offenders.join("\n")
    );
}
