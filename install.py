#!/usr/bin/env python3
"""
Agentic Control Plane — Generic Installer
=========================================

Deploys the workflow engine from this repository root to a target project
directory. Optionally overlays a specific task's workflow bundle.

Usage
-----
    python install.py <target>
    python install.py <target> --task <name>
    python install.py <target> --update
    python install.py <target> --update --task <name>
    python install.py <target> --dry-run
    python install.py <target> --claude            # Claude Code adapter only
    python install.py <target> --cursor            # Cursor adapter only
    python install.py --help

Modes
-----
    (default)  Full install. Copies engine; preserves nothing.
    --update   Preserves user content in target:
                 .agent/workflows/templates/my_workflows/
                 .agent/specs/ (custom files)
    --dry-run  Preview without writing.
    --force    (default already overwrites) Overwrite everything.

Task overlay
------------
    --task <name> copies .agent/workflows/templates/my_workflows/<name>/
    into the target (excluding `extras/` and `deploy.json`).

    If my_workflows/<name>/deploy.json exists, its `extras` array declares
    additional files to deploy to the target at specific paths, e.g.:

        {
          "version": 1,
          "extras": [
            { "src": "extras/tools/foo.html", "dst": ".agent/tools/foo.html" }
          ]
        }

Adapter selection
-----------------
    By default both adapters install (.claude/ and .cursor/ + .mcp.json).
    --claude installs only the Claude Code adapter.
    --cursor installs only the Cursor adapter.

Examples
--------
    # Full engine install into Argus, then overlay shapiro workflow.
    python install.py C:/Projects/ElliotWaveAnalyzer --task shapiro

    # Update existing installation; preserve user workflows.
    python install.py C:/Projects/ElliotWaveAnalyzer --update

    # Preview what --update would do.
    python install.py C:/Projects/ElliotWaveAnalyzer --update --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

ENGINE_ROOT = os.path.dirname(os.path.abspath(__file__))

# Directories that are ALWAYS part of the engine.
ENGINE_CORE_DIRS: list[str] = [
    ".agent/docs",
    ".agent/mcp",
    ".agent/scripts",
    ".agent/tools",
    ".agent/workflows/templates/predefined",
    ".agent/workflows/templates/examples",
]

# Files that are ALWAYS part of the engine core.
ENGINE_CORE_FILES: list[str] = [
    ".agent/specs/README.md",
    ".agent/specs/_scope-config.schema.json",
]

# Adapter layers.
CLAUDE_DIRS: list[str] = [
    ".claude/agents",
    ".claude/rules",
    ".claude/skills",
]
CLAUDE_FILES: list[str] = [
    ".claude/settings.json",
    ".mcp.json",
]

CURSOR_DIRS: list[str] = [
    ".cursor/rules",
    ".cursor/skills",
]
CURSOR_FILES: list[str] = [
    ".cursor/hooks.json",
    ".cursor/mcp.json",
]

# Engine baseline specs (scoped spec system).
ENGINE_SPECS_DIRS: list[str] = [
    ".agent/specs/generic",
]

# Files created if missing; never overwritten.
INIT_FILES: dict[str, str] = {
    ".agent/specs/_index.json":
        '{\n  "version": 1,\n  "updated_at": "",\n  "specs": []\n}\n',
    ".agent/specs/_registry.json":
        '{\n  "version": 2,\n  "updated_at": "",\n  "mappings": {}\n}\n',
    ".agent/workflows/templates/my_workflows/.gitkeep": "",
}

# Paths excluded from directory copies.
EXCLUDE_BASENAMES: set[str] = {"__pycache__", ".pytest_cache"}


# ─── Helpers ────────────────────────────────────────────────────────────


def _is_excluded(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(p in EXCLUDE_BASENAMES for p in parts)


def copy_file(src: str, dst: str, dry_run: bool = False) -> bool:
    if not os.path.exists(src):
        return False
    if not dry_run:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return True


def copy_dir(
    src: str,
    dst: str,
    dry_run: bool = False,
    exclude_sub: tuple[str, ...] = (),
) -> int:
    """Copy src tree into dst. Returns file count. Skips excluded dirs."""
    count = 0
    if not os.path.isdir(src):
        return 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_BASENAMES]
        rel_root = os.path.relpath(root, src)
        if rel_root == ".":
            rel_root = ""
        if rel_root and rel_root.replace("\\", "/").split("/")[0] in exclude_sub:
            dirs[:] = []
            continue
        dst_root = os.path.join(dst, rel_root) if rel_root else dst
        if not dry_run:
            os.makedirs(dst_root, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            if _is_excluded(src_file):
                continue
            dst_file = os.path.join(dst_root, f)
            if not dry_run:
                shutil.copy2(src_file, dst_file)
            count += 1
    return count


def print_copy_dir(label: str, rel: str, src: str, dst: str, dry_run: bool) -> int:
    if not os.path.isdir(src):
        print(f"  [skip]    {rel}/ (not in engine)")
        return 0
    count = copy_dir(src, dst, dry_run=dry_run)
    tag = "[dry]" if dry_run else f"[{label}]"
    print(f"  {tag:<9} {rel}/ ({count} files)")
    return count


def print_copy_file(label: str, rel: str, src: str, dst: str, dry_run: bool) -> int:
    if copy_file(src, dst, dry_run=dry_run):
        tag = "[dry]" if dry_run else f"[{label}]"
        print(f"  {tag:<9} {rel}")
        return 1
    print(f"  [skip]    {rel} (not in engine)")
    return 0


# ─── Task overlay ───────────────────────────────────────────────────────


def install_task(task: str, target: str, dry_run: bool) -> int:
    """Copy my_workflows/<task>/ + any declared extras. Returns file count."""
    task_src = os.path.join(
        ENGINE_ROOT, ".agent", "workflows", "templates", "my_workflows", task
    )
    if not os.path.isdir(task_src):
        print(f"\nERROR: task workflow not found: {task_src}")
        print("Available tasks:")
        my_wf_root = os.path.join(
            ENGINE_ROOT, ".agent", "workflows", "templates", "my_workflows"
        )
        if os.path.isdir(my_wf_root):
            for entry in sorted(os.listdir(my_wf_root)):
                if os.path.isdir(os.path.join(my_wf_root, entry)):
                    print(f"  - {entry}")
        sys.exit(2)

    total = 0
    task_dst = os.path.join(
        target, ".agent", "workflows", "templates", "my_workflows", task
    )

    # Copy the workflow bundle (exclude extras/ and deploy.json; those deploy
    # separately via the extras manifest).
    count = copy_dir(task_src, task_dst, dry_run=dry_run, exclude_sub=("extras",))
    # Remove deploy.json from destination if we copied it.
    dst_deploy = os.path.join(task_dst, "deploy.json")
    if os.path.exists(dst_deploy) and not dry_run:
        os.remove(dst_deploy)
        count = max(count - 1, 0)
    total += count
    tag = "[dry]" if dry_run else "[task]"
    print(
        f"  {tag:<9} my_workflows/{task}/ "
        f"({count} files, excluding extras/ + deploy.json)"
    )

    # Process deploy.json if present.
    deploy_path = os.path.join(task_src, "deploy.json")
    if os.path.isfile(deploy_path):
        with open(deploy_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        extras = manifest.get("extras", [])
        for entry in extras:
            rel_src = entry["src"]
            rel_dst = entry["dst"]
            src_path = os.path.join(task_src, rel_src)
            dst_path = os.path.join(target, rel_dst)
            if copy_file(src_path, dst_path, dry_run=dry_run):
                total += 1
                print(f"  {tag:<9} extra: {rel_dst}")
            else:
                print(f"  [warn]    extra missing: {rel_src}")

    return total


# ─── Main install ───────────────────────────────────────────────────────


def install(
    target: str,
    *,
    update_only: bool,
    dry_run: bool,
    task: str | None,
    install_claude: bool,
    install_cursor: bool,
) -> None:
    if not os.path.isdir(target):
        print(f"ERROR: target directory does not exist: {target}")
        sys.exit(1)

    mode_parts = []
    if dry_run:
        mode_parts.append("DRY-RUN")
    mode_parts.append("UPDATE" if update_only else "FULL INSTALL")
    if task:
        mode_parts.append(f"task={task}")
    adapters = []
    if install_claude:
        adapters.append("claude")
    if install_cursor:
        adapters.append("cursor")
    mode_parts.append("adapters=" + ",".join(adapters))

    bar = "=" * 68
    print(f"\n{bar}")
    print("  Agentic Control Plane — Installer")
    print(f"  Engine: {ENGINE_ROOT}")
    print(f"  Target: {target}")
    print(f"  Mode  : {' | '.join(mode_parts)}")
    print(bar + "\n")

    total = 0

    # Engine core.
    for rel in ENGINE_CORE_DIRS:
        total += print_copy_dir(
            "engine", rel, os.path.join(ENGINE_ROOT, rel), os.path.join(target, rel), dry_run
        )
    for rel in ENGINE_CORE_FILES:
        total += print_copy_file(
            "engine", rel, os.path.join(ENGINE_ROOT, rel), os.path.join(target, rel), dry_run
        )

    # Adapter layers.
    if install_claude:
        for rel in CLAUDE_DIRS:
            total += print_copy_dir(
                "claude", rel, os.path.join(ENGINE_ROOT, rel),
                os.path.join(target, rel), dry_run,
            )
        for rel in CLAUDE_FILES:
            total += print_copy_file(
                "claude", rel, os.path.join(ENGINE_ROOT, rel),
                os.path.join(target, rel), dry_run,
            )
    if install_cursor:
        for rel in CURSOR_DIRS:
            total += print_copy_dir(
                "cursor", rel, os.path.join(ENGINE_ROOT, rel),
                os.path.join(target, rel), dry_run,
            )
        for rel in CURSOR_FILES:
            total += print_copy_file(
                "cursor", rel, os.path.join(ENGINE_ROOT, rel),
                os.path.join(target, rel), dry_run,
            )

    # Engine baseline specs (only on full install; --update preserves existing).
    if update_only:
        print("\n  Preserved (--update):")
        preserved_dirs = [
            ".agent/workflows/templates/my_workflows",
            ".agent/specs",
        ]
        for rel in preserved_dirs:
            dst = os.path.join(target, rel)
            if os.path.isdir(dst):
                count = sum(len(f) for _, _, f in os.walk(dst))
                print(f"    {rel}/ ({count} files)")
            else:
                print(f"    {rel}/ (does not exist yet)")
    else:
        for rel in ENGINE_SPECS_DIRS:
            total += print_copy_dir(
                "engine", rel, os.path.join(ENGINE_ROOT, rel),
                os.path.join(target, rel), dry_run,
            )

    # Task overlay (explicit — runs under both full and update modes).
    if task:
        print(f"\n  Task overlay: {task}")
        total += install_task(task, target, dry_run=dry_run)

    # Init files (create if missing).
    print()
    for rel, content in INIT_FILES.items():
        dst = os.path.join(target, rel)
        if os.path.exists(dst):
            print(f"  [exists]  {rel} (kept)")
            continue
        if not dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write(content)
        total += 1
        tag = "[dry]" if dry_run else "[init]"
        print(f"  {tag:<9} {rel} (created)")

    # Regenerate per-step agent files.
    print("\n  Regenerating per-step agent files...")
    if dry_run:
        print("  [dry]     update-workflows.py (skipped in dry-run)")
    else:
        update_script = os.path.join(target, ".agent", "scripts", "update-workflows.py")
        if os.path.isfile(update_script):
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, update_script],
                cwd=target,
                env=env,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  [ok]      update-workflows.py completed")
                for line in (result.stdout or "").strip().splitlines():
                    print(f"            {line}")
            else:
                print(f"  [warn]    update-workflows.py failed (exit {result.returncode})")
                for line in (result.stderr or "").strip().splitlines()[:10]:
                    print(f"            {line}")
        else:
            print("  [skip]    update-workflows.py not found in target")

    # Summary.
    print(f"\n{bar}")
    suffix = " (dry-run — no files written)" if dry_run else ""
    print(f"  Done! {total} files processed.{suffix}")
    print("\n  Next steps:")
    print("    1. Restart Claude Code / Cursor to pick up new agents & MCP.")
    print("    2. Run: /run-workflow <name>")
    print(bar + "\n")


# ─── CLI ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy Agentic Control Plane to a target project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", help="Target project root directory.")
    parser.add_argument(
        "--task",
        default=None,
        metavar="<name>",
        help="Overlay a my_workflows/<name>/ task bundle on top of the engine.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Preserve user workflows and specs in target.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Preview without writing files.",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Install only the Claude Code adapter.",
    )
    parser.add_argument(
        "--cursor",
        action="store_true",
        help="Install only the Cursor adapter.",
    )
    args = parser.parse_args()

    # Adapter selection: if neither flag set, install both.
    if args.claude or args.cursor:
        install_claude = args.claude
        install_cursor = args.cursor
    else:
        install_claude = True
        install_cursor = True

    install(
        os.path.abspath(args.target),
        update_only=args.update,
        dry_run=args.dry_run,
        task=args.task,
        install_claude=install_claude,
        install_cursor=install_cursor,
    )


if __name__ == "__main__":
    main()
