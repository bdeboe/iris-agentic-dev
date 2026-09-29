use clap::Parser;
use iris_agentic_dev::cmd::exec::{CodeSource, ExecCommand};

#[derive(Parser)]
struct TestCli {
    #[command(flatten)]
    cmd: ExecCommand,
}

fn parse(args: &[&str]) -> ExecCommand {
    let mut argv = vec!["test-cli"];
    argv.extend_from_slice(args);
    TestCli::parse_from(argv).cmd
}

#[test]
fn test_inline_code() {
    let cmd = parse(&["write $ZVersion,!"]);
    assert!(matches!(cmd.source(), CodeSource::Inline(_)));
}

#[test]
fn test_stdin_sentinel() {
    let cmd = parse(&["-"]);
    assert!(matches!(cmd.source(), CodeSource::Stdin));
}

#[test]
fn test_file_flag() {
    let cmd = parse(&["--file", "/tmp/script.os"]);
    assert!(matches!(cmd.source(), CodeSource::File(_)));
}

#[test]
fn test_no_code_is_stdin() {
    // No positional arg and no --file → defaults to stdin
    let cmd = parse(&[]);
    assert!(matches!(cmd.source(), CodeSource::Stdin));
}

#[test]
fn test_file_flag_path_preserved() {
    let cmd = parse(&["--file", "/tmp/my script.os"]);
    if let CodeSource::File(p) = cmd.source() {
        assert_eq!(p.to_str().unwrap(), "/tmp/my script.os");
    } else {
        panic!("expected CodeSource::File");
    }
}

#[test]
fn test_inline_code_with_namespace() {
    let cmd = parse(&["--namespace", "MYNS", "write 1,!"]);
    assert_eq!(cmd.conn.namespace, "MYNS");
    assert!(matches!(cmd.source(), CodeSource::Inline(_)));
}

#[test]
fn test_inline_code_preserved_verbatim() {
    let code = "write $ZVersion,!";
    let cmd = parse(&[code]);
    if let CodeSource::Inline(s) = cmd.source() {
        assert_eq!(s, code);
    } else {
        panic!("expected inline");
    }
}

// 130 round 4: a gate refusal carries `message`, not `output` or `error`, so `iad exec` printed
// nothing and exited 1. The purge of the leaked scratch classes hit exactly that.
#[test]
fn exec_prints_a_gate_refusal() {
    use iris_agentic_dev::cmd::exec::exec_text;
    let refusal = serde_json::json!({
        "success": false,
        "error_code": "CODE_EDIT_BLOCKED",
        "message": "Reaching class or routine code through arbitrary execution is blocked"
    });
    let text = exec_text(&refusal).expect("a refusal must print something");
    assert!(text.contains("CODE_EDIT_BLOCKED"), "{text}");
    assert!(text.contains("is blocked"), "{text}");

    let ok = serde_json::json!({"success": true, "output": "1\n"});
    assert_eq!(exec_text(&ok).as_deref(), Some("1\n"));
    let err = serde_json::json!({"success": false, "error": "TIMEOUT"});
    assert_eq!(exec_text(&err).as_deref(), Some("TIMEOUT\n"));
}
