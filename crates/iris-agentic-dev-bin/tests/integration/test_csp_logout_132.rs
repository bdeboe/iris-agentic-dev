//! 132 B1: an iad process ends the CSP sessions it opened.
//!
//! Before the fix every `iad exec` left two sessions in `^%cspSession` (10 calls took 139 from 15
//! to 35), each holding its slot for the web app's 3600 s timeout. A ladder task makes about 15
//! calls, so two tasks were enough for `<LICENSE LIMIT EXCEEDED>` on 139's key. These tests count
//! the sessions on `iad-aihub-iris` before and after, through `docker exec`, so the count does not
//! open a session of its own.

use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

fn container() -> String {
    std::env::var("IAD_AIHUB_CONTAINER").unwrap_or_else(|_| "iad-aihub-iris".to_string())
}

fn web_port() -> String {
    std::env::var("IAD_AIHUB_WEB_PORT").unwrap_or_else(|_| "52781".to_string())
}

fn csp_sessions() -> usize {
    let script =
        "s n=0,r=\"\" f  { s r=$o(^%cspSession(r)) q:r=\"\"  s n=n+1 } w \"SESS=\",n,!\nhalt\n";
    let out = Command::new("docker")
        .args([
            "exec",
            "-i",
            &container(),
            "iris",
            "session",
            "IRIS",
            "-U",
            "%SYS",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .and_then(|mut c| {
            c.stdin.take().unwrap().write_all(script.as_bytes())?;
            c.wait_with_output()
        })
        .expect("docker exec iris session");
    let text = String::from_utf8_lossy(&out.stdout);
    text.split("SESS=")
        .nth(1)
        .and_then(|s| s.split_whitespace().next())
        .and_then(|n| n.parse().ok())
        .unwrap_or_else(|| panic!("no session count from {}: {text}", container()))
}

fn iad(dir: &std::path::Path) -> Command {
    let bin = iris_agentic_dev_core::testing::iad_binary_path();
    assert!(bin.exists(), "binary not found at {}", bin.display());
    let mut cmd = Command::new(bin);
    cmd.current_dir(dir)
        .env("OBJECTSCRIPT_WORKSPACE", dir)
        .env("IRIS_HOST", "localhost")
        .env("IRIS_WEB_PORT", web_port())
        .env("IRIS_USERNAME", "_SYSTEM")
        .env("IRIS_PASSWORD", "SYS")
        .env("IRIS_CONTAINER", container())
        .env("IRIS_NAMESPACE", "USER");
    cmd
}

#[test]
#[ignore = "requires live iad-aihub-iris and IAD_BINARY"]
fn repeated_exec_calls_leave_no_csp_session_132() {
    let dir = tempfile::tempdir().unwrap();
    let before = csp_sessions();

    for _ in 0..5 {
        let out = iad(dir.path())
            .args(["exec", "-n", "USER", "write 1+1"])
            .output()
            .expect("run iad exec");
        assert!(
            out.status.success() && String::from_utf8_lossy(&out.stdout).trim() == "2",
            "iad exec failed: {out:?}"
        );
    }

    let after = csp_sessions();
    assert!(
        after <= before,
        "5 exec calls left {} CSP session(s) on {} ({before} before, {after} after)",
        after - before,
        container()
    );
}

#[test]
#[ignore = "requires live iad-aihub-iris and IAD_BINARY"]
fn a_failed_exec_still_ends_its_session_132() {
    let dir = tempfile::tempdir().unwrap();
    let before = csp_sessions();

    let out = iad(dir.path())
        .args([
            "exec",
            "-n",
            "USER",
            "write $$nosuchlabel^NoSuchRoutine132()",
        ])
        .output()
        .expect("run iad exec");
    assert!(!out.status.success(), "expected a failure: {out:?}");

    let after = csp_sessions();
    assert!(
        after <= before,
        "a failed exec left {} CSP session(s) ({before} before, {after} after)",
        after - before
    );
}

#[cfg(unix)]
#[test]
#[ignore = "requires live iad-aihub-iris and IAD_BINARY"]
fn mcp_stopped_by_sigterm_ends_its_sessions_132() {
    let dir = tempfile::tempdir().unwrap();
    let before = csp_sessions();

    let mut child = iad(dir.path())
        .arg("mcp")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("spawn iad mcp");
    let mut stdin = child.stdin.take().unwrap();
    let mut lines = BufReader::new(child.stdout.take().unwrap()).lines();
    for msg in [
        r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"csp-132","version":"0"}}}"#,
        r#"{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}"#,
        r#"{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"iris_execute","arguments":{"code":"write 1+1","namespace":"USER"}}}"#,
        r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"iris_query","arguments":{"query":"SELECT 1 AS one","namespace":"USER"}}}"#,
    ] {
        writeln!(stdin, "{msg}").unwrap();
    }
    stdin.flush().unwrap();
    let answered = lines
        .by_ref()
        .map_while(Result::ok)
        .any(|l| serde_json::from_str::<serde_json::Value>(&l).is_ok_and(|v| v["id"] == 3));
    assert!(answered, "no response to the iris_query call");
    assert!(
        csp_sessions() > before,
        "the server opened no CSP session, so this test measures nothing"
    );

    let status = Command::new("kill")
        .args(["-TERM", &child.id().to_string()])
        .status()
        .unwrap();
    assert!(status.success());
    let deadline = Instant::now() + Duration::from_secs(15);
    while child.try_wait().unwrap().is_none() {
        if Instant::now() > deadline {
            child.kill().ok(); // allow-kill: SIGTERM already failed
            panic!("iad mcp still running 15 s after SIGTERM");
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    drop(stdin);

    let after = csp_sessions();
    assert!(
        after <= before,
        "iad mcp left {} CSP session(s) after SIGTERM ({before} before, {after} after)",
        after - before
    );
}
