# Tasks: install and set up from inside Claude Code

**Branch**: `122-plugin-install-setup` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Tests come before the thing they check, and each phase gate has to pass before the next phase starts.
`[P]` marks tasks with no dependency on each other.

## Phase 0 — find out what the loader does

- [ ] **T001** Record the `marketplace.json` keys `claude plugin validate` accepts, and the minimum
      that validates with no warnings. Confirmed so far: `name`, `owner.name`, `plugins[].name`,
      `plugins[].source`, `plugins[].description`, plus a top-level `description` to clear the one
      warning. Write it to `research.md` with the command and its output.
- [ ] **T002** [P] Determine whether a plugin's skills root is configurable, or whether
      `skills/<name>/SKILL.md` at the plugin root is the only place the loader looks. Answer by
      installing a scratch plugin from a local path with skills one directory down, then listing what
      loaded. Record in `research.md`.
- [ ] **T003** [P] Determine what a plugin-supplied MCP server with no `env` block resolves to:
      whether `.iris-agentic-dev.toml` discovery and the auto-discovery chain run the same as for a
      hand-registered server. Record in `research.md` with a `check_config` output.
- [ ] **T004** Decide the skills layout from T002 and write the decision into `plan.md` under "The
      skills-layout decision", replacing the two options with the one taken and why.

**Gate**: `research.md` answers all three questions with commands and output, not prose.

## Phase 1 — manifests

- [ ] **T005** Write `tests/e2e/test_plugin_manifest.py`, failing, asserting: (a) both manifests are
      valid JSON; (b) every `mcpServers.*.command` is a bare name or path whose basename is
      `iris-agentic-dev`; (c) no `env` value in either manifest is a `${...}` placeholder; (d)
      `marketplace.json` exists and names the plugin that `plugin.json` declares; (e) the version in
      `marketplace.json`, `plugin.json` and the workspace `Cargo.toml` agree.
- [ ] **T006** Add `.claude-plugin/marketplace.json` per T001, with a top-level description.
- [ ] **T007** Fix `plugin.json`: command `iris-agentic-dev`, `env` block removed per FR-003.
- [ ] **T008** Add a CI step running `claude plugin validate` on both manifests, if the CLI is
      available on the runner; if it is not, assert the manifest shape in Python instead and say so in
      the step name. A step that silently skips is the #118 pattern.
- [ ] **T009** Verify the round trip by hand: `claude plugin marketplace add <local checkout>`, then
      `claude plugin install iris-dev@iris-agentic-dev`, then `claude mcp list` showing the plugin's
      server connected. Paste the output into `research.md`.

**Gate**: T005 passes, and T009's output is in the repo.

## Phase 2 — skills parity

- [ ] **T010** Write `tests/e2e/test_plugin_skills.py`, failing, asserting the set of skills the
      plugin exposes equals the set `iris-agentic-dev skill install` writes. Read the binary's list
      from `skill list` rather than hardcoding 34 names.
- [ ] **T011** Apply the T004 decision. If it is the move, update every reference to
      `skills/skills/`: `tests/e2e/`, `skills/AGENTS.md`, `skills/BENCHMARKING.md`, the raw
      GitHub URL in that file, and any Rust that embeds the path.
- [ ] **T012** Run the skill-eval harness's collection step (not a scored run) to prove the relocation
      did not strand it: `pytest tests/e2e/skill_eval -q` with no billable opt-in.

**Gate**: T010 passes, T012 collects the same number of skills as before the change.

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
