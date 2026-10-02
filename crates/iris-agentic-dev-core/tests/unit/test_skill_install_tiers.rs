//! Which skills `skill install` picks in each mode, and which older installs it reports or prunes.
//! See `test_skill_tiers.rs` for the tiers themselves.

use iris_agentic_dev_core::skill_install::{
    find_leftovers, keep_after_fetch, prune_leftovers, select_paths, InstallMode,
};
use iris_agentic_dev_core::skills::bundled::SkillTier;
use tempfile::TempDir;

fn manifest() -> Vec<String> {
    [
        "objectscript-guardrails",
        "iris-query-plans",
        "brand-new-skill",
    ]
    .iter()
    .map(|n| format!("skills/skills/{n}"))
    .collect()
}

fn names(sel: &[(String, String)]) -> Vec<&str> {
    sel.iter().map(|(n, _)| n.as_str()).collect()
}

const CORE_MD: &str = "---\nname: x\ntier: core\n---\n";
const EXTRA_MD: &str = "---\nname: x\ntier: extra\n---\n";
const INTERNAL_MD: &str = "---\nname: x\ntier: internal\n---\n";
const UNTIERED_MD: &str = "---\nname: x\n---\n";

/// A bare install fetches core skills and any skill this binary does not know yet, since only
/// its frontmatter can say whether it is core.
#[test]
fn core_mode_selects_known_core_and_unknown() {
    let sel = select_paths(&manifest(), &InstallMode::Core);
    assert_eq!(names(&sel), ["objectscript-guardrails", "brand-new-skill"]);
}

#[test]
fn all_mode_selects_everything_in_the_manifest() {
    let sel = select_paths(&manifest(), &InstallMode::All);
    assert_eq!(
        names(&sel),
        [
            "objectscript-guardrails",
            "iris-query-plans",
            "brand-new-skill"
        ]
    );
}

/// A named skill installs at any tier, internal included, even when the manifest does not list it.
#[test]
fn named_mode_installs_any_tier_by_name() {
    let mode = InstallMode::Named(vec![
        "iris-query-plans".into(),
        "opencode-introspect".into(),
    ]);
    let sel = select_paths(&manifest(), &mode);
    assert_eq!(
        sel,
        [
            (
                "iris-query-plans".into(),
                "skills/skills/iris-query-plans".into()
            ),
            (
                "opencode-introspect".into(),
                "skills/skills/opencode-introspect".into()
            ),
        ]
    );
}

#[test]
fn fetched_frontmatter_decides_the_tier() {
    assert!(keep_after_fetch(
        &InstallMode::Core,
        "brand-new-skill",
        CORE_MD
    ));
    assert!(!keep_after_fetch(
        &InstallMode::Core,
        "brand-new-skill",
        EXTRA_MD
    ));
    assert!(!keep_after_fetch(
        &InstallMode::Core,
        "brand-new-skill",
        UNTIERED_MD
    ));
    assert!(keep_after_fetch(
        &InstallMode::All,
        "brand-new-skill",
        EXTRA_MD
    ));
    assert!(keep_after_fetch(
        &InstallMode::All,
        "brand-new-skill",
        UNTIERED_MD
    ));
    assert!(!keep_after_fetch(
        &InstallMode::All,
        "brand-new-skill",
        INTERNAL_MD
    ));
    let named = InstallMode::Named(vec!["opencode-introspect".into()]);
    assert!(keep_after_fetch(&named, "opencode-introspect", INTERNAL_MD));
}

/// `main` before the tier change has no `tier:` lines. The binary's own catalog fills the gap,
/// so a bare install from an older `HEAD` still installs the core skills.
#[test]
fn embedded_tier_covers_untiered_upstream_files() {
    assert!(keep_after_fetch(
        &InstallMode::Core,
        "objectscript-guardrails",
        UNTIERED_MD
    ));
    assert!(!keep_after_fetch(
        &InstallMode::Core,
        "iris-query-plans",
        UNTIERED_MD
    ));
    assert!(!keep_after_fetch(
        &InstallMode::All,
        "opencode-introspect",
        UNTIERED_MD
    ));
}

#[test]
fn mode_wants_matches_the_tiers() {
    assert!(InstallMode::Core.wants(Some(SkillTier::Core)));
    assert!(!InstallMode::Core.wants(Some(SkillTier::Extra)));
    assert!(!InstallMode::Core.wants(None));
    assert!(InstallMode::All.wants(Some(SkillTier::Extra)));
    assert!(InstallMode::All.wants(None));
    assert!(!InstallMode::All.wants(Some(SkillTier::Internal)));
}

fn put(base: &std::path::Path, name: &str, body: &str) -> std::path::PathBuf {
    let p = base.join(name).join("SKILL.md");
    std::fs::create_dir_all(p.parent().unwrap()).unwrap();
    std::fs::write(&p, body).unwrap();
    p
}

const MANAGED: &str = "---\nname: x\nmanaged_by: \"iris-agentic-dev\"\n---\n";
const MINE: &str = "---\nname: x\n---\nmy own notes\n";

/// Leftovers are managed copies of shipped skills the mode would not install. A user-authored
/// file with the same name, a core skill, and a skill this binary does not ship are not leftovers.
#[test]
fn leftovers_are_managed_shipped_skills_outside_the_mode() {
    let tmp = TempDir::new().unwrap();
    let base = tmp.path();
    put(base, "iris-query-plans", MANAGED);
    put(base, "opencode-introspect", MANAGED);
    put(base, "objectscript-guardrails", MANAGED);
    put(base, "iris-vector-ai", MINE);
    put(base, "someone-elses-skill", MANAGED);

    let core: Vec<_> = find_leftovers(&[base.to_path_buf()], &InstallMode::Core)
        .into_iter()
        .map(|(n, _)| n)
        .collect();
    assert_eq!(core, ["iris-query-plans", "opencode-introspect"]);

    let all: Vec<_> = find_leftovers(&[base.to_path_buf()], &InstallMode::All)
        .into_iter()
        .map(|(n, _)| n)
        .collect();
    assert_eq!(all, ["opencode-introspect"]);

    let named = InstallMode::Named(vec!["iris-sql".into()]);
    assert!(find_leftovers(&[base.to_path_buf()], &named).is_empty());
}

#[test]
fn leftovers_tolerate_a_missing_base() {
    let tmp = TempDir::new().unwrap();
    assert!(find_leftovers(&[tmp.path().join("nope")], &InstallMode::Core).is_empty());
}

/// Prune deletes the managed file and its now-empty directory, and leaves everything else.
#[test]
fn prune_removes_only_the_managed_file_and_its_empty_dir() {
    let tmp = TempDir::new().unwrap();
    let base = tmp.path();
    let gone = put(base, "iris-query-plans", MANAGED);
    let kept_dir = put(base, "opencode-introspect", MANAGED);
    std::fs::write(kept_dir.parent().unwrap().join("notes.md"), "mine").unwrap();
    let mine = put(base, "iris-vector-ai", MINE);

    let left = find_leftovers(&[base.to_path_buf()], &InstallMode::Core);
    let results = prune_leftovers(&left, false);
    assert!(results.iter().all(|(_, r)| r.is_ok()), "{results:?}");

    assert!(!gone.exists());
    assert!(!gone.parent().unwrap().exists(), "empty dir should go");
    assert!(!kept_dir.exists());
    assert!(
        kept_dir.parent().unwrap().join("notes.md").exists(),
        "a dir with other files stays"
    );
    assert!(mine.exists(), "user-authored file must stay");
}

#[test]
fn prune_dry_run_deletes_nothing() {
    let tmp = TempDir::new().unwrap();
    let p = put(tmp.path(), "iris-query-plans", MANAGED);
    let left = find_leftovers(&[tmp.path().to_path_buf()], &InstallMode::Core);
    assert_eq!(left.len(), 1);
    let results = prune_leftovers(&left, true);
    assert_eq!(results.len(), 1);
    assert!(p.exists());
}

/// The installer appends the marker at the end of the frontmatter. A skill whose frontmatter runs
/// past 512 bytes (`objectscript-guardrails`, `iris-query-plans`) must still read as managed, or
/// every re-install reports it as user-authored and no leftover hint ever names it.
#[test]
fn marker_after_a_long_frontmatter_still_counts_as_managed() {
    use iris_agentic_dev_core::skill_install::is_managed;
    let tmp = TempDir::new().unwrap();
    let long = format!(
        "---\nname: x\ndescription: {}\nmanaged_by: \"iris-agentic-dev\"\n---\nbody\n",
        "d".repeat(2000)
    );
    let p = put(tmp.path(), "long", &long);
    assert!(is_managed(&p));
    let in_body = format!(
        "---\nname: x\n---\n{}\nmanaged_by: \"iris-agentic-dev\"\n",
        "b".repeat(10)
    );
    let q = put(tmp.path(), "body", &in_body);
    assert!(!is_managed(&q), "a marker in the body is not frontmatter");
}
