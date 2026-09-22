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
