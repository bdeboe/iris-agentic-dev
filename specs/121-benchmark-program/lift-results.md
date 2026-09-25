# Per-tool attribution

Run `ladder-121-tools-holdout`, tool surface `1.4.2+fa0b694f8725`. This is a join over that run's sessions and cost no extra ones: every session recorded which tools it called and what came back, and every task already had a machine verdict.

19 of 81 advertised tools were reached for. 17 had an applicable task and were passed over: `compare_document`, `find_subclass_implementations`, `global_kill`, `global_preview`, `iris_debug`, `iris_generate`, `iris_macro`, `resolve_dynamic_dispatch`, `resolve_storage`, `skill`, `skill_community`, `skill_community_list`, `skill_describe`, `skill_forget`, `skill_list`, `skill_search`, `stream_inspect`.

45 had no applicable task in this corpus, which is a statement about the corpus and not about the tool.

Applicability is declared in `tests/e2e/skill_eval/tool_applicability.toml`, committed before the run. `pass_rate_when_called` is observational — which tasks called a tool was the agent's choice, not an assignment — so it is not a lift and the two rates below are not comparable as one.

## Reach

| Tool | Domain | Applicable | Reached | Reach rate | Calls | Failed | Verdict |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `compare_document` | objectscript-code | 62 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `find_subclass_implementations` | introspection | 62 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `global_kill` | globals | 6 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `global_preview` | globals | 6 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `iris_debug` | debugging | 1 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `iris_generate` | objectscript-code | 62 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `iris_macro` | objectscript-code | 62 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `resolve_dynamic_dispatch` | introspection | 62 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `resolve_storage` | storage | 1 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_community` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_community_list` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_describe` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_forget` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_list` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `skill_search` | skills | 12 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `stream_inspect` | streams | 1 | 0 | 0% | 0 | 0 | a task needed it and the agent chose otherwise |
| `iris_doc` | objectscript-code | 62 | 41 | 66% | 270 | 0 | reached |
| `iris_execute_method` | execution | 62 | 34 | 55% | 200 | 0 | reached |
| `iris_compile` | objectscript-code | 62 | 30 | 48% | 67 | 0 | reached |
| `iris_symbols` | introspection | 62 | 26 | 42% | 44 | 0 | reached |
| `iris_execute` | execution | 62 | 19 | 31% | 65 | 0 | reached |
| `iris_info` | instance-admin | 0 | 15 | — | 22 | 2 | reached |
| `docs_introspect` | introspection | 62 | 10 | 16% | 12 | 0 | reached |
| `iris_search` | objectscript-code | 62 | 7 | 11% | 18 | 0 | reached |
| `iris_doc_search` | objectscript-code | 62 | 6 | 10% | 15 | 0 | reached |
| `iris_query` | sql | 15 | 6 | 40% | 26 | 0 | reached |
| `iris_add_server` | configuration | 0 | 5 | — | 6 | 0 | reached |
| `iris_servers` | configuration | 0 | 5 | — | 5 | 0 | reached |
| `iris_symbols_local` | introspection | 62 | 4 | 6% | 8 | 0 | reached |
| `iris_global` | globals | 6 | 3 | 50% | 5 | 0 | reached |
| `iris_generate_test` | testing | 0 | 2 | — | 2 | 2 | reached |
| `iris_table_info` | sql | 15 | 2 | 13% | 2 | 0 | reached |
| `iris_generate_class` | objectscript-code | 62 | 1 | 2% | 1 | 1 | reached |
| `iris_reload_pool` | configuration | 0 | 1 | — | 1 | 0 | reached |
| `iris_test` | testing | 0 | 1 | — | 1 | 0 | reached |
| `agent_history` | agent-audit | 0 | 0 | — | 0 | 0 | no task needed it |
| `agent_stats` | agent-audit | 0 | 0 | — | 0 | 0 | no task needed it |
| `capability_matrix` | access | 0 | 0 | — | 0 | 0 | no task needed it |
| `check_config` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `compare_namespace` | namespace-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `extract_message_map_routing` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `hl7_schema_inspect` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `hl7_schema_list` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_admin` | instance-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_business_rule_info` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_containers` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_coverage` | testing | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_credential_list` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_credential_manage` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_database_list` | instance-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_database_stats` | instance-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_get_log` | instance-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_import_servers` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_interop_query` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_lookup_manage` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_lookup_transfer` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_message_body` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_mirror_status` | mirroring | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_namespace_create` | namespace-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_namespace_list` | namespace-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_production` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_production_diff` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_production_item` | interop | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_remove_server` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_source_control` | source-control | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_system_performance` | instance-admin | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_test_server` | configuration | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_ws_close` | interactive-session | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_ws_exec` | interactive-session | 0 | 0 | — | 0 | 0 | no task needed it |
| `iris_ws_open` | interactive-session | 0 | 0 | — | 0 | 0 | no task needed it |
| `journal_search` | journalling | 0 | 0 | — | 0 | 0 | no task needed it |
| `kb` | knowledge-base | 0 | 0 | — | 0 | 0 | no task needed it |
| `kb_index` | knowledge-base | 0 | 0 | — | 0 | 0 | no task needed it |
| `kb_recall` | knowledge-base | 0 | 0 | — | 0 | 0 | no task needed it |
| `mermaid_class` | diagram | 0 | 0 | — | 0 | 0 | no task needed it |
| `mermaid_production` | diagram | 0 | 0 | — | 0 | 0 | no task needed it |
| `my_access` | access | 0 | 0 | — | 0 | 0 | no task needed it |
| `query_audit_log` | auditing | 0 | 0 | — | 0 | 0 | no task needed it |
| `telemetry_export_trace` | telemetry | 0 | 0 | — | 0 | 0 | no task needed it |
| `telemetry_query` | telemetry | 0 | 0 | — | 0 | 0 | no task needed it |

## What came back when a call failed

| Tool | Failed calls | What came back |
| --- | ---: | --- |
| `iris_generate_test` | 2 | 2x MCP error -32600: LLM_UNAVAILABLE: Set IRIS_GENERATE_CLASS_MODEL and OPENAI_API_KEY |
| `iris_info` | 2 | 1x MCP error -32600: SERVER_NOT_FOUND: no server named 'dev-bench' in pool. Use iris_servers to list available instances.; 1x MCP error -32600: SERVER_NOT_FOUND: no server named 'dev-benchmark' in pool. Use iris_servers to list available instances. |
| `iris_generate_class` | 1 | 1x MCP error -32600: LLM_UNAVAILABLE: Set IRIS_GENERATE_CLASS_MODEL and OPENAI_API_KEY |
