#!/usr/bin/env bash
# The verifier for GOLDEN-01. Runs this task's own deterministic check and writes Harbor's reward
# file. No model, no rubric, no judge: the check prints PASS or FAIL from IRIS state (FR-003).
#
# Three outcomes, not two. A check that printed neither word, or both, or that could not run at all
# has graded nothing, and this writes no reward file for it — Harbor reads a missing reward as a
# trial with no reward, which is honest, where a `0` would file a harness fault in the arm's column.
set -uo pipefail

REWARD_DIR="${REWARD_DIR:-/logs/verifier}"
NS="${IRIS_NAMESPACE:-BENCHMARK}"
IAD="${IAD_BINARY:-iris-agentic-dev}"

output="$("$IAD" exec -n "$NS" 'set tOK = 0
try { set tOK = ($classmethod("Golden.Buggy","Triple",4) = 12) } catch { set tOK = 0 }
write $select(tOK:"PASS",1:"FAIL")' 2>&1)"
status=$?
if [ "$status" -ne 0 ]; then
  printf 'the check exited %s, so it answered neither PASS nor FAIL and no reward was written:\n%s\n' \
    "$status" "$output" >&2
  exit 1
fi

has_pass=0
has_fail=0
case "$output" in *PASS*) has_pass=1 ;; esac
case "$output" in *FAIL*) has_fail=1 ;; esac

if [ "$has_pass" -eq 1 ] && [ "$has_fail" -eq 0 ]; then
  reward=1.0
elif [ "$has_fail" -eq 1 ] && [ "$has_pass" -eq 0 ]; then
  reward=0.0
else
  printf 'check output is neither PASS nor FAIL, so it graded nothing and no reward was written: %s\n' \
    "$output" >&2
  exit 1
fi

mkdir -p "$REWARD_DIR"
printf '%s\n' "$reward" > "$REWARD_DIR/reward.txt"
