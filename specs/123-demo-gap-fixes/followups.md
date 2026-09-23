# Follow-ups: findings drafted, not fixed

Nothing here is filed. Each draft waits for Tom's word before it becomes an issue (FR-015).

## (d) `iris_execute` does by ObjectScript what the destructive tier refuses by tool call

**Status**: blocked until the destructive tier has a written purpose.

With `IRIS_DESTRUCTIVE_TOOLS_ENABLED` unset, `iris_admin(action="delete_webapp")` is refused at
the gate in `call_tool`. `iris_execute` is write tier (`write_gate.rs`), so with only the write tier
on it can run `##class(Security.Applications).Delete("/x")` in `%SYS` and nothing checks the
destructive tier. The demo used the same route to create its web application. Spec 087 closed
one case, a literal `Kill ^global`, and documented that indirection gets past it.

I can't choose between the fixes without knowing what the tier is for:

- If it keeps a careless agent from removing things by accident, the tool-call gate is enough,
  and the description should say `iris_execute` is outside it.
- If it keeps a write-tier session from removing things at all, `iris_execute` needs the
  destructive tier whenever it runs in `%SYS` or calls `Delete`/`%KillExtent`/`Kill`. That breaks
  every existing write-tier workflow that runs ObjectScript.

**Next step**: write the purpose into the constitution (Environment Guard). Then pick one.

## (e) SQL errors come back without a hint that names the likely fix

`iris_query` returns SQLCODE and the parser message. It does not say what to change. The demo hit
SQLCODE -12 with the position marker at `$`. The fix, `CURRENT_TIMESTAMP` for `$ZDATETIME`, is now
in `objectscript-sql-patterns` §7, but the agent only finds it if it goes looking.

**Draft**: an optional `hint` field on SQL error responses, filled from a short table keyed on
SQLCODE plus a pattern in the message. The first row is the one reproduced here: SQLCODE -12
with the marker at `$` means an ObjectScript function inside SQL (research R1). Each further row
gets reproduced live before it goes in, and each row cites the skill section it came from. An
unmatched error gets no hint, which is better than a wrong one.

## (f) `IRIS_ADMIN_TOOLS` is a second gate that no doc names

`iris_admin`'s user, namespace and web application actions check `admin_write_allowed()`
(`src/tools/admin.rs:22`) inside the handler, after `call_tool` has already passed them on the
write or destructive tier. An agent with both tiers on is still refused, and `docs/` never
mentions the variable (only `docs/backlog-empty-success-audit.md`, which notes 11 tests gated on
it that the suite never sets). The round-trip test sets it (research R4).

**Draft**: name `IRIS_ADMIN_TOOLS=1` in `iris_admin`'s description next to the tier claim and in
`docs/connecting.md`. Or fold it into the gate table so there is one gate, not two.

## (g) An agent on a NoPWS container reads iad as unusable

This comes from an ai-core session on 2026-09-22. `ai-core-iris` is IRISHealth 2026.3.0AI.144.0,
with no private web server: a GET on its published web port 45873 gets no answer. The agent
concluded that iad could not help, for four reasons. I checked each against the source.

| Claim                                                                     | Verdict | Where it came from                                                                                                                                                                          |
| ------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| iad's MCP servers belong to other projects, so using one would cross them | Wrong   | Every iad server registered in that session was pinned to another project's container. iad targets any IRIS through a toml, env vars or `iris_add_server`. Nothing said so where it looked. |
| Adding a server needs an iad restart                                      | Wrong   | iad's own text said so. Fixed in `7310273`: add, remove and import now point at `iris_reload_pool`, with a unit and a binary test.                                                          |
| Without Atelier REST, `iris_doc` put/compile is out                       | Right   | `iris_doc` returns `NOPWS_ATELIER_REQUIRED` under `docker_only` (`src/tools/mod.rs`, FR-010 guard).                                                                                         |
| On the docker exec path `{}` blocks fail                                  | Right   | `iris session` is a line interpreter. `docs/tools.md` gives the `.mac` escape hatch.                                                                                                        |

The two wrong claims are about instructions, not code. The two right ones leave a real gap:

**Draft (g1)**: `iris_doc(mode="put")` over docker exec. Copy the source into the container with
`docker cp`, then `$system.OBJ.Load(path, "ck")` through the existing docker exec path. Put and
compile are what an agent needs most on a NoPWS build, and today it has to hand-roll this with
`iris_execute`, where the code-edit gate refuses `$system.OBJ`.

**Draft (g2)**: `NOPWS_ATELIER_REQUIRED` should say what does work under `docker_only`
(`iris_execute`, `iris_compile`), not just what doesn't.

### Changes outside this repo (drafts, not applied)

These live in other repos or in global config, so each needs Tom's go-ahead.

1. **productivity-framework, `tools/lab_manager/iris_registry_verify.py:1331`.** The container-guard
   message says iad "speaks HTTP only (--web-port/--scheme, no SQL transport), so this cannot be
   fixed in the toml". That is false: `docker_only = true` with `container = "<name>"` in the toml
   gives `iris_execute` and `iris_compile` over docker exec (`docs/connecting.md`). Proposed text:

   > iris-agentic-dev needs a private web server or a Web Gateway for Atelier REST (`iris_doc`,
   > `iris_source_control`). Without one, set `docker_only = true` and `container = "{want}"` in
   > the project's `.iris-agentic-dev.toml`: `iris_execute` and `iris_compile` then
   > run through `docker exec`. For full coverage, put a Web Gateway sidecar in front of the
   > container.

   `tools/los/tests/unit/test_webgateway_fronts_los_iris.py` asserts on the current text and
   would change with it.

2. **`~/.claude/CLAUDE.md`, "IRIS Containers Are Project-Exclusive".** The rule is right, but an
   agent read "NEVER cross them" together with iad servers named after other projects as "iad
   belongs to other projects". Proposed addition after the table:

   > iris-agentic-dev is not tied to any project. Point it at this project's container with a
   > `.iris-agentic-dev.toml` in the repo root (or `iris_add_server` + `iris_reload_pool`). The
   > rule forbids using another project's _container_, not iad.

3. **ai-core, repo and memory.** ai-core has no `.iris-agentic-dev.toml`. Proposed file:

   ```toml
   docker_only = true
   container = "ai-core-iris"
   namespace = "USER"
   ```

   Proposed memory for that project: "iad works on ai-core-iris via `docker_only`: execute and compile
   yes; `iris_doc` no (no PWS on 2026.3.0AI); `{}` blocks only inside compiled `.mac`."

## Folding the lists (T016)

Specs 121 and 122 have drafted-defect lists of their own on unmerged branches. Once 121 merges,
the three become one list. T016 stays open until then.
