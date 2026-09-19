#!/usr/bin/env bash
# Seed GOLDEN-01's fixture into BENCHMARK. Wired as `[environment.healthcheck] command`,
# because a single-step Harbor task has no setup hook.
#
# The marker file is the whole reason this is safe to run from a healthcheck: the command fires again
# every interval, and a second seed would put the broken fixture back over whatever the agent fixed.
#
# The compile is allowed to fail. A fixture that does not compile is the task in most of this corpus,
# and a non-zero exit here would mean the fixture never landed at all.
set -uo pipefail

MARKER="${SEED_MARKER:-/tmp/.iad-seeded-golden-01}"
if [ -f "$MARKER" ]; then
  exit 0
fi

NS="${IRIS_NAMESPACE:-BENCHMARK}"
IAD="${IAD_BINARY:-iris-agentic-dev}"
work="$(mktemp -d)"

cat > "$work/Golden.Buggy.cls" <<'IAD_DOC_1_EOF'
Class Golden.Buggy Extends %RegisteredObject
{
ClassMethod Triple(n As %Integer) As %Integer
{
    Quit n * 3
}
Property Broken As %String [ SqlFieldName = ];
}
IAD_DOC_1_EOF
"$IAD" doc -n "$NS" put Golden.Buggy -f "$work/Golden.Buggy.cls"

"$IAD" tool iris_compile -a '{"target": "Golden.Buggy.cls", "namespace": "'"$NS"'"}' || true

# Named files and `rmdir`, not `rm -rf` on a variable. This runs as the container's healthcheck, and
# a recursive delete rooted on an expansion is not something to leave in a script that runs on a loop.
rm -f "$work"/*.cls
rmdir "$work" 2>/dev/null || true

# Last, and deliberately: the marker means "the fixture is in place", so nothing may set it earlier.
touch "$MARKER"
