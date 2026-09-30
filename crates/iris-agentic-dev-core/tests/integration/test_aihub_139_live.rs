//! Spec 132: AI Hub claims measured on the licensed 2026.3.0AI.139 instance.
//!
//! Every test here talks to `iad-aihub-iris` through `iad-aihub-webgateway` on 52781, via a spawned
//! iad over HTTP (`testing::aihub_session`). With the instance down each one panics naming the
//! container; `IAD_ALLOW_SKIP=1` turns that into a printed skip. The claims each test backs are in
//! the claim table in `specs/132-aihub-139/research.md`.
//!
//! Run with (quickstart.md):
//!   IAD_BINARY=$PWD/target/debug/iris-agentic-dev IAD_AIHUB_WEB_PORT=52781 \
//!   cargo test --features testing --test integration test_aihub_139 -- \
//!     --include-ignored --test-threads=1

use iris_agentic_dev_core::testing::{
    aihub_env, aihub_session, aihub_vars, answer_text, AihubEnv, McpSession,
};

/// The tool's own JSON, out of the JSON-RPC envelope.
fn payload(answer: &serde_json::Value) -> serde_json::Value {
    let text = answer
        .pointer("/result/content/0/text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_else(|| panic!("no text content in {}", answer_text(answer)));
    serde_json::from_str(text).unwrap_or_else(|e| panic!("content was not JSON ({e}): {text}"))
}

/// A session with the write and destructive gates open, for tests that put and delete classes.
fn writable(env: &AihubEnv) -> McpSession {
    let mut vars = aihub_vars(env);
    vars.push(("IRIS_WRITE_TOOLS_ENABLED".into(), "1".into()));
    vars.push(("IRIS_DESTRUCTIVE_TOOLS_ENABLED".into(), "1".into()));
    McpSession::start(&vars)
}

/// Run ObjectScript over `iris_execute` and return its output; a failed run fails the test.
fn exec(mcp: &mut McpSession, code: &str) -> String {
    let got = payload(&mcp.call("iris_execute", &serde_json::json!({ "code": code })));
    assert_eq!(
        got["success"], true,
        "iris_execute failed for {code:?}: {got}"
    );
    got["output"]
        .as_str()
        .unwrap_or_default()
        .trim()
        .to_string()
}

// ── US1: a 139 instance the tests can reach ─────────────────────────────────

#[test]
#[ignore = "live iad-aihub-iris"]
fn aihub_version_is_139() {
    let Some(env) = aihub_env() else { return };
    let mut mcp = aihub_session(&env);
    let got = payload(&mcp.call("iris_info", &serde_json::json!({"what": "metadata"})));
    let version = got
        .pointer("/result/content/version")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_else(|| panic!("no version in iris_info metadata: {got}"));
    assert!(version.contains("2026.3.0AI"), "{version}");
    assert!(version.contains("Build 139"), "{version}");
}

#[test]
#[ignore = "live iad-aihub-iris"]
fn aihub_has_ai_package() {
    let Some(env) = aihub_env() else { return };
    let mut mcp = aihub_session(&env);
    let got = payload(&mcp.call(
        "iris_query",
        &serde_json::json!({
            "query": "SELECT COUNT(*) AS n FROM %Dictionary.CompiledClass WHERE ID %STARTSWITH '%AI.'"
        }),
    ));
    assert_eq!(got["namespace"], env.namespace, "{got}");
    let n = got
        .pointer("/rows/0/n")
        .and_then(serde_json::Value::as_i64)
        .unwrap_or_else(|| panic!("no count row: {got}"));
    assert!(n >= 60, "%AI classes visible from USER: {n}, want >= 60");
}

const PROBE: &str = "IadAihub139.Probe.cls";
const PROBE_SRC: &str = r#"Class IadAihub139.Probe Extends %AI.Agent
{

ClassMethod Ping() As %String
{
    Quit "pong"
}

}
"#;

/// Deletes the probe class when the test ends, pass or panic.
struct DeleteOnDrop<'a> {
    mcp: &'a mut McpSession,
    doc: &'static str,
}

impl Drop for DeleteOnDrop<'_> {
    fn drop(&mut self) {
        let _ = self.mcp.call(
            "iris_doc",
            &serde_json::json!({"mode": "delete", "name": self.doc}),
        );
    }
}

#[test]
#[ignore = "live iad-aihub-iris"]
fn aihub_http_path() {
    let Some(env) = aihub_env() else { return };
    let mut mcp = writable(&env);
    let guard = DeleteOnDrop {
        mcp: &mut mcp,
        doc: PROBE,
    };
    let put = payload(&guard.mcp.call(
        "iris_doc",
        &serde_json::json!({"mode": "put", "name": PROBE, "content": PROBE_SRC, "compile": true}),
    ));
    assert_eq!(put["success"], true, "put: {put}");
    assert_eq!(
        put["compiled"], true,
        "a %AI.Agent subclass must compile on 139: {put}"
    );

    let run = payload(&guard.mcp.call(
        "iris_execute",
        &serde_json::json!({"code": "Write ##class(IadAihub139.Probe).Ping()"}),
    ));
    assert_eq!(run["execution_path"], "atelier", "{run}");
    assert_eq!(run["output"].as_str().map(str::trim), Some("pong"), "{run}");
    drop(guard);

    let left = payload(&mcp.call(
        "iris_query",
        &serde_json::json!({
            "query": "SELECT COUNT(*) AS n FROM %Dictionary.CompiledClass WHERE ID = 'IadAihub139.Probe'"
        }),
    ));
    assert_eq!(
        left.pointer("/rows/0/n")
            .and_then(serde_json::Value::as_i64),
        Some(0),
        "the probe class must be gone after delete: {left}"
    );
}

// ── US2: the topic map points at files that exist ───────────────────────────

/// One HEAD per recorded path against GitHub raw on `master`. Needs network, not IRIS; a path that
/// upstream moved or deleted since `upstream-files.txt` was recorded fails here, by name.
#[tokio::test]
#[ignore = "live GitHub raw"]
async fn aihub_139_upstream_files() {
    let list = include_str!("../fixtures/aihub139/upstream-files.txt");
    let client = reqwest::Client::new();
    let mut bad = Vec::new();
    let paths: Vec<&str> = list.lines().skip(1).collect();
    assert_eq!(
        paths.len(),
        56,
        "upstream-files.txt holds the 56 paths at 72749d6"
    );
    for path in paths {
        let url = format!(
            "https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/{path}"
        );
        match client.head(&url).send().await {
            Ok(r) if r.status().as_u16() == 200 => {}
            Ok(r) => bad.push(format!("{path}: HTTP {}", r.status().as_u16())),
            Err(e) => bad.push(format!("{path}: {e}")),
        }
    }
    assert!(
        bad.is_empty(),
        "not on ai-hub-eap master:\n{}",
        bad.join("\n")
    );
}
