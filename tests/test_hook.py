#!/usr/bin/env python3
"""
Tests for the toolcheck PreToolUse hook.

The hook's job is narrow: notice when a command adds something new, stay quiet
otherwise. Both halves matter. A hook that misses real installs is useless, and
a hook that fires on `git commit -m "add install docs"` gets switched off in a
week.

Run: python3 tests/test_hook.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_PATH = os.path.join(HERE, "..", "hooks", "toolcheck-hook.py")

# The filename has a hyphen, so load it as a module explicitly. Testing the
# functions directly beats parsing the prose note, which is free to change.
_spec = importlib.util.spec_from_file_location("toolcheck_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


# A project that already depends on react and vitest, so re-adding either is
# not a new decision and should produce nothing.
MANIFEST = {
    "name": "fixture",
    "dependencies": {"react": "^18.0.0"},
    "devDependencies": {"vitest": "^1.0.0"},
}

EXTRACTION = [
    ("npm install zod",                                 ["zod"]),
    ("npm install",                                     []),
    ("npm run build",                                   []),
    ("git pull && npm install zod",                      ["zod"]),
    ("sudo pip install flask",                           ["flask"]),
    ("npm install zod > install.log",                    ["zod"]),
    ('echo "npm install zod" > notes.txt',               []),
    ("npm install react@18 zod",                        ["react", "zod"]),
    ("pnpm add @anthropic-ai/sdk",                      ["@anthropic-ai/sdk"]),
    ("npm i --save-dev typescript",                     ["typescript"]),
    ("pip install requests",                            ["requests"]),
    ("claude mcp add elevenlabs -- npx elevenlabs-mcp", ["elevenlabs"]),
    ("npm install lodash && npm run build",             ["lodash"]),
    ("npm install ./local-pkg",                         []),
    ("yarn add axios got",                              ["axios", "got"]),
    ("cargo add serde",                                 ["serde"]),
    ("go get github.com/foo/bar",                       ["github.com/foo/bar"]),
    ("pip install 'requests==2.31.0'",                  ["'requests"]),
    ("git clone https://github.com/openai/whisper.git", ["openai/whisper"]),
    ("git clone git@github.com:foo/bar.git",            ["foo/bar"]),
    ("git clone --depth 1 https://github.com/a/b.git",  ["a/b"]),
    ("git clone https://github.com/a/b.git my-folder",  ["a/b"]),
    ("git pull",                                        []),
]

# Commands that must never produce a note, including near misses that share
# vocabulary with a real install.
SILENT = [
    "npm run build",
    "git commit -m 'add install docs'",
    "echo npm install zod > notes.txt",
    "cat requirements.txt",
    "git status",
    "git commit -m 'clone the config'",
    "npm install",
]


def check(label, got, want):
    ok = got == want
    print(f"[{'ok  ' if ok else 'FAIL'}] {label[:52]:54s} -> {got if got != [] else 'quiet'}")
    if not ok:
        print(f"         expected {want}")
    return 0 if ok else 1


def main():
    failures = 0

    print("extraction")
    for command, expected in EXTRACTION:
        failures += check(command, hook.extract_packages(command), expected)

    print("\nalready installed is respected")
    with tempfile.TemporaryDirectory() as cwd:
        with open(os.path.join(cwd, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(MANIFEST, fh)
        for name, want in (("react", True), ("vitest", True), ("zod", False)):
            got = hook.already_installed(name, cwd)
            ok = got == want
            failures += 0 if ok else 1
            print(f"[{'ok  ' if ok else 'FAIL'}] {name:54s} -> {got}")

    print("\nend to end, the JSON envelope Claude Code expects")
    with tempfile.TemporaryDirectory() as cwd:
        with open(os.path.join(cwd, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(MANIFEST, fh)

        payload = {"tool_name": "Bash", "cwd": cwd,
                   "tool_input": {"command": "npm install zod"}}
        result = subprocess.run([sys.executable, HOOK_PATH],
                                input=json.dumps(payload),
                                capture_output=True, text=True)
        ok = result.returncode == 0
        failures += 0 if ok else 1
        print(f"[{'ok  ' if ok else 'FAIL'}] exit code is 0")

        body = json.loads(result.stdout)["hookSpecificOutput"]
        for field, want in (("hookEventName", "PreToolUse"),):
            got = body.get(field)
            ok = got == want
            failures += 0 if ok else 1
            print(f"[{'ok  ' if ok else 'FAIL'}] {field} is {want}")

        ok = "zod" in body.get("additionalContext", "")
        failures += 0 if ok else 1
        print(f"[{'ok  ' if ok else 'FAIL'}] the note names the package")

        # The hook must never block. permissionDecision would stop the command.
        ok = "permissionDecision" not in body
        failures += 0 if ok else 1
        print(f"[{'ok  ' if ok else 'FAIL'}] no permissionDecision, so it cannot block")

        print("\nstays quiet")
        for command in SILENT:
            payload = {"tool_name": "Bash", "cwd": cwd,
                       "tool_input": {"command": command}}
            result = subprocess.run([sys.executable, HOOK_PATH],
                                    input=json.dumps(payload),
                                    capture_output=True, text=True)
            got = result.stdout.strip()
            ok = got == ""
            failures += 0 if ok else 1
            print(f"[{'ok  ' if ok else 'FAIL'}] {command[:52]:54s} -> {'quiet' if ok else got[:40]}")

    print()
    if failures:
        print(f"{failures} failing")
        return 1
    print("all passing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
