//! Hints for IRIS errors an agent is known to hit (specs 125, 129).
//!
//! iad hands IRIS errors back in IRIS's words, which is right for `error` but leaves an agent that
//! has never seen one guessing at the fix. A matched error gets a `hint` (what to do) and a
//! `hint_ref` (`{skill, section, why}`: where the fix is written down). A rule goes in only after
//! its error was reproduced live (`specs/125-error-hints/research.md`,
//! `specs/129-tool-result-hints/research.md`), and anything unmatched gets nothing: a wrong hint
//! sends the agent further off than the raw error does.
//!
//! Wording lives in `hints.toml`; matching lives here. `IAD_CODING_PACK=off` drops `hint_ref` and
//! keeps the text, which is why no text names a skill.

use regex::Regex;
use serde::Deserialize;
use std::sync::OnceLock;

/// One row of `hints.toml`.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Rule {
    pub id: String,
    pub skill: String,
    pub section: String,
    pub why: String,
    pub text: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RuleFile {
    rule: Vec<Rule>,
}

const RULES_TOML: &str = include_str!("hints.toml");

/// Every rule id a matcher below can return. A test checks this equals the ids in `hints.toml`.
const MATCHERS: &[&str] = &[
    "sql_objectscript_function",
    "sys_only_class",
    "sys_only_table",
    "deep_package_table",
    "double_quoted_string",
    "reserved_word",
    "nonstandard_insert",
];

/// Packages whose classes resolve only in %SYS (spec 125 research R2). `%SYS.*` and `%SYSTEM.*`
/// are not here: `%` packages resolve in every namespace.
const SYS_ONLY_PACKAGES: &[&str] = &["Security.", "Config.", "SYS."];

/// SQL schemas whose tables resolve only in %SYS (spec 129 research R2). `SYS` is left out: it
/// has three tables, and `SYS.Database` gives -30 even in %SYS because it is a class, not a table.
const SYS_ONLY_SCHEMAS: &[&str] = &["SECURITY", "CONFIG"];

pub fn rules() -> &'static [Rule] {
    static RULES: OnceLock<Vec<Rule>> = OnceLock::new();
    RULES.get_or_init(|| {
        toml::from_str::<RuleFile>(RULES_TOML)
            .expect("hints.toml parses")
            .rule
    })
}

pub fn matcher_ids() -> &'static [&'static str] {
    MATCHERS
}

/// Every `(skill, section)` a rule cites, one per rule. A test checks each heading exists.
pub fn cited_sections() -> Vec<(&'static str, &'static str)> {
    rules()
        .iter()
        .map(|r| (r.skill.as_str(), r.section.as_str()))
        .collect()
}

fn rule(id: &str) -> &'static Rule {
    rules()
        .iter()
        .find(|r| r.id == id)
        .unwrap_or_else(|| panic!("hints.toml has no rule {id}"))
}

/// `IAD_CODING_PACK` value → whether `hint_ref` is sent. Unset or anything but an off word is on.
pub fn coding_pack_from(v: Option<&str>) -> bool {
    !matches!(
        v.map(|s| s.trim().to_ascii_lowercase()).as_deref(),
        Some("off" | "0" | "false" | "no")
    )
}

/// Read per call, like the other `IAD_*` switches.
pub fn coding_pack_on() -> bool {
    coding_pack_from(std::env::var("IAD_CODING_PACK").ok().as_deref())
}

/// A matched rule with its placeholders filled.
#[derive(Debug, Clone)]
pub struct Hint {
    rule: &'static Rule,
    text: String,
    vars: Vec<(&'static str, String)>,
}

impl Hint {
    fn new(id: &str, vars: Vec<(&'static str, String)>) -> Self {
        let rule = rule(id);
        let mut text = rule.text.clone();
        for (k, v) in &vars {
            text = text.replace(&format!("{{{k}}}"), v);
        }
        Hint { rule, text, vars }
    }
    pub fn rule(&self) -> &str {
        &self.rule.id
    }
    pub fn text(&self) -> &str {
        &self.text
    }
    pub fn skill(&self) -> &str {
        &self.rule.skill
    }
    pub fn section(&self) -> &str {
        &self.rule.section
    }
    /// Placeholder values, so the hints loop can re-render a candidate template.
    pub fn vars(&self) -> &[(&'static str, String)] {
        &self.vars
    }
    /// Set `hint`, and `hint_ref` unless the coding pack is off.
    pub fn apply(&self, v: &mut serde_json::Value) {
        self.apply_with(v, coding_pack_on())
    }
    pub fn apply_with(&self, v: &mut serde_json::Value, pack_on: bool) {
        v["hint"] = serde_json::Value::String(self.text.clone());
        if pack_on {
            v["hint_ref"] = serde_json::json!({
                "skill": self.rule.skill,
                "section": self.rule.section,
                "why": self.rule.why,
            });
        }
    }
}

fn re(pat: &'static str, cell: &'static OnceLock<Regex>) -> &'static Regex {
    cell.get_or_init(|| Regex::new(pat).expect("static regex"))
}

/// The innermost SQLCODE and the message text after it. EXPLAIN wraps errors as
/// `SQLCODE: -482 ... SQLCODE = -30 : ...`, so the last code wins.
fn sqlcode(msg: &str) -> Option<(i32, &str)> {
    static RE: OnceLock<Regex> = OnceLock::new();
    let m = re(r"SQLCODE(?::| =) (-?\d+)", &RE)
        .captures_iter(msg)
        .last()?;
    let code = m[1].parse().ok()?;
    Some((code, &msg[m.get(0)?.end()..]))
}

/// The query's own spelling of a name IRIS reported upper-cased, if the query has it.
fn spelled<'q>(query: &'q str, upper: &str) -> Option<&'q str> {
    static RE: OnceLock<Regex> = OnceLock::new();
    re(r"[%\w]+(?:\.[%\w]+)*", &RE)
        .find_iter(query)
        .map(|m| m.as_str())
        .find(|t| t.eq_ignore_ascii_case(upper))
}

/// The query's spelling of a reserved word. `COUNT(*) AS count` has it twice; the alias after `AS`
/// is the one IRIS stopped at, and otherwise the last one is.
fn spelled_word<'q>(query: &'q str, upper: &str) -> Option<&'q str> {
    static AS: OnceLock<Regex> = OnceLock::new();
    static WORD: OnceLock<Regex> = OnceLock::new();
    re(r"(?i)\bAS\s+(\w+)", &AS)
        .captures_iter(query)
        .filter_map(|c| c.get(1))
        .map(|m| m.as_str())
        .find(|w| w.eq_ignore_ascii_case(upper))
        .or_else(|| {
            re(r"\w+", &WORD)
                .find_iter(query)
                .map(|m| m.as_str())
                .filter(|w| w.eq_ignore_ascii_case(upper))
                .last()
        })
}

/// The hint for an `iris_query` `SQL_ERROR` message, given the statement (or the table name, in
/// count mode) and the namespace it ran in.
pub fn sql_error_hint(msg: &str, query: &str, namespace: &str) -> Option<Hint> {
    let (code, rest) = sqlcode(msg)?;
    static TABLE: OnceLock<Regex> = OnceLock::new();
    static FIELD: OnceLock<Regex> = OnceLock::new();
    static RESERVED: OnceLock<Regex> = OnceLock::new();
    static OR_FORM: OnceLock<Regex> = OnceLock::new();
    static INSERT_IGNORE: OnceLock<Regex> = OnceLock::new();
    static ON_CONFLICT: OnceLock<Regex> = OnceLock::new();
    static DEEP: OnceLock<Regex> = OnceLock::new();
    static DQUOTE: OnceLock<Regex> = OnceLock::new();
    let table = re(r"Table '([^']+)' not found", &TABLE)
        .captures(rest)
        .map(|c| c[1].to_string());
    match code {
        -12 => {
            // The expected-terms list before the marker itself contains `$$` and `^`, so read
            // only what follows the last `^`: the statement up to where the parser stopped.
            let at = rest.rsplit('^').next()?.trim_end();
            (at.ends_with('$') && !at.ends_with("$$"))
                .then(|| Hint::new("sql_objectscript_function", vec![]))
        }
        -1 => {
            if let Some(c) = re(r"IDENTIFIER \((IGNORE|REPLACE)\) found", &OR_FORM).captures(rest) {
                if rest.contains("INSERT OR") {
                    return Some(Hint::new(
                        "nonstandard_insert",
                        vec![("form", format!("INSERT OR {}", &c[1]))],
                    ));
                }
            }
            let c = re(r"reserved word (\S+) found", &RESERVED).captures(rest)?;
            let word = spelled_word(query, &c[1]).unwrap_or(&c[1]).to_string();
            Some(Hint::new("reserved_word", vec![("word", word)]))
        }
        -25 => (rest.contains("Input (ON) encountered")
            && re(r"(?i)\bON\s+CONFLICT\b", &ON_CONFLICT).is_match(query))
        .then(|| Hint::new("nonstandard_insert", vec![("form", "ON CONFLICT".into())])),
        -29 => {
            let field = re(r"Field '([^']+)' not found", &FIELD).captures(rest)?[1].to_string();
            // Only where a value goes: after a comparison, a pattern keyword, THEN/ELSE, or inside
            // IN (...) / VALUES (...). A quoted name in a select list is an identifier.
            let literal = re(
                r#"(?i)(?:[=<>]|\bLIKE|%STARTSWITH|%CONTAINS|\bTHEN|\bELSE|\b(?:IN|VALUES)\s*\([^)]*?)\s*"([^"]*)""#,
                &DQUOTE,
            )
                .captures_iter(query)
                .map(|c| c.get(1).map_or("", |m| m.as_str()).to_string())
                .find(|s| s.to_uppercase() == field)?;
            Some(Hint::new(
                "double_quoted_string",
                vec![("literal", literal)],
            ))
        }
        -30 => {
            let table = table?;
            if table == "SQLUSER.IGNORE"
                && re(r"(?i)\bINSERT\s+IGNORE\b", &INSERT_IGNORE).is_match(query)
            {
                return Some(Hint::new(
                    "nonstandard_insert",
                    vec![("form", "INSERT IGNORE".into())],
                ));
            }
            let (schema, _) = table.split_once('.')?;
            if SYS_ONLY_SCHEMAS.contains(&schema) && !namespace.eq_ignore_ascii_case("%SYS") {
                let spelled = spelled(query, &table).unwrap_or(&table).to_string();
                return Some(Hint::new(
                    "sys_only_table",
                    vec![("table", spelled), ("namespace", namespace.to_string())],
                ));
            }
            // IRIS reports the last two parts of a name with three or more.
            let name = re(r"[%\w]+(?:\.[%\w]+){2,}", &DEEP)
                .find_iter(query)
                .map(|m| m.as_str())
                .find(|t| {
                    let parts: Vec<&str> = t.split('.').collect();
                    parts[parts.len() - 2..].join(".").to_uppercase() == table
                })?;
            let (pkg, last) = name.rsplit_once('.')?;
            Some(Hint::new(
                "deep_package_table",
                vec![
                    ("name", name.to_string()),
                    ("reported", table.clone()),
                    ("fixed", format!("{}.{last}", pkg.replace('.', "_"))),
                ],
            ))
        }
        _ => None,
    }
}

/// The hint for an `iris_execute` `IRIS_RUNTIME_ERROR` output run in `namespace`, if a rule matches.
pub fn runtime_error_hint(output: &str, namespace: &str) -> Option<Hint> {
    if namespace.eq_ignore_ascii_case("%SYS") {
        return None;
    }
    let line = output
        .lines()
        .find(|l| l.contains("<CLASS DOES NOT EXIST>"))?;
    // IRIS puts the class name last: `<CLASS DOES NOT EXIST> 150 Execute+7^Routine.1 Security.Users`.
    let class = line.split_whitespace().last()?.trim_start_matches('*');
    if !SYS_ONLY_PACKAGES.iter().any(|p| class.starts_with(p)) {
        return None;
    }
    Some(Hint::new(
        "sys_only_class",
        vec![("class", class.to_string())],
    ))
}
