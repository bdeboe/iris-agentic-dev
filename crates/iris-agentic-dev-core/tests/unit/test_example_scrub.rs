//! Spec 123 US3: the published todo-app example leaks nothing it was recorded with.
//!
//! `docs/examples/todo-app/` is a cleaned copy of a real session. The session ran on a laptop, for
//! named people, with hook output and reminders in the context. This file fails on the generic
//! shapes of those leaks: home directories, email addresses, reminder and hook markers, and
//! credential literals other than the container default `_SYSTEM`/`SYS` that the example documents.
//!
//! Names are not generic, so they come from a local denylist at `.iad-local/denylist.txt`, which is
//! gitignored. One name per line, `#` starts a comment. Without the file the names go unchecked and
//! the test says so, rather than passing as though it had looked.
//!
//! No IRIS connection.

use std::fs;
use std::path::{Path, PathBuf};

/// `CARGO_MANIFEST_DIR` is `<root>/crates/iris-agentic-dev-core`, so the root is two up. A source-tree
/// test, so the build-time path is correct here.
fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .expect("CARGO_MANIFEST_DIR should be <root>/crates/<crate>")
        .to_path_buf()
}

fn example_dir() -> PathBuf {
    repo_root().join("docs/examples/todo-app")
}

const PUBLISHED: &[&str] = &[
    "Demo.Todo.cls",
    "Demo.TodoREST.cls",
    "STEPS.md",
    "transcript.md",
];

/// The documented container default. Any other user:password pair is a leak.
const DEFAULT_CREDENTIAL: &str = "_SYSTEM:SYS";

/// (what it is, pattern). Each is a leak wherever it appears.
fn leak_patterns() -> Vec<(&'static str, regex::Regex)> {
    let re = |p: &str| regex::Regex::new(p).expect("leak regex");
    vec![
        (
            "home directory",
            re(r"(/Users/|/home/)[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\"),
        ),
        (
            "email address",
            re(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
        ),
        (
            "reminder or hook marker",
            re(
                r"(?i)system-reminder|hookSpecificOutput|additionalContext|\b(SessionStart|UserPromptSubmit|PreToolUse|PostToolUse)\b|hook success|<command-name>",
            ),
        ),
        (
            "API token",
            re(
                r"\b(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[bpa]-[A-Za-z0-9-]{10,})",
            ),
        ),
    ]
}

/// A `user:password` pair in `curl -u` or a URL's userinfo, other than the default.
fn credential_pairs(text: &str) -> Vec<String> {
    // The URL arm needs the `@`, or `://localhost:52780` reads as a pair.
    let re = regex::Regex::new(
        r"(?:-u\s+|--user\s+)([A-Za-z0-9_%.-]+:[^\s@/:'\x22\\]+)|://([A-Za-z0-9_%.-]+:[^\s@/:'\x22\\]+)@",
    )
    .expect("credential regex");
    re.captures_iter(text)
        .filter_map(|c| {
            c.get(1)
                .or_else(|| c.get(2))
                .map(|m| m.as_str().to_string())
        })
        .filter(|pair| pair != DEFAULT_CREDENTIAL)
        .collect()
}

/// A `password = "..."` style assignment whose value is not the default.
fn password_assignments(text: &str) -> Vec<String> {
    let re = regex::Regex::new(r#"(?i)\b(?:iris_)?password\b\s*[:=]\s*["']?([^\s"',)]+)"#)
        .expect("password regex");
    re.captures_iter(text)
        .map(|c| c[1].to_string())
        .filter(|v| v != "SYS")
        .collect()
}

/// `name` appears in `text` as a whole word, case-insensitively.
fn names_word(text: &str, name: &str) -> bool {
    let pattern = format!(
        r"(?i)(^|[^A-Za-z0-9_]){}($|[^A-Za-z0-9_])",
        regex::escape(name)
    );
    regex::Regex::new(&pattern)
        .expect("name regex")
        .is_match(text)
}

fn denylist() -> Option<Vec<String>> {
    let raw = fs::read_to_string(repo_root().join(".iad-local/denylist.txt")).ok()?;
    Some(
        raw.lines()
            .map(|l| l.split('#').next().unwrap_or_default().trim())
            .filter(|l| !l.is_empty())
            .map(str::to_string)
            .collect(),
    )
}

/// Every leak in one file's text, as human-readable lines.
fn leaks(text: &str, names: &[String]) -> Vec<String> {
    let mut out = Vec::new();
    for (lineno, line) in text.lines().enumerate() {
        let at = lineno + 1;
        for (what, re) in leak_patterns() {
            if let Some(m) = re.find(line) {
                out.push(format!("line {at}: {what}: {}", m.as_str()));
            }
        }
        for pair in credential_pairs(line) {
            out.push(format!("line {at}: credential literal: {pair}"));
        }
        for value in password_assignments(line) {
            out.push(format!("line {at}: password literal: {value}"));
        }
        for name in names {
            if names_word(line, name) {
                out.push(format!("line {at}: denylisted name: {name}"));
            }
        }
    }
    out
}

/// The patterns on the strings the session actually produced, so a regex change shows up here
/// rather than as a scrub that quietly stopped matching.
#[test]
fn the_leak_patterns() {
    let none: Vec<String> = Vec::new();
    for bad in [
        "cd /Users/someone/ws/iris-agentic-dev",
        "HOME=/home/runner",
        r"C:\Users\someone\ws",
        "author: someone@example.com",
        "<system-reminder>",
        "SessionStart:compact hook success",
        "curl -s -u admin:hunter2 http://localhost:52780/todo/rows",
        "http://admin:hunter2@localhost:52780/todo/",
        "IRIS_PASSWORD=hunter2",
        "token sk-ant-api03-abcdefghijkl",
    ] {
        assert!(!leaks(bad, &none).is_empty(), "missed a leak in: {bad}");
    }
    for fine in [
        "curl -s -u _SYSTEM:SYS http://localhost:52780/todo/rows",
        "curl: option -s -u _SYSTEM:SYS: is unknown",
        r#"{"command": "curl -s -u _SYSTEM:SYS\" $B/rows"}"#,
        "open http://_SYSTEM:SYS@localhost:52780/todo/",
        "IRIS_PASSWORD=SYS",
        "curl -s http://localhost:52780/todo/rows",
        "the browser prompts once for `_SYSTEM` / `SYS`",
        "Set tSC = ##class(Security.Applications).Create(\"/todo\", .p)",
        "a PM presents this to a customer",
    ] {
        assert!(
            leaks(fine, &none).is_empty(),
            "false leak in: {fine}: {:?}",
            leaks(fine, &none)
        );
    }

    let names = vec!["Pat".to_string()];
    assert!(!leaks("show this to Pat first", &names).is_empty());
    assert!(!leaks("title=<b>pat</b>", &names).is_empty());
    assert!(
        leaks("a pattern and a patch", &names).is_empty(),
        "matched inside a word"
    );
}

/// FR-009: exactly the four files, nothing the session left beside them.
#[test]
fn the_example_holds_exactly_four_files() {
    let dir = example_dir();
    let entries = fs::read_dir(&dir).unwrap_or_else(|e| {
        panic!(
            "{} must exist — it is the published example (spec 123 US3): {e}",
            dir.display()
        )
    });
    let mut found: Vec<String> = entries
        .map(|e| {
            e.expect("dir entry")
                .file_name()
                .to_string_lossy()
                .into_owned()
        })
        .collect();
    found.sort();
    let mut want: Vec<String> = PUBLISHED.iter().map(|s| s.to_string()).collect();
    want.sort();
    assert_eq!(
        found, want,
        "docs/examples/todo-app/ must hold exactly the published files"
    );
}

/// FR-010, FR-011: no generic leak, and no denylisted name when the denylist is present.
#[test]
fn the_example_leaks_nothing() {
    let names = match denylist() {
        Some(names) => {
            assert!(
                !names.is_empty(),
                ".iad-local/denylist.txt exists but lists no names; delete it or fill it"
            );
            names
        }
        None => {
            eprintln!("denylist absent — names unchecked");
            Vec::new()
        }
    };

    let dir = example_dir();
    let mut report = Vec::new();
    for file in PUBLISHED {
        let path = dir.join(file);
        let text = fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("cannot read {}: {e}", path.display()));
        assert!(!text.trim().is_empty(), "{file} is empty");
        report.extend(
            leaks(&text, &names)
                .into_iter()
                .map(|l| format!("  {file} {l}")),
        );
    }
    assert!(
        report.is_empty(),
        "{} leaks in docs/examples/todo-app/:\n{}",
        report.len(),
        report.join("\n")
    );
}

/// FR-016: the claim the live repro disproved is gone from the steps, and the transcript, which
/// records what the agent wrote at the time, says so up front.
#[test]
fn the_disproved_initial_expression_claim_is_not_published() {
    let dir = example_dir();
    let steps = fs::read_to_string(dir.join("STEPS.md")).expect("STEPS.md");
    assert!(
        !steps.contains("not on a SQL INSERT"),
        "STEPS.md still says InitialExpression does not fire on SQL INSERT; research R2 shows it does"
    );
    let transcript = fs::read_to_string(dir.join("transcript.md")).expect("transcript.md");
    let head: String = transcript.lines().take(12).collect::<Vec<_>>().join("\n");
    assert!(
        head.contains("InitialExpression"),
        "transcript.md must open with a note that its InitialExpression claim was disproved"
    );
}
