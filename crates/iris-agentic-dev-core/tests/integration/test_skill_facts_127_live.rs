//! Spec 127: live proof for each corrected skill claim.
//!
//! Every test here shows iris-dev-iris doing what the corrected skill text says. The wording guard
//! for the same item is in `tests/unit/test_skill_facts_127.rs`. Reproductions and the IRIS build
//! they ran on are in `specs/127-skill-fact-fixes/research.md`.
//!
//! Nothing here calls embedded Python. On iris-dev-iris a Python call can segfault the process and
//! leave the routine cache poisoned until IRIS restarts (research.md, item 9).
//!
//! Run with:
//!   IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS \
//!   cargo test --features testing --test integration test_skill_facts_127_live -- \
//!     --ignored --test-threads=1

use iris_agentic_dev_core::iris::connection::{
    is_generator_error, CompileResult, DiscoverySource, IrisConnection,
};

const NS: &str = "USER";

/// The connection, or a panic naming what to set. `IAD_ALLOW_SKIP=1` opts into skipping.
fn conn() -> Option<(IrisConnection, reqwest::Client)> {
    let host = std::env::var("IRIS_HOST").unwrap_or_default();
    if host.is_empty() {
        if std::env::var("IAD_ALLOW_SKIP").is_ok() {
            eprintln!("SKIP (IAD_ALLOW_SKIP set): IRIS_HOST unset");
            return None;
        }
        panic!(
            "IRIS_HOST unset. This test proves a skill claim against live IRIS; without IRIS it \
             asserts nothing, so it fails instead of passing quietly.\n\
             Set: IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS\n\
             Or opt into skipping deliberately: IAD_ALLOW_SKIP=1"
        );
    }
    let port = std::env::var("IRIS_WEB_PORT").unwrap_or_else(|_| "52780".into());
    let user = std::env::var("IRIS_USERNAME").unwrap_or_else(|_| "_SYSTEM".into());
    let pass = std::env::var("IRIS_PASSWORD").unwrap_or_else(|_| "SYS".into());
    let conn = IrisConnection::new(
        format!("http://{host}:{port}"),
        NS,
        user,
        pass,
        DiscoverySource::EnvVar,
    );
    Some((conn, reqwest::Client::new()))
}

/// Save a document (`Test127.X.cls`, `ROU127.mac`) by Atelier PUT.
async fn put_doc(c: &IrisConnection, client: &reqwest::Client, doc: &str, src: &str) {
    let url = c.versioned_ns_url(NS, &format!("/doc/{}", urlencoding::encode(doc)));
    let lines: Vec<&str> = src.lines().collect();
    let resp = client
        .put(&url)
        .basic_auth(&c.username, Some(&c.password))
        .json(&serde_json::json!({"enc": false, "content": lines}))
        .send()
        .await
        .expect("PUT must reach IRIS");
    assert!(
        resp.status().is_success(),
        "PUT {doc}: HTTP {}",
        resp.status()
    );
}

async fn compile(c: &IrisConnection, client: &reqwest::Client, doc: &str) -> CompileResult {
    c.compile_document(doc, NS, "cuk", client)
        .await
        .expect("compile request must reach IRIS")
}

/// Run ObjectScript and return its output; a generator error fails the test.
async fn run(c: &IrisConnection, client: &reqwest::Client, code: &str) -> String {
    let out = c
        .execute_via_generator(code, NS, client)
        .await
        .expect("execute request must reach IRIS");
    assert!(!is_generator_error(&out), "IRIS run failed: {out}");
    out.trim().to_string()
}

/// Cleanup: delete classes with `e`, so no Test127 rows outlive the test.
async fn drop_classes(c: &IrisConnection, client: &reqwest::Client, names: &[&str]) {
    for n in names {
        let _ = c
            .execute_via_generator(
                &format!(" Do $system.OBJ.Delete(\"{n}\",\"e-d\")"),
                NS,
                client,
            )
            .await;
    }
}

async fn count(c: &IrisConnection, client: &reqwest::Client, table: &str) -> String {
    run(
        c,
        client,
        &format!(
            " Set rs=##class(%SQL.Statement).%ExecDirect(,\"SELECT COUNT(*) AS n FROM {table}\")\n \
             If rs.%SQLCODE<0 {{ Write \"SQLCODE=\",rs.%SQLCODE Quit }}\n \
             Do rs.%Next() Write rs.%Get(\"n\")"
        ),
    )
    .await
}

const EXT: &str = "Class Test127.Ext Extends %Persistent
{

Property Name As %String;

}";

/// US1. Compile and Load with the flags the skill recommends keep the rows. `Delete` with `e`
/// drops the extent, which is what `ShowFlags` says `e` means.
#[tokio::test]
#[ignore]
async fn e_flag_deletes_the_extent_and_recommended_flags_keep_rows() {
    let Some((c, client)) = conn() else { return };
    drop_classes(&c, &client, &["Test127.Ext"]).await;
    put_doc(&c, &client, "Test127.Ext.cls", EXT).await;
    let r = compile(&c, &client, "Test127.Ext.cls").await;
    assert!(r.success(), "Test127.Ext must compile: {:?}", r.errors);

    run(
        &c,
        &client,
        " For i=1:1:3 { Set o=##class(Test127.Ext).%New(), o.Name=i Set sc=o.%Save() If 'sc { Write \"save failed\" Quit } }",
    )
    .await;
    assert_eq!(count(&c, &client, "Test127.Ext").await, "3");

    // Recompile with the recommended flags: rows stay.
    let r = compile(&c, &client, "Test127.Ext.cls").await;
    assert!(r.success(), "recompile: {:?}", r.errors);
    assert_eq!(
        count(&c, &client, "Test127.Ext").await,
        "3",
        "recompile lost rows"
    );

    // Export, delete without `e`, load with `ck`: rows stay.
    let out = run(
        &c,
        &client,
        " Set f=\"/tmp/test127_ext.xml\"\n \
         Set sc=$system.OBJ.Export(\"Test127.Ext.cls\",f,\"-d\") If 'sc { Write \"export failed\" Quit }\n \
         Set sc=$system.OBJ.Delete(\"Test127.Ext\",\"-d\") If 'sc { Write \"delete failed\" Quit }\n \
         Set sc=$system.OBJ.Load(f,\"ck-d\") If 'sc { Write \"load failed\" Quit }\n \
         Write \"ok\"",
    )
    .await;
    assert_eq!(out, "ok");
    assert_eq!(
        count(&c, &client, "Test127.Ext").await,
        "3",
        "Delete without e lost rows"
    );

    // Delete with `e`, load again: the extent is gone.
    let out = run(
        &c,
        &client,
        " Set f=\"/tmp/test127_ext.xml\"\n \
         Set sc=$system.OBJ.Delete(\"Test127.Ext\",\"e-d\") If 'sc { Write \"delete failed\" Quit }\n \
         Set sc=$system.OBJ.Load(f,\"ck-d\") If 'sc { Write \"load failed\" Quit }\n \
         Write \"ok\"",
    )
    .await;
    assert_eq!(out, "ok");
    assert_eq!(
        count(&c, &client, "Test127.Ext").await,
        "0",
        "Delete with e kept rows"
    );

    drop_classes(&c, &client, &["Test127.Ext"]).await;
}
