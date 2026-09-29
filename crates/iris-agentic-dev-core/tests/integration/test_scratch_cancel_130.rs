//! 130 round 4 (FR-014): a scratch class must not outlive a cancelled execute.
//!
//! `execute_via_generator` deletes its `IrisDevTmp` class on every exit it reaches, but a dropped
//! future reaches none of them. That happens when a tokio runtime shuts down with the call in
//! flight (every in-process test, and `main` returning) and when an MCP client cancels a slow
//! `iris_execute`. After one full test run 122 `IrisDevTel` and 3 `IrisDevRun` classes were left in
//! USER on iris-dev-iris.

use iris_agentic_dev_core::iris::connection::{DiscoverySource, IrisConnection};
use std::collections::BTreeSet;
use std::time::Duration;

fn make_conn() -> Option<IrisConnection> {
    let host = std::env::var("IRIS_HOST").ok().filter(|h| !h.is_empty())?;
    let port = std::env::var("IRIS_WEB_PORT").unwrap_or_else(|_| "52780".to_string());
    Some(IrisConnection::new(
        format!("http://{host}:{port}"),
        "USER",
        std::env::var("IRIS_USERNAME").unwrap_or_else(|_| "_SYSTEM".to_string()),
        std::env::var("IRIS_PASSWORD").unwrap_or_else(|_| "SYS".to_string()),
        DiscoverySource::EnvVar,
    ))
}

/// Names of `IrisDevTmp.<prefix>*` classes in USER, read through docnames (no scratch class of
/// its own, so the count is not disturbed by taking it).
fn scratch_classes(conn: &IrisConnection, prefix: &str) -> BTreeSet<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let url = format!(
            "{}/api/atelier/v1/USER/docnames/CLS?filter=IrisDevTmp.{prefix}%25",
            conn.base_url
        );
        let body: serde_json::Value = IrisConnection::http_client()
            .unwrap()
            .get(&url)
            .basic_auth(&conn.username, Some(&conn.password))
            .send()
            .await
            .expect("docnames")
            .json()
            .await
            .expect("docnames JSON");
        body["result"]["content"]
            .as_array()
            .expect("docnames content")
            .iter()
            .filter_map(|d| d["name"].as_str())
            .filter(|n| n.starts_with(&format!("IrisDevTmp.{prefix}")))
            .map(str::to_string)
            .collect()
    })
}

#[test]
#[ignore = "requires live IRIS (IRIS_HOST)"]
fn a_runtime_dropped_mid_execute_leaves_no_scratch_class_130() {
    let Some(conn) = make_conn() else {
        eprintln!("IRIS_HOST not set, skipping");
        return;
    };
    let before = scratch_classes(&conn, "IrisDevRun");

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    let c = conn.clone();
    rt.block_on(async move {
        // `Hang 5` keeps the query in flight well past the PUT and compile, so the runtime goes
        // away with the class compiled and the delete not yet reached.
        tokio::spawn(async move {
            let client = IrisConnection::http_client().unwrap();
            let _ = c.execute_via_generator("Hang 5", "USER", &client).await;
        });
        tokio::time::sleep(Duration::from_millis(2500)).await;
    });
    drop(rt);

    // Let the server-side call finish so nothing is mid-flight when we look.
    std::thread::sleep(Duration::from_secs(4));
    let leaked: Vec<_> = scratch_classes(&conn, "IrisDevRun")
        .difference(&before)
        .cloned()
        .collect();
    assert!(
        leaked.is_empty(),
        "dropping the runtime mid-execute left {leaked:?}"
    );
}
