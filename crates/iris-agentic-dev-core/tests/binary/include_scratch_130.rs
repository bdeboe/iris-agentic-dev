//! `iris_info` and `iris_doc` advertise `include_scratch` — 130 round 4 (FR-016).
//!
//! Both tools now hide the `IrisDevTmp` scratch package by default. A caller who wants it back has
//! to be able to find the switch, so the param must reach `tools/list`, not only the struct.

use iris_agentic_dev_core::testing::{require_iad_binary, resolve_property};

#[test]
#[ignore = "spawns the built binary; run with --include-ignored"]
fn iris_info_and_iris_doc_advertise_include_scratch_as_a_boolean() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let schemas = iris_agentic_dev_core::testing::advertised_schemas();
    for tool in ["iris_info", "iris_doc"] {
        let schema = schemas
            .get(tool)
            .unwrap_or_else(|| panic!("{tool} must appear in tools/list"));
        let prop = resolve_property(schema, "include_scratch");
        assert!(
            prop.to_string().contains("boolean"),
            "{tool}: `include_scratch` must be a boolean: {prop}"
        );
    }
}
