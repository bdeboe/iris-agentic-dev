//! Spec 127: wording guards for skill claims that IRIS contradicted.
//!
//! Each test pins one correction from `specs/127-skill-fact-fixes/research.md`. It fails if the old
//! wrong wording comes back. The matching live test, showing IRIS doing what the corrected text
//! says, is in `tests/integration/test_skill_facts_127_live.rs`.

use std::path::PathBuf;

fn skills_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../skills/skills")
        .canonicalize()
        .expect("skills/skills must exist in the repo")
}

fn skill(name: &str) -> String {
    let path = skills_dir().join(name).join("SKILL.md");
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

/// US1. `e` is "Delete extent" in `ShowFlags` on 2026.2. The skill called it "display errors only"
/// and put it in a CI recipe, where `Delete` with it wipes a table.
#[test]
fn eval_skill_does_not_call_e_harmless() {
    let text = skill("iris-objectscript-eval");
    assert!(
        !text.contains("display errors only"),
        "iris-objectscript-eval still describes compile flag `e` as \"display errors only\""
    );
    assert!(
        text.contains("delete extent") || text.contains("Delete extent"),
        "iris-objectscript-eval must say what `e` does: delete the extent"
    );
}
