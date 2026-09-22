"""Every document that tells someone how to install has to name the real tap.

`brew tap intersystems-community/iris-agentic-dev` reads like the right answer — the repo is
called that, and the formula inside the tap is called that. The tap is
`intersystems-community/tap`, and the wrong form fails with a 404 on the first command a new
reader types, before anything else in a guide can go right.

Nothing else catches this. The tap lives in another repo, so no build step here resolves it, and
a reader with the binary already installed never runs the line.
"""

from __future__ import annotations

import glob
import os
import re

#: The one true tap, matching `brew info iris-agentic-dev` -> intersystems-community/tap.
#: Changing the tap means changing this line, which is the point: the failure then names every
#: document that has to change with it.
TAP = "intersystems-community/tap"

#: `brew tap <owner>/<name>`, and the same owner/name when passed to `brew install` as a
#: fully-qualified formula.
_TAP_RE = re.compile(r"brew\s+tap\s+(\S+)")
_QUALIFIED_INSTALL_RE = re.compile(r"brew\s+(?:install|reinstall)\s+([\w.-]+/[\w.-]+)/")

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

#: Release notes record what the instructions were at the time and are not edited afterwards.
_EXCLUDED = ("docs/release-notes/",)


def _markdown_files() -> list[str]:
    found = []
    for path in glob.glob(os.path.join(_REPO_ROOT, "**", "*.md"), recursive=True):
        relative = os.path.relpath(path, _REPO_ROOT)
        if relative.startswith(("target/", "node_modules/", ".git/")):
            continue
        if relative.startswith(_EXCLUDED):
            continue
        found.append(relative)
    assert found, "no markdown files found, so this test is checking nothing"
    return found


def test_every_document_names_the_real_homebrew_tap():
    wrong: list[str] = []
    for relative in _markdown_files():
        with open(os.path.join(_REPO_ROOT, relative), encoding="utf-8") as handle:
            text = handle.read()
        for named in _TAP_RE.findall(text) + _QUALIFIED_INSTALL_RE.findall(text):
            if named != TAP:
                wrong.append(f"{relative}: {named}")
    assert not wrong, (
        f"these documents name a Homebrew tap that is not {TAP}, so the first command a reader "
        f"types 404s:\n  " + "\n  ".join(sorted(wrong))
    )


def test_the_install_instructions_are_somewhere_a_reader_lands():
    """A tap named nowhere is as bad as one named wrongly."""
    naming = [
        relative
        for relative in _markdown_files()
        if TAP in open(os.path.join(_REPO_ROOT, relative), encoding="utf-8").read()
    ]
    for required in ("README.md", "docs/getting-started.md"):
        assert required in naming, (
            f"{required} does not name the {TAP} tap. Both are entry points, and a reader who "
            f"lands on one should not have to find the other to install anything"
        )
