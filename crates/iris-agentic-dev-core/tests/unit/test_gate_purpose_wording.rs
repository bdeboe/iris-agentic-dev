//! Spec 123 follow-ups (d), (f), (g2): what each gate is for, said where an agent reads it.
//!
//! - (f) `iris_admin` checks `IRIS_ADMIN_TOOLS` inside ten handlers, after `call_tool` has passed
//!   them on their tier. The description must list exactly those ten, and `docs/connecting.md`
//!   must name the variable.
//! - (d) The destructive tier is an accident guard for tool calls. `iris_execute` runs arbitrary
//!   code at the write tier, so its description says so and names the real hard limit: an IRIS
//!   user without delete privileges. (Principle VI says the same, but `.specify/` is not tracked,
//!   so no test here can read it.)
//! - (g2) `NOPWS_ATELIER_REQUIRED` says what still works under `docker_only`.
//!
//! No IRIS connection.

use std::collections::BTreeSet;

use iris_agentic_dev_core::tools::nopws::nopws_atelier_required_error;
use iris_agentic_dev_core::tools::{IrisTools, Toolset};

const ADMIN_SRC: &str = include_str!("../../src/tools/admin.rs");
const CONNECTING: &str = include_str!("../../../../docs/connecting.md");

fn description(tool: &str) -> String {
    let tools = IrisTools::new_with_toolset(None, Toolset::Merged).expect("IrisTools::new");
    tools
        .tool_catalogue()
        .into_iter()
        .find(|t| t.name == tool)
        .and_then(|t| t.description)
        .unwrap_or_else(|| panic!("{tool} missing from the catalogue"))
}

/// Actions whose handler calls `admin_write_allowed()`: `admin_<action>_impl` in `admin.rs`.
fn admin_gated_actions() -> BTreeSet<String> {
    let fn_re = regex::Regex::new(r"^pub async fn admin_([a-z_]+)_impl\(").expect("fn regex");
    let mut current: Option<String> = None;
    let mut out = BTreeSet::new();
    for line in ADMIN_SRC.lines() {
        // A test module sits between the handlers; nothing in it is a handler.
        if line.starts_with("#[cfg(test)]") {
            current = None;
        }
        if let Some(c) = fn_re.captures(line) {
            current = Some(c[1].to_string());
        } else if line.contains("if !admin_write_allowed()") {
            if let Some(name) = &current {
                out.insert(name.clone());
            }
        }
    }
    out
}

#[test]
fn the_admin_gate_is_listed_action_by_action() {
    let gated = admin_gated_actions();
    assert_eq!(
        gated.len(),
        10,
        "expected ten IRIS_ADMIN_TOOLS-gated handlers, found {gated:?}"
    );

    let d = description("iris_admin");
    let sentence = d
        .split(". ")
        .find(|s| s.contains("IRIS_ADMIN_TOOLS=1"))
        .unwrap_or_else(|| panic!("iris_admin names no IRIS_ADMIN_TOOLS=1: {d}"));
    let ident = regex::Regex::new(r"\b[a-z]+(?:_[a-z]+)+\b").expect("ident regex");
    let named: BTreeSet<String> = ident
        .find_iter(sentence)
        .map(|m| m.as_str().to_string())
        .collect();
    assert_eq!(
        named, gated,
        "the IRIS_ADMIN_TOOLS sentence must list exactly the gated actions: {sentence}"
    );
}

#[test]
fn connecting_names_the_admin_gate() {
    assert!(
        CONNECTING.contains("IRIS_ADMIN_TOOLS"),
        "docs/connecting.md must say that iris_admin needs IRIS_ADMIN_TOOLS=1 for its admin actions"
    );
}

#[test]
fn iris_execute_says_the_destructive_gate_is_not_a_boundary() {
    let d = description("iris_execute");
    for needle in ["destructive gate", "IRIS user without delete privileges"] {
        assert!(
            d.contains(needle),
            "iris_execute must say its code is outside the destructive gate and name the hard \
             limit ({needle:?} missing): {d}"
        );
    }
}

#[test]
fn the_nopws_error_says_what_still_works() {
    let v = nopws_atelier_required_error();
    let msg = v["error"].as_str().expect("error string");
    for needle in ["iris_execute", "iris_compile", ".mac"] {
        assert!(
            msg.contains(needle),
            "NOPWS_ATELIER_REQUIRED must name {needle:?}: {msg}"
        );
    }
}
