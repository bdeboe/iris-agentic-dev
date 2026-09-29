//! Spec 131 US1 over the wire: the `iris_info` description and the `sa_schema` refusal.
//!
//! The refusal must reach a caller with no IRIS configured, because the name check runs before the
//! server is resolved. That is also what stops a cube name from costing an IRIS round trip.

use iris_agentic_dev_core::testing::{answer_text, call_tool_with_env, require_iad_binary};

#[test]
#[ignore = "spawns the built binary; run with --include-ignored"]
fn iris_info_description_says_studio_assist_grammar() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let tools = iris_agentic_dev_core::testing::advertised_tools();
    let desc = tools["iris_info"]["description"]
        .as_str()
        .expect("iris_info has a description")
        .to_string();
    assert!(!desc.contains("SQL Analytics"), "{desc}");
    assert!(desc.contains("Studio Assist grammar"), "{desc}");
    assert!(desc.contains("XData namespace URL"), "{desc}");
}

#[test]
#[ignore = "spawns the built binary; run with --include-ignored"]
fn a_cube_name_is_refused_without_iris() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let answer = call_tool_with_env(
        "iris_info",
        &serde_json::json!({"what": "sa_schema", "name": "HoleFoods"}),
        &[],
    );
    let text = answer_text(&answer);
    assert!(text.contains("INVALID_PARAMS"), "{text}");
    assert!(text.contains("%GetCubeList"), "{text}");
    assert!(!text.contains("IRIS_UNREACHABLE"), "{text}");
}
