//! Spec 131 US4: the `&sql` translator's output has to run in terminal mode.
//!
//! `translate_sql_macros` only matters on the docker exec path now, which pipes code into
//! `iris session` a line at a time. Before 131 its SELECT INTO output read every column by its
//! expression text (`%Get("COUNT(*)")`, `<PROPERTY DOES NOT EXIST>`), left SQLCODE unset when a row
//! came back, and opened an `if ... {` block the docker path's own guard refuses.

use iris_agentic_dev_core::tools::translate_sql_macros;
use iris_agentic_dev_core::tools::write_gate::contains_terminal_block_syntax;

#[test]
fn an_expression_column_is_read_by_position() {
    let r = translate_sql_macros("&sql(SELECT COUNT(*) INTO :n FROM Sample.Person)");
    assert!(
        r.translated_code.contains("%GetData(1)"),
        "{}",
        r.translated_code
    );
    assert!(
        !r.translated_code.contains("%Get(\""),
        "{}",
        r.translated_code
    );
}

#[test]
fn a_top_clause_stays_in_the_prepared_sql() {
    let r = translate_sql_macros("&sql(SELECT TOP 1 Name INTO :n FROM Sample.Person)");
    assert!(
        r.translated_code
            .contains("%Prepare(\"SELECT TOP 1 Name FROM Sample.Person\")"),
        "{}",
        r.translated_code
    );
    assert!(
        r.translated_code.contains("%GetData(1)"),
        "{}",
        r.translated_code
    );
}

#[test]
fn every_host_variable_gets_its_own_column_number() {
    let r =
        translate_sql_macros("&sql(SELECT Name, 1/:d, Age INTO :a, :b, :c FROM T WHERE ID = :id)");
    let code = &r.translated_code;
    for (var, col) in [("a", 1), ("b", 2), ("c", 3)] {
        assert!(
            code.contains(&format!(
                "{var} = $Select(sqlnx1:sqlrs1.%GetData({col}),1:\"\")"
            )),
            "{var} should read column {col}: {code}"
        );
    }
}

#[test]
fn select_into_output_has_no_block_syntax() {
    let r = translate_sql_macros(
        "&sql(SELECT Name INTO :n FROM T WHERE ID = :id)\nWrite SQLCODE,\":\",n,!",
    );
    assert!(
        !contains_terminal_block_syntax(&r.translated_code),
        "the docker path refuses braces: {}",
        r.translated_code
    );
}

#[test]
fn select_into_sets_sqlcode_whether_or_not_a_row_came_back() {
    let r = translate_sql_macros("&sql(SELECT Name INTO :n FROM T)");
    let code = &r.translated_code;
    assert!(
        code.contains("sqlSQLCODE1 = $Select(sqlnx1:0,1:sqlrs1.%SQLCODE)"),
        "{code}"
    );
    assert!(code.contains("SQLCODE = sqlSQLCODE1"), "{code}");
    assert!(code.contains("%msg = sqlrs1.%Message"), "{code}");
}

#[test]
fn sqlcode_on_the_macro_line_reads_the_real_variable() {
    // Real &sql sets SQLCODE itself, so a check on the same line has to see it too, not only a
    // check on the line after.
    let r = translate_sql_macros("&sql(SELECT Name INTO :n FROM T) Write SQLCODE,!");
    assert!(
        r.translated_code.contains("SQLCODE = sqlSQLCODE1"),
        "{}",
        r.translated_code
    );
}

#[test]
fn dml_sets_sqlcode_msg_and_rowcount() {
    let r = translate_sql_macros("&sql(DELETE FROM T WHERE ID = :id)\nWrite SQLCODE,!");
    let code = &r.translated_code;
    assert!(code.contains("sqlSQLCODE1 = sqlrs1.%SQLCODE"), "{code}");
    assert!(code.contains("SQLCODE = sqlSQLCODE1"), "{code}");
    assert!(code.contains("%ROWCOUNT = sqlrs1.%ROWCOUNT"), "{code}");
    assert!(!contains_terminal_block_syntax(code), "{code}");
}
