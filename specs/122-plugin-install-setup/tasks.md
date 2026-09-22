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

- [x] **T010** Wrote `tests/e2e/test_plugin_skills.py`, failing first. It ended up stronger than the
      task asked for: rather than allowlisting the three root skills, it walks the whole `skills/`
      tree and requires every `SKILL.md` in it to be reachable by some entry in the declaration. So a
      new skill at any depth that no entry covers fails, which is how `nopws-setup` was found. A
      fourth test reads `plugin details` and compares the loader's own inventory against the tree.
- [x] **T011** Added `"skills": ["./skills/skills", "./skills/skills/iris-agentic-dev/nopws-setup"]`
      to `plugin.json`. The second entry is there because a declared path holding its own `SKILL.md`
      loads as one skill instead of as a parent, so `nopws-setup` two levels down needed naming.
      No files move, so no reference to `skills/skills/` changes.
- [x] **T012** Confirm the declaration loads what the test claims by installing the plugin from this
      checkout and reading `claude plugin details iris-dev`, and paste the inventory into
      `research.md`. `plugin details` is the loader's own account, which is the only thing that can
      contradict the test.

**Gate**: PASSED — T010's four tests green and mutation-checked, and `plugin details iris-dev`
lists 38: the 34 bundled, the three at `skills/` root, and `nopws-setup`.

## Phase 3 — the setup skill

- [x] **T013** Wrote `tests/e2e/test_setup_skill.py`, failing first (four failures, all on the
      missing skill file). `test_getting_started.py` is not on this branch — it lives on the
      unmerged `121-benchmark-program` — so the checker is written here against `--help`
      `Commands:`, `tool --list` and `tool <name> --schema --json`. **The shared factoring happens
      when 121 merges**, whichever way round that is; the two checkers overlap on subcommand and
      tool-name extraction. A missing skill file asserts rather than skips: a skip would let the
      whole feature disappear with CI green, which is the #118 pattern this policy exists for.
- [x] **T014** Wrote `skills/iris-agentic-dev-setup/SKILL.md`. It sits at `skills/` root, not under
      `skills/skills/`: the root is what the loader scans implicitly, and a directory under
      `skills/skills/` would have to be added to `bundled.rs` to keep
      `embedded_catalog_matches_the_skills_directory_on_disk` green. A setup skill has no business
      in the binary's embedded catalog anyway, since it has to be readable before the binary exists.
- [x] **T015** FR-007 branch written from measured output rather than from the error strings. Three
      findings went into it that the task did not anticipate:
      (a) an ad-hoc `iris_test_server` probe does **not** default `username`/`password` from the
      active config, so omitting them returns `auth: false` against a perfectly healthy server;
      (b) an expired password and a wrong password produce byte-identical
      `reachable: true, auth: false, "Authentication failed (HTTP 401)"`;
      (c) when authentication fails, discovery keeps looking and can settle on an **unrelated**
      container that does answer, reporting `connected: true`. `IRIS_WEB_PORT=9773` was honoured
      once the password was cleared and ignored while it was expired. So `connected: true` never
      proves you reached the instance you started, and the skill tells the reader to check
      `port`/`container`.
- [x] **T016** Every command in the skill run live against a throwaway `iad-quickstart` container
      (community 2026.1, ports 9772/9773), removed afterwards. `docker ps --filter expose=1972`,
      `docker port`, the `UnExpireUserPasswords` exec, the authenticated `curl`, `check_config`,
      `query` (6,870 rows) and both `iris_test_server` branches all ran. `claude mcp add` was run
      in a temp directory and removed. The health-wait loop in the skill polls the REST endpoint
      because **this image declares no healthcheck** — `docker inspect` reports an empty health
      status forever, so the obvious wait never returns.
      Not runnable yet: `claude plugin marketplace add intersystems-community/iris-agentic-dev`.
      `.claude-plugin/marketplace.json` is 404 on `master`, so the remote form only starts working
      when this branch lands. Phase 1 verified the same round trip from a local checkout.
- [x] **T017** `test_install_instructions.py` is also a 121 file, so the tap guard went into
      `test_setup_skill.py` as a repo-wide markdown scan, which is FR-006's actual scope. It found
      one offender: `skills/BENCHMARKING.md:23` named `intersystems-community/iris-agentic-dev`,
      whose `homebrew-` repository does not exist, so the first command in the benchmarking guide
      404s. Fixed here. 121 fixes the same line, and the change is identical, so the merge is clean.

**Gate**: PASSED — all five tests in `test_setup_skill.py` green and mutation-checked (a bad
subcommand, a bad tool name, an undeclared `--args` key, a description with no trigger phrase and a
wrong tap each fail exactly one test), every command in the skill has been run live, and
`claude plugin details iris-dev` now reports 39 skills including `iris-agentic-dev-setup`.

## Phase 4 — the measurement

- [ ] **T018** Run the SC-001 probe: a session on a PATH with no `iris-agentic-dev`, plugin installed,
      one plain-English prompt, ending at a query with rows. Billable, so behind the existing opt-in.
      Keep the transcript at `specs/122-plugin-install-setup/probe-after.md`.
- [~] **T019** Run, but the measurement is contaminated and does not settle SC-002. A
  `claude -p --strict-mcp-config --permission-mode plan` session on a PATH without
  `iris-agentic-dev`, asked for the install commands, named
  `brew install intersystems-community/tap/iris-agentic-dev` and said "**known** — not
  guessing". So the 2026-09-22 guess is gone. But it got there by running `brew info` and
  finding the formula already installed on this machine, which stripping PATH does not hide,
  so the answer is attributable to local state rather than to the skill. A clean read needs a
  host where the formula is genuinely absent: a CI runner, or a container. Transcript summary
  in `research.md`.

**Gate**: NOT MET. T018 is unrun and T019 is contaminated. T018 needs a decision first, because
the probe is an unattended session with permissions relaxed that downloads a binary and starts a
container on this laptop; both are reversible, neither is something to do unasked.

## Phase 5 — docs

- [x] **T020** Plugin route added to `README.md` at the head of the CLI host quick start, ahead of
      the hand-written MCP config block, which stays for every other host.
      `docs/getting-started.md` does not exist on this branch (another 121 file), so there is no
      step 6 to edit here; when 121 merges, the same three lines belong there too.
- [x] **T021** The tap guard from T017 covers `README.md`, since it scans every markdown file in
      the tree. `markdownlint-cli2 --fix` and `prettier --write` run clean on the skill, `README.md`,
      `skills/BENCHMARKING.md`, `research.md` and this file.
- [x] **T022** Slop pass clean on the skill. The reviewer raised two things on the README section:
      bold mid-sentence, which was reworded to the `**Label** —` form the two neighbouring
      paragraphs already use, and then the em dash in that same form, which is left alone because
      matching the adjacent lines beats the general rule here. `antipatterns.py` clean, 220 baseline
      instances unchanged.
- [x] **T023** `pytest tests/e2e -q --ignore=tests/e2e/skill_eval`: 116 passed, 4 skipped. The
      ignore is deliberate — collecting `skill_eval` as a directory bills real model calls.
      `cargo fmt --all -- --check` and `cargo clippy --features testing --all-targets -- -D warnings`
      clean. Full Rust suite against live `iris-dev-iris` with CI's env and skip list: 5,234 passed,
      0 failed. Without `IRIS_HOST` and friends exported, 96 of those fail on `IRIS_HOST must be
    set` and on discovery finding an unrelated container; that is the invocation, not the code,
      and it is why the CI job sets them.

**Gate**: PASSED for everything except the Phase 4 probe.

## Out of scope

- Windows automation. The skill says what to do there; nothing measures it.
- Publishing the marketplace to any registry. `claude plugin marketplace add <owner>/<repo>` from
  GitHub is the target, and whether it needs a release tag is T001's business.
- Making the skills measurably help. They are at nothing on the graded holdout and that is spec 121's
  problem, not this one.
