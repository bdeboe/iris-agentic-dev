# Data model: 132 AI Hub on EAP build 139

No database. These are the shapes the tests and harness read.

## AihubEnv (`testing.rs`)

| Field              | Source env var        | Default          |
| ------------------ | --------------------- | ---------------- |
| `container`        | `IAD_AIHUB_CONTAINER` | `iad-aihub-iris` |
| `host`             | `IAD_AIHUB_HOST`      | `localhost`      |
| `superserver_port` | `IAD_AIHUB_PORT`      | `11976`          |
| `namespace`        | `IAD_AIHUB_NAMESPACE` | `USER`           |

- `aihub_env() -> Option<AihubEnv>` returns `Some` when `docker inspect` reports the container is running.
- When it is not running, it panics with the start command from quickstart.md.
- With `IAD_ALLOW_SKIP=1` set, it prints the same message and returns `None` instead of panicking.
- Parsing is a pure `AihubEnv::from_vars(impl Fn(&str) -> Option<String>)` so the unit test needs no container.

## Upstream file list (`tests/fixtures/aihub139/upstream-files.txt`)

- Line 1 is `# ai-hub-eap master <40-hex commit> <YYYY-MM-DD>`.
- After that, one repo-relative path per line, sorted, with no blank lines.
- Rules:
  - The commit in line 1 equals the commit the skill's `source:` names.
  - Every map entry in the skill is on the list. A directory entry (`objectscript/cls/`) matches when at least one listed path starts with it.

## Topic map (in the skill)

- A markdown table with the columns `Topic | File`.
- Topics: ConfigStore, MCP, SDK, LangChain, Samples. SDK has three files and MCP has two.
- Every `File` cell is one backticked repo-relative path.

## Claim (row in research.md "Claim table")

| Field     | Rule                                                                                          |
| --------- | --------------------------------------------------------------------------------------------- |
| `id`      | `C<n>`, unique                                                                                |
| `claim`   | one sentence as the skill states it                                                           |
| `source`  | `ai-hub-eap:<file>:<line>`, `hackathon:<skill>:<line>`, or `own`                              |
| `verdict` | `holds` / `false` / `reworded` / `not taken`                                                  |
| `test`    | the live test fn name in `test_aihub_139_live.rs`; required unless the verdict is `not taken` |
| `credit`  | `Gabriel Ing` when source is `hackathon:*`                                                    |

- A `not taken` row carries its reason in the `claim` cell after a `—`.
- Every `%AI.*` / `%ConfigStore.*` class name in the skill must appear in some `holds`/`reworded` row.

## Mismatch (entry in drafts.md)

- Doc file:line.
- What the doc says.
- What 139 does.
- The test name.
- Draft upstream text.
- Status is always `drafted`. Nothing is filed.

## Ladder task (YAML, extends the 130 shape)

- Existing fields: `id`, `prompt`, `fixtures[{name, content}]`, `check`, `solution`, `skill`, `tags`, `namespace`.
- New optional field `teardown`: an ObjectScript string, run in `namespace` through `iris-agentic-dev exec`.
  - It runs before the session and after the check.
  - Output other than an optional `OK` is ignored.
  - A non-zero exit raises `CheckBroken`, which leaves the run unscored.
- The AI Hub tasks set `namespace: USER` and name `iad-aihub-iris` in the prompt.

## Ladder run record (existing, one new field)

- `side`: `holdout` (default) or `train`.
- A `train` record is refused by `split.assert_holdout_only` on the publish path.

## Fixed names used by fixtures and teardown

| Kind                | Name                                                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------------------- |
| class package       | `IadAihub139`                                                                                                   |
| ConfigStore entries | names starting `IadAihub139`. The area/type follow `%AI.ConfigStore.LLMDescriptor`/`MCPDescriptor` (to measure) |
| Wallet collection   | `IadAihub139`                                                                                                   |
| MCP web app         | `/mcp/iadaihub139`                                                                                              |
