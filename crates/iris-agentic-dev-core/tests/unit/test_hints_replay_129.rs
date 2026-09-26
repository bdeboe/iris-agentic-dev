//! Spec 129 FR-006: every replay corpus item, live or mined, gets its labelled rule from the
//! matchers offline, and positives get the placeholder values the loop re-renders with.
//!
//! The captures are real IRIS output (`test_hints_replay_129_live` regenerates the live ones).

use iris_agentic_dev_core::tools::error_hints::{runtime_error_hint, sql_error_hint, Hint};
use std::path::Path;

fn corpus() -> Vec<serde_json::Value> {
    let path =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/e2e/tasks/hints/replay.jsonl");
    std::fs::read_to_string(path)
        .expect("replay.jsonl")
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| serde_json::from_str(l).expect("json line"))
        .collect()
}

fn hint_of(item: &serde_json::Value) -> Option<Hint> {
    let captured = item["captured"].as_str().unwrap();
    let ns = item["namespace"].as_str().unwrap();
    if item["tool"] == "iris_execute" {
        return runtime_error_hint(captured, ns);
    }
    let args = &item["args"];
    let query = match (args["table"].as_str(), args["query"].as_str()) {
        (Some(t), q) => format!("{t} {}", q.unwrap_or("")),
        (None, Some(q)) => q.to_string(),
        _ => String::new(),
    };
    sql_error_hint(captured, &query, ns)
}

#[test]
fn every_corpus_item_gets_its_labelled_rule() {
    let items = corpus();
    assert!(items.len() >= 40, "{} items", items.len());
    let mut problems = Vec::new();
    for item in &items {
        let id = item["id"].as_str().unwrap();
        let want = item["rule"].as_str().unwrap();
        let got = hint_of(item);
        match (got.as_ref().map(|h| h.rule()), want) {
            (None, "none") => {}
            (Some(g), w) if g == w => {}
            (g, w) => problems.push(format!("{id}: expected {w}, got {g:?}")),
        }
    }
    assert!(problems.is_empty(), "{}", problems.join("\n"));
}

/// SC-001: all seven rules have at least one live positive, and there are live negatives.
#[test]
fn every_rule_has_a_live_positive_and_there_are_negatives() {
    let items = corpus();
    let live: Vec<_> = items.iter().filter(|i| i["source"] == "live").collect();
    let mut rules: Vec<&str> = live
        .iter()
        .map(|i| i["rule"].as_str().unwrap())
        .filter(|r| *r != "none")
        .collect();
    rules.sort_unstable();
    rules.dedup();
    assert_eq!(rules.len(), 7, "{rules:?}");
    assert!(live.iter().filter(|i| i["rule"] == "none").count() >= 10);
    for i in &items {
        assert!(
            i["source"] == "live" || i["source"] == "mined",
            "{}",
            i["id"]
        );
    }
}

/// The loop re-renders candidate templates from `vars`, so they must match the matcher's own.
#[test]
fn live_positives_carry_the_matchers_placeholder_values() {
    for item in corpus()
        .iter()
        .filter(|i| i["source"] == "live" && i["rule"] != "none")
    {
        let h = hint_of(item).unwrap();
        let want: serde_json::Map<String, serde_json::Value> = h
            .vars()
            .iter()
            .map(|(k, v)| (k.to_string(), serde_json::Value::String(v.clone())))
            .collect();
        assert_eq!(
            item["vars"],
            serde_json::Value::Object(want),
            "{}",
            item["id"]
        );
        assert!(item["fix"].is_object(), "{} has no fix", item["id"]);
    }
}

#[test]
fn corpus_ids_are_unique() {
    let items = corpus();
    let mut ids: Vec<&str> = items.iter().map(|i| i["id"].as_str().unwrap()).collect();
    ids.sort_unstable();
    let n = ids.len();
    ids.dedup();
    assert_eq!(ids.len(), n);
}

/// Spec 129 skill edits: the sections the hints cite show the errors the hints are for.
#[test]
fn cited_skills_show_the_errors_the_new_hints_cover() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../skills/skills");
    let sql = std::fs::read_to_string(root.join("objectscript-sql-patterns/SKILL.md")).unwrap();
    assert!(
        sql.contains("SQLCODE -29 \"Field 'HELLO' not found"),
        "sql-patterns §7"
    );
    let iad = std::fs::read_to_string(root.join("iris-agentic-dev/SKILL.md")).unwrap();
    assert!(
        iad.contains("SELECT Name FROM Security.Users"),
        "iris-agentic-dev"
    );
    assert!(iad.contains("SQLCODE -30"), "iris-agentic-dev");
}

/// A spawned binary must not inherit the switch from the developer's shell.
#[test]
fn clean_command_strips_the_coding_pack_switch() {
    assert!(iris_agentic_dev_core::testing::BEHAVIOR_ENV_VARS.contains(&"IAD_CODING_PACK"));
}
