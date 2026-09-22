//! Spec 123 US1: a tier a tool description names is the tier the call meets.
//!
//! The todo-app demo read "Write actions (require IRIS_WRITE_TOOLS_ENABLED=1): ... create_webapp"
//! in `iris_admin`'s description, called it, and was refused by the destructive gate. The text and
//! `write_gate::CLASSIFICATION` had drifted, and nothing compared them. This file compares them.
//!
//! The grammar is in `specs/123-demo-gap-fixes/research.md` R6. In short: a *claim* is
//! `write|destructive` joined by a space or hyphen to `gated|tier|action(s)`. The claim's clause
//! runs between the nearest `.` or `;` on each side. The claim covers the tool's actions named in
//! that clause, or the whole tool when the clause names none. The underscore is deliberately not a
//! separator, so `IRIS_WRITE_TOOLS_ENABLED` and `destructive_tools_source` are not claims, and
//! `Execute-gated` / `PHI-gated` are different gates that never match.
//!
//! No IRIS connection. The descriptions and the gate table are both properties of the binary.

use std::collections::{BTreeMap, BTreeSet};

use iris_agentic_dev_core::testing::handler_match_arms;
use iris_agentic_dev_core::tools::write_gate::{classify, WriteClass, CLASSIFICATION};
use iris_agentic_dev_core::tools::{IrisTools, Toolset};

/// A failure unit: tool plus action, `-` for the tool as a whole.
type Unit = (String, String);

const WHOLE: &str = "-";

fn claim_re() -> regex::Regex {
    regex::Regex::new(r"(?i)\b(write|destructive)[ -](gated|tier|actions?)\b").expect("claim regex")
}

fn tier_of(word: &str) -> WriteClass {
    if word.eq_ignore_ascii_case("destructive") {
        WriteClass::Destructive
    } else {
        WriteClass::Write
    }
}

/// The resolved tier for `tool` called with `action`, or with no action at all for `WHOLE`.
fn resolve(tool: &str, action: &str) -> Option<WriteClass> {
    if action == WHOLE {
        return classify(tool, None);
    }
    let mut args = serde_json::Map::new();
    args.insert("action".into(), action.into());
    args.insert("mode".into(), action.into());
    classify(tool, Some(&args))
}

/// Every action the tool accepts: the gate table's explicit keys plus the literals its handler
/// branches on. The table alone is not enough. A `mixed()` tool with a destructive default lists
/// only its read-only actions, so the destructive ones exist nowhere but the handler.
fn known_actions(tool: &str) -> BTreeSet<String> {
    let mut out: BTreeSet<String> = BTreeSet::new();
    if let Some(entry) = CLASSIFICATION.iter().find(|e| e.tool == tool) {
        out.extend(entry.actions.iter().map(|(a, _)| a.to_ascii_lowercase()));
        if entry.actions.is_empty() {
            return out;
        }
    }
    out.extend(handler_match_arms(tool, "action"));
    out.extend(handler_match_arms(tool, "mode"));
    out
}

/// `action` appears in `text` as a whole identifier, not inside `delete_user` or `list_keys`.
fn names(text: &str, action: &str) -> bool {
    let is_ident = |c: char| c.is_ascii_alphanumeric() || c == '_';
    let lower = text.to_ascii_lowercase();
    let mut from = 0;
    while let Some(i) = lower[from..].find(action) {
        let start = from + i;
        let end = start + action.len();
        let before = lower[..start].chars().next_back();
        let after = lower[end..].chars().next();
        if !before.is_some_and(is_ident) && !after.is_some_and(is_ident) {
            return true;
        }
        from = end;
    }
    false
}

/// Each claim as (tier, covered actions), where an empty set means the claim is about the tool.
fn claims(description: &str, actions: &BTreeSet<String>) -> Vec<(WriteClass, BTreeSet<String>)> {
    let bounds = |c: char| c == '.' || c == ';';
    claim_re()
        .captures_iter(description)
        .map(|cap| {
            let m = cap.get(0).expect("whole match");
            let start = description[..m.start()]
                .rfind(bounds)
                .map(|i| i + 1)
                .unwrap_or(0);
            let end = description[m.end()..]
                .find(bounds)
                .map(|i| m.end() + i)
                .unwrap_or(description.len());
            let clause = &description[start..end];
            let covered = actions
                .iter()
                .filter(|a| names(clause, a))
                .cloned()
                .collect();
            (tier_of(&cap[1]), covered)
        })
        .collect()
}

fn label(class: Option<WriteClass>) -> &'static str {
    match class {
        Some(WriteClass::ReadOnly) => "read-only",
        Some(WriteClass::Write) => "write",
        Some(WriteClass::Destructive) => "destructive",
        None => "unclassified",
    }
}

/// Every disagreement between the descriptions and the table, as unit → reasons.
fn disagreements() -> BTreeMap<Unit, Vec<String>> {
    let tools = IrisTools::new_with_toolset(None, Toolset::Merged).expect("IrisTools::new");
    let catalogue = tools.tool_catalogue();
    assert!(
        catalogue.len() >= 80,
        "only {} tools in the catalogue; this would be checking a stub surface",
        catalogue.len()
    );

    let mut bad: BTreeMap<Unit, Vec<String>> = BTreeMap::new();
    let mut flag = |tool: &str, action: &str, why: String| {
        bad.entry((tool.to_string(), action.to_string()))
            .or_default()
            .push(why);
    };

    for entry in &catalogue {
        let tool = entry.name.as_str();
        let description = entry.description.as_deref().unwrap_or_default();
        let actions = known_actions(tool);
        let found = claims(description, &actions);

        // Checks 1 and 2: every claim agrees with the table.
        for (tier, covered) in &found {
            if covered.is_empty() {
                let mut targets: Vec<&str> = actions.iter().map(String::as_str).collect();
                if targets.is_empty() {
                    targets.push(WHOLE);
                }
                for action in targets {
                    let resolved = resolve(tool, action);
                    if resolved != Some(WriteClass::ReadOnly) && resolved != Some(*tier) {
                        flag(
                            tool,
                            action,
                            format!(
                                "description says {} for the tool, table resolves {}",
                                label(Some(*tier)),
                                label(resolved)
                            ),
                        );
                    }
                }
            } else {
                for action in covered {
                    let resolved = resolve(tool, action);
                    if resolved != Some(*tier) {
                        flag(
                            tool,
                            action,
                            format!(
                                "description says {}, table resolves {}",
                                label(Some(*tier)),
                                label(resolved)
                            ),
                        );
                    }
                }
            }
        }

        // Check 3: every destructive unit is named destructive.
        let destructive_claims: Vec<&BTreeSet<String>> = found
            .iter()
            .filter(|(t, _)| *t == WriteClass::Destructive)
            .map(|(_, c)| c)
            .collect();
        let whole_tool_destructive = destructive_claims.iter().any(|c| c.is_empty());
        let mut targets: Vec<&str> = actions.iter().map(String::as_str).collect();
        if targets.is_empty() {
            targets.push(WHOLE);
        }
        for action in targets {
            if resolve(tool, action) != Some(WriteClass::Destructive) {
                continue;
            }
            let said = if action == WHOLE {
                whole_tool_destructive
            } else {
                destructive_claims.iter().any(|c| c.contains(action))
                    || (whole_tool_destructive && actions.len() <= 1)
            };
            if !said {
                flag(
                    tool,
                    action,
                    "resolves destructive, description does not say so".to_string(),
                );
            }
        }
    }
    bad
}

/// The action sets this file leans on are read out of handler source. If that read ever came back
/// empty for a dispatcher with a destructive default, check 3 would loop over nothing and pass.
#[test]
fn destructive_default_dispatchers_have_readable_actions() {
    let dispatchers: Vec<&str> = CLASSIFICATION
        .iter()
        .filter(|e| !e.actions.is_empty() && e.default == WriteClass::Destructive)
        .map(|e| e.tool)
        .collect();
    assert!(
        !dispatchers.is_empty(),
        "no mixed() tool with a destructive default; the table changed shape"
    );
    for tool in dispatchers {
        let explicit: BTreeSet<String> = CLASSIFICATION
            .iter()
            .find(|e| e.tool == tool)
            .expect("entry")
            .actions
            .iter()
            .map(|(a, _)| a.to_ascii_lowercase())
            .collect();
        let fall_through: Vec<String> = known_actions(tool)
            .into_iter()
            .filter(|a| !explicit.contains(a))
            .collect();
        assert!(
            !fall_through.is_empty(),
            "{tool}: no actions beyond the table's explicit ones were read from the handler, so \
             the destructive fall-through set is invisible to this test"
        );
    }
}

/// The parser on the phrasings the surface actually uses, so a grammar change shows up here rather
/// than as a silent drop in the count below.
#[test]
fn the_claim_grammar() {
    let acts: BTreeSet<String> = ["get", "set", "delete", "delete_user", "create_webapp"]
        .iter()
        .map(|s| s.to_string())
        .collect();

    let c = claims("get always available; set/delete write-gated.", &acts);
    assert_eq!(c.len(), 1);
    assert_eq!(c[0].0, WriteClass::Write);
    assert_eq!(
        c[0].1,
        ["delete", "set"].iter().map(|s| s.to_string()).collect()
    );

    let c = claims(
        "Destructive actions (require IRIS_DESTRUCTIVE_TOOLS_ENABLED=1): delete_user, create_webapp.",
        &acts,
    );
    assert_eq!(c.len(), 1);
    assert_eq!(c[0].0, WriteClass::Destructive);
    assert!(
        !c[0].1.contains("delete"),
        "delete matched inside delete_user"
    );
    assert!(c[0].1.contains("delete_user") && c[0].1.contains("create_webapp"));

    assert!(claims("Kill a global. WRITE-GATED.", &acts)[0].1.is_empty());
    assert!(claims("reports destructive_tools_source", &acts).is_empty());
    assert!(claims("needs IRIS_WRITE_TOOLS_ENABLED=1", &acts).is_empty());
    assert!(claims("destructive SQL blocked unless force=true", &acts).is_empty());
    assert!(claims("Execute-gated. PHI-gated.", &acts).is_empty());
}

/// FR-001, FR-002, FR-005: no description names a tier the table does not resolve, and every
/// destructive tool and action says destructive.
#[test]
fn descriptions_agree_with_the_gate_table() {
    let bad = disagreements();
    let report: Vec<String> = bad
        .iter()
        .map(|((tool, action), why)| format!("  {tool}:{action} — {}", why.join("; ")))
        .collect();
    assert!(
        bad.is_empty(),
        "{} tool/action units disagree with write_gate::CLASSIFICATION:\n{}",
        bad.len(),
        report.join("\n")
    );
}
