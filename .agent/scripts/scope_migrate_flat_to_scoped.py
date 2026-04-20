#!/usr/bin/env python3
"""
scope_migrate_flat_to_scoped.py — one-shot migration helper.

Converts a pre-scoping project layout:
    .agent/specs/<domain>/<SPEC-ID>.md
    .agent/specs/_index.json       (global)
    .agent/specs/_registry.json    (global)

into the scope-aware layout:
    .agent/specs/<target-scope>/<domain>/<SPEC-ID>.md
    .agent/specs/<target-scope>/_index.json
    .agent/specs/<target-scope>/_registry.json
    .agent/specs/generic/_index.json     (empty, always present)
    .agent/specs/generic/_registry.json  (empty, always present)
    .agent/specs/_scope-config.json      (declaring target-scope)

Usage:
    python scope_migrate_flat_to_scoped.py <target-scope> [--label "..."]
                                          [--dry-run] [--project-root PATH]

Behavior:
  - All spec .md files are MOVED (git mv semantics: shutil.move) into the
    target scope directory.
  - Each spec's frontmatter gets `scope: [<target-scope>]` added if missing.
    Existing scope: entries are left untouched.
  - Old global _index.json / _registry.json are MOVED to the target scope
    directory and their `file_path` values are rewritten to the new paths.
  - _scope-config.json is CREATED (not overwritten) with {target-scope}
    declared. If the file already exists, the target scope is APPENDED
    if not already present.
  - generic/ scope dir is ALWAYS ensured with empty indexes.

Safety:
  - Dry-run mode prints all planned actions without touching disk.
  - Refuses to run if <target-scope> directory already contains specs
    (use --force to override).
  - Never deletes spec .md files.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# ── Utilities ──

FRONTMATTER_RE = re.compile(
    r"^---\r?\n(.*?)\r?\n---\r?\n",
    re.DOTALL,
)


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_scope_in_frontmatter(content: str, scope: str) -> tuple[str, bool]:
    """Return (new_content, modified). Inserts `scope: [<scope>]` after
    the spec_id line if no scope field is present in the YAML frontmatter."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return content, False  # no frontmatter — skip

    fm_text = m.group(1)
    if re.search(r"^scope:", fm_text, re.MULTILINE):
        return content, False  # already has scope

    # Insert after spec_id line, or at top if no spec_id
    lines = fm_text.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("spec_id:"):
            insert_idx = i + 1
            break
    lines.insert(insert_idx, f"scope: [{scope}]")
    new_fm = "\n".join(lines)

    new_content = content.replace(m.group(0), f"---\n{new_fm}\n---\n", 1)
    return new_content, True


def move_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"  WOULD MOVE  {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"  MOVED       {src} -> {dst}")


# ── Migration steps ──

def find_spec_domains(specs_root: Path, known_scope_ids: set[str]) -> list[Path]:
    """Return domain directories under .agent/specs/ (excluding scope dirs
    and management files)."""
    result = []
    if not specs_root.is_dir():
        return result
    for entry in specs_root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in known_scope_ids:
            continue
        if entry.name.startswith("_") or entry.name == "local":
            continue
        result.append(entry)
    return sorted(result, key=lambda p: p.name)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"  WOULD WRITE {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  WROTE       {path}")


def rewrite_index_paths(index_data: dict, target_scope: str) -> dict:
    """Rewrite file_path entries to include the target scope prefix."""
    specs = index_data.get("specs", [])
    for entry in specs:
        fp = entry.get("file_path", "")
        # Drop a leading ".agent/specs/" if present, then prepend the new
        # scoped path.
        norm = fp.removeprefix(".agent/specs/").removeprefix(".agent\\specs\\")
        if norm == fp:
            # path didn't include .agent/specs/ prefix — keep as-is under scope
            pass
        entry["file_path"] = f".agent/specs/{target_scope}/{norm}"
    index_data["scope"] = target_scope
    return index_data


def update_scope_config(
    config_path: Path, target_scope: str, label: str | None, dry_run: bool
) -> None:
    """Add target_scope to _scope-config.json, creating the file if missing."""
    if config_path.is_file():
        config = load_json(config_path)
    else:
        config = {"scopes": [], "default_active_scope": None}

    existing_ids = {s.get("id") for s in config.get("scopes", [])}
    if target_scope in existing_ids:
        print(f"  SKIP        _scope-config.json already has '{target_scope}'")
    else:
        entry = {"id": target_scope}
        if label:
            entry["label"] = label
        config.setdefault("scopes", []).append(entry)
        save_json(config_path, config, dry_run)


# ── Main ──

def migrate(
    target_scope: str,
    label: str | None,
    project_root: Path,
    dry_run: bool,
    force: bool,
) -> int:
    specs_root = project_root / ".agent" / "specs"
    if not specs_root.is_dir():
        print(f"ERROR: {specs_root} does not exist.", file=sys.stderr)
        return 1

    scope_dir = specs_root / target_scope
    generic_dir = specs_root / "generic"

    # Safety check: target scope dir must be empty (or not exist) unless --force
    if scope_dir.is_dir():
        non_mgmt = [
            p for p in scope_dir.iterdir() if not p.name.startswith("_")
        ]
        if non_mgmt and not force:
            print(
                f"ERROR: {scope_dir} already contains spec content:\n"
                f"  {[p.name for p in non_mgmt]}\n"
                f"Use --force to proceed anyway.",
                file=sys.stderr,
            )
            return 1

    print(
        f"Migrating specs -> scope '{target_scope}'\n"
        f"  Project root: {project_root}\n"
        f"  Dry-run:      {dry_run}\n"
    )

    # Step 1: discover domain directories to move
    known_scopes = {target_scope, "generic"}
    domains = find_spec_domains(specs_root, known_scopes)
    if not domains:
        print("  No domain directories to migrate. Already migrated?")
    else:
        print(f"  Discovered {len(domains)} domain(s): "
              f"{[d.name for d in domains]}")

    # Step 2: move each domain directory into the scope dir
    print("\n[1/5] Moving domain directories")
    for dom in domains:
        target = scope_dir / dom.name
        if dry_run:
            print(f"  WOULD MOVE  {dom} -> {target}")
            # In dry-run we still want to show per-file frontmatter status
            for md in sorted(dom.rglob("*.md")):
                content = md.read_text(encoding="utf-8")
                _, modified = ensure_scope_in_frontmatter(content, target_scope)
                if modified:
                    print(f"              + scope: [{target_scope}] -> {md.name}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dom), str(target))
            print(f"  MOVED       {dom.name}/ -> {target_scope}/{dom.name}/")

    # Step 3: update frontmatter of each spec (in the new location)
    print("\n[2/5] Updating spec frontmatters")
    if not dry_run and scope_dir.is_dir():
        count_modified = 0
        count_total = 0
        for md in sorted(scope_dir.rglob("*.md")):
            if md.name.startswith("_"):
                continue
            count_total += 1
            content = md.read_text(encoding="utf-8")
            new_content, modified = ensure_scope_in_frontmatter(
                content, target_scope
            )
            if modified:
                md.write_text(new_content, encoding="utf-8")
                count_modified += 1
        print(f"  Modified {count_modified}/{count_total} spec files")
    else:
        print("  (shown above in dry-run mode)")

    # Step 4: migrate _index.json and _registry.json
    print("\n[3/5] Migrating index and registry")
    old_index = specs_root / "_index.json"
    new_index = scope_dir / "_index.json"
    if old_index.is_file():
        data = load_json(old_index)
        data = rewrite_index_paths(data, target_scope)
        save_json(new_index, data, dry_run)
        if not dry_run:
            old_index.unlink()
            print(f"  REMOVED     {old_index}")
    elif not new_index.is_file():
        # no old index -> create empty
        save_json(
            new_index,
            {"scope": target_scope, "specs": [], "version": 2},
            dry_run,
        )

    old_reg = specs_root / "_registry.json"
    new_reg = scope_dir / "_registry.json"
    if old_reg.is_file():
        data = load_json(old_reg)
        data["scope"] = target_scope
        save_json(new_reg, data, dry_run)
        if not dry_run:
            old_reg.unlink()
            print(f"  REMOVED     {old_reg}")
    elif not new_reg.is_file():
        save_json(
            new_reg,
            {"scope": target_scope, "mappings": {}, "version": 2},
            dry_run,
        )

    # Step 5: ensure generic/ exists with empty indexes
    print("\n[4/5] Ensuring generic/ scope directory")
    if not generic_dir.is_dir() or not (generic_dir / "_index.json").is_file():
        save_json(
            generic_dir / "_index.json",
            {"scope": "generic", "specs": [], "version": 2},
            dry_run,
        )
        save_json(
            generic_dir / "_registry.json",
            {"scope": "generic", "mappings": {}, "version": 2},
            dry_run,
        )
    else:
        print("  SKIP        generic/ already initialized")

    # Step 6: update _scope-config.json
    print("\n[5/5] Updating _scope-config.json")
    update_scope_config(
        specs_root / "_scope-config.json",
        target_scope,
        label,
        dry_run,
    )

    print("\nMigration "
          + ("DRY-RUN complete — no changes made." if dry_run
             else "complete."))
    if not dry_run:
        print(f"\nNext steps:")
        print(f"  /scope-show                # verify")
        print(f"  /scope-set {target_scope}           # switch your active context")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate a pre-scoping .agent/specs/ layout into the "
            "scope-aware structure."
        ),
    )
    parser.add_argument(
        "target_scope",
        help="Scope id to move existing specs under (e.g., 'astro')",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Human-readable label for the scope (stored in _scope-config.json)",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without modifying the filesystem",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if target scope dir already contains content",
    )
    args = parser.parse_args(argv)

    # Validate target scope id against scope_context rules
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import scope_context as sc
    if args.target_scope == sc.GENERIC_SCOPE:
        print(
            f"ERROR: '{sc.GENERIC_SCOPE}' is reserved. "
            f"Cannot migrate into generic directly.",
            file=sys.stderr,
        )
        return 1
    try:
        sc.validate_scope_id(args.target_scope)
    except sc.InvalidScopeIdError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return migrate(
        target_scope=args.target_scope,
        label=args.label,
        project_root=Path(args.project_root).resolve(),
        dry_run=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
