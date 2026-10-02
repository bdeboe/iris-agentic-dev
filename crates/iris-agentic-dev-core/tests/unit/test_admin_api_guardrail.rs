//! The guardrails skill's admin-via-API rule. Each fact it names is measured by
//! `tests/integration/test_admin_api_guardrail_live.rs` on iris-dev-iris.

fn guardrails() -> String {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../skills/skills/objectscript-guardrails/SKILL.md");
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

/// Security and Config tables refuse SQL writes, and `%SYS.Task` takes them, so the skill names the
/// class API for each, an `Exists` check before `Create`, and no secrets in output.
#[test]
fn guardrails_carry_the_admin_api_rule() {
    let t = guardrails();
    for want in [
        "**Admin via class API, not SQL**",
        "Security.Users",
        "Security.Roles",
        "Security.Resources",
        "Config.",
        "%SYS.Task",
        "Exists(",
        "-132",
        "-134",
        "#837",
        "Security.Users.Modify(",
        "password",
    ] {
        assert!(
            t.contains(want),
            "objectscript-guardrails must contain {want:?}"
        );
    }
}

/// The description's item count follows the checklist.
#[test]
fn guardrails_description_counts_its_checklist() {
    let t = guardrails();
    let items = t.lines().filter(|l| l.starts_with("- [ ] **")).count();
    let desc = t
        .split("description:")
        .nth(1)
        .and_then(|s| s.split("iris_version:").next())
        .unwrap_or_default();
    assert!(
        desc.contains(&format!("{items}-item")),
        "description must say {items}-item: {desc:?}"
    );
}

/// iad stays generic IRIS.
#[test]
fn guardrails_stay_generic() {
    let t = guardrails();
    for bad in ["HealthShare", "HSLIB", "HSCUSTOM", "Universal Login"] {
        assert!(!t.contains(bad), "objectscript-guardrails names {bad:?}");
    }
}
