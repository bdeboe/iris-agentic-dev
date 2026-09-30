//! 132 B1: the process-wide CSP cookie store and the logout targets it records.
//!
//! Each iad process used to open a CSP session per client (probe, `client`, `exec_client`) and
//! end none of them. On 139's 128-LU key the leaked sessions ran into `<LICENSE LIMIT EXCEEDED>`
//! after two ladder tasks. The store is shared by every client, and it keeps the path of each
//! CSP session cookie IRIS sets, so the exit path can end each session with `?IRISLogout=end`.
//! The live half is `bin/tests/integration/test_csp_logout_132.rs`.

use iris_agentic_dev_core::iris::csp_session::{shared_cookie_store, CspSessionStore};
use reqwest::cookie::CookieStore;
use reqwest::header::HeaderValue;

fn set(store: &CspSessionStore, url: &str, cookies: &[&str]) {
    let values: Vec<HeaderValue> = cookies
        .iter()
        .map(|c| HeaderValue::from_str(c).unwrap())
        .collect();
    store.set_cookies(&mut values.iter(), &url.parse().unwrap());
}

const ATELIER: &str =
    "CSPSESSIONID-SP-52781-UP-api-atelier-=00g0000200; path=/api/atelier/; httpOnly;";

#[test]
fn a_csp_session_cookie_records_its_logout_url() {
    let store = CspSessionStore::new();
    set(
        &store,
        "http://localhost:52781/api/atelier/v1/USER/action/query",
        &[ATELIER],
    );

    assert_eq!(
        store.logout_urls(),
        vec!["http://localhost:52781/api/atelier/?IRISLogout=end".to_string()]
    );
}

#[test]
fn the_store_still_sends_the_cookie_back() {
    let store = CspSessionStore::new();
    set(
        &store,
        "http://localhost:52781/api/atelier/v1/USER",
        &[ATELIER],
    );

    let sent = store
        .cookies(
            &"http://localhost:52781/api/atelier/v1/USER/doc/x.cls"
                .parse()
                .unwrap(),
        )
        .expect("cookie sent back");
    assert!(sent
        .to_str()
        .unwrap()
        .contains("CSPSESSIONID-SP-52781-UP-api-atelier-=00g0000200"));
}

#[test]
fn other_cookies_record_nothing() {
    let store = CspSessionStore::new();
    set(
        &store,
        "http://localhost:52781/api/atelier/",
        &["CSPWSERVERID=hzZIUtro; path=/;"],
    );

    assert!(store.logout_urls().is_empty());
}

#[test]
fn a_session_renewed_on_the_same_path_is_one_target() {
    let store = CspSessionStore::new();
    for _ in 0..3 {
        set(
            &store,
            "http://localhost:52781/api/atelier/v1/USER",
            &[ATELIER],
        );
    }

    assert_eq!(store.logout_urls().len(), 1);
}

#[test]
fn each_origin_and_path_is_its_own_target() {
    let store = CspSessionStore::new();
    set(
        &store,
        "http://localhost:52781/api/atelier/v1/USER",
        &[ATELIER],
    );
    set(
        &store,
        "http://localhost:52780/api/atelier/v1/USER",
        &["CSPSESSIONID-SP-52780-UP-api-atelier-=11; path=/api/atelier/;"],
    );
    set(
        &store,
        "https://iris.example.com/irisaicore/api/atelier/v1/USER",
        &["CSPSESSIONID-SP-443-UP-irisaicore-api-atelier-=22; path=/irisaicore/api/atelier/;"],
    );

    let mut urls = store.logout_urls();
    urls.sort();
    assert_eq!(
        urls,
        vec![
            "http://localhost:52780/api/atelier/?IRISLogout=end".to_string(),
            "http://localhost:52781/api/atelier/?IRISLogout=end".to_string(),
            "https://iris.example.com/irisaicore/api/atelier/?IRISLogout=end".to_string(),
        ]
    );
}

#[test]
fn a_cookie_with_no_path_uses_the_request_directory() {
    let store = CspSessionStore::new();
    set(
        &store,
        "http://localhost:52781/api/atelier/v1/USER",
        &["CSPSESSIONID-SP-52781-UP-api-atelier-=33"],
    );

    assert_eq!(
        store.logout_urls(),
        vec!["http://localhost:52781/api/atelier/v1/?IRISLogout=end".to_string()]
    );
}

#[test]
fn every_client_gets_the_same_store() {
    assert!(std::sync::Arc::ptr_eq(
        &shared_cookie_store(),
        &shared_cookie_store()
    ));
}
