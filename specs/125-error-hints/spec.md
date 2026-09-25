# 125: Error hints

**Status**: in progress, local only (freeze). **Origin**: 123 follow-up (e), plus one row from the
2026-09-23 iad vs AGENTS.md todo-app comparison.

## Problem

iad passes IRIS errors through as IRIS wrote them. That is right for the error text, but an agent
that has never seen the error has to guess what to change. Two cases from real runs:

1. **SQLCODE -12 at `$`.** The 123 demo put `$ZDATETIME($HOROLOG,3)` inside an INSERT.
   `iris_query` returned `ERROR #5540: SQLCODE: -12 ... ^ INSERT INTO ... VALUES ( $`. The fix,
   `CURRENT_TIMESTAMP`, is in `objectscript-sql-patterns` §7, but the agent only finds it if it
   goes looking.
2. **`<CLASS DOES NOT EXIST>` for a %SYS class.** In the comparison run, arm B's first
   `iris_execute` called `##class(Security.Applications)` in USER and got
   `ERROR: <CLASS DOES NOT EXIST> 150 Execute+11^IrisDevTmp... Security.Applications`. Nothing
   said the class lives only in %SYS.

## Requirements

- **FR-001**: An `iris_query` `SQL_ERROR` response carries a `hint` string when the error matches
  a row in the hint table. `error` is unchanged.
- **FR-002**: An `iris_execute` `IRIS_RUNTIME_ERROR` response carries a `hint` on the same terms,
  on every execution path (Atelier, docker exec, docker exec fallback).
- **FR-003**: An error that matches no row gets no `hint` key. A wrong hint is worse than none.
- **FR-004**: A row goes into the table only after its error was reproduced live on
  `iris-dev-iris`, and the evidence goes in `research.md`.
- **FR-005**: Every hint names the skill section it came from, and a test fails if that section
  heading is missing from the skill file.
- **FR-006**: `iris_execute`'s description says which packages need `namespace: "%SYS"`, so the
  agent can get it right before the first error.

## Rows

| Tool           | Match                                                                                   | Hint names                                          |
| -------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `iris_query`   | `SQLCODE: -12` and the text after the parser's last `^` ends at a lone `$`              | `CURRENT_TIMESTAMP`; `objectscript-sql-patterns` §7 |
| `iris_execute` | `<CLASS DOES NOT EXIST>`, class in `Security.`, `Config.` or `SYS.`, namespace not %SYS | `namespace: "%SYS"`; `iris-agentic-dev` skill       |

## Out of scope

- Hints for other runtime errors (`<PROTECT>`, `<UNDEFINED>`, ...). Each needs its own live
  reproduction first.
- `%`-prefixed packages (`%SYS.*`, `%SYSTEM.*`): they resolve in every namespace, so no hint.

## Findings

- **F1: the docker exec path reports a runtime error as success.** With `docker_only = true`,
  `Write ##class(Config.Namespaces).Exists("USER")` in USER returns `success: true` and the output
  `<CLASS DOES NOT EXIST> *Config.Namespaces`. `is_generator_error` looks for an `ERROR:` prefix,
  which the terminal never writes, so neither `IRIS_RUNTIME_ERROR` nor the hint is set on that path.
  The hint is wired there and fires once the error is detected. Detecting terminal errors is its
  own fix, not part of this spec.
