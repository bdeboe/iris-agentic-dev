"""The getting-started guide is executable, and these tests are why that claim survives.

A newcomer's first hour is spent typing what a document told them to type. Every wrong
command in it costs that person more than a wrong line of code costs me, because they have
no way to tell a typo in the guide from a broken install. So the guide is checked against
the binary rather than proofread:

- every subcommand it names is a real subcommand
- every tool it calls is in the tool catalogue
- every `--args` payload parses, and its keys are in that tool's own schema
- every relative link resolves

The third is the one with teeth. Writing this guide I typed `{"sql": "..."}` at `iris_query`,
whose field is `query`, and `check-config` as a subcommand when it is the `check_config`
tool. Both read fine. Both would have sent a reader to a dead end. `tool --list` and
`tool <name> --schema` read the router with no IRIS connection (spec 114), so all of this
costs nothing and needs no container.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

import pytest

from tests.e2e.skill_eval import provenance

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

GUIDE = "docs/getting-started.md"

#: `iris-agentic-dev <subcommand>`, first word only. `tool` is handled separately.
#: `[ \t]` rather than `\s`, or `brew install iris-agentic-dev` followed by a newline and
#: another command reads as the subcommand `brew`.
_SUBCOMMAND_RE = re.compile(r"iris-agentic-dev[ \t]+(?:--\S+[ \t]+)*([a-z][a-z-]+)")

#: `tool <name>`, with or without an `--args`/`--schema` tail.
_TOOL_CALL_RE = re.compile(r"iris-agentic-dev[ \t]+tool[ \t]+([a-z][a-z0-9_]+)")

#: `--args '<json>'`, single-quoted, possibly continued across lines with a trailing `\`.
#: `'\''` inside it is the shell's way of putting a single quote in a single-quoted string,
#: which a SQL literal needs, so the pattern has to step over it rather than end there.
_ARGS_RE = re.compile(r"--args\s+'((?:[^']|'\\'')*)'", re.S)

#: What the shell sees once it has processed `'\''`.
_SHELL_QUOTE_ESCAPE = "'\\''"

#: Markdown links to a path in this repo. Skips URLs and anchors.
_LINK_RE = re.compile(r"\]\((?!https?://|#)([^)\s]+)")

#: Named in prose as flags of the binary, not as subcommands.
_NOT_SUBCOMMANDS = frozenset({"help"})

#: Fence languages whose contents are commands someone types.
_COMMAND_FENCES = frozenset({"bash", "sh", "shell", "console"})

#: `claude mcp add iris-agentic-dev --scope user` passes the name as an argument, so the token
#: after it is a flag's value rather than a subcommand. The binary's own invocation in that
#: command is after the `--`, on a later line, so dropping this line checks less than nothing.
_SERVER_NAME_CONTEXT = "claude mcp"


def _lines_invoking_the_binary(guide: str) -> str:
    """Prose and command blocks, without expected output.

    `text` blocks hold what IRIS and the CLI print back, and `Added stdio MCP server
    iris-agentic-dev with command:` reads to a regex as the subcommand `with`. Output is not
    something a reader types, so it is not scanned for typed commands.
    """
    kept: list[str] = []
    fence: str | None = None
    for line in guide.splitlines():
        if line.startswith("```"):
            fence = None if fence is not None else line[3:].strip().lower() or "none"
            continue
        if fence is not None and fence not in _COMMAND_FENCES:
            continue
        if _SERVER_NAME_CONTEXT in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def _guide() -> str:
    path = os.path.join(_REPO_ROOT, GUIDE)
    if not os.path.isfile(path):
        pytest.fail(
            f"{GUIDE} does not exist. It is the one document a first-time reader needs, and "
            f"the README's Documentation table links it"
        )
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _binary() -> str:
    binary = provenance.resolve_binary()
    if binary:
        return binary
    searched = "; ".join(c.describe() for c in provenance.binary_candidates())
    # A skip is right on a laptop with nothing built and wrong the moment someone named the
    # build they wanted checked. `IAD_BINARY` set and unresolvable means the path is wrong, and
    # the #118 nightly is what a skip in that situation costs: a month of green over nothing.
    if os.environ.get("IAD_BINARY"):
        pytest.fail(
            f"IAD_BINARY={os.environ['IAD_BINARY']} does not resolve to an executable. "
            f"Searched: {searched}"
        )
    pytest.skip(
        "no iris-agentic-dev binary resolved — set IAD_BINARY to the build under test. "
        f"Searched: {searched}"
    )


def _run(binary: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary, *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        # A dead port on purpose: everything asserted here reads the tool router, so a test
        # that needs a container would be testing the wrong thing.
        env={**os.environ, "IRIS_HOST": "localhost", "IRIS_WEB_PORT": "59999"},
    )


def test_the_guide_is_linked_from_the_readme():
    """An unlinked guide is a guide nobody arrives at."""
    _guide()
    with open(os.path.join(_REPO_ROOT, "README.md"), encoding="utf-8") as handle:
        readme = handle.read()
    assert GUIDE in readme, (
        f"README does not link {GUIDE}. docs/cursor-quickstart.md has been in the repo "
        f"unlinked from the Documentation table, which is how a document goes unread"
    )


@pytest.mark.requires_binary
def test_every_subcommand_the_guide_names_exists():
    binary = _binary()
    top_level = _run(binary, "--help")
    assert top_level.returncode == 0, top_level.stderr
    real = set(re.findall(r"^\s{2}([a-z][a-z-]+)\s{2,}", top_level.stdout, re.M))
    assert "mcp" in real, (
        f"could not parse subcommands from --help:\n{top_level.stdout}"
    )

    named = (
        set(_SUBCOMMAND_RE.findall(_lines_invoking_the_binary(_guide())))
        - _NOT_SUBCOMMANDS
    )
    unknown = sorted(named - real)
    assert not unknown, (
        f"{GUIDE} names {unknown} as subcommands and the binary has no such command. "
        f"`check-config` is the live example: it reads like a subcommand and is actually the "
        f"`check_config` tool, reached through `tool check_config`"
    )


@pytest.mark.requires_binary
def test_every_tool_the_guide_calls_is_in_the_catalogue():
    binary = _binary()
    listing = _run(binary, "tool", "--list")
    assert listing.returncode == 0, listing.stderr
    catalogue = {
        line.split()[0] for line in listing.stdout.splitlines() if line.strip()
    }
    assert len(catalogue) > 50, f"tool --list returned {len(catalogue)} names"

    called = set(_TOOL_CALL_RE.findall(_guide()))
    assert called, (
        f"{GUIDE} calls no tools, which cannot be right for a getting-started guide"
    )
    unknown = sorted(called - catalogue)
    assert not unknown, f"{GUIDE} calls tools that do not exist: {unknown}"


@pytest.mark.requires_binary
def test_every_args_payload_parses_and_uses_real_fields():
    """The teeth. A plausible-looking wrong field name is invisible to a proofreader."""
    binary = _binary()
    guide = _guide()

    payloads: list[tuple[str, str]] = []
    for match in _TOOL_CALL_RE.finditer(guide):
        tail = guide[match.end() : match.end() + 600]
        args = _ARGS_RE.match(tail.lstrip()) or _ARGS_RE.search(tail.split("\n```")[0])
        if args:
            payloads.append((match.group(1), args.group(1)))
    assert payloads, f"{GUIDE} shows no --args payload, so nothing here is checked"

    failures = []
    for tool, raw in payloads:
        try:
            parsed = json.loads(raw.replace(_SHELL_QUOTE_ESCAPE, "'"))
        except json.JSONDecodeError as exc:
            failures.append(f"{tool}: payload is not JSON ({exc})")
            continue
        if not isinstance(parsed, dict):
            failures.append(
                f"{tool}: payload is {type(parsed).__name__}, not an object"
            )
            continue
        schema = _run(binary, "tool", tool, "--schema")
        if schema.returncode != 0:
            failures.append(f"{tool}: --schema failed: {schema.stderr.strip()[:120]}")
            continue
        body = schema.stdout[schema.stdout.find("inputSchema:") :]
        try:
            declared = set(json.loads(body[body.find("{") :])["properties"])
        except (ValueError, KeyError) as exc:
            failures.append(f"{tool}: could not read properties from --schema ({exc})")
            continue
        unknown = sorted(set(parsed) - declared)
        if unknown:
            failures.append(
                f"{tool}: guide passes {unknown}, schema declares {sorted(declared)}"
            )
    assert not failures, (
        "the guide passes fields the tool does not accept:\n  " + "\n  ".join(failures)
    )


def test_every_relative_link_in_the_guide_resolves():
    guide = _guide()
    broken = [
        target
        for target in _LINK_RE.findall(guide)
        if not os.path.exists(os.path.join(_REPO_ROOT, "docs", target.split("#")[0]))
        and not os.path.exists(os.path.join(_REPO_ROOT, target.split("#")[0]))
    ]
    assert not broken, (
        f"{GUIDE} links to paths that do not exist: {sorted(set(broken))}"
    )
