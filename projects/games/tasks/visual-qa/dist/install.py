#!/usr/bin/env python3
"""
Visual QA — Installer
=====================
Installs the visual-qa workflow into the agentic-control-plane directory
of a target project.

Usage:
    python install.py <target>              # Install (skip existing files)
    python install.py <target> --update     # Update changed files
    python install.py <target> --force      # Overwrite all files
    python install.py <target> --dry-run    # Preview without writing

What gets installed:
    <target>/.agent/tools/visual-qa.html
        ← Input collector UI (generates visual-qa-config.json)

    <target>/.agent/docs/visual-qa-rules.md
        ← 50+ validation rules for Alpha Family VLT games

    <target>/.agent/workflows/templates/my_workflows/visual-qa/workflow.yaml
        ← 4-step workflow (gather → analyze → visual validate → fix)

    <target>/.agent/workflows/templates/my_workflows/visual-qa/structs/
        ← Struct schemas (4 files: game-model, analysis, visual, fix reports)
"""

import os
import sys
import argparse
import shutil
import hashlib

INSTALLER_VERSION = "1.0"

# ─── FILE HELPERS ─────────────────────────────────────────────────────────────

def file_hash(path):
    """MD5 hash of a file's contents."""
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def copy_file(src, dst, force=False, update=False, dry_run=False):
    """
    Copy src → dst with mode handling.
    Returns: 'new' | 'updated' | 'unchanged' | 'skipped'
    """
    if os.path.exists(dst):
        if update:
            if file_hash(src) == file_hash(dst):
                return 'unchanged'
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            return 'updated'
        elif force:
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            return 'updated'
        else:
            return 'skipped'
    else:
        if not dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return 'new'

def copy_tree(src_dir, dst_dir, force=False, update=False, dry_run=False):
    """
    Recursively copy src_dir → dst_dir.
    Returns dict with counts: new, updated, unchanged, skipped.
    """
    counts = {'new': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
    for root, dirs, files in os.walk(src_dir):
        for fname in files:
            src = os.path.join(root, fname)
            rel = os.path.relpath(src, src_dir)
            dst = os.path.join(dst_dir, rel)
            result = copy_file(src, dst, force=force, update=update, dry_run=dry_run)
            counts[result] += 1
            flag = {'new': '  NEW   ', 'updated': '  UPD   ',
                    'unchanged': '  ----  ', 'skipped': '  skip  '}[result]
            if result in ('new', 'updated') or not (update or force):
                if result != 'unchanged':
                    print(f"  {flag} {rel}")
    return counts

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Install visual-qa workflow into a project.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('target',
                        help='Target project root (where .agent/ should be installed)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite all existing files')
    parser.add_argument('--update', action='store_true',
                        help='Only overwrite files that have changed')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='Preview what would be installed without writing anything')
    args = parser.parse_args()

    target = os.path.abspath(args.target)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.isdir(target):
        print(f"ERROR: Target directory not found: {target}")
        sys.exit(1)

    mode = ('dry-run' if args.dry_run
            else 'force' if args.force
            else 'update' if args.update
            else 'default')
    print(f"Visual QA Installer v{INSTALLER_VERSION}")
    print(f"Target : {target}")
    print(f"Mode   : {mode}")
    if args.dry_run:
        print("  (dry-run — no files will be written)")
    print()

    total = {'new': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}

    def merge(counts):
        for k in total:
            total[k] += counts[k]

    # ── [1/4] Tools (.agent/tools/) ────────────────────────────────────────────
    print("[1/4] UI Tool (.agent/tools/)")
    src_tools = os.path.join(script_dir, '.agent', 'tools')
    dst_tools = os.path.join(target, '.agent', 'tools')
    if os.path.isdir(src_tools):
        counts = copy_tree(src_tools, dst_tools,
                           force=args.force, update=args.update, dry_run=args.dry_run)
        merge(counts)
        if not any(counts[k] > 0 for k in ('new', 'updated')):
            print("  (no changes)")
    else:
        print("  WARN  .agent/tools/ not found in dist — skipping")
    print()

    # ── [2/4] Docs (.agent/docs/) ────────────────────────────────────────────
    print("[2/4] Rules document (.agent/docs/)")
    src_docs = os.path.join(script_dir, '.agent', 'docs')
    dst_docs = os.path.join(target, '.agent', 'docs')
    if os.path.isdir(src_docs):
        counts = copy_tree(src_docs, dst_docs,
                           force=args.force, update=args.update, dry_run=args.dry_run)
        merge(counts)
        if not any(counts[k] > 0 for k in ('new', 'updated')):
            print("  (no changes)")
    else:
        print("  WARN  .agent/docs/ not found in dist — skipping")
    print()

    # ── [3/4] Workflow (.agent/workflows/templates/my_workflows/visual-qa/) ──
    print("[3/4] Workflow (.agent/workflows/templates/my_workflows/visual-qa/)")
    src_wf = os.path.join(script_dir, '.agent', 'workflows', 'visual-qa')
    dst_wf = os.path.join(target, '.agent', 'workflows', 'templates',
                          'my_workflows', 'visual-qa')
    if os.path.isdir(src_wf):
        counts = copy_tree(src_wf, dst_wf,
                           force=args.force, update=args.update, dry_run=args.dry_run)
        merge(counts)
        if not any(counts[k] > 0 for k in ('new', 'updated')):
            print("  (no changes)")
    else:
        print("  WARN  .agent/workflows/visual-qa/ not found in dist — skipping")
    print()

    # ── [4/4] Reports directory ──────────────────────────────────────────────
    print("[4/4] Reports directory (.agent/workflows/templates/my_workflows/visual-qa/reports/)")
    reports_dir = os.path.join(target, '.agent', 'workflows', 'templates',
                               'my_workflows', 'visual-qa', 'reports')
    if not os.path.isdir(reports_dir):
        if not args.dry_run:
            os.makedirs(reports_dir, exist_ok=True)
        print("  NEW    reports/ (empty directory for workflow output)")
    else:
        print("  (already exists)")
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("-" * 50)
    print(f"Done.  new={total['new']}  updated={total['updated']}  "
          f"unchanged={total['unchanged']}  skipped={total['skipped']}")
    if args.dry_run:
        print("(dry-run: no files were written)")

if __name__ == '__main__':
    main()
