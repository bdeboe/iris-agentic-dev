//! Spec 129 FR-002 through the shipped binary: `IAD_CODING_PACK=off` in the server's environment
//! drops `hint_ref` from a real hinted error and keeps `hint`.
//!
//! Needs live IRIS for the error itself (iris-dev-iris, `IRIS_HOST` etc.), and `IAD_BINARY`.

use iris_agentic_dev_core::testing::{answer_text, require_iad_binary, McpSession};

fn iris_env() -> Option<Vec<(String, String)>> {
    let host = std::env::var("IRIS_HOST").unwrap_or_default();
    if host.is_empty() {
        if std::env::var("IAD_ALLOW_SKIP").is_ok() {
            eprintln!("SKIP (IAD_ALLOW_SKIP set): IRIS_HOST unset");
            return None;
        }
        panic!("IRIS_HOST unset; set IRIS_HOST=localhost IRIS_WEB_PORT=52780, or IAD_ALLOW_SKIP=1");
    }
    let get = |k: &str, d: &str| std::env::var(k).unwrap_or_else(|_| d.to_string());
    Some(vec![
        ("IRIS_HOST".into(), host),
        ("IRIS_WEB_PORT".into(), get("IRIS_WEB_PORT", "52780")),
        ("IRIS_USERNAME".into(), get("IRIS_USERNAME", "_SYSTEM")),
        ("IRIS_PASSWORD".into(), get("IRIS_PASSWORD", "SYS")),
        ("IRIS_NAMESPACE".into(), "USER".into()),
    ])
}

fn hinted_error(extra: &[(String, String)]) -> serde_json::Value {
    let mut env = iris_env().unwrap();
    env.extend_from_slice(extra);
    let mut session = McpSession::start(&env);
    let answer = session.call(
        "iris_query",
        &serde_json::json!({"query": "SELECT TOP 1 Name FROM Security.Users", "namespace": "USER"}),
    );
    answer
        .pointer("/result/structuredContent")
        .cloned()
        .unwrap_or_else(|| panic!("no structuredContent: {}", answer_text(&answer)))
}

#[test]
#[ignore = "spawns the built binary against live IRIS; run with --include-ignored"]
fn coding_pack_off_in_the_server_env_drops_hint_ref() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    if iris_env().is_none() {
        return;
    }
    let on = hinted_error(&[]);
    let off = hinted_error(&[("IAD_CODING_PACK".into(), "off".into())]);
    assert_eq!(on["hint_ref"]["skill"], "iris-agentic-dev", "{on}");
    assert!(on["hint_ref"]["section"].is_string(), "{on}");
    assert!(off.get("hint_ref").is_none(), "{off}");
    assert!(off["hint"].is_string(), "{off}");
    assert_eq!(on["hint"], off["hint"]);
}
