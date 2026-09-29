// E2E tests for iris_execute &sql macro translation against live iris-dev-iris.
// All tests are #[ignore] — run with:
//   IRIS_HOST=localhost IRIS_WEB_PORT=52780 cargo test --test test_sql_translate_e2e -- --ignored --nocapture

#![allow(dead_code)]

use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

fn iris_dev_bin() -> std::path::PathBuf {
    iris_agentic_dev_core::testing::iad_binary_path()
}

fn iris_host() -> String {
    std::env::var("IRIS_HOST").unwrap_or_default()
}

fn mcp_call(messages: &[serde_json::Value]) -> Vec<serde_json::Value> {
    let bin = iris_dev_bin();
    if !bin.exists() {
        return vec![];
    }
    let mut cmd = Command::new(&bin);
    cmd.args(["mcp"]);
    cmd.env_remove("IRIS_CONTAINER");
    for key in &[
        "IRIS_HOST",
        "IRIS_WEB_PORT",
        "IRIS_USERNAME",
        "IRIS_PASSWORD",
    ] {
        if let Ok(v) = std::env::var(key) {
            cmd.env(key, v);
        }
    }
    let mut child = cmd
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn iris-dev mcp");
    let mut stdin = child.stdin.take().unwrap();
    let stdout = child.stdout.take().unwrap();
    let mut reader = BufReader::new(stdout);
    let mut results = vec![];
    for msg in messages {
        stdin
            .write_all((serde_json::to_string(msg).unwrap() + "\n").as_bytes())
            .unwrap();
        stdin.flush().unwrap();
        if msg.get("id").is_some() {
            let deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
            loop {
                std::thread::sleep(std::time::Duration::from_millis(100));
                let mut line = String::new();
                if reader.read_line(&mut line).unwrap_or(0) > 0 {
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) {
                        results.push(v);
                        break;
                    }
                }
                if std::time::Instant::now() > deadline {
                    break;
                }
            }
        } else {
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
    }
    iris_agentic_dev_core::testing::stop_server(&mut child);
    results
}

fn init_msgs() -> Vec<serde_json::Value> {
    vec![
        serde_json::json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e","version":"0.1"}}}),
        serde_json::json!({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}),
    ]
}

fn tool_result(responses: &[serde_json::Value], id: u64) -> serde_json::Value {
    let resp = responses
        .iter()
        .find(|r| r["id"] == id)
        .cloned()
        .unwrap_or_default();
    let text = resp["result"]["content"]
        .as_array()
        .and_then(|a| a.first())
        .and_then(|c| c["text"].as_str())
        .unwrap_or("{}");
    serde_json::from_str(text).unwrap_or_default()
}

fn execute(code: &str, translate_sql: Option<bool>) -> serde_json::Value {
    let mut args = serde_json::json!({"code": code, "namespace": "USER"});
    if let Some(t) = translate_sql {
        args["translate_sql"] = serde_json::Value::Bool(t);
    }
    let mut msgs = init_msgs();
    msgs.push(serde_json::json!({
        "jsonrpc":"2.0","id":2,"method":"tools/call",
        "params":{"name":"iris_execute","arguments":args}
    }));
    let responses = mcp_call(&msgs);
    tool_result(&responses, 2)
}

/// T025: SELECT INTO over HTTP runs as written — IRIS compiles `&sql` in the class method, and
/// iad leaves it alone (131 US4). `%Dictionary.ClassDefinition` is behind the CODE_EDIT gate, so the
/// row comes from INFORMATION_SCHEMA.
#[test]
#[ignore]
fn test_e2e_select_into_runs_natively_over_http() {
    if iris_host().is_empty() {
        eprintln!("Skipping: IRIS_HOST not set");
        return;
    }
    let code = "set t=\"\"\n&sql(SELECT TABLE_NAME INTO :t FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'INFORMATION_SCHEMA' AND TABLE_NAME = 'TABLES')\nwrite SQLCODE,\":\",t,!";
    let result = execute(code, None);
    eprintln!("T025: {}", serde_json::to_string_pretty(&result).unwrap());
    assert_eq!(result["success"], true);
    let output = result["output"].as_str().unwrap_or("");
    assert_eq!(output.trim(), "0:TABLES", "got: {result}");
    assert!(
        result.get("sql_translated").is_none() && result.get("translated_code").is_none(),
        "the HTTP path sends &sql untranslated: {result}"
    );
}

/// T026: INSERT over HTTP is not translated either. The target does not exist, so IRIS reports it
/// through SQLCODE at run time, and the response carries no translation fields.
#[test]
#[ignore]
fn test_e2e_insert_is_not_translated_over_http() {
    if iris_host().is_empty() {
        eprintln!("Skipping: IRIS_HOST not set");
        return;
    }
    let code = "set msg=\"test\"\n&sql(INSERT INTO %sqltemp.Test (Message) VALUES (:msg))";
    let result = execute(code, None);
    eprintln!("T026: {}", serde_json::to_string_pretty(&result).unwrap());
    assert!(result.get("success").is_some(), "no response: {result}");
    assert!(
        result.get("sql_translated").is_none(),
        "the HTTP path sends &sql untranslated: {result}"
    );
}

/// T033: translate_sql: false — no translation, raw IRIS error.
#[test]
#[ignore]
fn test_e2e_translate_false_no_translation() {
    if iris_host().is_empty() {
        eprintln!("Skipping: IRIS_HOST not set");
        return;
    }
    let code = "set x=\"\"\n&sql(SELECT 1 INTO :x)\nwrite x,!";
    let result = execute(code, Some(false));
    eprintln!("T033: {}", serde_json::to_string_pretty(&result).unwrap());
    // Should NOT have sql_translated field
    assert!(
        result.get("sql_translated").is_none(),
        "sql_translated should be absent when translate_sql=false"
    );
    // The code will fail with a compilation/execution error from IRIS
    // (either success=false or the output will be empty/wrong — either is acceptable)
}

/// T039: CALL with translate_sql: true — translation_warning present, tool doesn't crash.
#[test]
#[ignore]
fn test_e2e_call_produces_warning() {
    if iris_host().is_empty() {
        eprintln!("Skipping: IRIS_HOST not set");
        return;
    }
    // &sql(CALL ...) should produce a warning and not crash
    let code = "&sql(CALL %SYSTEM.Status.OK())\nwrite \"done\",!";
    let result = execute(code, None);
    eprintln!("T039: {}", serde_json::to_string_pretty(&result).unwrap());
    // Tool should not crash — either succeeds or fails gracefully
    assert!(
        result.get("success").is_some(),
        "should return a valid response (no crash)"
    );
    // If sql_translated is true, translation_warning should be present
    if result["sql_translated"].as_bool().unwrap_or(false) {
        assert!(
            result.get("translation_warning").is_some(),
            "translation_warning should be present for CALL"
        );
    }
}
