# Tasks: install and set up from inside Claude Code

**Branch**: `122-plugin-install-setup` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Tests come before the thing they check, and each phase gate has to pass before the next phase starts.
`[P]` marks tasks with no dependency on each other.

## Phase 0 — find out what the loader does

- [x] **T001** Record the `marketplace.json` keys `claude plugin validate` accepts, and the minimum
      that validates clean. Minimum is `name`, a top-level `description`, `owner.name` and
      `plugins[]`; `plugins[].description` is optional; the plugin manifest each `source` points at
      needs `author`. `--strict` turns warnings into exit 1, and cannot pass on this repo — the
      `CLAUDE.md`-at-root warning is inherent. `--json` is what a test should read.
- [x] **T002** [P] Skills root is configurable: `"skills": ["./skills/skills"]` in `plugin.json`
      loads every `<name>/SKILL.md` under that parent. The declaration is additive, not a
      replacement, so the three skills at `skills/` root ship as well. Four scratch plugins,
      `claude plugin details` output in `research.md`.
- [x] **T003** [P] A plugin MCP server with no `env` block lands on
      `connection_source: "config_file"` from the host's `.iris-agentic-dev.toml`, connected, with a
      real `iris_version`. Same resolution as a hand-registered server. `check_config` output in
      `research.md`.
- [x] **T004** Decision written into `plan.md`: keep `skills/skills/` and declare it. No 34-directory
      move, so `include_str!`, the eval harness and the docs stay intact.

**Gate**: PASSED — `research.md` answers all three with commands and output. Two requirements changed
as a result: FR-001/SC-003 allowlist the `CLAUDE.md` warning instead of demanding zero warnings, and
FR-004/SC-004 expect the 34 bundled skills plus three named root ones rather than an exact match.

## Phase 1 — manifests

- [x] **T005** Write `tests/e2e/test_plugin_manifest.py`, failing, asserting: (a) both manifests are
      valid JSON; (b) every `mcpServers.*.command` is a bare name or path whose basename is
      `iris-agentic-dev`; (c) no `env` value in either manifest is a `${...}` placeholder; (d)
      `marketplace.json` exists and names the plugin that `plugin.json` declares; (e) the version in
      `marketplace.json`, `plugin.json` and the workspace `Cargo.toml` agree.
- [x] **T006** Add `.claude-plugin/marketplace.json` per T001, with a top-level description.
- [x] **T007** Fix `plugin.json`: command `iris-agentic-dev`, `env` block removed per FR-003.
- [x] **T008** Add a CI step running `claude plugin validate --json` on both manifests, asserting an
      empty `errors` array and no warning outside the `CLAUDE.md`-at-root allowlist. Not `--strict`:
      T001 showed it can never pass here. If the CLI is absent from the runner, assert the manifest
      shape in Python instead and say so in the step name. A step that silently skips is the #118
      pattern.
- [x] **T009** Verify the round trip by hand: `claude plugin marketplace add <local checkout>`, then
      `claude plugin install iris-dev@iris-agentic-dev`, then `claude mcp list` showing the plugin's
      server connected. Paste the output into `research.md`.

**Gate**: PASSED — all eight tests in `test_plugin_manifest.py` green, mutation-checked (a
reverted command name and one `${IRIS_HOST}` env value fail two of them), and T009's install
output is in `research.md`.

## Phase 2 — skills parity

- [ ] **T010** Write `tests/e2e/test_plugin_skills.py`, failing, asserting the skills the plugin
      exposes are every skill the binary bundles plus exactly `iris-coverage-run`,
      `iris-coverage-setup` and `pyprod`. Read the bundled list from `skill list`, and the plugin's
      from the `skills` roots declared in `plugin.json`, rather than hardcoding names on either side.
      A fourth root skill has to fail this test.
- [ ] **T011** Add `"skills": ["./skills/skills"]` to `plugin.json`. No files move, so no reference to
      `skills/skills/` changes.
- [ ] **T012** Confirm the declaration loads what the test claims by installing the plugin from this
      checkout and reading `claude plugin details iris-dev`, and paste the inventory into
      `research.md`. `plugin details` is the loader's own account, which is the only thing that can
      contradict the test.

**Gate**: T010 passes, and `plugin details` lists the 37.

## Phase 3 — the setup skill

- [ ] **T013** Write `tests/e2e/test_setup_skill.py`, failing, reusing the guide checker in
      `test_getting_started.py`: every `iris-agentic-dev` subcommand the skill names exists, every
      tool is in the catalogue, every `--args` payload parses and uses declared fields. Factor the
      shared helpers out rather than copying them.
- [ ] **T014** Write `skills/iris-agentic-dev-setup/SKILL.md` covering FR-005 in order: detect the
      binary with `command -v`; install per platform naming `intersystems-community/tap`; find an
      existing IRIS with `docker ps` before starting one; start
      `intersystemsdc/iris-community:latest` when there is none; clear the expired default password;
      resolve the web port from `docker port` rather than assuming 52773; register with
      `claude mcp add` using the absolute path; verify with `check_config` and one query.
- [ ] **T015** Add the FR-007 branch to the skill: `iris_test_server` splits reachable from
      authenticated, the expired default password is named as the first cause of a 401 on a fresh
      container, and the known-wrong `IRIS_UNREACHABLE` code on a 401 is called out so a reader does
      not chase the hint.
- [ ] **T016** Run every command in the skill against a live container while writing it, the standard
      `docs/getting-started.md` is held to. Use a throwaway container name and remove it afterwards.
- [ ] **T017** Extend `test_install_instructions.py` so the tap guard covers the new skill file, and
      confirm it fails when the tap is wrong there.

**Gate**: T013 and T017 pass; the skill's commands have all been run.

## Phase 4 — the measurement

- [ ] **T018** Run the SC-001 probe: a session on a PATH with no `iris-agentic-dev`, plugin installed,
      one plain-English prompt, ending at a query with rows. Billable, so behind the existing opt-in.
      Keep the transcript at `specs/122-plugin-install-setup/probe-after.md`.
- [ ] **T019** Record the SC-002 comparison next to it: the 2026-09-22 "I don't know the publish
      channel" answer against what the same prompt produces with the plugin installed. If the guess is
      still there, the skill is not discoverable and Phase 3 is not done.

**Gate**: the probe ends at rows from IRIS, and the channel guess is gone.

## Phase 5 — docs

- [ ] **T020** Add the plugin path to `README.md` and to `docs/getting-started.md` step 6, ahead of
      the manual `claude mcp add`, which stays.
- [ ] **T021** Confirm the guide's guard covers the new commands, then run `markdownlint-cli2 --fix`
      and `prettier --write` on every file touched.
- [ ] **T022** Slop pass on the skill and both docs: `python3 ~/.claude/skills/no-ai-slop/review.py`,
      then `python3 scripts/gates/antipatterns.py`.
- [ ] **T023** Full suite before the PR: `pytest tests/e2e -q` and
      `cargo test --features testing -- --include-ignored` with `--test-threads=1`.

**Gate**: everything green, no unaddressed slop finding.

## Out of scope

- Windows automation. The skill says what to do there; nothing measures it.
- Publishing the marketplace to any registry. `claude plugin marketplace add <owner>/<repo>` from
  GitHub is the target, and whether it needs a release tag is T001's business.
- Making the skills measurably help. They are at nothing on the graded holdout and that is spec 121's
  problem, not this one.
