# Quickstart: running the 123 tests

## Tier claims and scrub (no IRIS)

```bash
cargo test -p iris-agentic-dev-core --features testing --test unit -- \
  test_description_tiers test_example_scrub
```

The scrub test prints `denylist absent — names unchecked` unless `.iad-local/denylist.txt`
exists at the repo root. That file is gitignored. It holds one name per line, and `#` starts a
comment.

## Round trip (live `iris-dev-iris`, `#[ignore]`)

```bash
cargo build -p iris-agentic-dev
IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS \
  cargo test -p iris-agentic-dev-core --features testing --test integration -- \
  test_todo_example_live --include-ignored --test-threads=1 --nocapture
```

The test sets the write, destructive and admin tiers in the server it spawns, so the shell does
not need them. Without `IRIS_HOST` it panics. It builds the example as `IADEx123.*` on
`/iadex123-todo` and removes all of it afterwards. It never touches `Demo.*` or `/todo`.

## Pool reload wording (no IRIS)

```bash
cargo test -p iris-agentic-dev-core --features testing --test unit -- test_pool_reload_wording
cargo build -p iris-agentic-dev
IAD_BINARY=./target/debug/iris-agentic-dev \
  cargo test -p iris-agentic-dev-core --features testing --test binary -- pool_reload_hint \
  --include-ignored
```

The binary test adds a server in a temp `HOME`, calls `iris_reload_pool`, sees the server in
`iris_servers`, removes it and reloads again. It needs no IRIS, because the server points at
`127.0.0.1:1`.

## SC-006: `tools/list` payload

Measured on 2026-09-22 against the debug binary with an empty `HOME`, as the compact JSON of the
`tools/list` result. "Before" swaps in the descriptions from `master` at `5f38c46`.

| Build  | Bytes   | Tools |
| ------ | ------- | ----- |
| before | 107,760 | 81    |
| after  | 108,505 | 81    |

The payload grew by 745 bytes (0.7%), and all of it is description text. Eleven descriptions
changed: the nine tier corrections, plus `iris_add_server` and `iris_import_servers`, which now
name `iris_reload_pool` instead of a restart. `iris_remove_server` is one of the nine and
carries both changes.
