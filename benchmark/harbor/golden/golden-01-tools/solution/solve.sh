#!/usr/bin/env bash
# The reference solution for GOLDEN-01, applied the same way the fixture was.
#
# This is what tells a hard task from a check that cannot grade (FR-022). Harbor runs it in place of the agent,
# and the verifier must then report a reward of 1.0; if it does not, the task grades nothing and no
# arm's score from it means anything.
set -euo pipefail

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
}
IAD_DOC_1_EOF
"$IAD" doc -n "$NS" put Golden.Buggy -f "$work/Golden.Buggy.cls"

"$IAD" tool iris_compile -a '{"target": "Golden.Buggy.cls", "namespace": "'"$NS"'"}'

rm -f "$work"/*.cls
rmdir "$work" 2>/dev/null || true
