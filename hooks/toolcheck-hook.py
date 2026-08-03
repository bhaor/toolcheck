#!/usr/bin/env python3
"""
toolcheck PreToolUse hook.

Fires before Claude Code runs a shell command. If the command is about to add a
new dependency or MCP server, it injects a note asking for a toolcheck first.

It never blocks. A gate that interrupts a working session gets uninstalled
within a week, so this only ever adds context and lets the command proceed.
The agent decides what to do with the note.

Reads the hook payload on stdin, writes an optional decision to stdout, exits 0.
See https://code.claude.com/docs/en/hooks
"""

from __future__ import annotations  # keeps the type hints working on Python 3.7+

import json
import os
import re
import sys

# Commands that add something new to the project.
#
# These are anchored to the start of a command segment on purpose. An unanchored
# search matches the middle of `echo "npm install zod" > notes.txt`, and a hook
# that fires on prose about installing gets switched off within a week.
INSTALL_PATTERNS = [
    r"^(?:npm|pnpm|bun)\s+(?:install|add|i)\b",
    r"^yarn\s+add\b",
    r"^pip3?\s+install\b",
    r"^(?:uv|poetry)\s+add\b",
    r"^cargo\s+add\b",
    r"^go\s+get\b",
    r"^claude\s+mcp\s+add\b",
    # Cloning a repo is the same decision as installing one, and for anyone
    # evaluating tools it is usually the first move rather than the last.
    r"^git\s+clone\b",
]

# Prefixes that sit in front of a real command without changing what it is.
PREFIXES = re.compile(r"^(?:sudo|command|time|nice|env|npx|\w+=\S+)\s+")

# Flags, and the subcommand words themselves, are not package names.
NOT_A_PACKAGE = {
    "install", "add", "i", "get", "mcp", "claude", "npm", "pnpm", "yarn",
    "bun", "pip", "pip3", "uv", "poetry", "cargo", "go", "--", "-",
}


def install_segment(command: str) -> str | None:
    """Return the first segment of a chain that really is an install command.

    Splitting first, then anchoring, is what keeps `echo "npm install zod"`
    from matching while `git pull && npm install zod` still does.
    """
    for segment in re.split(r"&&|\|\||;|\|", command):
        # Redirections are not arguments, so drop them before matching.
        segment = re.split(r"[><]", segment)[0].strip()
        while PREFIXES.match(segment):
            segment = PREFIXES.sub("", segment, count=1)
        if any(re.search(p, segment) for p in INSTALL_PATTERNS):
            return segment
    return None


def extract_packages(command: str) -> list[str]:
    """Pull candidate package names out of an install command.

    Returns an empty list for anything that is not an install, so this is safe
    to call on any command.
    """
    segment = install_segment(command)
    if segment is None:
        return []

    # A clone names a repository rather than a package. Report it as owner/repo,
    # which is what someone would actually search for.
    if segment.startswith("git "):
        for tok in segment.split()[2:]:
            # A repo reference always contains a path separator, which is what
            # tells it apart from a flag value like the 1 in `--depth 1`.
            if tok.startswith("-") or not ("/" in tok or ":" in tok):
                continue
            repo = re.sub(r"\.git$", "", tok.rstrip("/"))
            repo = re.sub(r"^(?:https?://|git@)[^/:]+[/:]", "", repo)
            return [repo] if repo else []
        return []

    tokens = segment.split()
    # Everything after a bare `--` is a passthrough command, not a package.
    # `claude mcp add name -- npx some-server` names one server, not three.
    if "--" in tokens:
        tokens = tokens[: tokens.index("--")]
    packages = []
    for tok in tokens:
        if tok.startswith("-"):
            continue
        if tok.lower() in NOT_A_PACKAGE:
            continue
        # Local paths and URLs are not registry packages.
        if tok.startswith((".", "/", "~")) or "://" in tok:
            continue
        # Strip a version specifier: react@18 -> react, requests==2.0 -> requests
        name = re.split(r"(?<!^)@|==|>=|<=|~=", tok)[0]
        if name and name not in packages:
            packages.append(name)
    return packages


def already_installed(name: str, cwd: str) -> bool:
    """True if this is a reinstall of something the project already declares."""
    manifest = os.path.join(cwd, "package.json")
    try:
        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    for field in ("dependencies", "devDependencies", "peerDependencies"):
        if name in (data.get(field) or {}):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0  # Malformed input is not our problem to report.

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    if install_segment(command) is None:
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    packages = [p for p in extract_packages(command) if not already_installed(p, cwd)]
    if not packages:
        return 0  # Bare install, or everything here is already a dependency.

    listed = ", ".join(packages[:5])
    note = (
        f"toolcheck: this command adds {listed}. "
        "Before running it, use the toolcheck skill to check whether it is "
        "maintained, whether it has known advisories, and whether something "
        "already in this project does the same job. Report the card, then "
        "carry on. If the user has already decided, just proceed."
    )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": note,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
