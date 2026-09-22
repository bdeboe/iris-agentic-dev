"""The two plugin manifests have to describe something a stranger can install.

Nothing in `cargo test` or the build reaches these files. `.claude-plugin/plugin.json` is a
JSON blob read by another program at install time, so a wrong command name in it compiles,
lints and ships. It did: the manifest named `iris-dev` as the MCP command, which no release
has ever installed, and it worked on one machine only because a stale binary of that name
from 2026-07-30 sat on PATH. `.claude-plugin/marketplace.json` did not exist at all, which
makes `plugin marketplace add` fail outright and the plugin uninstallable by anyone.

Both defects are invisible to a maintainer who already has the tools working. These tests
are the layer that sees them.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_PLUGIN_DIR = os.path.join(_REPO_ROOT, ".claude-plugin")
_PLUGIN_JSON = os.path.join(_PLUGIN_DIR, "plugin.json")
_MARKETPLACE_JSON = os.path.join(_PLUGIN_DIR, "marketplace.json")

#: The only executable a release installs. Homebrew, the release assets and the VS Code
#: extension all write this name and nothing else.
SHIPPED_EXECUTABLE = "iris-agentic-dev"

#: `${FOO}` in a manifest env value expands to an empty string when FOO is unset, which is
#: worse than leaving the key out: the server starts with host="" and never runs discovery.
_PLACEHOLDER_RE = re.compile(r"\$\{[^}]+\}")


def _read(path: str) -> dict:
    if not os.path.exists(path):
        pytest.fail(
            f"{os.path.relpath(path, _REPO_ROOT)} is missing. Without it "
            "`claude plugin marketplace add` fails and nobody can install the plugin."
        )
    with open(path, encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{os.path.relpath(path, _REPO_ROOT)} is not valid JSON: {exc}")


def _workspace_version() -> str:
    with open(os.path.join(_REPO_ROOT, "Cargo.toml"), encoding="utf-8") as handle:
        cargo = handle.read()
    match = re.search(
        r"^\[workspace\.package\][^\[]*?^version\s*=\s*\"([^\"]+)\"",
        cargo,
        re.M | re.S,
    )
    assert match, "could not find the workspace version in Cargo.toml"
    return match.group(1)


def test_both_manifests_are_valid_json():
    assert _read(_PLUGIN_JSON)
    assert _read(_MARKETPLACE_JSON)


def test_every_mcp_command_is_an_executable_a_release_installs():
    plugin = _read(_PLUGIN_JSON)
    servers = plugin.get("mcpServers", {})
    assert servers, (
        "plugin.json declares no MCP server, which is the point of the plugin"
    )
    for name, server in servers.items():
        command = server.get("command", "")
        assert command, f"mcpServers.{name} has no command"
        assert os.path.basename(command) == SHIPPED_EXECUTABLE, (
            f"mcpServers.{name}.command is {command!r}, which no release installs. "
            f"The one executable a release provides is {SHIPPED_EXECUTABLE!r}."
        )


def test_no_manifest_env_value_is_an_unset_variable_placeholder():
    for path in (_PLUGIN_JSON, _MARKETPLACE_JSON):
        manifest = _read(path)
        for server_name, server in manifest.get("mcpServers", {}).items():
            for key, value in (server.get("env") or {}).items():
                assert not _PLACEHOLDER_RE.search(str(value)), (
                    f"{os.path.relpath(path, _REPO_ROOT)} mcpServers.{server_name}.env.{key} "
                    f"is {value!r}. An unset variable expands to an empty string, so the "
                    "server starts with a blank host and never reaches discovery. Leave the "
                    "key out and let .iris-agentic-dev.toml resolve the connection."
                )


def test_the_marketplace_offers_the_plugin_this_repo_declares():
    plugin = _read(_PLUGIN_JSON)
    market = _read(_MARKETPLACE_JSON)

    assert market.get("name"), "marketplace.json needs a name"
    assert market.get("description"), (
        "marketplace.json needs a top-level description; without one `plugin validate` warns"
    )
    assert (market.get("owner") or {}).get("name"), "marketplace.json needs owner.name"

    offered = {entry.get("name") for entry in market.get("plugins", [])}
    assert plugin["name"] in offered, (
        f"marketplace.json offers {sorted(offered)}, which does not include "
        f"{plugin['name']!r} from plugin.json — the manifests disagree about what this repo "
        "ships."
    )

    for entry in market.get("plugins", []):
        source = entry.get("source", "")
        assert source, f"plugins entry {entry.get('name')!r} has no source"
        if source.startswith("."):
            resolved = os.path.normpath(os.path.join(_REPO_ROOT, source))
            assert os.path.isdir(resolved), (
                f"plugins entry {entry.get('name')!r} sources {source!r}, which is not a "
                "directory in this repo"
            )


def test_the_plugin_manifest_carries_author_attribution():
    author = _read(_PLUGIN_JSON).get("author")
    assert author and (author.get("name") if isinstance(author, dict) else author), (
        "plugin.json needs an author; `claude plugin validate` warns for every plugin in a "
        "marketplace without one"
    )


def test_the_version_lives_in_exactly_one_manifest():
    """marketplace.json must not restate the version.

    `plugin.json`'s version is already pinned to the workspace by
    `crates/iris-agentic-dev-bin/tests/unit/test_plugin_manifest_version.rs` and by
    `scripts/gates/check_versions.py`. A second copy in marketplace.json would be a third
    place to forget, and the marketplace schema does not need it, so the requirement is that
    it stays absent rather than that it agrees.
    """
    plugin = _read(_PLUGIN_JSON)
    assert plugin.get("version") == _workspace_version(), (
        f"plugin.json version {plugin.get('version')!r} does not match the workspace "
        f"version {_workspace_version()!r}"
    )

    market = _read(_MARKETPLACE_JSON)
    assert "version" not in market, (
        "marketplace.json declares a version. Drop it — plugin.json is the one place the "
        "release version belongs, and a second copy is a second thing to forget."
    )
    for entry in market.get("plugins", []):
        assert "version" not in entry, (
            f"marketplace.json plugins entry {entry.get('name')!r} declares a version. The "
            "plugin's own manifest is the source of truth; a copy here drifts silently."
        )


#: The one warning the repo cannot clear: the plugin root is the repo root, and a repo root
#: has a CLAUDE.md because contributors work in it. The advice ("ship context as a skill")
#: is right for a plugin-only directory and wrong here, so it is allowlisted rather than
#: acted on. Everything else the validator says is a failure.
_ALLOWED_WARNING = "CLAUDE.md at the plugin root is not loaded as project context"


def _validate(target: str) -> dict:
    """Run `claude plugin validate --json` and return the parsed report."""
    result = subprocess.run(
        ["claude", "plugin", "validate", "--json", target],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.stdout.strip(), (
        f"`claude plugin validate --json {target}` printed nothing. stderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def _reports(report: dict):
    """Every per-file report in a validation result, the manifest's own included."""
    yield report["manifest"]
    yield from report.get("contents", [])


@pytest.mark.parametrize("manifest", ["plugin.json", "marketplace.json"])
def test_the_installer_itself_accepts_the_manifest(manifest):
    """The validator's own verdict, which is the only one that decides an install.

    Skipped where the CLI is absent, which is most CI runners; the pure-JSON assertions
    above run everywhere and cover the shape. `--strict` is deliberately not used: it turns
    the allowlisted CLAUDE.md warning into exit 1, so it is a gate nothing can pass.
    """
    if shutil.which("claude") is None:
        pytest.skip(
            "the claude CLI is not installed, so its verdict cannot be read here"
        )

    report = _validate(os.path.join(_PLUGIN_DIR, manifest))
    for entry in _reports(report):
        where = os.path.relpath(entry.get("file", manifest), _REPO_ROOT)
        assert not entry["errors"], f"{where} has validation errors: {entry['errors']}"
        unexpected = [
            warning
            for warning in entry.get("warnings", [])
            if _ALLOWED_WARNING not in warning.get("message", "")
        ]
        assert not unexpected, f"{where} has unexpected warnings: {unexpected}"
    assert report["success"], f"validation of {manifest} did not succeed: {report}"
