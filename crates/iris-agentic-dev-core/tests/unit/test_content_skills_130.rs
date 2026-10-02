//! Spec 130: wording guards for the content skills.
//!
//! Each test pins one row of `specs/130-content-skills/research.md`. It fails if the old wrong text
//! returns or the new content goes missing. The live proof for each row is in
//! `tests/integration/test_content_skills_130_live.rs`.

use std::path::PathBuf;

fn repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root must exist")
}

fn read(rel: &str) -> String {
    let path = repo().join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

fn skill(name: &str) -> String {
    read(&format!("skills/skills/{name}/SKILL.md"))
}

fn lacks(name: &str, text: &str, bad: &[&str]) {
    for b in bad {
        assert!(!text.contains(b), "{name} still contains {b:?}");
    }
}

fn has(name: &str, text: &str, good: &[&str]) {
    for g in good {
        assert!(text.contains(g), "{name} must contain {g:?}");
    }
}

/// R1. A fetch-time error shows up only in `%Next`'s status or in `%SQLCODE` after the loop.
#[test]
fn sql_patterns_check_the_fetch_and_the_prepare() {
    let t = skill("objectscript-sql-patterns");
    lacks("objectscript-sql-patterns", &t, &["Do stmt.%Prepare("]);
    has(
        "objectscript-sql-patterns",
        &t,
        &["%Next(.tSC)", "-400", "after the loop"],
    );
}

/// R3. The tool is `iris_test`, and the pattern that runs one class starts with a colon. Only
/// `Test*` methods run, and a run of nothing still says `All PASSED`.
#[test]
fn unit_test_skill_names_real_tools_and_patterns() {
    let t = skill("objectscript-unit-test");
    lacks(
        "objectscript-unit-test",
        &t,
        &[
            "objectscript_iris_test",
            "objectscript_iris_generate_test",
            "objectscript_docs_introspect",
            "objectscript_iris_compile",
            "Test.MyApp.*",
            "path to generated .cls file",
        ],
    );
    has(
        "objectscript-unit-test",
        &t,
        &[
            "iris_test(pattern=\":",
            "iris_generate_test",
            "iris_doc(mode=\"put\"",
            "All PASSED",
            "NO_TESTS_FOUND",
            "start with `Test`",
        ],
    );
}

/// R3. The eval and coverage skills showed package patterns that find no tests.
#[test]
fn eval_and_coverage_use_the_colon_class_pattern() {
    let e = skill("iris-objectscript-eval");
    lacks(
        "iris-objectscript-eval",
        &e,
        &[
            "pattern=\"MyPackage.Tests.*\"",
            "pattern=\"MyPackage.Tests.MyClassTest\"",
        ],
    );
    has("iris-objectscript-eval", &e, &["iris_test(pattern=\":"]);

    let c = skill("objectscript-coverage");
    lacks("objectscript-coverage", &c, &["pattern=\"MyApp.Tests\","]);
    has("objectscript-coverage", &c, &["pattern=\":"]);
}

/// R4. A typo'd local and a dynamic call to a missing method both compile clean.
#[test]
fn tdd_says_a_clean_compile_is_not_a_test() {
    let t = skill("objectscript-tdd");
    has(
        "objectscript-tdd",
        &t,
        &["compiles clean", "<UNDEFINED>", "<METHOD DOES NOT EXIST>"],
    );
}

/// R6. `GetProductionState` and `$$$EnsProductionRunning` do not exist.
#[test]
fn ensemble_production_uses_real_director_calls() {
    let t = skill("ensemble-production");
    lacks(
        "ensemble-production",
        &t,
        &["GetProductionState(", "$$$EnsProductionRunning"],
    );
    has(
        "ensemble-production",
        &t,
        &[
            "GetProductionStatus(",
            "IsProductionRunning(",
            "ErrProductionAlreadyRunning",
            "NetworkStopped",
        ],
    );
}

/// R2. `New $NAMESPACE` before switching, so the caller's namespace comes back.
#[test]
fn guardrails_carry_the_namespace_rule() {
    let t = skill("objectscript-guardrails");
    has("objectscript-guardrails", &t, &["New $NAMESPACE"]);
}

/// R7. An XML export goes on under its `.cls` name, with the XML declaration on its own line.
#[test]
fn iris_agentic_dev_says_how_to_load_an_xml_export() {
    let t = skill("iris-agentic-dev");
    has(
        "iris-agentic-dev",
        &t,
        &["XML export", "#16006", "#16021", "own line"],
    );
}

/// R5. The new skill carries the plan facts the live tests check.
#[test]
fn query_plans_skill_exists_with_its_facts() {
    let t = skill("iris-query-plans");
    assert!(
        t.starts_with("---\nname: iris-query-plans\n"),
        "iris-query-plans frontmatter must open with its name"
    );
    has(
        "iris-query-plans",
        &t,
        &[
            "Read master map",
            "Read index map",
            "%BuildIndices",
            "%NOINDEX",
            "TUNE TABLE",
            "outlier",
        ],
    );
}

/// The Statistics section. Each line is held by a test in `test_query_stats_139_live.rs`. The
/// docs' TUNE TABLE page still says it writes the class and recompiles cached queries, which 139
/// does not do, so the skill must not repeat that.
#[test]
fn query_plans_has_the_statistics_facts_139_holds() {
    let t = skill("iris-query-plans");
    has(
        "iris-query-plans",
        &t,
        &[
            "## Statistics: fixed and collected",
            "DROP FIXED STATISTICS",
            "FIX STATISTICS",
            "SetExtentSize",
            "$SYSTEM.SQL.Stats.Table.Export",
            "$SYSTEM.SQL.Stats.Table.Import",
            "ClearTableStats",
            "INFORMATION_SCHEMA.STATEMENTS",
            "%SYS.Task.AutoStatsCollection",
            "RSQL_tunetable",
            "GSOD_opttable",
        ],
    );
    lacks(
        "iris-query-plans",
        &t,
        &[
            "recompiles all cached queries",
            "`TUNE TABLE Pkg.Orders` gathers selectivity and extent size, and the planner uses them",
        ],
    );
}

/// Round 3, SKILL-13. "Run `%BuildIndices` after a `%NOINDEX` bulk load" read as a one-off admin
/// step: all three skill-arm sessions rebuilt the index by hand, and the loader's next run emptied it
/// again. The skill now says the loader has to call it, and that a rebuild by hand does not last.
#[test]
fn query_plans_puts_the_rebuild_in_the_loader() {
    let t = skill("iris-query-plans");
    lacks(
        "iris-query-plans",
        &t,
        &["Run `%BuildIndices` after a `%NOINDEX` bulk load."],
    );
    has(
        "iris-query-plans",
        &t,
        &[
            "the method that does the `INSERT %NOINDEX` has to call `%BuildIndices`",
            "A rebuild by hand lasts until the next load",
        ],
    );
}

/// FR-003. Every list of bundled skills names the new one. `cmd/skill.rs` no longer keeps a
/// list: `skill list` and `skill status` read the embedded catalog (`test_skill_tiers.rs`).
#[test]
fn query_plans_skill_is_registered_everywhere() {
    for rel in [
        "crates/iris-agentic-dev-core/src/skills/bundled.rs",
        "skills.sh.json",
        "iris-agentic-dev.toml",
        "skills/iris-dev.toml",
        "skills/README.md",
        "docs/skills.md",
    ] {
        assert!(
            read(rel).contains("iris-query-plans"),
            "{rel} does not list iris-query-plans"
        );
    }
}

/// FR-007. Clean-room: nothing HealthShare-specific in the new or edited text.
#[test]
fn content_skills_stay_generic() {
    for name in [
        "iris-query-plans",
        "objectscript-sql-patterns",
        "objectscript-unit-test",
        "ensemble-production",
    ] {
        let t = skill(name);
        lacks(name, &t, &["HealthShare", "HSLIB", "HSCUSTOM"]);
    }
}
