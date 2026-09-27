//! `iris_macro` request and response shapes — 130 round 3, written before the fix.
//!
//! Every action called a route Atelier does not have: `/action/getmacro` answers 404 and
//! `/docnames/INC` answers 400. The handler read the 404 body with `unwrap_or_default()` and
//! returned `success: true, result: {}`, and `list` turned the 400 into "No include files found".
//! In the 130 round-2 ladder that `{}` for `eProductionStateRunning` is what made agents guess the
//! value as 2.
//!
//! The shapes below are captured from iris-dev-iris (BENCHMARK). The live tests in
//! `integration/test_handlers_live.rs` check the same calls against IRIS.

use iris_agentic_dev_core::tools::info::{
    macro_arguments, macro_atelier_error, macro_defines, macro_include_names, macro_location,
    macro_request_body, macro_route, macro_url, MacroParams,
};
use serde_json::json;

#[test]
fn each_action_posts_to_its_own_getmacro_route() {
    assert_eq!(macro_route("signature"), Some("/action/getmacrosignature"));
    assert_eq!(macro_route("location"), Some("/action/getmacrolocation"));
    assert_eq!(
        macro_route("definition"),
        Some("/action/getmacrodefinition")
    );
    assert_eq!(macro_route("expand"), Some("/action/getmacroexpansion"));
    assert_eq!(macro_route("list"), None);
}

#[test]
fn the_body_names_the_macro_and_its_includes() {
    let body = macro_request_body("eProductionStateRunning", &["EnsConstants".into()], &[]);
    assert_eq!(body["macroname"], "eProductionStateRunning");
    assert_eq!(body["includes"], json!(["EnsConstants"]));
    assert_eq!(body["arguments"], "");
    assert!(
        body["docname"]
            .as_str()
            .is_some_and(|d| d.ends_with(".cls")),
        "Atelier needs a docname even though it does not resolve includes from it: {body}"
    );
}

#[test]
fn arguments_go_as_one_parenthesised_string() {
    // An array answers `expansion: []`; "(sc)" answers `('sc)`.
    assert_eq!(macro_arguments(&[]), "");
    assert_eq!(macro_arguments(&["sc".into()]), "(sc)");
    assert_eq!(macro_arguments(&["a".into(), "b".into()]), "(a,b)");
}

#[test]
fn includes_given_with_the_extension_are_sent_without_it() {
    let body = macro_request_body("X", &["EnsConstants.inc".into(), "%occStatus".into()], &[]);
    assert_eq!(body["includes"], json!(["EnsConstants", "%occStatus"]));
}

#[test]
fn a_found_location_parses_to_document_and_line() {
    let body = json!({"status":{"errors":[],"summary":""},"console":[],
        "result":{"content":{"document":"EnsConstants.inc","line":8}}});
    assert_eq!(
        macro_location(&body),
        Some(("EnsConstants.inc".to_string(), 8))
    );
}

#[test]
fn an_unknown_macro_has_no_location() {
    let body = json!({"status":{"errors":[],"summary":""},"console":[],
        "result":{"content":{"document":"","line":""}}});
    assert_eq!(macro_location(&body), None);
    assert_eq!(macro_location(&json!({"result":{}})), None);
}

#[test]
fn status_errors_are_surfaced() {
    let body = json!({"status":{"errors":[{"error":"ERROR #5001: Utility failed","code":5001}],
        "summary":"ERROR #5001: Utility failed"},
        "console":["ERROR #5001: Failure to compile include files"],"result":{}});
    let msg = macro_atelier_error(&body).expect("an Atelier error must not read as success");
    assert!(msg.contains("#5001"), "{msg}");
    assert!(msg.contains("Failure to compile include files"), "{msg}");

    let ok = json!({"status":{"errors":[],"summary":""},"console":[],"result":{"content":{}}});
    assert_eq!(macro_atelier_error(&ok), None);
}

#[test]
fn include_names_come_from_docnames_rtn_inc() {
    let body = json!({"status":{"errors":[]},"result":{"content":[
        {"name":"EnsConstants.inc","cat":"RTN","db":"ENSLIB"},
        {"name":"%occStatus.inc","cat":"RTN","db":"IRISLIB"}]}});
    assert_eq!(
        macro_include_names(&body),
        vec!["EnsConstants".to_string(), "%occStatus".to_string()]
    );
}

#[test]
fn includes_is_an_optional_param() {
    let p: MacroParams = serde_json::from_str(
        r#"{"action":"definition","name":"eProductionStateRunning","includes":["EnsConstants"]}"#,
    )
    .unwrap();
    assert_eq!(p.includes, Some(vec!["EnsConstants".to_string()]));
    let p: MacroParams = serde_json::from_str(r#"{"action":"list"}"#).unwrap();
    assert_eq!(p.includes, None);
}

#[test]
fn an_unprobed_v1_connection_still_asks_v2() {
    use iris_agentic_dev_core::iris::connection::{
        AtelierVersion, DiscoverySource, IrisConnection,
    };
    let mut c = IrisConnection::new(
        "http://localhost:52780".to_string(),
        "USER",
        "_SYSTEM".to_string(),
        "SYS".to_string(),
        DiscoverySource::EnvVar,
    );
    let url = macro_url(&c, "BENCHMARK", "/action/getmacrolocation");
    assert!(
        url.ends_with("/api/atelier/v2/BENCHMARK/action/getmacrolocation"),
        "{url}"
    );
    c.atelier_version = AtelierVersion::V8;
    let url = macro_url(&c, "%SYS", "/docnames/RTN/INC");
    assert!(
        url.ends_with("/api/atelier/v8/%25SYS/docnames/RTN/INC"),
        "{url}"
    );
}

#[test]
fn an_include_lists_its_own_defines() {
    // `getmacrolist` ignores `includes`: every body answers the same 610 system macros.
    let lines: Vec<String> = [
        "ROUTINE EnsConstants [Type=INC]",
        "#; constants for Production state",
        "#define eProductionStateRunning        1",
        "  #def1arg  ERR(%args) $$$ERROR(%args)",
        "#define Sum(%a,%b) (%a+%b)",
        "#include Other",
        "#defineX not a define",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect();
    assert_eq!(
        macro_defines(&lines),
        vec!["eProductionStateRunning", "ERR(", "Sum("]
    );
}
