//! Spec 125: an IRIS error that matches a row in the hint table carries a `hint`; anything else
//! carries none.
//!
//! Every input string below is copied from a live run on iris-dev-iris (spec 125 research R1, R2),
//! not written from memory of what IRIS says.

use iris_agentic_dev_core::tools::error_hints::{
    cited_sections, runtime_error_hint, sql_error_hint,
};
use iris_agentic_dev_core::tools::{IrisTools, Toolset};
use std::path::Path;

const SQL_12_INSERT: &str = "ERROR #5540: SQLCODE: -12 Message:  A term expected, beginning with \
either of:  identifier, constant, aggregate, $$, (, :, +, -, %ALPHAUP, %EXACT, %MVR %SQLSTRING, \
%SQLUPPER, %STRING, %TRUNCATE, or %UPPER^ INSERT INTO DemoB . Todo ( Title , Completed ) VALUES ( $";

const SQL_12_SELECT: &str = "ERROR #5540: SQLCODE: -12 Message:  A term expected, beginning with \
either of:  identifier, constant, aggregate, $$, (, :, +, -, %ALPHAUP, %EXACT, %MVR %SQLSTRING, \
%SQLUPPER, %STRING, %TRUNCATE, or %UPPER^ SELECT $";

fn class_missing(class: &str) -> String {
    format!(
        "ERROR: <CLASS DOES NOT EXIST> 150 Execute+11^IrisDevTmp.IrisDevRun22527a5816fd.1 {class}"
    )
}

// ── SQL ──────────────────────────────────────────────────────────────────────────────────────

#[test]
fn sqlcode_12_at_a_dollar_points_at_current_timestamp_and_the_skill() {
    for msg in [SQL_12_INSERT, SQL_12_SELECT] {
        let hint = sql_error_hint(msg).expect("SQLCODE -12 at `$` has a row");
        assert!(hint.contains("CURRENT_TIMESTAMP"), "{hint}");
        assert!(hint.contains("objectscript-sql-patterns"), "{hint}");
    }
}

#[test]
fn sqlcode_12_elsewhere_gets_no_hint() {
    // The same parser message, but the marker is at a keyword, not at `$`. The expected-terms
    // list itself contains `$$` and `^`, which is why the check reads only what follows the last `^`.
    let msg = SQL_12_SELECT.replace("^ SELECT $", "^ SELECT FROM");
    assert_eq!(sql_error_hint(&msg), None);
}

#[test]
fn a_double_dollar_at_the_marker_is_not_the_objectscript_row() {
    let msg = SQL_12_SELECT.replace("^ SELECT $", "^ SELECT $$");
    assert_eq!(sql_error_hint(&msg), None);
}

#[test]
fn other_sqlcodes_get_no_hint() {
    let msg = "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.NOPE' not found^ SELECT $";
    assert_eq!(sql_error_hint(msg), None);
}

// ── runtime ──────────────────────────────────────────────────────────────────────────────────

#[test]
fn a_system_class_outside_sys_points_at_the_sys_namespace() {
    for class in [
        "Security.Applications",
        "Security.Users",
        "Security.Roles",
        "Config.Namespaces",
        "SYS.Database",
    ] {
        let hint = runtime_error_hint(&class_missing(class), "USER")
            .unwrap_or_else(|| panic!("{class} in USER has a row"));
        assert!(hint.contains(class), "{hint}");
        assert!(hint.contains("\"%SYS\""), "{hint}");
        assert!(hint.contains("iris-agentic-dev"), "{hint}");
    }
}

#[test]
fn already_in_sys_gets_no_hint() {
    for ns in ["%SYS", "%sys"] {
        assert_eq!(
            runtime_error_hint(&class_missing("Security.Applications"), ns),
            None
        );
    }
}

#[test]
fn percent_packages_and_unknown_classes_get_no_hint() {
    // %SYS.* and %SYSTEM.* resolve in every namespace; Nope.Missing fails in %SYS too.
    for class in [
        "%SYS.ProcessQuery",
        "%SYSTEM.Security",
        "Nope.Missing",
        "SYSX.Thing",
    ] {
        assert_eq!(
            runtime_error_hint(&class_missing(class), "USER"),
            None,
            "{class}"
        );
    }
}

#[test]
fn other_runtime_errors_get_no_hint() {
    let out = "ERROR: <UNDEFINED> Execute+3^IrisDevTmp.IrisDevRun1.1 *Security";
    assert_eq!(runtime_error_hint(out, "USER"), None);
}

// ── citations and descriptions ───────────────────────────────────────────────────────────────

/// FR-005: a hint that sends the agent to a section that isn't there is a wrong hint.
#[test]
fn every_cited_skill_section_exists() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    assert!(!cited_sections().is_empty());
    for (skill, heading) in cited_sections() {
        let path = root.join(format!("skills/skills/{skill}/SKILL.md"));
        let text =
            std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        assert!(
            text.lines()
                .any(|l| l.trim_start_matches('#').trim() == *heading),
            "{skill}/SKILL.md has no heading {heading:?}"
        );
    }
}

/// FR-006: the description gets it right before the first error does.
#[test]
fn iris_execute_description_names_the_sys_only_packages() {
    let tools = IrisTools::new_with_toolset(None, Toolset::Merged).expect("IrisTools::new");
    let desc = tools
        .tool_catalogue()
        .into_iter()
        .find(|e| e.name == "iris_execute")
        .and_then(|e| e.description)
        .expect("iris_execute is registered");
    for needle in ["Security.*", "Config.*", "SYS.*", "namespace: \"%SYS\""] {
        assert!(
            desc.contains(needle),
            "iris_execute description lacks {needle:?}"
        );
    }
}
