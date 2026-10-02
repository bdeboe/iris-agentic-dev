"""`/plugin install` has to bring the skills, and it silently did not.

Plugin skills load from `<plugin root>/skills/<name>/SKILL.md`. The 34 skills this repo
bundles live at `skills/skills/<name>/SKILL.md`, one directory deeper, so an install shipped
only the three that happen to sit at `skills/` root and none of the ones the plugin exists to
deliver. `claude plugin details iris-dev` reported `Skills (3)`. Nothing failed; the plugin
just arrived nearly empty.

A `skills` array in `plugin.json` names extra paths and is additive rather than a replacement,
so the fix is a declaration and no files move — which matters, because the 34 directory names
are compiled into the binary by `include_str!`, referenced by the eval harness and linked from
the benchmark doc.

Each entry in that array is read one of two ways, measured rather than assumed: a path holding
its own `SKILL.md` loads as a single skill, and a path that does not loads every
`<name>/SKILL.md` directly beneath it. It does not recurse. That is why
`skills/skills/iris-agentic-dev/nopws-setup` needs naming — it sits two levels down, and
`tools/nopws.rs` points people at it by path when a NoPWS build refuses a connection.

Since 1.5.0 the plugin ships only the bundled skills whose frontmatter says `tier: core`, each
named by its own path (docs/adr/0001-skill-tiers.md). Extra and internal skills stay in the
binary and reach an agent through the MCP `skill_describe` tool, not the plugin.
"""

import json
import os
import shutil
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_PLUGIN_JSON = os.path.join(_REPO_ROOT, ".claude-plugin", "plugin.json")
_SKILLS_ROOT = os.path.join(_REPO_ROOT, "skills")

#: Where the binary's bundled catalog lives. `bundled.rs` embeds these with `include_str!` and
#: a Rust test keeps the two in sync, so this directory decides what the plugin has to ship.
_BUNDLED_ROOT = os.path.join(_SKILLS_ROOT, "skills")


def _plugin() -> dict:
    with open(_PLUGIN_JSON, encoding="utf-8") as handle:
        return json.load(handle)


def _has_skill_file(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "SKILL.md"))


def _every_skill_in_the_repo() -> set[str]:
    """Every directory under `skills/` holding a SKILL.md, at any depth."""
    found = set()
    for dirpath, _dirnames, filenames in os.walk(_SKILLS_ROOT):
        if "SKILL.md" in filenames:
            found.add(os.path.basename(dirpath))
    return found


def _tier(skill_dir: str) -> str | None:
    """`tier:` from a SKILL.md's frontmatter, or None."""
    with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---\n"):
        return None
    for line in text[4 : text.find("\n---", 4)].splitlines():
        if line.startswith("tier:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def _bundled_by_tier() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for entry in os.listdir(_BUNDLED_ROOT):
        path = os.path.join(_BUNDLED_ROOT, entry)
        if _has_skill_file(path):
            out.setdefault(_tier(path) or "", set()).add(entry)
    return out


def _skills_the_plugin_should_ship() -> set[str]:
    """Core bundled skills, `nopws-setup`, and the plugin-only skills at `skills/` root."""
    bundled = {name for names in _bundled_by_tier().values() for name in names}
    return (_every_skill_in_the_repo() - bundled) | _bundled_by_tier().get(
        "core", set()
    )


def _skills_the_loader_would_see() -> set[str]:
    """Apply the loader's rule to this repo: implicit `skills/` root plus declared paths.

    A declared path with its own SKILL.md is one skill; a declared path without one is a
    parent whose immediate children are skills. Neither case recurses.
    """
    seen: set[str] = set()

    def scan_parent(root: str) -> None:
        if not os.path.isdir(root):
            return
        for entry in sorted(os.listdir(root)):
            if _has_skill_file(os.path.join(root, entry)):
                seen.add(entry)

    scan_parent(_SKILLS_ROOT)
    for declared in _plugin().get("skills", []):
        path = os.path.normpath(os.path.join(_REPO_ROOT, declared))
        if _has_skill_file(path):
            seen.add(os.path.basename(path))
        else:
            scan_parent(path)
    return seen


def test_the_core_skills_are_under_a_path_the_plugin_declares():
    core = _bundled_by_tier().get("core", set())
    assert len(core) == 10, f"expected the 10 core skills, found {sorted(core)}"

    missing = sorted(core - _skills_the_loader_would_see())
    assert not missing, (
        f"{len(missing)} core skills are invisible to the plugin loader: {missing}. "
        'Name each in plugin.json, e.g. "./skills/skills/objectscript-guardrails".'
    )


def test_the_plugin_ships_no_extra_or_internal_skill():
    tiers = _bundled_by_tier()
    shipped = (tiers.get("extra", set()) | tiers.get("internal", set())) & (
        _skills_the_loader_would_see()
    )
    assert not shipped, (
        f"the plugin loads non-core skills: {sorted(shipped)}. Declare core skills one path "
        "each rather than their parent directory."
    )


def test_every_skill_the_plugin_should_ship_reaches_someone_who_installs_it():
    """No SKILL.md the plugin is meant to carry may be unreachable, whatever depth it sits at.

    A skill nobody can load is worse than one that does not exist: it is referenced in docs
    and error messages, and a reader who follows the pointer finds nothing.
    """
    missing = sorted(_skills_the_plugin_should_ship() - _skills_the_loader_would_see())
    assert not missing, (
        f"these skills should ship with the plugin but no `plugin install` delivers them: "
        f"{missing}. The loader does not recurse, so a skill more than one level under a "
        'declared path needs its own entry in plugin.json "skills".'
    )


def test_the_skills_declaration_names_paths_that_exist():
    for declared in _plugin().get("skills", []):
        path = os.path.normpath(os.path.join(_REPO_ROOT, declared))
        assert os.path.isdir(path), (
            f"plugin.json declares skills path {declared!r}, which is not a directory. The "
            "loader ignores it silently, so the plugin ships without those skills."
        )
        if not _has_skill_file(path):
            children = [
                entry
                for entry in os.listdir(path)
                if _has_skill_file(os.path.join(path, entry))
            ]
            assert children, (
                f"plugin.json declares skills path {declared!r}, which has no SKILL.md of "
                "its own and no child holding one"
            )


def test_the_loader_reports_the_skills_this_repo_expects():
    """The installed plugin's own inventory, which is the only account that settles it.

    Skipped where the CLI is absent or the plugin is not installed from this checkout; the
    disk-shape assertions above run everywhere. Install with
    `claude plugin marketplace add <checkout> && claude plugin install iris-dev@iris-agentic-dev`.
    """
    if shutil.which("claude") is None:
        pytest.skip(
            "the claude CLI is not installed, so its inventory cannot be read here"
        )

    plugin_name = _plugin()["name"]
    result = subprocess.run(
        ["claude", "plugin", "details", plugin_name],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        pytest.skip(
            f"{plugin_name} is not installed here, so there is no inventory to read: "
            f"{result.stderr.strip()[:200]}"
        )

    line = next(
        (
            raw.strip()
            for raw in result.stdout.splitlines()
            if raw.strip().startswith("Skills (")
        ),
        None,
    )
    assert (
        line
    ), f"`plugin details {plugin_name}` printed no Skills line:\n{result.stdout}"

    reported = {
        name.strip() for name in line.split(")", 1)[1].split(",") if name.strip()
    }
    expected = _skills_the_plugin_should_ship()
    assert reported == expected, (
        f"the loader reports {len(reported)} skills and the plugin should ship {len(expected)}. "
        f"Only in the loader: {sorted(reported - expected)}. "
        f"Only on disk: {sorted(expected - reported)}."
    )
