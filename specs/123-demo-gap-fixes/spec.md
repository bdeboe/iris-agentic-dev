# Feature Specification: fix what the todo-app demo exposed

**Feature Branch**: `123-demo-gap-fixes`
**Created**: 2026-09-22
**Status**: Draft
**Input**: a grilling session on the gaps found while building a todo app on IRIS from one prompt,
in answer to a PM's question. Twelve decisions settled one at a time; this spec records them.

## Measured starting point

The demo worked: one prompt, 25 tool calls, 4 min 53 s, a live app at `/todo`. Reading the
transcript afterwards turned up three things wrong with iad itself, each checked on `master`
(`5f38c46`) on 2026-09-22:

1. **Tool descriptions contradict the gate table on eighteen actions across nine tools.** In the
   demo the agent read "write tier" in `iris_admin`'s description, called `create_webapp`, and was
   refused with `iris_admin is a destructive tool and the destructive tier is disabled`. Reading
   all 81 registered descriptions against `CLASSIFICATION` in `write_gate.rs`:

   | Tool                     | Description says                                                                                                             | Table resolves                      |
   | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
   | `iris_admin`             | write: `create_user`, `update_user`, `delete_user`, `create_namespace`, `delete_namespace`, `create_webapp`, `delete_webapp` | destructive (the `mixed()` default) |
   | `global_kill`            | `WRITE-GATED`                                                                                                                | destructive                         |
   | `iris_namespace_create`  | `WRITE-GATED`                                                                                                                | destructive                         |
   | `iris_credential_manage` | `Write-gated` for create, update, delete                                                                                     | destructive                         |
   | `iris_lookup_manage`     | `set/delete write-gated`                                                                                                     | destructive                         |
   | `iris_global`            | nothing about `kill`                                                                                                         | destructive                         |
   | `skill`                  | nothing about `forget`                                                                                                       | destructive                         |
   | `iris_remove_server`     | nothing                                                                                                                      | destructive                         |
   | `skill_forget`           | nothing                                                                                                                      | destructive                         |

   Fourteen are wrong claims; four are destructive actions described as if ungated. For
   `global_kill` the description understates the gate on the single most destructive tool in the
   surface.

2. **Nothing checks any of this.** Ten descriptions mention a gate in some form, and two of those
   (`iris_query`'s "destructive SQL blocked", `check_config`'s `destructive_tools_source`) use the
   word without claiming a tier. Three more name other gates entirely
   (`Execute-gated` twice, `PHI-gated` once).
3. **One SQL fact the demo paid for is in no skill, and one the demo wrote down is false.**
   `$ZDATETIME($HOROLOG,3)` inside an SQL INSERT fails with SQLCODE -12, and `CURRENT_TIMESTAMP`
   is the SQL spelling. The demo's `STEPS.md` also says a property's `InitialExpression` fires on
   `%Save()` but not on an SQL INSERT. Reproduced on `iris-dev-iris` (2026.2.0L build 208U), that
   is wrong: an INSERT that omits the column gets the `InitialExpression` value, including the
   braced `{$ZDateTime($Horolog,3)}` form (`research.md` R2). The agent asserted it without
   checking, which is the more useful thing for a skill to correct.

The demo itself sits untracked in `demos/todo-app/`. It is the clearest evidence this project has
of which work iad does and which the host does (12 of 25 calls, the twelve that touched IRIS), but
the files name a customer and a colleague, carry home-directory paths, and the raw JSONL holds hook
output that cannot be audited by hand.

## User Scenarios & Testing

### User Story 1 - An agent reads a tool description and gets the gate right (Priority: P1)

An agent deciding whether it can call a tool reads the description. Whatever tier the description
names is the tier the call will meet.

**Why this priority**: a description that understates the gate sends the agent into a refusal it
could have predicted, and on `global_kill` it misstates the protection around permanent data loss.
It is the only finding that is wrong rather than missing.

**Independent Test**: one test reads every tool description and the gate table and compares them.
It fails today on exactly the eighteen actions above and passes once the text is corrected.

**Acceptance Scenarios**:

1. **Given** a description names a tier for a tool or action, **When** the test runs, **Then** the
   named tier equals the tier `write_gate.rs` resolves for it.
2. **Given** a tool or action resolves to the destructive tier, **When** the test runs, **Then**
   its description says destructive, and a description that says nothing about gating fails.
3. **Given** a read-only or write-tier tool whose description is silent on gating, **When** the
   test runs, **Then** it passes; silence is only a failure for the destructive tier.
4. **Given** someone adds a new destructive action to a `mixed()` map without touching the
   description, **When** the test runs, **Then** it fails naming the tool and the action.

---

### User Story 2 - An agent that hits SQLCODE -12 or an empty column finds the reason in a skill (Priority: P2)

An agent writing ObjectScript that builds SQL, or a developer reading the skills, meets the two
facts where they look for that kind of mistake.

**Why this priority**: the demo agent recovered from the -12 in one step by itself; the
`InitialExpression` belief sends an agent to populate columns by hand that IRIS already fills.
Real, but it costs time, not correctness.

**Independent Test**: each fact is reproduced live against `iris-dev-iris` with the exact error or
value recorded, and the skill text quotes what the reproduction returned.

**Acceptance Scenarios**:

1. **Given** `objectscript-sql-patterns` §7 (ObjectScript that breaks inside SQL strings), **When**
   read, **Then** it has a third example: `$ZDATETIME` inside an INSERT, the SQLCODE the live
   reproduction returned, and `CURRENT_TIMESTAMP` as the fix.
2. **Given** `iris-sql`'s "Key IRIS INSERT constraints" list, **When** read, **Then** it states
   that `InitialExpression` also supplies the value when an SQL INSERT omits the column, so it
   need not be populated by hand.
3. **Given** `objectscript-sql-patterns`, **When** read, **Then** one line points to the
   `iris-sql` entry for the `InitialExpression` case.
4. **Given** the reproduction returns something other than what this spec says, **Then** the skill
   records what IRIS returned and this spec is corrected, not the other way round.

---

### User Story 3 - Someone evaluating iad reads a worked example that still works (Priority: P2)

A reader in `docs/examples/todo-app/` sees the two classes, the steps, and the call-by-call
transcript showing which calls were iad and which were the host, and can reproduce the app.

**Why this priority**: it is the most concrete account this project has of what iad adds. It must
not leak names, and it must not rot into a claim that no longer holds.

**Independent Test**: a scrub test over the published files, and a live round-trip test that builds
the app on a throwaway path and exercises it the way step 5 of `STEPS.md` does.

**Acceptance Scenarios**:

1. **Given** the published directory, **When** listed, **Then** it holds `Demo.Todo.cls`,
   `Demo.TodoREST.cls`, `STEPS.md` and `transcript.md`, and no JSONL, bundler script or cache.
2. **Given** the published files, **When** the scrub test runs, **Then** it fails on any home
   directory path, email address, system-reminder or hook-context marker, or credential literal
   beyond the documented `_SYSTEM`/`SYS` container default.
3. **Given** a local denylist exists at a fixed gitignored path, **When** the scrub test runs,
   **Then** it fails on any listed name. **Given** it does not exist, **Then** the test passes the
   generic checks and prints `denylist absent — names unchecked`.
4. **Given** a live `iris-dev-iris` with the destructive tier enabled, **When** the round-trip test
   runs, **Then** both classes put and compile cleanly, a web application on a throwaway path
   serves the list fragment, add raises the outstanding count, toggle lowers it, delete removes
   the row, and the application, rows and classes are all gone afterwards, whether the test
   passed or failed.
5. **Given** the round-trip test, **When** it starts, **Then** it declares the write,
   destructive and admin tiers in its own server environment, so the tiers are never the reason
   it cannot run; **Given** no reachable IRIS, **Then** it panics with the reason, as
   constitution XI requires of every skip, unless `IAD_ALLOW_SKIP=1` is set.
6. **Given** `STEPS.md` and `transcript.md`, **When** read, **Then** the customer and colleague
   appear only as roles ("a PM", "a customer").

---

### User Story 4 - The findings not fixed here stay findable (Priority: P3)

Two further findings are drafted rather than fixed, and the drafted-defect lists that already
exist on other branches get a plan to become one list.

**Why this priority**: nothing breaks if these wait. They are recorded so that deciding later does
not mean rediscovering them.

**Independent Test**: `followups.md` exists in this spec directory with both drafts, and
`tasks.md` has an open task to fold the lists together.

**Acceptance Scenarios**:

1. **Given** `followups.md`, **When** read, **Then** it has (d): `iris_execute` can do by
   ObjectScript what the destructive tier refuses by tool call, marked blocked until the
   destructive tier has a written purpose; and (e): SQL errors come back without a hint field
   that names the likely fix.
2. **Given** `tasks.md`, **Then** an open task folds the drafted defects from specs 121, 122 and
   123 into one list once 121 merges.
3. **Given** any draft, **Then** it is not filed as an issue without explicit instruction.

### Edge Cases

- A description names a tier in words the parser does not recognise ("Execute-gated",
  "PHI-gated"): those are different gates, not tier claims, and the test ignores them rather
  than failing.
- A `mixed()` map whose default is destructive and whose description lists some actions but not
  others: every action that falls through to the default must still be named as destructive.
  A blanket "anything else is destructive" is not parsed, because it would let a new action ship
  unnamed.
- A tool the table does not list at all is read-only by default; a description claiming a gate
  for it fails.
- The round-trip test's throwaway path already exists from an aborted earlier run: the test
  removes it first rather than failing on create.
- The live `/todo` application is present: the test never touches it.
- The denylist file exists but is empty: treated as present, and says so.
- Regenerating `transcript.md` later reintroduces a name: caught locally by the denylist, the only
  place regeneration happens.

## Requirements

### Functional Requirements

- **FR-001**: A test MUST compare every tier claim in every tool description with the tier the gate
  table resolves, and fail naming the tool, the action and both tiers on any mismatch.
- **FR-002**: The same test MUST fail when a tool or action that resolves to the destructive tier
  has a description that does not say destructive.
- **FR-003**: The test MUST be written and seen failing on all eighteen current mismatches before any
  description changes.
- **FR-004**: The descriptions of the nine tools in the table above MUST be corrected so FR-001
  and FR-002 pass, without changing any gate behaviour.
- **FR-005**: Tool descriptions whose tools are read-only or write tier and silent on gating MUST
  NOT be required to add text.
- **FR-006**: `objectscript-sql-patterns` §7 MUST gain the `$ZDATETIME`-in-INSERT example with the
  SQLCODE as reproduced live.
- **FR-007**: `iris-sql`'s INSERT constraints list MUST gain the `InitialExpression` fact as
  reproduced live (it applies on SQL INSERT), and `objectscript-sql-patterns` MUST point to it in
  one line.
- **FR-008**: Each fact in FR-006 and FR-007 MUST be reproduced on `iris-dev-iris` before its text
  is written, and the reproduction recorded in this spec directory.
- **FR-009**: `docs/examples/todo-app/` MUST contain exactly the two classes, `STEPS.md` and
  `transcript.md`.
- **FR-010**: A committed test MUST fail on the generic leak patterns in US3 scenario 2.
- **FR-011**: The same test MUST read an optional local denylist from a gitignored path, fail on
  any listed name, and print `denylist absent — names unchecked` when the file is missing.
- **FR-012**: A live round-trip test MUST build and exercise the example as US3 scenario 4
  describes, on a throwaway path, with teardown that runs on failure.
- **FR-013**: The round-trip test MUST NOT report success when it could not run.
- **FR-014**: `followups.md` MUST hold drafts (d) and (e) as US4 describes.
- **FR-015**: Nothing on this branch is pushed, merged or tagged before the PM's presentation;
  local commits only.
- **FR-016**: Every claim about IRIS behaviour in the published `STEPS.md` MUST have been checked
  live; the false `InitialExpression` claim is removed, and `transcript.md` carries a one-line note
  at the top saying so, since the transcript records what the agent wrote at the time.

### Key Entities

- **Tier claim**: a statement in a tool description that a tool, or a named action of it,
  requires the write or destructive tier.
- **Resolved tier**: what `write_gate.rs` returns for a tool and action, including `mixed()`
  defaults.
- **Published example**: the four files in `docs/examples/todo-app/`.
- **Denylist**: a local, uncommitted list of names that must not appear in published files.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero disagreements between description tier claims and the gate table, down from
  eighteen, and a regression reintroducing any one of them fails a test.
- **SC-002**: Every destructive-tier tool and action is identified as destructive in its own
  description.
- **SC-003**: Both SQL facts are in a skill, each backed by a recorded live reproduction.
- **SC-004**: The published example contains no home paths, emails, hook output or names, as
  checked by a test that fails on each class of leak.
- **SC-005**: The example app is built and exercised end to end by a test, and leaves nothing
  behind on the instance.
- **SC-006**: The `tools/list` payload grows by no more than the corrected sentences (measured
  against spec 114's method), since only nine descriptions change.

## Assumptions

- "Freeze" means nothing pushed, merged or tagged before the PM presents. Local commits on this
  branch are allowed.
- `_SYSTEM`/`SYS` in the example is the community container's documented default, not a leaked
  credential, and the scrub test allows it explicitly.
- The destructive-tier tool list is read from `write_gate.rs` at test time, not copied into the
  test, so the test follows the table.
- The `demos/` directory stays untracked; `docs/examples/todo-app/` is built from it.

## Out of Scope

- The `iris-rest-webapp` skill. Its own spec, later: live correctness of every claim plus a
  contained `claude -p` probe with and without the skill; no lift claim, `benchmark_tasks: []`.
- Fixing (d) or (e). Drafts only.
- Generating descriptions from the gate table.
- Filing any issue, opening any PR, or pushing.
