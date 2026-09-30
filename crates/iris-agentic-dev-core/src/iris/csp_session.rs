//! One CSP cookie store per process, and the logout that ends its sessions (132 B1).
//!
//! Each `reqwest::Client` built with `.cookie_store(true)` gets a jar of its own, so the probe,
//! `client` and `exec_client` each opened a CSP session on `/api/atelier`, and none was ever ended.
//! A session holds its slot for the web app's timeout (3600 s by default): ten `iad exec` calls
//! left twenty sessions on 139, and two ladder tasks ran its key into `<LICENSE LIMIT EXCEEDED>`.
//!
//! Every IRIS client now takes [`shared_cookie_store`], so a process holds one session per web
//! application. The store keeps the path of each `CSPSESSIONID-*` cookie IRIS sets, and
//! [`logout_blocking`] sends `?IRISLogout=end` to each one on the way out. IRIS ends the session
//! named by the cookie and answers 401, so the reply is not checked.

use std::collections::BTreeSet;
use std::sync::{Arc, LazyLock, Mutex};
use std::time::Duration;

use reqwest::cookie::{CookieStore, Jar};
use reqwest::header::HeaderValue;
use reqwest::Url;

const SESSION_COOKIE_PREFIX: &str = "CSPSESSIONID";

/// A `reqwest` cookie jar that also records where each CSP session lives.
#[derive(Default)]
pub struct CspSessionStore {
    jar: Jar,
    // `origin + cookie path`, e.g. `http://localhost:52781/api/atelier/`.
    sessions: Mutex<BTreeSet<String>>,
}

impl CspSessionStore {
    pub fn new() -> Self {
        Self::default()
    }

    /// One `?IRISLogout=end` URL per CSP session this store has seen.
    pub fn logout_urls(&self) -> Vec<String> {
        self.sessions
            .lock()
            .unwrap()
            .iter()
            .map(|base| format!("{base}?IRISLogout=end"))
            .collect()
    }

    fn record(&self, header: &HeaderValue, url: &Url) {
        let Ok(text) = header.to_str() else { return };
        let mut parts = text.split(';').map(str::trim);
        let Some(name) = parts.next().and_then(|kv| kv.split('=').next()) else {
            return;
        };
        if !name.starts_with(SESSION_COOKIE_PREFIX) {
            return;
        }
        let path = parts
            .filter_map(|p| p.split_once('='))
            .find(|(k, _)| k.eq_ignore_ascii_case("path"))
            .map(|(_, v)| v.to_string())
            // RFC 6265 5.1.4: with no Path attribute the cookie belongs to the request's directory.
            .unwrap_or_else(|| {
                let p = url.path();
                p[..=p.rfind('/').unwrap_or(0)].to_string()
            });
        let path = if path.ends_with('/') {
            path
        } else {
            format!("{path}/")
        };
        let origin = url.origin().ascii_serialization();
        self.sessions
            .lock()
            .unwrap()
            .insert(format!("{origin}{path}"));
    }
}

impl CookieStore for CspSessionStore {
    fn set_cookies(&self, cookie_headers: &mut dyn Iterator<Item = &HeaderValue>, url: &Url) {
        let headers: Vec<&HeaderValue> = cookie_headers.collect();
        for header in &headers {
            self.record(header, url);
        }
        self.jar.set_cookies(&mut headers.into_iter(), url);
    }

    fn cookies(&self, url: &Url) -> Option<HeaderValue> {
        self.jar.cookies(url)
    }
}

static SHARED: LazyLock<Arc<CspSessionStore>> = LazyLock::new(|| Arc::new(CspSessionStore::new()));

/// The store every IRIS-bound client in this process shares.
pub fn shared_cookie_store() -> Arc<CspSessionStore> {
    SHARED.clone()
}

/// End every CSP session the shared store has seen. Waits at most `timeout` in all.
///
/// Runs on a thread of its own with its own runtime, so it can be called from `main` after the
/// runtime has returned and from `crate::exit` inside a tokio task alike.
pub fn logout_blocking(timeout: Duration) {
    let urls = SHARED.logout_urls();
    if urls.is_empty() {
        return;
    }
    let (done_tx, done_rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let Ok(rt) = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
        else {
            return;
        };
        rt.block_on(async {
            let Ok(client) = reqwest::Client::builder()
                .user_agent(super::connection::user_agent(
                    super::connection::caller_mode(),
                ))
                .danger_accept_invalid_certs(super::connection::tls_insecure_from_env())
                .cookie_provider(SHARED.clone())
                .timeout(timeout)
                .build()
            else {
                return;
            };
            let sends = urls.iter().map(|u| client.get(u).send());
            for result in futures_util::future::join_all(sends).await {
                if let Err(e) = result {
                    tracing::debug!("CSP logout failed: {e}");
                }
            }
        });
        let _ = done_tx.send(());
    });
    let _ = done_rx.recv_timeout(timeout);
}
