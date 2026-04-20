#!/usr/bin/env python3
"""
scope_cli.py — CLI entry point for /scope-* skills.

Subcommands:
  show                 Print active scope, label, source, and available list
  set <id> [--project] Set active scope (user-level or team default)
  unset                Clear .agent/local/active-scope
  list [--counts]      List available scopes (optionally with spec counts)
  add <id> <label>     Create a new scope (config entry + directory)

Exit codes:
  0 success
  1 validation/usage error
  2 scope-related error (not found, duplicate, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow import when invoked from project root
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import scope_context as sc  # noqa: E402


# ── Subcommand implementations ──

def cmd_show(args: argparse.Namespace) -> int:
    try:
        active, source = sc.resolve_active_scope()
    except sc.ScopeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    scopes = sc.get_available_scopes()
    label = next((s["label"] for s in scopes if s["id"] == active), active)
    src_label = {
        "cli": "CLI --scope flag",
        "user": "user override (.agent/local/active-scope)",
        "project-default": "project default (_scope-config.json)",
        "fallback": "hard-coded fallback (no config, no override)",
    }.get(source, source)

    print(f"Active scope: {active}")
    print(f"Label:        {label}")
    print(f"Source:       {src_label}")
    print()
    print("Available scopes:")
    print(sc.format_scope_table(scopes))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    scope_id = args.scope_id
    try:
        sc.validate_scope_id(scope_id)
    except sc.InvalidScopeIdError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not sc.scope_exists(scope_id):
        available = ", ".join(s["id"] for s in sc.get_available_scopes())
        print(
            f"Error: scope '{scope_id}' is not declared. "
            f"Available: {available}.\n"
            f"Hint: /scope-add {scope_id} \"<label>\" to create it first.",
            file=sys.stderr,
        )
        return 2

    if args.project:
        config = sc.load_scope_config()
        config["default_active_scope"] = scope_id
        sc.save_scope_config(config)
        print(f"Project default_active_scope set to '{scope_id}'.")
        print("(Committed to _scope-config.json — team-wide.)")
    else:
        sc.write_user_active_scope(scope_id)
        print(f"Active scope set to '{scope_id}' (user-level override).")
        print(f"Stored in {sc.ACTIVE_SCOPE_FILE} (gitignored).")

    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    cleared = sc.clear_user_active_scope()
    if cleared:
        print("User active-scope override cleared.")
        active, source = sc.resolve_active_scope()
        print(f"Now resolving to: {active} (source: {source})")
    else:
        print("No user active-scope override to clear.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    scopes = sc.get_available_scopes()
    if args.counts:
        for entry in scopes:
            sdir = sc.scope_dir(entry["id"])
            if sdir.is_dir():
                count = sum(
                    1
                    for p in sdir.rglob("*.md")
                    if not p.name.startswith("_")
                )
            else:
                count = 0
            entry["label"] = f"{entry['label']}  ({count} specs)"
    print("Available scopes:")
    print(sc.format_scope_table(scopes))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    scope_id = args.scope_id
    label = args.label or scope_id

    try:
        sc.validate_scope_id(scope_id)
    except sc.InvalidScopeIdError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if scope_id == sc.GENERIC_SCOPE:
        print(
            f"Error: '{sc.GENERIC_SCOPE}' is a reserved implicit scope "
            f"and cannot be declared.",
            file=sys.stderr,
        )
        return 1

    config = sc.load_scope_config()
    scopes = config.get("scopes", [])
    if any(s.get("id") == scope_id for s in scopes):
        print(
            f"Error: scope '{scope_id}' already exists in _scope-config.json.",
            file=sys.stderr,
        )
        return 2

    scopes.append({"id": scope_id, "label": label})
    config["scopes"] = scopes
    if "default_active_scope" not in config:
        config["default_active_scope"] = None

    sc.save_scope_config(config)
    sdir = sc.ensure_scope_dir(scope_id)

    print(f"Scope '{scope_id}' added.")
    print(f"  Config:    {sc.SCOPE_CONFIG_PATH}")
    print(f"  Directory: {sdir}/")
    print(f"  Indexes:   _index.json, _registry.json (empty)")
    print()
    print("Next: /scope-set " + scope_id + "  to switch to it.")
    return 0


# ── Argument parser ──

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scope_cli",
        description="CLI for /scope-* skills (show, set, unset, list, add)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Show active scope and available list")
    p_show.set_defaults(func=cmd_show)

    p_set = sub.add_parser("set", help="Set active scope")
    p_set.add_argument("scope_id", help="Scope id to set active")
    p_set.add_argument(
        "--project",
        action="store_true",
        help="Write to project config (team-wide) instead of user override",
    )
    p_set.set_defaults(func=cmd_set)

    p_unset = sub.add_parser("unset", help="Clear user-level active scope override")
    p_unset.set_defaults(func=cmd_unset)

    p_list = sub.add_parser("list", help="List available scopes")
    p_list.add_argument(
        "--counts",
        action="store_true",
        help="Include per-scope spec counts",
    )
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Create a new scope")
    p_add.add_argument("scope_id", help="New scope id")
    p_add.add_argument("label", nargs="?", help="Human-readable description")
    p_add.set_defaults(func=cmd_add)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except sc.ScopeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
