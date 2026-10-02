//! Table statistics on 2026.3.0AI.139: fixed against collected, what TUNE TABLE writes, when a
//! cached plan changes, and the Export/Clear/Import round trip. Each test backs a claim in the
//! Statistics section of `skills/skills/iris-query-plans/SKILL.md`; a claim that fails here
//! comes out of the skill.
//!
//! The docs (RSQL_tunetable, GSOD_opttable) still describe the pre-2025.2 model, where TUNE
//! TABLE writes extent size and selectivity into the class and recompiles cached queries. On
//! 139 it writes a collected set only, and the plan changes at the next prepare.
//!
//! Each test builds `IadLiveStats139.T` and drops it. Run with:
//!   IAD_BINARY=$PWD/target/debug/iris-agentic-dev IAD_AIHUB_WEB_PORT=52781 \
//!   cargo test --features testing --test integration test_query_stats_139 -- \
//!     --include-ignored --test-threads=1

use std::collections::HashMap;

use iris_agentic_dev_core::testing::{aihub_env, aihub_vars, answer_text, AihubEnv, McpSession};

const TEARDOWN: &str =
    r#" Do ##class(%SQL.Statement).%ExecDirect(,"DROP TABLE IF EXISTS IadLiveStats139.T")"#;

/// 2000 rows, 1% of them `Flag = 'Y'`, then TUNE TABLE. A table this small is read in full, so
/// the collected extent size is exactly 2000.
const BUILD: &str = r#" Do ##class(%SQL.Statement).%ExecDirect(,"DROP TABLE IF EXISTS IadLiveStats139.T")
 Set r=##class(%SQL.Statement).%ExecDirect(,"CREATE TABLE IadLiveStats139.T (ID1 INT, Flag VARCHAR(10), Name VARCHAR(50))")
 Write "create=",r.%SQLCODE,!
 Set ins=##class(%SQL.Statement).%New() Do ins.%Prepare("INSERT INTO IadLiveStats139.T (ID1,Flag,Name) VALUES (?,?,?)")
 For i=1:1:2000 { Set x=ins.%Execute(i,$Select(i#100=0:"Y",1:"N"),"n"_(i#37)) }
 Set r=##class(%SQL.Statement).%ExecDirect(,"TUNE TABLE IadLiveStats139.T")
 Write "tune=",r.%SQLCODE,!"#;

/// Writes `<tag>_cost=` and `<tag>_outlier=` for one EXPLAIN. `Flag = 'Y'` is the query whose
/// plan reads the collected outlier selectivity, so the outlier line tells which set it used.
fn explain(tag: &str) -> String {
    format!(
        r#" Set r=##class(%SQL.Statement).%ExecDirect(,"EXPLAIN SELECT Name FROM IadLiveStats139.T WHERE Flag = 'Y'") Do r.%Next() Set p=r.%GetData(1)
 Write "{tag}_cost=",$ZStrip($Piece($Piece(p,"Cost: ",2),$Char(10)),"<>W"),!
 Write "{tag}_outlier=",(p["outlier selectivity"),!"#
    )
}

/// Writes `<tag>_fixed=`: the extent size in the class storage, which is the fixed set.
fn fixed(tag: &str) -> String {
    format!(
        r#" Set r=##class(%SQL.Statement).%ExecDirect(,"SELECT ExtentSize FROM %Dictionary.StorageDefinition WHERE parent='IadLiveStats139.T'") Do r.%Next()
 Write "{tag}_fixed=[",r.ExtentSize,"]",!"#
    )
}

/// Writes `<tag>_collected=`: the extent size of the latest collected set, from Export type 2.
fn collected(tag: &str) -> String {
    format!(
        r#" Set cf="/tmp/iad-stats139-{tag}.xml" Set sc=$SYSTEM.SQL.Stats.Table.Export(cf,"IadLiveStats139","T",0,2)
 Set s=##class(%Stream.FileCharacter).%New() Do s.LinkToFile(cf) Set v=""
 While 's.AtEnd {{ Set l=s.ReadLine() If l["<extentsize>" {{ Set v=$Piece($Piece(l,"<extentsize>",2),"<") }} }}
 Write "{tag}_collected=[",v,"]",!"#
    )
}

fn payload(answer: &serde_json::Value) -> serde_json::Value {
    let text = answer
        .pointer("/result/content/0/text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_else(|| panic!("no text content in {}", answer_text(answer)));
    serde_json::from_str(text).unwrap_or_else(|e| panic!("content was not JSON ({e}): {text}"))
}

/// A session that owns `IadLiveStats139.T`: built on start, dropped on drop.
struct Stats {
    mcp: McpSession,
}

impl Stats {
    fn new(env: &AihubEnv) -> Self {
        let mut vars = aihub_vars(env);
        vars.push(("IRIS_WRITE_TOOLS_ENABLED".into(), "1".into()));
        vars.push(("IRIS_DESTRUCTIVE_TOOLS_ENABLED".into(), "1".into()));
        let mut s = Self {
            mcp: McpSession::start(&vars),
        };
        let m = s.kv(BUILD);
        assert_eq!(get(&m, "create"), "0", "{m:?}");
        assert_eq!(get(&m, "tune"), "0", "{m:?}");
        s
    }

    /// Run `code` over iris_execute and read its `key=value` lines.
    fn kv(&mut self, code: &str) -> HashMap<String, String> {
        let got = payload(
            &self
                .mcp
                .call("iris_execute", &serde_json::json!({ "code": code })),
        );
        assert_eq!(got["success"], true, "iris_execute failed: {got}");
        got["output"]
            .as_str()
            .unwrap_or_default()
            .lines()
            .filter_map(|l| l.split_once('='))
            .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
            .collect()
    }
}

impl Drop for Stats {
    fn drop(&mut self) {
        let _ = self
            .mcp
            .call("iris_execute", &serde_json::json!({ "code": TEARDOWN }));
    }
}

fn get<'a>(m: &'a HashMap<String, String>, k: &str) -> &'a str {
    m.get(k)
        .unwrap_or_else(|| panic!("no {k}= line in {m:?}"))
        .as_str()
}

fn cost(m: &HashMap<String, String>, tag: &str) -> f64 {
    let k = format!("{tag}_cost");
    get(m, &k)
        .parse()
        .unwrap_or_else(|_| panic!("{k} is not a number in {m:?}"))
}

/// TUNE TABLE writes a collected set and leaves the class storage alone. A DDL table starts with
/// no fixed extent size, and Export type 1 then reports the 100000 default rather than nothing.
#[test]
#[ignore = "live iad-aihub-iris"]
fn query_stats_139_tune_writes_collected_not_fixed() {
    let Some(env) = aihub_env() else { return };
    let mut s = Stats::new(&env);
    let m = s.kv(&format!(
        "{}\n{}\n{}",
        fixed("t"),
        collected("t"),
        r#" Set f="/tmp/iad-stats139-type1.xml" Set sc=$SYSTEM.SQL.Stats.Table.Export(f,"IadLiveStats139","T",0,1)
 Set s=##class(%Stream.FileCharacter).%New() Do s.LinkToFile(f) Set v=""
 While 's.AtEnd { Set l=s.ReadLine() If l["<extentsize>" { Set v=$Piece($Piece(l,"<extentsize>",2),"<") } }
 Write "type1=[",v,"]",!"#
    ));
    assert_eq!(get(&m, "t_fixed"), "[]", "TUNE wrote no fixed set: {m:?}");
    assert_eq!(get(&m, "t_collected"), "[2000]", "{m:?}");
    assert_eq!(get(&m, "type1"), "[100000]", "{m:?}");
}

/// A fixed set wins over a collected one, whole: the plan costs the fixed extent size and loses
/// the collected outlier selectivity. TUNE TABLE does not replace it. DROP FIXED STATISTICS
/// brings the collected plan back, and FIX STATISTICS copies the collected set into the class.
#[test]
#[ignore = "live iad-aihub-iris"]
fn query_stats_139_fixed_beats_collected() {
    let Some(env) = aihub_env() else { return };
    let mut s = Stats::new(&env);
    let m = s.kv(&[
        explain("a"),
        r#" Do $SYSTEM.SQL.Stats.Table.SetExtentSize("IadLiveStats139","T",5000000)"#.into(),
        explain("b"),
        r#" Do ##class(%SQL.Statement).%ExecDirect(,"TUNE TABLE IadLiveStats139.T")"#.into(),
        fixed("c"),
        explain("c"),
        r#" Set r=##class(%SQL.Statement).%ExecDirect(,"ALTER TABLE IadLiveStats139.T DROP FIXED STATISTICS") Write "drop=",r.%SQLCODE,!"#.into(),
        fixed("d"),
        explain("d"),
        r#" Set r=##class(%SQL.Statement).%ExecDirect(,"ALTER TABLE IadLiveStats139.T FIX STATISTICS") Write "fix=",r.%SQLCODE,!"#.into(),
        fixed("e"),
    ]
    .join("\n"));

    // Collected only: the plan uses the outlier selectivity TUNE found on Flag.
    assert_eq!(get(&m, "a_outlier"), "1", "{m:?}");
    // Fixed 5,000,000 against collected 2000: cost follows the fixed figure, outlier gone.
    assert!(cost(&m, "b") > 100.0 * cost(&m, "a"), "{m:?}");
    assert_eq!(get(&m, "b_outlier"), "0", "{m:?}");
    // TUNE with a fixed set present leaves it, and the plan, where they were.
    assert_eq!(get(&m, "c_fixed"), "[5000000]", "{m:?}");
    assert_eq!(cost(&m, "c"), cost(&m, "b"), "{m:?}");
    // DROP FIXED STATISTICS: storage empty, collected plan back.
    assert_eq!(get(&m, "drop"), "0", "{m:?}");
    assert_eq!(get(&m, "d_fixed"), "[]", "{m:?}");
    assert_eq!(cost(&m, "d"), cost(&m, "a"), "{m:?}");
    assert_eq!(get(&m, "d_outlier"), "1", "{m:?}");
    // FIX STATISTICS pins the collected set in the class.
    assert_eq!(get(&m, "fix"), "0", "{m:?}");
    assert_eq!(get(&m, "e_fixed"), "[2000]", "{m:?}");
}

/// TUNE TABLE does not touch a cached plan when it runs. The next prepare of the same text
/// replans, which `INFORMATION_SCHEMA.STATEMENTS.Timestamp` shows; a re-prepare with no TUNE in
/// between reuses the cached plan.
#[test]
#[ignore = "live iad-aihub-iris"]
fn query_stats_139_tune_replans_at_next_prepare() {
    let Some(env) = aihub_env() else { return };
    let mut s = Stats::new(&env);
    let m = s.kv(
        r#" Set q="SELECT Name FROM IadLiveStats139.T WHERE Name = ?"
 Set st=##class(%SQL.Statement).%New() Do st.%Prepare(q) Do st.%GetImplementationDetails(.cn) Set x=st.%Execute("n1")
 Set r=##class(%SQL.Statement).%ExecDirect(,"SELECT Statement FROM INFORMATION_SCHEMA.STATEMENT_LOCATIONS WHERE Location = ?",cn_".1") Do r.%Next() Set h=r.%GetData(1)
 Set tq="SELECT Timestamp FROM INFORMATION_SCHEMA.STATEMENTS WHERE Hash = ?"
 Set r=##class(%SQL.Statement).%ExecDirect(,tq,h) Do r.%Next() Set t1=r.%GetData(1)
 Hang 1
 Set st=##class(%SQL.Statement).%New() Do st.%Prepare(q) Set x=st.%Execute("n1")
 Set r=##class(%SQL.Statement).%ExecDirect(,tq,h) Do r.%Next() Set t2=r.%GetData(1)
 Hang 1
 Do ##class(%SQL.Statement).%ExecDirect(,"TUNE TABLE IadLiveStats139.T")
 Set r=##class(%SQL.Statement).%ExecDirect(,tq,h) Do r.%Next() Set t3=r.%GetData(1)
 Set st=##class(%SQL.Statement).%New() Do st.%Prepare(q) Set x=st.%Execute("n1")
 Set r=##class(%SQL.Statement).%ExecDirect(,tq,h) Do r.%Next() Set t4=r.%GetData(1)
 Write "hash=",(h'=""),!
 Write "reprepare_same=",(t2=t1),!
 Write "tune_same=",(t3=t2),!
 Write "after_tune_new=",(t4]]t3),!"#,
    );
    assert_eq!(get(&m, "hash"), "1", "no statement row: {m:?}");
    assert_eq!(get(&m, "reprepare_same"), "1", "{m:?}");
    assert_eq!(get(&m, "tune_same"), "1", "{m:?}");
    assert_eq!(get(&m, "after_tune_new"), "1", "{m:?}");
}

/// Export type 1 then Import restores a fixed set. ClearTableStats clears the fixed set and
/// leaves the collected one.
#[test]
#[ignore = "live iad-aihub-iris"]
fn query_stats_139_export_clear_import() {
    let Some(env) = aihub_env() else { return };
    let mut s = Stats::new(&env);
    let m = s.kv(&[
        r#" Do ##class(%SQL.Statement).%ExecDirect(,"ALTER TABLE IadLiveStats139.T FIX STATISTICS")"#.into(),
        fixed("a"),
        r#" Set f="/tmp/iad-stats139-fixed.xml" Write "export=",$SYSTEM.SQL.Stats.Table.Export(f,"IadLiveStats139","T",0,1),!
 Write "clear=",$SYSTEM.SQL.Stats.Table.ClearTableStats("IadLiveStats139.T"),!"#.into(),
        fixed("b"),
        collected("b"),
        r#" Write "import=",$SYSTEM.SQL.Stats.Table.Import(f,0),!"#.into(),
        fixed("c"),
    ]
    .join("\n"));
    assert_eq!(get(&m, "a_fixed"), "[2000]", "{m:?}");
    assert_eq!(get(&m, "export"), "1", "{m:?}");
    assert_eq!(get(&m, "clear"), "1", "{m:?}");
    assert_eq!(
        get(&m, "b_fixed"),
        "[]",
        "Clear removed the fixed set: {m:?}"
    );
    assert_eq!(
        get(&m, "b_collected"),
        "[2000]",
        "collected survives: {m:?}"
    );
    assert_eq!(get(&m, "import"), "1", "{m:?}");
    assert_eq!(get(&m, "c_fixed"), "[2000]", "Import restored it: {m:?}");
}

/// 139 ships with Adaptive Mode on, collected statistics gathered for tables that also have a
/// fixed set, and a system task that collects them.
#[test]
#[ignore = "live iad-aihub-iris"]
fn query_stats_139_auto_collection_defaults() {
    let Some(env) = aihub_env() else { return };
    let mut s = Stats::new(&env);
    let m = s.kv(
        r#" New $NAMESPACE Set $NAMESPACE="%SYS"
 Set sc=##class(Config.SQL).Get(.p)
 Write "adaptive=",$Get(p("AdaptiveMode")),!
 Write "fixedtoo=",$Get(p("AutoStatsForFixedStatsTable")),!
 Set r=##class(%SQL.Statement).%ExecDirect(,"SELECT COUNT(*) FROM %SYS.Task WHERE TaskClass = '%SYS.Task.AutoStatsCollection'") Do r.%Next()
 Write "task=",r.%GetData(1),!"#,
    );
    assert_eq!(get(&m, "adaptive"), "1", "{m:?}");
    assert_eq!(get(&m, "fixedtoo"), "1", "{m:?}");
    assert_eq!(get(&m, "task"), "1", "{m:?}");
}
