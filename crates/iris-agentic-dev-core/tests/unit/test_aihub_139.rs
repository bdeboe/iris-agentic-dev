//! Spec 132: AI Hub on EAP build 139 — the parts that need no IRIS.
//!
//! The live half is `tests/integration/test_aihub_139_live.rs`. This file checks the helpers those
//! tests stand on (`AihubEnv`, the probe, the child env) and, from US2 on, the skill text itself.

use iris_agentic_dev_core::testing::{aihub_probe, clean_mcp_command, AihubEnv};
use std::collections::HashMap;
use std::path::Path;

fn vars(pairs: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
    let m: HashMap<String, String> = pairs
        .iter()
        .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
        .collect();
    move |k| m.get(k).cloned()
}

#[test]
fn aihub_env_defaults() {
    let env = AihubEnv::from_vars(vars(&[])).expect("no vars set is valid");
    assert_eq!(env.container, "iad-aihub-iris");
    assert_eq!(env.host, "localhost");
    assert_eq!(env.web_port, 52781);
    assert_eq!(env.namespace, "USER");
}

#[test]
fn aihub_env_overrides() {
    let env = AihubEnv::from_vars(vars(&[
        ("IAD_AIHUB_CONTAINER", "other-iris"),
        ("IAD_AIHUB_HOST", "10.0.0.5"),
        ("IAD_AIHUB_WEB_PORT", "8080"),
        ("IAD_AIHUB_NAMESPACE", "AIHUB"),
    ]))
    .expect("all four set is valid");
    assert_eq!(env.container, "other-iris");
    assert_eq!(env.host, "10.0.0.5");
    assert_eq!(env.web_port, 8080);
    assert_eq!(env.namespace, "AIHUB");
}

#[test]
fn aihub_env_bad_port_names_the_variable() {
    let err = AihubEnv::from_vars(vars(&[("IAD_AIHUB_WEB_PORT", "52781x")]))
        .expect_err("a non-numeric port must be refused");
    assert!(err.contains("IAD_AIHUB_WEB_PORT"), "{err}");
    assert!(err.contains("52781x"), "{err}");
}

/// The message a developer sees when 139 is down: it must say which container and how to start it,
/// or the panic is a dead end.
#[test]
fn aihub_unreachable_message_names_container_and_start() {
    let env = AihubEnv::from_vars(vars(&[])).unwrap();
    let msg = env.unreachable_message("connection refused");
    assert!(msg.contains("iad-aihub-iris"), "{msg}");
    assert!(msg.contains("iad-aihub-webgateway"), "{msg}");
    assert!(
        msg.contains("specs/132-aihub-139/quickstart.md"),
        "names where the start command is: {msg}"
    );
    assert!(msg.contains("docker start"), "{msg}");
    assert!(msg.contains("IAD_ALLOW_SKIP=1"), "{msg}");
    assert!(msg.contains("connection refused"), "keeps the cause: {msg}");
}

/// XII hermetic: the real-turn key must never reach the iad child, even when the test process has
/// it. The child only ever sees what the test adds back.
#[test]
fn clean_mcp_command_removes_openai_key() {
    let cmd = clean_mcp_command(Path::new("/nonexistent/iris-agentic-dev"));
    let removed = cmd
        .get_envs()
        .any(|(k, v)| k == "OPENAI_API_KEY" && v.is_none());
    assert!(
        removed,
        "OPENAI_API_KEY must be env_remove'd from the child"
    );
}

/// T006: nothing listens on port 1, so the probe must fail, and fail with the text that says what
/// to do. No IRIS needed.
#[test]
fn aihub_probe_unreachable_is_an_actionable_error() {
    let env = AihubEnv::from_vars(vars(&[("IAD_AIHUB_WEB_PORT", "1")])).unwrap();
    let err = aihub_probe(&env).expect_err("nothing listens on localhost:1");
    assert!(err.contains("iad-aihub-iris"), "{err}");
    assert!(err.contains("localhost:1"), "{err}");
    assert!(err.contains("quickstart.md"), "{err}");
}
