//! 130 round 4 (FR-014): every exit from the CLI waits for its telemetry write first.
//!
//! `std::process::exit` ends the process without dropping anything, so a durable telemetry write
//! still in flight dies between compile and delete and leaves its `IrisDevTmp` scratch class in
//! USER. `iris_agentic_dev::exit` flushes and then exits; this guard keeps it the only way out.

use std::path::Path;

fn rust_files(dir: &Path, out: &mut Vec<std::path::PathBuf>) {
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            rust_files(&path, out);
        } else if path.extension().is_some_and(|e| e == "rs") {
            out.push(path);
        }
    }
}

#[test]
fn no_raw_process_exit_outside_the_flushing_helper() {
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut files = Vec::new();
    rust_files(&src, &mut files);
    assert!(
        files.len() > 10,
        "found only {} files under {src:?}",
        files.len()
    );

    let mut offenders = Vec::new();
    for file in &files {
        if file.ends_with("src/lib.rs") {
            continue;
        }
        let text = std::fs::read_to_string(file).unwrap();
        for (n, line) in text.lines().enumerate() {
            let code = line.trim_start();
            if code.starts_with("//") {
                continue;
            }
            if code.contains("process::exit(") {
                offenders.push(format!("{}:{}: {}", file.display(), n + 1, code));
            }
        }
    }
    assert!(
        offenders.is_empty(),
        "call iris_agentic_dev::exit instead, so pending telemetry writes finish:\n{}",
        offenders.join("\n")
    );
}

#[test]
fn the_helper_flushes_before_it_exits() {
    let lib =
        std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("src/lib.rs")).unwrap();
    let flush = lib
        .find("flush_before_exit()")
        .expect("exit helper must flush");
    let exit = lib
        .find("std::process::exit(code)")
        .expect("exit helper must exit");
    assert!(flush < exit, "the flush has to come before the exit");
}

#[test]
fn main_flushes_on_a_normal_return() {
    let main =
        std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("src/main.rs")).unwrap();
    assert!(
        main.contains("flush_before_exit()"),
        "returning from main drops the runtime and every task on it"
    );
}
