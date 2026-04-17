#!/usr/bin/env python3
"""
Agentic Control Plane — Installer

Deploys the workflow engine from dist/ to a target project directory.

Usage:
    python install.py <target-project-path>              # Full install
    python install.py --update <target-project-path>     # Update (preserves user content)

Full install:  Copies everything. Use for first-time setup.
Update:        Copies engine files only. Preserves:
               - .agent/workflows/templates/my_workflows/  (user workflows)
               - .agent/specs/ custom files (user specs)
               - .agent/workflows/<name>/  runtime state (manifests, traces, data)
"""

import argparse
import os
import shutil
import sys

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")

# ── Directories to ALWAYS copy (engine files) ──────────────────────────
ENGINE_DIRS = [
    ".agent/docs",
    ".agent/scripts",
    ".agent/mcp",
    ".agent/tools",
    ".agent/workflows/templates/predefined",
    ".agent/workflows/templates/examples",
    ".claude/agents",
    ".claude/rules",
    ".claude/skills",
    ".cursor/rules",
    ".cursor/skills",
]

# ── Single files to ALWAYS copy ────────────────────────────────────────
ENGINE_FILES = [
    ".mcp.json",
    ".claude/settings.json",
    ".cursor/hooks.json",
    ".cursor/mcp.json",
    ".agent/specs/README.md",
]

# ── Directories to copy ONLY on full install (preserved on update) ─────
USER_DIRS = [
    ".agent/workflows/templates/my_workflows",
    ".agent/specs",
]

# ── Files to create if missing (not overwritten on update) ─────────────
INIT_FILES = {
    ".agent/specs/_index.json": '{\n  "version": 1,\n  "updated_at": "",\n  "specs": []\n}\n',
    ".agent/specs/_registry.json": '{\n  "version": 2,\n  "updated_at": "",\n  "mappings": {}\n}\n',
    ".agent/workflows/templates/my_workflows/.gitkeep": "",
}


def copy_dir(src: str, dst: str) -> int:
    """Copy directory tree, overwriting existing files. Returns file count."""
    count = 0
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        dst_root = os.path.join(dst, rel_root) if rel_root != "." else dst
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(dst_root, f))
            count += 1
    return count


def copy_file(src: str, dst: str) -> bool:
    """Copy a single file, creating parent dirs. Returns True if copied."""
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def install(target: str, update_only: bool = False) -> None:
    if not os.path.isdir(DIST_DIR):
        print(f"Error: dist/ not found at {DIST_DIR}")
        sys.exit(1)

    if not os.path.isdir(target):
        print(f"Error: target directory does not exist: {target}")
        sys.exit(1)

    mode = "UPDATE" if update_only else "FULL INSTALL"
    print(f"\n{'='*60}")
    print(f"  Agentic Control Plane — {mode}")
    print(f"  Source: {DIST_DIR}")
    print(f"  Target: {target}")
    print(f"{'='*60}\n")

    total_files = 0

    # ── Engine directories ──────────────────────────────────────────
    for rel_dir in ENGINE_DIRS:
        src = os.path.join(DIST_DIR, rel_dir)
        dst = os.path.join(target, rel_dir)
        if os.path.isdir(src):
            count = copy_dir(src, dst)
            total_files += count
            print(f"  [engine]  {rel_dir}/ ({count} files)")
        else:
            print(f"  [skip]    {rel_dir}/ (not in dist)")

    # ── Engine single files ─────────────────────────────────────────
    for rel_file in ENGINE_FILES:
        src = os.path.join(DIST_DIR, rel_file)
        dst = os.path.join(target, rel_file)
        if copy_file(src, dst):
            total_files += 1
            print(f"  [engine]  {rel_file}")
        else:
            print(f"  [skip]    {rel_file} (not in dist)")

    # ── User directories (full install only) ────────────────────────
    if not update_only:
        for rel_dir in USER_DIRS:
            src = os.path.join(DIST_DIR, rel_dir)
            dst = os.path.join(target, rel_dir)
            if os.path.isdir(src):
                count = copy_dir(src, dst)
                total_files += count
                print(f"  [user]    {rel_dir}/ ({count} files)")
    else:
        print(f"\n  Preserved (--update):")
        for rel_dir in USER_DIRS:
            dst = os.path.join(target, rel_dir)
            if os.path.isdir(dst):
                file_count = sum(len(f) for _, _, f in os.walk(dst))
                print(f"    {rel_dir}/ ({file_count} files)")
            else:
                print(f"    {rel_dir}/ (does not exist yet)")

    # ── Init files (create if missing, never overwrite) ─────────────
    print()
    for rel_file, content in INIT_FILES.items():
        dst = os.path.join(target, rel_file)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)
            total_files += 1
            print(f"  [init]    {rel_file} (created)")
        else:
            print(f"  [exists]  {rel_file} (kept)")

    # ── Run update-workflows to regenerate AGENT.md files ───────────
    print(f"\n  Regenerating per-step agent files...")
    update_script = os.path.join(target, ".agent", "scripts", "update-workflows.py")
    if os.path.exists(update_script):
        import subprocess
        result = subprocess.run(
            [sys.executable, update_script],
            cwd=target,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  [ok]      update-workflows.py completed")
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    print(f"            {line}")
        else:
            print(f"  [warn]    update-workflows.py failed (exit {result.returncode})")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n")[:5]:
                    print(f"            {line}")
    else:
        print(f"  [skip]    update-workflows.py not found")

    # ── Summary ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Done! {total_files} files copied.")
    print(f"\n  Next steps:")
    print(f"    1. Restart Claude Code / Cursor (to pick up new agents & MCP)")
    print(f"    2. Run: /run-workflow <name>")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Agentic Control Plane to a target project"
    )
    parser.add_argument(
        "target",
        help="Path to the target project directory",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update mode: copy engine files only, preserve user workflows and specs",
    )
    args = parser.parse_args()

    target = os.path.abspath(args.target)
    install(target, update_only=args.update)


if __name__ == "__main__":
    main()
