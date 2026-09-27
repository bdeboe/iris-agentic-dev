//! `iris_macro` advertises `includes` — 130 round 3.
//!
//! The fix resolves a macro in named includes, or finds the include itself. A caller that knows the
//! include should be able to say so, so the param must reach `tools/list`, not only the struct.

use iris_agentic_dev_core::testing::{require_iad_binary, resolve_property};

#[test]
#[ignore = "spawns the built binary; run with --include-ignored"]
fn iris_macro_advertises_includes_as_a_string_array() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let schemas = iris_agentic_dev_core::testing::advertised_schemas();
    let schema = schemas
        .get("iris_macro")
        .expect("iris_macro must appear in tools/list");
    let includes = resolve_property(schema, "includes");
    let text = includes.to_string();
    assert!(
        text.contains("array"),
        "`includes` must be an array: {includes}"
    );
    assert!(
        text.contains("string"),
        "`includes` items are include names: {includes}"
    );
}
