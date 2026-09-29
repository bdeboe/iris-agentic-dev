# Plan: 131 MDX cube facts

Stacked on `130-content-skills`. Every verdict comes from a live test. Nothing is posted.

## Technical context

- Rust 2021, `iris-agentic-dev-core`. No new dependency.
- Live target: iris-dev-iris, USER, Atelier on 52780. `%DeepSee` ships with community; if a cube does not build there, stop and report.
- Claims read from the PR 142 worktree at 7f9b71c, `skills/skills/iris-mdx/SKILL.md`.

## `sa_schema` (US1)

- `info.rs`: a pure `sa_schema_name_problem(name: Option<&str>) -> Option<String>` returns the error text when the name is empty or not `http://`/`https://`. The handler returns `INVALID_PARAMS` with it before building a URL, so no IRIS call is made.
- A 404, or a 2xx whose `result` is empty, for `sa_schema` returns `SA_SCHEMA_NOT_FOUND` with the same guidance plus the URL tried. Other `what` values keep `IRIS_UNREACHABLE`.
- Text lives in one `const SA_SCHEMA_GUIDANCE` so the unit test, the binary test and the handler read the same words. It names `iris_execute`, `%DeepSee.Utils`, `%GetCubeList`, `%GetDimensionList` and the deepsee URL, and no skill.
- `mod.rs` `iris_info` description: "what=sa_schema returns the Studio Assist grammar for an XData namespace URL (name=<http://www.intersystems.com/deepsee>); it does not list cubes". `InfoParams.name` doc to match.

## Cube fixture (US2)

- Source class `IadLive131.Sale` (`%Persistent`): `Region` (string), `Channel` (integer 1/2/3), `SaleDate` (`%Date`), `Doctor` (integer id), `DoctorName` (string, two ids share "Smith"), `Amount` (`%Numeric`, some rows empty).
- Cube class `IadLive131.SalesCube` (`%DeepSee.CubeDefinition`), cube name `IadLive131Sales`:
  - `RegionD` / `H1` / `Region`
  - `ChannelD` / `H1` / `Channel Name`, `rangeExpression` mapping 1→Retail, 2→Online, 3→Phone (key stays the integer)
  - `DateD` (time) / `Actual` / `YearSold`, `MonthSold`
  - `DoctorD` / `H1` / `Doctor`, key `Doctor`, name property `DoctorName`
  - measures `Amount` (sum), plus built-in `%COUNT`
- A second cube `IadLive131Other` over the same source with one dimension `OtherD`, for the cross-cube claim.
- Rows are written with SQL `INSERT` in the fixture routine, fixed values, no `$RANDOM`. Hand-computed expected numbers go in `research.md`.
- Setup: drop `IadLive131.*`, put and compile the three classes, insert rows, `%BuildCube` both cubes, check statuses. Teardown: `%KillCube` where needed and `$system.OBJ.Delete` on the package.
- Fixture source lives in `crates/iris-agentic-dev-core/tests/fixtures/mdx131/` as `.cls` files, so the PR author can load the same cube by hand.

## Running MDX

A helper in the live test runs `%DeepSee.ResultSet`: `%PrepareMDX(q)`, `%Execute()`, then writes a marked, line-per-cell dump (row labels, column labels, `%GetOrdinalValue`) and any error status via `$system.Status.GetErrorText`. Each claim test parses that dump.

## Tests

- **Unit** `tests/unit/test_sa_schema_131.rs`: the name check (empty, cube name, URL); guidance names `%GetCubeList`, `%GetDimensionList`, `iris_execute`; guidance names no skill in `skills/`; `InfoParams` TOML/JSON round-trip for `name`.
- **Binary** `tests/binary/test_sa_schema_131_binary.rs`: `tools/list` `iris_info` has no "SQL Analytics" and has "Studio Assist"; `tools/call` with `name=HoleFoods` returns `INVALID_PARAMS` with `%GetCubeList`, with no IRIS configured.
- **Live** `tests/integration/test_mdx_131_live.rs`: `sa_schema` deepsee URL returns a grammar; unknown URL returns `SA_SCHEMA_NOT_FOUND`; fixture build and teardown; one test per claim in `research.md`.
- `mod` lines in `tests/unit/main.rs`, `tests/binary/main.rs`, `tests/integration/main.rs`.

## Constitution check

- IV test-first: unit and binary tests written and red before `info.rs` changes; live claim tests assert IRIS, not the claim (XI no vacuous tests).
- III HTTP-first: fixture and claims run over Atelier; no docker exec.
- Error code registry: `SA_SCHEMA_NOT_FOUND` in `data-model.md`; `INVALID_PARAMS` is standard.
- User-facing strings are API: `iris_execute` named in guidance exists in the registry; tests cover the description and error text.
- 129 rule: hint and error text name no skill.

## Out of scope

Editing the contributor's skill, an MDX tool, posting or pushing.
