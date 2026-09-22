//! Spec 123: nothing tells an agent to restart iad to pick up a server change.
//!
//! `iris_reload_pool` rebuilds the pool from disk in the running server. `iris_add_server`'s
//! description and the success notes of `iris_add_server` and `iris_remove_server` still said the
//! pool does not hot-reload and to restart iad. An agent in another repo took that at its word,
//! concluded it could not reach its own container without a restart, and stopped using iad.
//!
//! No IRIS connection. The descriptions come from the tool router; the notes are string literals in
//! the handler source, so they are read from the source.

use iris_agentic_dev_core::tools::{IrisTools, Toolset};

const HANDLERS: &str = include_str!("../../src/tools/mod.rs");

/// Phrasings that send an agent to restart the server for a pool change.
fn restart_advice() -> regex::Regex {
    regex::Regex::new(r"(?i)restart iad|does not hot-reload|doesn't hot-reload|no hot-reload")
        .expect("restart regex")
}

#[test]
fn the_restart_regex_matches_what_shipped() {
    let re = restart_advice();
    for bad in [
        "The running pool does not hot-reload; restart iad after adding a server",
        "Restart iad for the pool to include this server.",
        "Restart iad for the pool to reflect the removal.",
    ] {
        assert!(re.is_match(bad), "missed: {bad}");
    }
    for fine in [
        "Hot-reload the IRIS connection pool from disk without restarting iad.",
        "Call iris_reload_pool to make it routable via the `server` param.",
    ] {
        assert!(!re.is_match(fine), "false hit: {fine}");
    }
}

#[test]
fn no_description_says_to_restart_for_a_pool_change() {
    let tools = IrisTools::new_with_toolset(None, Toolset::Merged).expect("IrisTools::new");
    let catalogue = tools.tool_catalogue();
    assert!(
        catalogue.iter().any(|t| t.name == "iris_reload_pool"),
        "iris_reload_pool is gone; this test's premise no longer holds"
    );
    let re = restart_advice();
    let bad: Vec<String> = catalogue
        .iter()
        .filter_map(|t| {
            let d = t.description.as_deref().unwrap_or_default();
            re.find(d).map(|m| format!("{}: {}", t.name, m.as_str()))
        })
        .collect();
    assert!(bad.is_empty(), "descriptions say to restart: {bad:?}");

    for name in ["iris_add_server", "iris_remove_server"] {
        let d = catalogue
            .iter()
            .find(|t| t.name == name)
            .and_then(|t| t.description.as_deref())
            .unwrap_or_else(|| panic!("{name} missing from the catalogue"));
        assert!(
            d.contains("iris_reload_pool"),
            "{name} must name iris_reload_pool as the way to apply the change: {d}"
        );
    }
}

#[test]
fn no_handler_text_says_to_restart_for_a_pool_change() {
    let re = restart_advice();
    let bad: Vec<String> = HANDLERS
        .lines()
        .enumerate()
        .filter(|(_, l)| re.is_match(l))
        .map(|(i, l)| format!("mod.rs:{}: {}", i + 1, l.trim()))
        .collect();
    assert!(
        bad.is_empty(),
        "handler text says to restart:\n{}",
        bad.join("\n")
    );
}
