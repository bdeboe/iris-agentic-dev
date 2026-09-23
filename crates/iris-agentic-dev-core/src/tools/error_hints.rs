//! Hints for IRIS errors an agent is known to hit (spec 125).
//!
//! iad hands IRIS errors back in IRIS's words, which is right for `error` but leaves an agent that
//! has never seen one guessing at the fix. Each row here adds a `hint` that names the fix and the
//! skill section it came from. A row goes in only after its error was reproduced live
//! (`specs/125-error-hints/research.md`), and anything unmatched gets no hint: a wrong hint sends
//! the agent further off than the raw error does.

/// SQLCODE -12 with the parser's marker at a lone `$`: an ObjectScript function inside SQL.
const SQL_OBJECTSCRIPT_FUNCTION: (&str, &str) = (
    "objectscript-sql-patterns",
    "7. ObjectScript Operators That Break Inside SQL Strings",
);

/// `<CLASS DOES NOT EXIST>` for a class that exists only in %SYS.
const SYS_ONLY_CLASS: (&str, &str) = (
    "iris-agentic-dev",
    "`<CLASS DOES NOT EXIST>` for a system class",
);

/// Packages whose classes resolve only in %SYS (research R2). `%SYS.*` and `%SYSTEM.*` are not
/// here: `%` packages resolve in every namespace.
const SYS_ONLY_PACKAGES: &[&str] = &["Security.", "Config.", "SYS."];

/// Every `(skill, heading)` a hint cites. A test checks each heading exists in its SKILL.md.
pub fn cited_sections() -> &'static [(&'static str, &'static str)] {
    &[SQL_OBJECTSCRIPT_FUNCTION, SYS_ONLY_CLASS]
}

/// The hint for an `iris_query` `SQL_ERROR` message, if a row matches.
pub fn sql_error_hint(msg: &str) -> Option<String> {
    if !msg.contains("SQLCODE: -12") {
        return None;
    }
    // The expected-terms list before the marker itself contains `$$` and `^`, so read only what
    // follows the last `^`: the statement up to where the parser stopped.
    let at = msg.rsplit('^').next()?.trim_end();
    if !at.ends_with('$') || at.ends_with("$$") {
        return None;
    }
    let (skill, heading) = SQL_OBJECTSCRIPT_FUNCTION;
    Some(format!(
        "The parser stopped at `$`: an ObjectScript function such as $ZDATETIME or $HOROLOG is \
         inside the SQL. Use the SQL spelling, e.g. CURRENT_TIMESTAMP for \
         $ZDATETIME($HOROLOG,3), or pass the value as a ? parameter. Skill {skill}, \"{heading}\"."
    ))
}

/// The hint for an `iris_execute` `IRIS_RUNTIME_ERROR` output run in `namespace`, if a row matches.
pub fn runtime_error_hint(output: &str, namespace: &str) -> Option<String> {
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
    let (skill, heading) = SYS_ONLY_CLASS;
    Some(format!(
        "{class} exists only in %SYS. Rerun with namespace: \"%SYS\". Skill {skill}, \"{heading}\"."
    ))
}
