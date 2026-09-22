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


def test_the_bundled_catalog_is_under_a_path_the_plugin_declares():
    bundled = {
        entry
        for entry in os.listdir(_BUNDLED_ROOT)
        if _has_skill_file(os.path.join(_BUNDLED_ROOT, entry))
    }
    assert bundled, f"{_BUNDLED_ROOT} holds no skills, which cannot be right"

    missing = sorted(bundled - _skills_the_loader_would_see())
    assert not missing, (
        f"{len(missing)} bundled skills are invisible to the plugin loader: {missing}. "
        'Declare their parent directory in plugin.json, e.g. "skills": ["./skills/skills"].'
    )


def test_every_skill_in_the_repo_reaches_someone_who_installs_the_plugin():
    """No SKILL.md in the tree may be unreachable, whatever depth it sits at.

    A skill nobody can load is worse than one that does not exist: it is referenced in docs
    and error messages, and a reader who follows the pointer finds nothing.
    """
    missing = sorted(_every_skill_in_the_repo() - _skills_the_loader_would_see())
    assert not missing, (
        f"these skills exist in the repo but no `plugin install` delivers them: {missing}. "
        "The loader does not recurse, so a skill more than one level under a declared path "
        'needs its own entry in plugin.json "skills".'
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
    assert line, (
        f"`plugin details {plugin_name}` printed no Skills line:\n{result.stdout}"
    )

    reported = {
        name.strip() for name in line.split(")", 1)[1].split(",") if name.strip()
    }
    expected = _every_skill_in_the_repo()
    assert reported == expected, (
        f"the loader reports {len(reported)} skills and this repo holds {len(expected)}. "
        f"Only in the loader: {sorted(reported - expected)}. "
        f"Only on disk: {sorted(expected - reported)}."
    )
