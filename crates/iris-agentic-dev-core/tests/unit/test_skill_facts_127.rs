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

/// A file under `skills/` that is not a bundled skill (`compile.md`, `AGENTS.md`).
fn skills_file(rel: &str) -> String {
    let path = skills_dir().join("..").join(rel);
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

/// US2.1. A postfix `Quit:key=""` sharing a line compiles. The space form fails with #1054, not
/// #5559.
#[test]
fn postconditional_claims_match_iris() {
    let loops = skill("objectscript-loop-patterns");
    assert!(
        !loops.contains("#5559"),
        "objectscript-loop-patterns still blames the postconditional forms on #5559"
    );
    assert!(
        !loops.contains("postfix Quit on same line as anything else"),
        "objectscript-loop-patterns still says a postfix Quit cannot share a line"
    );
    assert!(loops.contains("#1054"), "loop-patterns must name #1054");

    let fewshot = skill("objectscript-fewshot-fixes");
    assert!(
        !fewshot.contains("parser error #5559") && !fewshot.contains("causes #5559 parse error"),
        "objectscript-fewshot-fixes still says the spaced postconditional is #5559"
    );
    assert!(fewshot.contains("#1054"), "fewshot-fixes must name #1054");

    assert!(
        !skill("objectscript-guardrails").contains("alone on its own line"),
        "objectscript-guardrails still says a postfix Quit must be alone on its line"
    );
}

/// US2.2. `Quit <value>` in a loop compiles and fails at runtime with `<COMMAND>`; only inside
/// `Try` is it the compile error #1043.
#[test]
fn quit_value_in_loop_claims_match_iris() {
    let tdd = skill("objectscript-tdd");
    assert!(
        !tdd.contains("inside TRY/CATCH or loop "),
        "objectscript-tdd still lists a loop as a cause of the compile error"
    );
    assert!(
        tdd.contains("<COMMAND>"),
        "objectscript-tdd must name the runtime <COMMAND>"
    );

    let loops = skill("objectscript-loop-patterns");
    assert!(
        !loops.contains("method returns \"\"!") && !loops.contains("actually \"\""),
        "objectscript-loop-patterns still says Quit in a loop returns \"\""
    );
    assert!(
        loops.contains("<COMMAND>"),
        "loop-patterns must name <COMMAND>"
    );
    assert!(
        loops.contains("#1043"),
        "loop-patterns must name #1043 for Try"
    );

    let compile = skills_file("compile.md");
    assert!(
        !compile.contains("#5563") && !compile.contains("inside TRY/CATCH or loop"),
        "skills/compile.md still gives #5563 and blames loops for the Quit compile error"
    );
}

/// US2.3. Routines can use `Try/Catch` and `Return`; the checklist listed both as wrong.
#[test]
fn mac_routines_do_not_forbid_try_or_return() {
    let mac = skill("objectscript-mac-routines");
    assert!(
        !mac.contains("| Error trap             | `Try { } Catch e { }`  |"),
        "objectscript-mac-routines still lists Try/Catch as wrong in a routine"
    );
    assert!(
        !mac.contains("| Return from subroutine | `Return`               |"),
        "objectscript-mac-routines still lists Return as wrong in a routine"
    );
}

/// US2.4. `lst_$LB(x)` is the linear form; `$LIST(lst,*+1)` is the one that is slow in a loop.
#[test]
fn list_patterns_label_the_fast_form_correctly() {
    let list = skill("objectscript-list-patterns");
    assert!(
        !list.contains("WRONG — $LISTBUILD creates a new list each iteration"),
        "objectscript-list-patterns still labels concatenation as the O(n²) form"
    );
    assert!(
        list.contains("$LIST(lst, *+1)"),
        "list-patterns must show $LIST(lst, *+1) as the slow form"
    );
}

/// US2.5. The SQL skill follows its own last-dot rule: an underscore form of a two-level class
/// appears only on a line marked wrong, or right under one.
#[test]
fn sql_patterns_follow_their_own_naming_rule() {
    let sql = skill("objectscript-sql-patterns");
    let lines: Vec<&str> = sql.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        for bad in ["Catalog_Item", "Config_Setting", "Bench_Patient"] {
            if line.contains(bad) {
                let marked = |l: &str| l.to_lowercase().contains("wrong");
                assert!(
                    marked(line) || (i > 0 && marked(lines[i - 1])),
                    "objectscript-sql-patterns line {} uses {bad} as if it worked: {line}",
                    i + 1
                );
            }
        }
    }
}

/// US2.6. `%Execute(args...)` returns rows. The skill said `<STACK>` and told agents to
/// concatenate values into the SQL string, which is SQL injection.
#[test]
fn iris_sql_does_not_teach_in_list_concatenation() {
    let sql = skill("iris-sql");
    assert!(
        !sql.contains("<STACK> error!"),
        "iris-sql still says %Execute(args...) raises <STACK>"
    );
    assert!(
        !sql.contains("build the quoted values directly into the SQL string"),
        "iris-sql still recommends concatenating values into SQL"
    );
    assert!(
        !sql.contains("%Execute does NOT accept arrays"),
        "iris-sql still says %Execute does not accept arrays"
    );
    assert!(
        sql.contains("%Execute(args...)"),
        "iris-sql must show %Execute(args...)"
    );
}

/// US2.7. `New $Namespace` is the idiom; only `New` on a plain variable in a procedure block fails.
#[test]
fn review_new_rule_is_narrowed_to_plain_variables() {
    let review = skill("objectscript-review");
    assert!(
        !review.contains("No `New` command inside method/procedure blocks"),
        "objectscript-review still forbids every New"
    );
    assert!(
        review.contains("New $Namespace"),
        "review must allow New $Namespace"
    );
    assert!(review.contains("#1038"), "review must name #1038");
}

/// US2.8. A bare `TROLLBACK` rolls back every level, the caller's included.
#[test]
fn trollback_advice_rolls_back_one_level() {
    for name in ["objectscript-guardrails", "objectscript-review"] {
        let text = skill(name);
        assert!(
            !text.contains("`If $TLevel > 0 { TROLLBACK }`")
                && !text.contains("TRollback checks `$TLevel > 0` first"),
            "{name} still recommends a bare TROLLBACK"
        );
        assert!(
            text.contains("TROLLBACK:$TLevel>entry 1"),
            "{name} must show the one-level form"
        );
    }
    assert!(
        !skills_file("AGENTS.md").contains("If $TLevel > 0 { TRollback }"),
        "skills/AGENTS.md still recommends a bare TRollback"
    );
}

/// US2.9. An unquoted Python name with `_` is ObjectScript concatenation.
#[test]
fn embedded_python_quotes_underscore_names() {
    let py = skill("iris-embedded-python");
    assert!(
        !py.contains("pyobj.my_function(42)"),
        "iris-embedded-python still calls pyobj.my_function unquoted"
    );
    assert!(
        py.contains("pyobj.\"my_function\"(42)"),
        "must show the quoted form"
    );
}
