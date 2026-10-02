# 0001: Skill tiers

Date: 2026-10-02. Status: accepted, ships in 1.5.0.

## Context

A plugin install of 1.5.0 as first built registered 39 skills with Claude Code, and a bare
`skill install` wrote all 34 bundled skills. Claude Code lists every registered skill's name and
description in each session, so all 39 cost context on every turn, and most sessions use a few. `opencode-introspect` is useful only when working on iad itself.

## Decision

Each bundled `SKILL.md` carries `tier: core | extra | internal` in its frontmatter. That line is
the only place a tier is set. The layout stays flat (`skills/skills/<name>/SKILL.md`). Nothing
moves between folders; the model is mattpocock-skills' split between what ships by default and
what is reachable on request, without its directory moves.

- **core** (10): `iris-agentic-dev`, `objectscript-guardrails`, `objectscript-review`,
  `objectscript-sql-patterns`, `iris-sql`, `objectscript-tdd`, `objectscript-unit-test`,
  `objectscript-debugging`, `objectscript-list-patterns`, `iris-connectivity`.
- **internal**: `opencode-introspect`.
- **extra**: the other 23, `objectscript-fewshot-fixes` included.

Every channel follows the tier:

| Channel                               | Core | Extra | Internal |
| ------------------------------------- | ---- | ----- | -------- |
| `.claude-plugin/plugin.json`          | yes  | no    | no       |
| bare `skill install`                  | yes  | no    | no       |
| `skill install --all`                 | yes  | yes   | no       |
| `skill install <name>`                | yes  | yes   | yes      |
| `iris-agentic-dev.toml`, skills.sh    | yes  | yes   | no       |
| MCP `skill_list` / `skill_search`     | yes  | yes   | no       |
| MCP `skill_describe`                  | yes  | yes   | yes      |
| index in the `iris-agentic-dev` skill | n/a  | yes   | no       |

`plugin.json` names each core skill by explicit path. The `iris-agentic-dev` skill has an
`## Extra skills` section, one line per extra skill, so an agent with only core installed knows
the others exist and can fetch one with `skill_describe`.

The installer fetches skills from GitHub `HEAD`. When a fetched file has no `tier:` line (a `main`
from before this change), the binary's embedded copy supplies the tier. A skill that has no tier
anywhere counts as extra.

Old installs: a bare install deletes nothing. It names managed copies of skills outside the tier it
installed and points at `--prune`, which removes only files carrying the `managed_by` marker.

## Consequences

- Moving a skill between tiers is a one-line frontmatter edit. `test_skill_tiers.rs` then fails
  for every list that has to follow: `plugin.json`, both manifests and the extra-skills index.
  Core and internal membership is spelled out in that test, so changing it is a visible decision.
- Users who relied on a bare install for all 34 need `--all`. The 1.5.0 release notes say so, and
  the install hint says so each time it finds leftovers.
- The four plugin-only skills at `skills/` root have no tier. The plugin loads that directory by
  default, and the binary does not embed them.
