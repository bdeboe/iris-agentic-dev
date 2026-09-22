# Implementation Plan: install and set up from inside Claude Code

**Branch**: `122-plugin-install-setup` | **Date**: 2026-09-22 | **Spec**:
[spec.md](spec.md)

## Summary

Make the plugin installable, then let a skill do the setup. Four changes: a
`.claude-plugin/marketplace.json` so `claude plugin marketplace add` resolves the repo, a
`plugin.json` MCP command that names the binary a release actually ships, a skills layout the
plugin loader can see, and a new `iris-agentic-dev-setup` skill that takes someone from no binary
and no container to a query returning rows.

No Rust changes. The feature is manifests, a skill file, and the tests that keep all four honest.

## Technical Context

**Language/Version**: JSON manifests, Markdown skill, Python 3.11 tests. No Rust.
**Primary Dependencies**: the `claude` CLI (`plugin validate`, `plugin marketplace add`,
`plugin install`, `mcp add`, `mcp list`), Homebrew, Docker. No new library anywhere.
**Storage**: none.
**Testing**: `pytest tests/e2e` for manifest shape, version agreement, skill/plugin parity and the
tap guard; `claude plugin validate` in CI; a live container for the setup skill's own steps; one
probe session for SC-001 and SC-002, which costs money and is therefore opt-in.
**Target Platform**: macOS and Linux for the automated path; Windows documented, not automated.
**Project Type**: single repo, docs and manifests.
**Constraints**: the probe session is billable, so it runs behind the existing opt-in and never in
CI. Everything else has to be free and offline.
**Scale/Scope**: two manifests, one skill, 34 skill directories to relocate or expose, four test
files.

## Constitution Check

| Principle                  | Status | Notes                                                                                                 |
| -------------------------- | ------ | ----------------------------------------------------------------------------------------------------- |
| I. Zero-Install Binary     | PASS   | The point of the feature. No runtime added; the plugin carries instructions, not dependencies.        |
| II. ObjectScript Sanity    | N/A    | No ObjectScript beyond `UnExpireUserPasswords`, which the guide already runs against a live instance. |
| III. HTTP-First Execution  | PASS   | Setup verifies over Atelier HTTP. `docker` is used to find and start a container, not to run tools.   |
| IV. Test-First             | PASS   | Manifest and parity tests are written before the manifests they check. See the task order.            |
| V. Output Shape Parity     | N/A    | No new tool.                                                                                          |
| VI. Environment Guard      | PASS   | No new write surface. FR-003 removes an env block rather than adding one.                             |
| VII. Dependency Minimalism | PASS   | No new dependency.                                                                                    |
| VIII. 90% Coverage Gate    | N/A    | No Rust added, so the line-coverage gate has nothing new to cover.                                    |
| IX. Tool Lift Requirement  | N/A    | Not a tool. SC-001 and SC-002 are the equivalent measurement.                                         |
| X. ObjectScript Coverage   | N/A    | No ObjectScript feature.                                                                              |

No FAIL gates.

## Project Structure

```text
.claude-plugin/
├── plugin.json              # command fixed, env block removed
└── marketplace.json         # new
skills/
├── <name>/SKILL.md          # where the plugin loader looks
└── skills/<name>/SKILL.md   # where they are now
skills/iris-agentic-dev-setup/SKILL.md   # new
tests/e2e/
├── test_plugin_manifest.py      # new: shape, command, env, version agreement
├── test_plugin_skills.py        # new: plugin skills == skill install skills
├── test_install_instructions.py # extend: the tap guard covers the new skill
└── test_setup_skill.py          # new: the skill's own commands resolve
docs/
├── getting-started.md       # plugin path added ahead of the manual one
└── README.md               # same
```

## The skills-layout decision

Settled by T002, not by reading: `plugin.json` takes a `skills` array of parent directories, and
`"skills": ["./skills/skills"]` loads all 34 without moving anything. The 34 directories stay where
they are, so `include_str!` in `src/skills/bundled.rs`, the eval harness, `skills/AGENTS.md` and the
benchmark doc all keep working. `research.md` has the probe table.

The declaration adds to the default `skills/*` scan rather than replacing it, so the plugin ships 37:
the 34 bundled ones plus `iris-coverage-run`, `iris-coverage-setup` and `pyprod`, which have sat at
`skills/` root since #84 and are real skills the binary does not bundle. Shipping them is fine.
Parity is therefore "the plugin exposes every bundled skill, plus exactly these three" — named in the
test, so a fourth stray cannot appear unnoticed. Moving those three into `skills/skills/` would make
the sets equal, but it would also add them to the binary's embedded catalog, which is a behaviour
change this feature has no reason to make.

## Phases

**Phase 0 — find out what the loader does.** Done, 2026-09-22; see `research.md`. The minimum
`marketplace.json` is `name`, a top-level `description`, `owner.name` and `plugins[]`, with `author`
in the plugin manifest it points at. The skills root is configurable and additive. A plugin MCP
server with no `env` block resolves through `.iris-agentic-dev.toml` exactly as a hand-registered one
does (`connection_source: "config_file"`). One finding changes the requirements: `--strict` validate
can never pass on this repo, because the plugin root is the repo root and its `CLAUDE.md` draws a
warning that is correct and not worth acting on.

**Phase 1 — manifests, test-first.** `test_plugin_manifest.py` before the manifest edits: the
command names a shipped executable, no `${...}` placeholder appears in an env block, and the version
agrees with `plugin.json` and `Cargo.toml`. Then make them pass.

**Phase 2 — skills parity.** `test_plugin_skills.py` before the layout change, asserting the set the
plugin exposes equals the set `skill install` writes. Then whichever of the two options Phase 0
picked.

**Phase 3 — the setup skill.** Written against a live container, every command run while writing,
the same standard `docs/getting-started.md` is held to. `test_setup_skill.py` checks each
`iris-agentic-dev` subcommand, tool name and `--args` payload the skill names, reusing the guide's
checker rather than a second copy of it.

**Phase 4 — the measurement.** The probe from the spec, rerun with the plugin installed on a PATH
with no `iris-agentic-dev`: it has to name the real tap and finish at a query with rows. Billable,
opt-in, transcript kept under `specs/122-plugin-install-setup/`.

**Phase 5 — docs.** The plugin path goes into the README and into the guide ahead of the manual
`claude mcp add`, which stays for anyone who wants it. Then the slop pass and the markdown
formatters.

## Risks

- **The loader may not ship skills from a subdirectory at all**, in which case Phase 2 is a 34
  directory move on a branch that also changes distribution. If Phase 0 says so, Phase 2 splits into
  its own branch and this feature ships without US3.
- **`/plugin install` from a git repo may require a release tag or a pushed manifest.** Phase 0 tests
  the local-path form first; if the published form needs a tag, it lands with the next release rather
  than being faked.
- **The probe is one sample.** It shows the guess is gone, not that setup works everywhere. Windows
  stays documented and unmeasured, and the spec says so.
