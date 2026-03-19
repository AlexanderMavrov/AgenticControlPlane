#!/usr/bin/env python3
"""
install.py — Install the Agentic Control Plane into a target project.

Usage:
    python install.py <target-project-path>
    python install.py <target-project-path> --claude    # Claude Code adapter instead of Cursor
    python install.py <target-project-path> --update    # Update only changed files
    python install.py <target-project-path> --update --dry-run  # Preview what would change

What it does:
    1. Copies .agent/docs/ and .agent/scripts/ to the target
    2. Copies .agent/workflows/templates/ (workflow definitions — predefined + user) to the target
    3. Copies .agent/specs/ (behavioral specs template) to the target
    4. Copies .agent/tools/ (trace viewer and utilities) to the target
    5. Copies skills to the target (.cursor/ or .claude/)
    6. Merges hook config into existing hooks.json (doesn't overwrite)
    7. Copies rules (workflow-context + spec-guard) to the target

Modes:
    (default)   First install — copies new files, skips existing
    --force     Overwrite ALL existing files (destructive)
    --update    Smart update — only overwrite files whose content differs from source
    --dry-run   With --update: show what would change without modifying anything
"""

import argparse
import filecmp
import json
import os
import shutil
import sys


# Counters for summary
_counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}


def _reset_counts():
    for k in _counts:
        _counts[k] = 0


def copy_tree(src, dst, force=False, update=False, dry_run=False):
    """Copy directory tree, preserving structure.

    Modes:
    - default: skip existing files
    - force: overwrite everything
    - update: overwrite only if content differs (new files always copied)
    - dry_run (with update): only report, don't write
    """
    copied = []
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        dst_root = os.path.join(dst, rel_root) if rel_root != "." else dst

        if not dry_run:
            os.makedirs(dst_root, exist_ok=True)

        for f in files:
            src_file = os.path.join(root, f)
            dst_file = os.path.join(dst_root, f)
            rel_path = os.path.relpath(dst_file, dst)

            if os.path.exists(dst_file):
                if update:
                    # Compare content — skip if identical
                    if filecmp.cmp(src_file, dst_file, shallow=False):
                        _counts["unchanged"] += 1
                        continue
                    else:
                        if dry_run:
                            print(f"  WOULD UPDATE  {rel_path}")
                            _counts["updated"] += 1
                        else:
                            shutil.copy2(src_file, dst_file)
                            copied.append(rel_path)
                            _counts["updated"] += 1
                            print(f"  UPDATE  {rel_path}")
                elif force:
                    shutil.copy2(src_file, dst_file)
                    copied.append(rel_path)
                    print(f"  COPY  {rel_path}")
                else:
                    _counts["skipped"] += 1
                    print(f"  SKIP  {rel_path} (exists)")
            else:
                # New file — always copy (unless dry_run)
                if dry_run:
                    print(f"  WOULD ADD     {rel_path}")
                    _counts["new"] += 1
                else:
                    shutil.copy2(src_file, dst_file)
                    copied.append(rel_path)
                    _counts["new"] += 1
                    print(f"  NEW   {rel_path}")

    return copied


def merge_hooks(src_hooks_path, dst_hooks_path):
    """Merge our hook config into existing hooks.json without overwriting."""

    # Read our hooks
    with open(src_hooks_path, "r", encoding="utf-8") as f:
        our_hooks = json.load(f)

    our_subagent_hooks = (
        our_hooks.get("hooks", {}).get("subagentStop", [])
    )
    if not our_subagent_hooks:
        print("  WARN  No subagentStop hooks found in source — skipping merge")
        return

    our_command = our_subagent_hooks[0].get("command", "")

    # If target hooks.json exists, merge
    if os.path.exists(dst_hooks_path):
        with open(dst_hooks_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

        existing_hooks = existing.setdefault("hooks", {})
        existing_subagent = existing_hooks.setdefault("subagentStop", [])

        # Check if our hook is already there
        for hook in existing_subagent:
            if hook.get("command") == our_command:
                print(f"  SKIP  hooks.json (hook already present: {our_command})")
                return

        # Add our hook
        existing_subagent.extend(our_subagent_hooks)

        # Ensure version field
        existing.setdefault("version", 1)

        with open(dst_hooks_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"  MERGE hooks.json (added: {our_command})")
    else:
        # No existing file — just copy
        os.makedirs(os.path.dirname(dst_hooks_path), exist_ok=True)
        shutil.copy2(src_hooks_path, dst_hooks_path)
        print(f"  COPY  hooks.json")


def main():
    parser = argparse.ArgumentParser(
        description="Install Agentic Control Plane into a target project"
    )
    parser.add_argument(
        "target",
        help="Path to the target project root",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Install Claude Code adapter (.claude/) instead of Cursor (.cursor/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite ALL existing files (destructive)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Smart update — only overwrite files whose content differs from source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --update: preview what would change without modifying anything",
    )
    args = parser.parse_args()

    if args.dry_run and not args.update:
        print("ERROR: --dry-run requires --update")
        sys.exit(1)

    if args.force and args.update:
        print("ERROR: --force and --update are mutually exclusive")
        sys.exit(1)

    target = os.path.abspath(args.target)
    adapter_dir = ".claude" if args.claude else ".cursor"

    if not os.path.isdir(target):
        print(f"ERROR: Target directory not found: {target}")
        sys.exit(1)

    # Determine source directory (where this script lives)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    mode = "DRY RUN" if args.dry_run else "UPDATE" if args.update else "FORCE" if args.force else "INSTALL"
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Installing Agentic Control Plane into: {target}")
    print(f"Adapter: {adapter_dir}  |  Mode: {mode}")
    print()

    # 1. Copy .agent/docs/
    print("[1/8] Engine documentation (.agent/docs/)")
    src_docs = os.path.join(script_dir, ".agent", "docs")
    dst_docs = os.path.join(target, ".agent", "docs")
    if os.path.isdir(src_docs):
        copy_tree(src_docs, dst_docs, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  WARN  Source .agent/docs/ not found — skipping")
    print()

    # 2. Copy .agent/scripts/
    print("[2/8] Gate scripts (.agent/scripts/)")
    src_scripts = os.path.join(script_dir, ".agent", "scripts")
    dst_scripts = os.path.join(target, ".agent", "scripts")
    if os.path.isdir(src_scripts):
        copy_tree(src_scripts, dst_scripts, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  WARN  Source .agent/scripts/ not found — skipping")
    print()

    # 3. Copy .agent/workflows/templates/ (workflow definitions — predefined + my_workflows)
    print("[3/8] Workflow templates (.agent/workflows/templates/)")
    src_templates = os.path.join(script_dir, ".agent", "templates")
    dst_templates = os.path.join(target, ".agent", "templates")
    if os.path.isdir(src_templates):
        copy_tree(src_templates, dst_templates, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  WARN  Source .agent/workflows/templates/ not found — skipping")
    print()

    # 4. Copy .agent/specs/ (behavioral specs directory + templates)
    print("[4/8] Behavioral specs (.agent/specs/)")
    src_specs = os.path.join(script_dir, ".agent", "specs")
    dst_specs_dir = os.path.join(target, ".agent", "specs")
    if os.path.isdir(src_specs):
        copy_tree(src_specs, dst_specs_dir, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        # Create manually if source doesn't have it
        if not os.path.isdir(dst_specs_dir):
            os.makedirs(dst_specs_dir, exist_ok=True)
            print(f"  MKDIR .agent/specs/")
        # Create _index.json and _registry.json if they don't exist
        for fname, content in [
            ("_index.json", '{\n  "version": 1,\n  "specs": [],\n  "updated_at": null\n}\n'),
            ("_registry.json", '{\n  "version": 2,\n  "mappings": {},\n  "updated_at": null\n}\n'),
        ]:
            fpath = os.path.join(dst_specs_dir, fname)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"  COPY  .agent/specs/{fname}")
            else:
                print(f"  SKIP  .agent/specs/{fname} (exists)")
    print()

    # 5. Copy .agent/tools/ (trace viewer, utilities)
    print("[5/8] Tools (.agent/tools/)")
    src_tools = os.path.join(script_dir, ".agent", "tools")
    dst_tools = os.path.join(target, ".agent", "tools")
    if os.path.isdir(src_tools):
        copy_tree(src_tools, dst_tools, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  WARN  Source .agent/tools/ not found — skipping")
    print()

    # 6. Copy skills
    print(f"[6/8] Skills ({adapter_dir}/skills/)")
    src_skills = os.path.join(script_dir, ".cursor", "skills")
    dst_skills = os.path.join(target, adapter_dir, "skills")
    if os.path.isdir(src_skills):
        copy_tree(src_skills, dst_skills, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  WARN  Source .cursor/skills/ not found — skipping")
    print()

    # 7. Merge hooks
    print(f"[7/8] Hook configuration ({adapter_dir}/hooks.json)")
    src_hooks = os.path.join(script_dir, ".cursor", "hooks.json")
    if args.claude:
        # Claude Code hooks go in .claude/settings.json — different format
        # For now, just inform the user
        print("  INFO  Claude Code hooks require manual setup in .claude/settings.json")
        print(f"  INFO  Add subagentStop hook: python .agent/scripts/gate-check.py")
    elif os.path.isfile(src_hooks):
        dst_hooks = os.path.join(target, adapter_dir, "hooks.json")
        merge_hooks(src_hooks, dst_hooks)
    else:
        print("  WARN  Source hooks.json not found — skipping")
    print()

    # 8. Copy rules
    print(f"[8/8] Rules ({adapter_dir}/rules/)")
    src_rules = os.path.join(script_dir, ".cursor", "rules")
    dst_rules = os.path.join(target, adapter_dir, "rules")
    if os.path.isdir(src_rules):
        copy_tree(src_rules, dst_rules, force=args.force, update=args.update, dry_run=args.dry_run)
    else:
        print("  SKIP  No rules to copy")
    print()

    # Create empty workflows directory
    workflows_dir = os.path.join(target, ".agent", "workflows")
    if not os.path.isdir(workflows_dir):
        os.makedirs(workflows_dir, exist_ok=True)
        print(f"Created: .agent/workflows/ (put your workflow definitions here)")
    else:
        print(f"Exists:  .agent/workflows/")

    # Summary
    print()
    if args.update or args.dry_run:
        print(f"{'[DRY RUN] ' if args.dry_run else ''}Summary:")
        if _counts["new"]:
            print(f"  New files:     {_counts['new']}")
        if _counts["updated"]:
            print(f"  Updated:       {_counts['updated']}")
        if _counts["unchanged"]:
            print(f"  Unchanged:     {_counts['unchanged']}")
        if not _counts["new"] and not _counts["updated"]:
            print("  Everything is up to date!")
        if args.dry_run:
            print()
            print("  Run without --dry-run to apply changes.")
    else:
        print("Done! Next steps:")
        print(f"  1. Create a workflow:  /run-workflow create-workflow")
        print(f"  2. Learn the format:  /learn-workflows")
        print(f"  3. Run a workflow:    /run-workflow <name>")
        print(f"  4. Manage specs:      /spec add <component>")
        print(f"  5. Use [specs::X] in chat to capture behavioral requirements")


if __name__ == "__main__":
    main()
