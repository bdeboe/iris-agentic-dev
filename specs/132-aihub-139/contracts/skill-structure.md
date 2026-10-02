# Contract: `iris-ai-hub` SKILL.md structure

`tests/unit/test_aihub_139.rs` checks this contract.

## Frontmatter

```yaml
name: iris-ai-hub
description: <one paragraph>
author: tdyar
version: 0.2.0
managed_by: iris-agentic-dev
source: >-
  ai-hub-eap master 72749d6dbf0b856a60775378fa88d346bb79d4e4;
  ready-hackathon-dev-template 391c3d5 ai-hub-* skills by Gabriel Ing
```

## Sections, in this order

1. **Where the docs are.**
   - Must contain:
     - `https://github.com/intersystems-community/ai-hub-eap`
     - `master`
     - `https://raw.githubusercontent.com/intersystems-community/ai-hub-eap/master/<path>`
   - Tells the agent to check the repo's current state before relying on a file.
2. **Topic map.**
   - A `Topic | File` table (data-model.md).
   - Every path is on `upstream-files.txt`.
3. **Workflow.**
   - Numbered.
   - Step 1 reads the build version (`iris_info` or `$ZVERSION` via `iris_execute`).
   - Step 2 reads the installed `%AI` classes.
   - It states that the installed classes win over the docs and that the agent says so when they differ.
4. **No web gateway (fallback).**
   - Short. The primary path is HTTP through a gateway; this section covers AI builds that ship with none (DPP-1192), where iad runs `docker_only`.
   - Under `docker_only`, `docs_introspect`/`iris_symbols`/`iris_doc` do not work.
   - Read class metadata with `iris_execute` on `%Dictionary.CompiledClass`/`CompiledMethod` instead.
5. **Topic sections.** Every factual sentence maps to a `holds` or `reworded` claim row.
6. **Corrections.** Each line reads "the guide says X; on 2026.3 it is Y", one per drafts.md mismatch.
7. **Upstream's own skill.**
   - Gives its raw URL.
   - Does not say `skill_community` installs it.

## Must not contain

- `aihub-eap` as a skill name to load.
- Any `iris_*` tool name that is not in the registry.
- Any build number for the docs other than the builds the live tests run on.
