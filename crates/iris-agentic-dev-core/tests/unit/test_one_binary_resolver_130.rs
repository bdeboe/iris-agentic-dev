//! 130 round 4 (FR-014): every harness finds the `iris-agentic-dev` binary through
//! `testing::iad_binary_path`.
//!
//! Twenty test files each carried their own lookup. Six tried `target/llvm-cov-target/debug`
//! first, which a coverage run leaves behind, so a plain `cargo test` spawned a build from weeks
//! earlier. That build had no SIGTERM handler: `stop_server` ended it before its telemetry flush and
//! every tool call leaked an `IrisDevTmp` class. The rest ignored `IAD_BINARY`. A test file that
//! names the coverage directory in code is writing its own lookup again.

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
fn no_test_file_resolves_the_binary_by_hand() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap();
    let mut files = Vec::new();
    for krate in ["iris-agentic-dev-core", "iris-agentic-dev-bin"] {
        rust_files(&root.join("crates").join(krate).join("tests"), &mut files);
    }
    assert!(files.len() > 100, "found only {} test files", files.len());

    let needle = concat!("llvm-cov", "-target");
    // The two files that test the rule itself have to name the directory.
    let exempt = ["test_testing_helpers.rs", "test_cli_dispatch_helpers.rs"];
    let mut offenders = Vec::new();
    for f in &files {
        if f.file_name()
            .is_some_and(|n| exempt.iter().any(|e| n == *e))
        {
            continue;
        }
        let text = std::fs::read_to_string(f).unwrap();
        for (i, line) in text.lines().enumerate() {
            let code = line.split("//").next().unwrap_or("");
            if code.contains(needle) {
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
        "use iris_agentic_dev_core::testing::iad_binary_path instead of a local lookup:\n{}",
        offenders.join("\n")
    );
}
