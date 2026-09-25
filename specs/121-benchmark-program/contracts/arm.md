# Contract: Arm

Three configurations under test, and the assertions that make the bare arm believable. Implemented by
`tests/e2e/skill_eval/arms.py` (T025).

Plan.md calls this the harder of the two hard parts, and it is not the arithmetic. Every way the bare
arm can be contaminated produces a plausible-looking number rather than an error, which means the
failure is invisible in exactly the case that matters most: a bare arm that quietly had the tools
reports a small lift, and a small lift is the answer the whole program is trying to establish.

## The three arms

| Arm            | MCP servers                | Skills on disk | Toolset  |
| -------------- | -------------------------- | -------------- | -------- |
| `bare`         | none                       | no             | —        |
| `tools`        | iad, `transport = "stdio"` | no             | `Merged` |
| `tools+skills` | iad, `transport = "stdio"` | yes            | `Merged` |

**An arm is `task.toml`, not code (FR-023).** Harbor's `[[environment.mcp_servers]]` is a first-class
section, so the three arms are three configurations of a published schema. `arms.py` therefore does
only what the schema cannot: generate the three variants from one source task, and assert absence,
which no schema can check.

**The tools arm registers `Merged`, and that fixes the denominator.** Constitution III requires
`Merged` tools to work without `IRIS_CONTAINER`, which is the constraint a Harbor task runs under
anyway — the agent container is not the IRIS container. Docker-dependent `Baseline` tools cannot
reach IRIS from inside a task container, so Story 5 reports them **out of scope** rather than
unreached. Counting them as unreached would measure the harness.

## Comparisons are adjacent only

`bare` → `tools` is the tool surface's value. `tools` → `tools+skills` is a skill document's value.

A `bare` → `tools+skills` figure bundles both and gets attributed to whichever one is being sold at
the time. It is the most flattering number available and it is not reported. This is the whole reason
there are three arms and not two.

## Absence is asserted, not arranged

`assert_absent()` **raises**. It does not return a bool, so no caller can ignore it, and a
contaminated arm fails the run rather than reporting a number (FR-002). The four facts, from plan.md's
Complexity Tracking, each corresponding to a real way this breaks:

**A1 — No MCP registration anywhere on the resolution path.** Not just the task's `task.toml`: a
user-level config, a project-level config, or a stale entry from a previous run all reach the agent.
Check every path the driver resolves, not the one the harness wrote.

**A2 — No reachable skill file.** A skill directory on a search path is enough. The bare arm and the
tools arm differ from `tools+skills` here, and both must be clean.

**A3 — No `CLAUDE.md` naming an iad tool.** Prose is a tool hint. A `CLAUDE.md` saying "use
`iris_query` to inspect globals" hands over the tool surface's discoverability without registering a
single tool — which is the part Story 5 measures.

**A4 — No cached transcript.** A resumed session carries prior tool knowledge. The bare arm starts
cold.

The recorded `absence_facts` list is what makes the run auditable after the fact. An arm reporting a
number with an empty `absence_facts` is itself a failure — silence is not a clean environment.

This is the same class as the `clean_command` problem the Rust tests already have, and it gets the
same treatment: assert the absence, do not arrange it and hope.

## Test obligations

`test_arms.py`, before `arms.py` (Constitution IV). Each negative case constructs the specific
contamination and asserts a raise, because a test that only checks the happy path checks nothing here:

| Obligation                                                              | Fact   |
| ----------------------------------------------------------------------- | ------ |
| A stale MCP registration in a non-task config → raises                  | A1     |
| A reachable skill file → raises                                         | A2     |
| A `CLAUDE.md` naming an iad tool → raises                               | A3     |
| A cached transcript → raises                                            | A4     |
| A genuinely clean environment → passes, `absence_facts` non-empty       | A1–4   |
| `assert_absent()` returns no value — a bool return is itself a failure  | FR-002 |
| The three arms generate three `task.toml` variants from one source task | FR-023 |
| The bare variant has no `[[environment.mcp_servers]]` table at all      | FR-023 |
