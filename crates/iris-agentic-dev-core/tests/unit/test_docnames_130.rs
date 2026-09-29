//! 130 round 4 (FR-015, FR-016): document lists that fit in a response and name real routes.
//!
//! A skill-arm session called `iris_info what=documents inline=true` twice in USER and got about
//! 20 MB back each time. The list was 83,546 entries, 78,197 of them leaked `IrisDevTmp` scratch
//! classes; the handler copied `result.content` into `documents` and never removed the original, so
//! it went out twice; and `inline=true` skipped the only cap there was. Separately,
//! `/docnames/MAC`, `/INT` and `/INC` answer HTTP 400 — the routes are `/docnames/RTN/<type>` — so
//! `iris_doc mode=list` with no category failed outright.

use iris_agentic_dev_core::tools::doc::{
    docnames_route, is_scratch_doc, list_hides_scratch, list_routes,
};
use iris_agentic_dev_core::tools::info::{parse_document_ceiling, shape_documents};
use serde_json::{json, Value};

fn docs(names: &[&str]) -> Value {
    json!({
        "success": true,
        "what": "documents",
        "result": {"content": names.iter().map(|n| json!({"name": n, "cat": "CLS"})).collect::<Vec<_>>()}
    })
}

fn names(v: &Value) -> Vec<String> {
    v["documents"]
        .as_array()
        .unwrap()
        .iter()
        .map(|d| d["name"].as_str().unwrap().to_string())
        .collect()
}

#[test]
fn routines_go_through_the_rtn_routes() {
    assert_eq!(docnames_route("CLS"), "CLS");
    assert_eq!(docnames_route("mac"), "RTN/MAC");
    assert_eq!(docnames_route("INT"), "RTN/INT");
    assert_eq!(docnames_route("INC"), "RTN/INC");
    assert_eq!(docnames_route("CSP"), "CSP");
    // `ALL` used to send `/docnames/CLS`, so it never listed a routine.
    assert_eq!(docnames_route("ALL"), "*");
}

#[test]
fn iris_doc_list_all_reads_every_kind_through_a_valid_route() {
    assert_eq!(
        list_routes("ALL"),
        vec!["CLS", "RTN/MAC", "RTN/INT", "RTN/INC"]
    );
    assert_eq!(list_routes("MAC"), vec!["RTN/MAC"]);
    assert_eq!(list_routes("CLS"), vec!["CLS"]);
}

#[test]
fn scratch_documents_are_the_irisdevtmp_package() {
    assert!(is_scratch_doc("IrisDevTmp.IrisDevRun0a1b2c3d4e5f.cls"));
    assert!(is_scratch_doc("IrisDevTmp.IrisDevTel0a1b2c3d4e5f.cls"));
    assert!(!is_scratch_doc("IrisDevTmpFoo.Bar.cls"));
    assert!(!is_scratch_doc("User.IrisDevTmp.cls"));
}

#[test]
fn iris_doc_list_shows_scratch_only_when_asked() {
    assert!(list_hides_scratch("*", None));
    assert!(!list_hides_scratch("*", Some(true)));
    // A pattern that names the package is asking for it.
    assert!(!list_hides_scratch("IrisDevTmp.*", None));
    assert!(list_hides_scratch("IrisDevTmp.*", Some(false)));
}

#[test]
fn the_list_goes_out_once() {
    let mut v = docs(&["A.cls", "B.cls"]);
    shape_documents(&mut v, false, true, 500);
    assert_eq!(names(&v), vec!["A.cls", "B.cls"]);
    assert!(
        v["result"].get("content").is_none(),
        "result.content is the same list again: {v}"
    );
}

#[test]
fn scratch_classes_are_hidden_and_counted() {
    let mut v = docs(&["A.cls", "IrisDevTmp.IrisDevRun000000000001.cls", "B.cls"]);
    shape_documents(&mut v, false, true, 500);
    assert_eq!(names(&v), vec!["A.cls", "B.cls"]);
    assert_eq!(v["scratch_hidden"], 1);

    let mut v = docs(&["A.cls", "IrisDevTmp.IrisDevRun000000000001.cls"]);
    shape_documents(&mut v, true, true, 500);
    assert_eq!(names(&v).len(), 2);
    assert!(v.get("scratch_hidden").is_none());
}

#[test]
fn inline_does_not_lift_the_ceiling() {
    let many: Vec<String> = (0..600).map(|i| format!("Pkg.C{i}.cls")).collect();
    let refs: Vec<&str> = many.iter().map(String::as_str).collect();
    let mut v = docs(&refs);
    shape_documents(&mut v, false, true, 500);
    assert_eq!(names(&v).len(), 500);
    assert_eq!(v["truncated"], true);
    assert_eq!(v["total_count"], 600);
    let hint = v["hint"].as_str().unwrap();
    assert!(
        hint.contains("doc_type") && hint.contains("iris_doc"),
        "{hint}"
    );
}

#[test]
fn inline_under_the_ceiling_is_whole() {
    let mut v = docs(&["A.cls"]);
    shape_documents(&mut v, false, true, 500);
    assert_eq!(v["truncated"], false);
    assert_eq!(v["total_count"], 1);
}

#[test]
fn the_ceiling_reads_its_override() {
    assert_eq!(parse_document_ceiling(None), 500);
    assert_eq!(parse_document_ceiling(Some("50")), 50);
    assert_eq!(parse_document_ceiling(Some("junk")), 500);
    assert_eq!(parse_document_ceiling(Some("0")), 500);
}
