//! Spec 123: a server added or removed in a running iad is routable after `iris_reload_pool`, with
//! no restart, and the add/remove answers say so.
//!
//! No IRIS. `HOME` is a temp directory, so the registry is a throwaway `servers.json`. The server
//! points at `127.0.0.1:1`, which nothing answers; the test is about the pool, not the instance.

use iris_agentic_dev_core::testing::{answer_text, require_iad_binary, McpSession};

const NAME: &str = "iad123-reload";

fn note(answer: &serde_json::Value) -> String {
    let text = answer
        .pointer("/result/content/0/text")
        .and_then(|t| t.as_str())
        .unwrap_or_else(|| panic!("no text in: {answer}"));
    let v: serde_json::Value =
        serde_json::from_str(text).unwrap_or_else(|e| panic!("not JSON ({e}): {text}"));
    v.get("note")
        .and_then(|n| n.as_str())
        .unwrap_or_else(|| panic!("no note in: {text}"))
        .to_string()
}

fn listed(session: &mut McpSession) -> bool {
    let answer = session.call("iris_servers", &serde_json::json!({}));
    answer_text(&answer).contains(NAME)
}

#[test]
#[ignore = "spawns the built binary; run with --include-ignored"]
fn a_server_change_is_applied_by_reload_without_a_restart() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let home = tempfile::tempdir().expect("tempdir");
    let mut session = McpSession::start(&[
        (
            "HOME".to_string(),
            home.path().to_string_lossy().to_string(),
        ),
        ("IRIS_WRITE_TOOLS_ENABLED".to_string(), "1".to_string()),
        (
            "IRIS_DESTRUCTIVE_TOOLS_ENABLED".to_string(),
            "1".to_string(),
        ),
    ]);

    let added = session.call(
        "iris_add_server",
        &serde_json::json!({
            "name": NAME, "host": "127.0.0.1", "port": 1, "namespace": "USER",
            "username": "_SYSTEM", "password": "not-a-real-credential"
        }),
    );
    let n = note(&added);
    assert!(
        n.contains("iris_reload_pool") && !n.to_lowercase().contains("restart"),
        "the add note must point at iris_reload_pool, not a restart: {n}"
    );

    session.call("iris_reload_pool", &serde_json::json!({}));
    assert!(
        listed(&mut session),
        "after iris_reload_pool the added server must be in the running pool"
    );

    let removed = session.call("iris_remove_server", &serde_json::json!({"name": NAME}));
    let n = note(&removed);
    assert!(
        n.contains("iris_reload_pool") && !n.to_lowercase().contains("restart"),
        "the remove note must point at iris_reload_pool, not a restart: {n}"
    );

    session.call("iris_reload_pool", &serde_json::json!({}));
    assert!(
        !listed(&mut session),
        "after iris_reload_pool the removed server must be gone from the running pool"
    );
}
