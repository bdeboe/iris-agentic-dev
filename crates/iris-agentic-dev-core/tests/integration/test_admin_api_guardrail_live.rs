//! Live proof for the guardrails skill's admin-via-API rule, on iris-dev-iris.
//!
//! Security and Config tables refuse SQL writes; the class API does the same job and reports a
//! duplicate as a `%Status`. `%SYS.Task` takes SQL writes, which is why the rule covers it too.
//! Every object here is created by the test (`IadLiveAdm*`) and deleted at the end. No test writes
//! to a system task: an SQL UPDATE on one really changes it.
//!
//! Run with:
//!   IAD_BINARY=$PWD/target/debug/iris-agentic-dev IRIS_HOST=localhost IRIS_WEB_PORT=52780 \
//!   IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS cargo test --features testing --test integration \
//!   test_admin_api_guardrail_live -- --include-ignored --test-threads=1

use std::collections::HashMap;

use iris_agentic_dev_core::testing::{answer_text, live_env, require_iad_binary, McpSession};

const TEARDOWN: &str = r#" New $NAMESPACE Set $NAMESPACE="%SYS"
 If ##class(Security.Users).Exists("IadLiveAdmU") { Do ##class(Security.Users).Delete("IadLiveAdmU") }
 If ##class(Security.Roles).Exists("IadLiveAdmRole") { Do ##class(Security.Roles).Delete("IadLiveAdmRole") }
 If ##class(Security.Resources).Exists("IadLiveAdmRes") { Do ##class(Security.Resources).Delete("IadLiveAdmRes") }
 Set r=##class(%SQL.Statement).%ExecDirect(,"SELECT ID FROM %SYS.Task WHERE Name = 'IadLiveAdmTask'")
 While r.%Next() { Do ##class(%SYS.Task).%DeleteId(r.%GetData(1)) }"#;

struct Admin {
    mcp: McpSession,
}

impl Admin {
    fn new() -> Self {
        let mut env = live_env();
        env.push(("IRIS_WRITE_TOOLS_ENABLED".into(), "1".into()));
        env.push(("IRIS_DESTRUCTIVE_TOOLS_ENABLED".into(), "1".into()));
        let mut a = Self {
            mcp: McpSession::start(&env),
        };
        a.kv(TEARDOWN);
        a
    }

    /// Run `code` in %SYS over iris_execute and read its `key=value` lines.
    fn kv(&mut self, code: &str) -> HashMap<String, String> {
        let code = format!(" New $NAMESPACE Set $NAMESPACE=\"%SYS\"\n{code}");
        let answer = self
            .mcp
            .call("iris_execute", &serde_json::json!({ "code": code }));
        let text = answer
            .pointer("/result/content/0/text")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_else(|| panic!("no text content in {}", answer_text(&answer)));
        let got: serde_json::Value = serde_json::from_str(text)
            .unwrap_or_else(|e| panic!("content was not JSON ({e}): {text}"));
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

impl Drop for Admin {
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

/// `SQL` writes `<tag>=<SQLCODE>|<%Message>` for one statement.
fn sql(tag: &str, stmt: &str) -> String {
    format!(
        r#" Set r=##class(%SQL.Statement).%ExecDirect(,"{stmt}") Write "{tag}=",r.%SQLCODE,"|",r.%Message,!"#
    )
}

/// Users, roles, resources and namespaces refuse SQL writes. Reads still work. The refusal comes
/// per row: a write that matches no row returns 100, so each statement here hits a real row. The
/// namespace UPDATE sets USER's globals database to the value it already has.
#[test]
#[ignore = "requires live IRIS (iris-dev-iris) and the built binary"]
fn security_and_config_tables_refuse_sql_writes() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let mut a = Admin::new();
    let m = a.kv(&[
        r#" Write "create=",##class(Security.Users).Create("IadLiveAdmU","%Developer","Iad-Probe-1x","iad probe"),!"#.to_string(),
        sql("users_roles", "UPDATE Security.Users SET Roles='%All' WHERE Name='IadLiveAdmU'"),
        sql("users_comment", "UPDATE Security.Users SET Comment='x' WHERE Name='IadLiveAdmU'"),
        sql("users_delete", "DELETE FROM Security.Users WHERE Name='IadLiveAdmU'"),
        sql("roles_update", "UPDATE Security.Roles SET Description='x' WHERE Name='%Developer'"),
        sql("res_update", "UPDATE Security.Resources SET Description='x' WHERE Name='%DB_USER'"),
        r#" Write "res_create=",##class(Security.Resources).Create("IadLiveAdmRes","iad probe","R"),!"#.to_string(),
        sql("res_delete", "DELETE FROM Security.Resources WHERE Name='IadLiveAdmRes'"),
        r#" Do ##class(Config.Namespaces).Get("USER",.n) Write "ns_globals=",n("Globals"),!"#.to_string(),
        sql("ns_update", "UPDATE Config.Namespaces SET Globals='USER' WHERE Name='USER'"),
        sql("none_matched", "DELETE FROM Security.Resources WHERE Name='IadLiveAdmNone'"),
        sql("users_read", "SELECT Name FROM Security.Users WHERE Name='IadLiveAdmU'"),
        r#" Do ##class(Security.Users).Get("IadLiveAdmU",.p) Write "roles_after=",p("Roles"),!"#.to_string(),
    ]
    .join("\n"));
    assert_eq!(get(&m, "create"), "1", "{m:?}");
    // Roles through SQL: a <LIST> error, and the user keeps its roles.
    assert!(get(&m, "users_roles").starts_with("-400|"), "{m:?}");
    assert_eq!(get(&m, "roles_after"), "%Developer", "{m:?}");
    assert!(get(&m, "users_comment").starts_with("-132|"), "{m:?}");
    assert!(get(&m, "users_delete").starts_with("-134|"), "{m:?}");
    assert!(get(&m, "roles_update").starts_with("-132|"), "{m:?}");
    assert!(get(&m, "res_update").starts_with("-132|"), "{m:?}");
    assert_eq!(get(&m, "res_create"), "1", "{m:?}");
    assert!(get(&m, "res_delete").starts_with("-134|"), "{m:?}");
    assert_eq!(get(&m, "ns_globals"), "USER", "{m:?}");
    assert!(get(&m, "ns_update").starts_with("-132|"), "{m:?}");
    assert!(get(&m, "none_matched").starts_with("100|"), "{m:?}");
    assert!(get(&m, "users_read").starts_with("0|"), "{m:?}");
}

/// The class API: `Exists` before `Create`, a second `Create` is a `%Status` error naming the
/// object, and `Modify` takes a props array.
#[test]
#[ignore = "requires live IRIS (iris-dev-iris) and the built binary"]
fn class_api_does_the_same_jobs_and_reports_duplicates() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let mut a = Admin::new();
    let m = a.kv(
        r#" Write "u_exists0=",##class(Security.Users).Exists("IadLiveAdmU"),!
 Write "u_create=",##class(Security.Users).Create("IadLiveAdmU","%Developer","Iad-Probe-1x","iad probe"),!
 Write "u_exists1=",##class(Security.Users).Exists("IadLiveAdmU"),!
 Set sc=##class(Security.Users).Create("IadLiveAdmU","%Developer","Iad-Probe-1x","iad probe") Write "u_dup=",$SYSTEM.Status.GetErrorText(sc),!
 Set p("Roles")="%Developer,%SQL" Write "u_modify=",##class(Security.Users).Modify("IadLiveAdmU",.p),! Kill p
 Do ##class(Security.Users).Get("IadLiveAdmU",.p) Write "u_roles=",p("Roles"),!
 Write "r_create=",##class(Security.Roles).Create("IadLiveAdmRole","iad probe",""),!
 Write "s_create=",##class(Security.Resources).Create("IadLiveAdmRes","iad probe","R"),!
 Set sc=##class(Security.Resources).Create("IadLiveAdmRes","iad probe","R") Write "s_dup=",$SYSTEM.Status.GetErrorText(sc),!
 Write "u_delete=",##class(Security.Users).Delete("IadLiveAdmU"),!
 Write "r_delete=",##class(Security.Roles).Delete("IadLiveAdmRole"),!
 Write "s_delete=",##class(Security.Resources).Delete("IadLiveAdmRes"),!"#,
    );
    assert_eq!(get(&m, "u_exists0"), "0", "{m:?}");
    assert_eq!(get(&m, "u_create"), "1", "{m:?}");
    assert_eq!(get(&m, "u_exists1"), "1", "{m:?}");
    assert!(get(&m, "u_dup").contains("#837"), "{m:?}");
    assert_eq!(get(&m, "u_modify"), "1", "{m:?}");
    assert_eq!(get(&m, "u_roles"), "%Developer,%SQL", "{m:?}");
    assert_eq!(get(&m, "r_create"), "1", "{m:?}");
    assert_eq!(get(&m, "s_create"), "1", "{m:?}");
    assert!(get(&m, "s_dup").contains("#891"), "{m:?}");
    assert_eq!(get(&m, "u_delete"), "1", "{m:?}");
    assert_eq!(get(&m, "r_delete"), "1", "{m:?}");
    assert_eq!(get(&m, "s_delete"), "1", "{m:?}");
}

/// `%SYS.Task` takes an SQL UPDATE and the task really changes. Shown on a task the test creates.
/// `Resume` and `Suspend` do the same job through the class.
#[test]
#[ignore = "requires live IRIS (iris-dev-iris) and the built binary"]
fn sys_task_takes_sql_writes() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let mut a = Admin::new();
    let m = a.kv(
        r#" Set t=##class(%SYS.Task).%New() Set t.Name="IadLiveAdmTask",t.NameSpace="USER",t.TaskClass="%SYS.Task.PurgeErrorsAndLogs",t.Description="iad probe"
 Write "save=",t.%Save(),! Set id=t.%Id() Kill t
 Set r=##class(%SQL.Statement).%ExecDirect(,"UPDATE %SYS.Task SET Suspended=1 WHERE ID=?",id) Write "upd=",r.%SQLCODE,!
 Write "susp=",##class(%SYS.Task).%OpenId(id).Suspended,!
 Write "resume=",##class(%SYS.Task).Resume(id)," ",##class(%SYS.Task).%OpenId(id).Suspended,!
 Write "suspend=",##class(%SYS.Task).Suspend(id)," ",##class(%SYS.Task).%OpenId(id).Suspended,!
 Write "del=",##class(%SYS.Task).%DeleteId(id),!"#,
    );
    assert_eq!(get(&m, "save"), "1", "{m:?}");
    assert_eq!(get(&m, "upd"), "0", "{m:?}");
    assert_eq!(
        get(&m, "susp"),
        "1",
        "the SQL write changed the task: {m:?}"
    );
    // The class methods the skill names instead.
    assert_eq!(get(&m, "resume"), "1 0", "{m:?}");
    assert_eq!(get(&m, "suspend"), "1 1", "{m:?}");
    assert_eq!(get(&m, "del"), "1", "{m:?}");
}
