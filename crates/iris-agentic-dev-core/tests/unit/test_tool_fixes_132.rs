//! 132 B2 and B3: two tool bugs the AI Hub ladder hit on 139.
//!
//! B2: `iris_execute_method` wrote a returned %Status as it is, so an error status reached the
//! agent as `"0 \u0000+\u0004"` with `success: true`. SKILL-24 (tools, repeat 0) called
//! `Security.Applications.Create` 17 times and never learned why it failed.
//! B3: `iris_ws_exec` sent multi-line code as one terminal input, and the terminal read the
//! newline as part of line 1, so every multi-line call ended in `<SYNTAX>` (SKILL-24,
//! tools+iris-ai-hub, repeat 0, calls 51-68). The live half is
//! `tests/integration/test_tool_fixes_132_live.rs`.

use iris_agentic_dev_core::iris::ws_session::terminal_lines;
use iris_agentic_dev_core::tools::doc::{execute_method_code, method_output};

#[test]
fn a_returned_error_status_is_decoded_by_the_generated_code() {
    let code = execute_method_code("##class(%Library.Integer).IsValid(\"abc\")");
    assert!(
        code.contains("$System.Status.GetErrorText(result)"),
        "{code}"
    );
    assert!(code.contains("$ListValid($Extract(result,3,*))"), "{code}");
}

#[test]
fn the_generated_code_has_no_braces() {
    // The docker exec path runs the code line by line in a terminal, where a block cannot
    // span lines.
    let code = execute_method_code("##class(A.B).C()");
    assert!(!code.contains('{') && !code.contains('}'), "{code}");
}

#[test]
fn a_plain_value_is_the_first_line() {
    assert_eq!(method_output("1\nside effect\n"), Ok("1".to_string()));
}

#[test]
fn an_error_status_is_an_err_with_its_text() {
    let out = "IAD_STATUS_ERROR:ERROR #7207: Datatype value 'abc' is not a valid number\n";
    assert_eq!(
        method_output(out),
        Err("ERROR #7207: Datatype value 'abc' is not a valid number".to_string())
    );
}

#[test]
fn a_multi_error_status_keeps_every_line() {
    let out = "IAD_STATUS_ERROR:ERROR #5001: one\r\nERROR #5001: two\n";
    let err = method_output(out).unwrap_err();
    assert!(err.contains("one") && err.contains("two"), "{err}");
}

#[test]
fn terminal_lines_splits_on_newlines_and_drops_blank_lines() {
    assert_eq!(
        terminal_lines("Set a=1\r\nSet b=2\n\n   \n Write a+b"),
        vec!["Set a=1", "Set b=2", " Write a+b"]
    );
}

#[test]
fn a_single_line_is_one_input() {
    assert_eq!(terminal_lines("write 1+1"), vec!["write 1+1"]);
}

#[test]
fn empty_code_is_one_empty_input() {
    // An empty input still answers with a prompt, which is what an agent sending "" gets today.
    assert_eq!(terminal_lines(""), vec![""]);
}
